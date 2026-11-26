"""Validation 2 tầng, quản lý Relationship và Publish cho Semantic Model (Task 106 Bước 5)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_data_source,
    recon_rpt_model,
    recon_rpt_model_rel,
    recon_rpt_model_ver,
)
from app.engine.catalog import _sqlite_connection
from app.engine.catalog import list_columns as catalog_list_columns
from app.engine.sql_dialect import quote_identifier
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_model import (
    PublishModelDTO,
    RelationshipUpsertDTO,
    allowed_aggregations_for,
)
from app.services import service
from app.services.perm import requires_menu
from app.services.semantic_model import (
    _build_model_response,
    _ds_summary_map,
    _extract_measure_refs,
    _has_measure_cycle,
    _now,
    _pk_from_insert,
    _rel_dict,
    _require_editable_version,
    _touch_draft_version,
    _validate_ast_expr,
    compute_version_diff,
    load_version_bundle,
)
from app.services.source_conn import open_source_connection

_PUBLISH_LOCK_KEY = "MODEL_PUBLISH_LOCK"
_PUBLISH_LOCK_TTL = timedelta(seconds=60)
DEFAULT_PROFILING_SAMPLE = 50_000
DEFAULT_PROFILING_TIMEOUT_SEC = 15


def _datatype_compat(src_type: str, tgt_type: str) -> tuple[str, str]:
    """Kiểm tra tương thích kiểu dữ liệu cho 2 đầu quan hệ. Trả (status, message)."""
    s = str(src_type).upper()
    t = str(tgt_type).upper()
    if s == t:
        return "PASS", f"Kiểu dữ liệu tương thích ({s})"
    if {s, t} == {"DATE", "DATETIME"}:
        return "WARNING", f"Kiểu dữ liệu khác nhẹ giữa {s} và {t}; nên đồng nhất định dạng."
    return "ERROR", f"Kiểu dữ liệu không tương thích: {s} và {t}."


def validate_relationship_structure(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Validation Tầng 1: datatype, duplicate edge, cycle/loop, ambiguous active paths."""
    issues: list[dict[str, Any]] = []
    tables_by_id = {t["id"]: t for t in bundle["tables"]}
    fields_by_table_col: dict[tuple[int, str], dict[str, Any]] = {
        (t["id"], f["source_column"].upper()): f for t in bundle["tables"] for f in t["fields"]
    }

    active_edges: list[tuple[int, int, dict[str, Any]]] = []
    pair_rels: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for rel in bundle["relationships"]:
        from_tbl = tables_by_id.get(rel["from_table_id"])
        to_tbl = tables_by_id.get(rel["to_table_id"])
        if from_tbl is None or to_tbl is None:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": f"Quan hệ '{rel['name']}' trỏ tới bảng không tồn tại.",
                    "target_type": "relationship",
                    "target_id": rel["id"],
                }
            )
            continue

        f_src = fields_by_table_col.get((rel["from_table_id"], rel["from_column"].upper()))
        f_tgt = fields_by_table_col.get((rel["to_table_id"], rel["to_column"].upper()))
        if f_src is None or f_tgt is None:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.COLUMN_NOT_FOUND,
                    "message": f"Quan hệ '{rel['name']}' thiếu cột nguồn hoặc cột đích.",
                    "target_type": "relationship",
                    "target_id": rel["id"],
                }
            )
            continue

        compat_status, compat_msg = _datatype_compat(f_src["data_type"], f_tgt["data_type"])
        if compat_status != "PASS":
            issues.append(
                {
                    "severity": compat_status,
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": f"Quan hệ '{rel['name']}': {compat_msg}",
                    "target_type": "relationship",
                    "target_id": rel["id"],
                }
            )

        if not rel["is_active"]:
            continue

        a, b = sorted((rel["from_table_id"], rel["to_table_id"]))
        pair_rels.setdefault((a, b), []).append(rel)
        active_edges.append((rel["from_table_id"], rel["to_table_id"], rel))

    for (t1, t2), rels in pair_rels.items():
        if len(rels) > 1:
            names = ", ".join(r["name"] for r in rels)
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.AMBIGUOUS_PATH,
                    "message": (
                        f"Có {len(rels)} quan hệ cùng kích hoạt giữa "
                        f"'{tables_by_id[t1]['alias']}' và '{tables_by_id[t2]['alias']}' ({names})."
                    ),
                    "target_type": "relationship",
                    "target_id": rels[0]["id"],
                }
            )

    # Phát hiện vòng lặp trên đồ thị vô hướng của các quan hệ active (chỉ xét cạnh duy nhất giữa mỗi cặp bảng)
    adj: dict[int, list[tuple[int, dict[str, Any]]]] = {tid: [] for tid in tables_by_id}
    for (t1, t2), rels in pair_rels.items():
        rel0 = rels[0]
        if t1 == t2:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.RELATIONSHIP_LOOP,
                    "message": f"Quan hệ '{rel0['name']}' tự trỏ vào cùng một bảng.",
                    "target_type": "relationship",
                    "target_id": rel0["id"],
                }
            )
            continue
        adj[t1].append((t2, rel0))
        adj[t2].append((t1, rel0))

    visited: set[int] = set()
    reported_cycle = False

    def _dfs_cycle(node: int, parent: int | None) -> bool:
        nonlocal reported_cycle
        visited.add(node)
        for nxt, rel in adj.get(node, []):
            if nxt == parent:
                continue
            if nxt in visited:
                if not reported_cycle:
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": ErrorCode.RELATIONSHIP_LOOP,
                            "message": f"Phát hiện vòng lặp quan hệ (loop) đi qua '{rel['name']}'.",
                            "target_type": "relationship",
                            "target_id": rel["id"],
                        }
                    )
                    reported_cycle = True
                return True
            if _dfs_cycle(nxt, node):
                return True
        return False

    for tid in sorted(adj):
        if tid not in visited:
            _dfs_cycle(tid, None)

    return issues


@service
@requires_menu("report_model")
def upsert_relationship(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo hoặc cập nhật quan hệ giữa hai bảng trên bản Draft (kiểm tra datatype ngay)."""
    dto = RelationshipUpsertDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _require_editable_version(conn, version_id)
        bundle = load_version_bundle(conn, version_id)
        tables_by_id = {t["id"]: t for t in bundle["tables"]}

        from_tbl = tables_by_id.get(dto.from_table_id)
        to_tbl = tables_by_id.get(dto.to_table_id)
        if from_tbl is None or to_tbl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Bảng nguồn hoặc bảng đích không thuộc phiên bản mô hình này.")
        if dto.from_table_id == dto.to_table_id:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Không hỗ trợ quan hệ tự nối lên chính cùng một bảng ở V1.")

        from_col_map = {f["source_column"].upper(): f for f in from_tbl["fields"]}
        to_col_map = {f["source_column"].upper(): f for f in to_tbl["fields"]}
        f_from = from_col_map.get(dto.from_column.upper())
        f_to = to_col_map.get(dto.to_column.upper())
        if f_from is None or f_to is None:
            raise ServiceError(ErrorCode.COLUMN_NOT_FOUND, "Cột nguồn hoặc cột đích không tồn tại trong bảng.")

        compat_status, compat_msg = _datatype_compat(f_from["data_type"], f_to["data_type"])
        if compat_status == "ERROR":
            raise ServiceError(ErrorCode.VALIDATION_ERROR, compat_msg)

        values = {
            "MODEL_VERSION_ID": version_id,
            "NAME": dto.name.strip(),
            "FROM_TABLE_ID": dto.from_table_id,
            "FROM_COLUMN": f_from["source_column"],
            "TO_TABLE_ID": dto.to_table_id,
            "TO_COLUMN": f_to["source_column"],
            "CARDINALITY": dto.cardinality,
            "JOIN_TYPE": dto.join_type,
            "CROSS_FILTER": dto.cross_filter,
            "IS_ACTIVE": "Y" if dto.is_active else "N",
            "VALIDATION_STATUS": compat_status,
            "VALIDATION_JSON": {"datatype_compat": {"status": compat_status, "message": compat_msg}},
        }
        if dto.id is not None:
            existing = {r["id"] for r in bundle["relationships"]}
            if dto.id not in existing:
                raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy quan hệ cần sửa.")
            conn.execute(recon_rpt_model_rel.update().where(recon_rpt_model_rel.c.ID == dto.id).values(**values))
            rid = dto.id
        else:
            res = conn.execute(recon_rpt_model_rel.insert().values(**values))
            rid = _pk_from_insert(res)

        _touch_draft_version(conn, version_id, ctx.username)
        row = conn.execute(select(recon_rpt_model_rel).where(recon_rpt_model_rel.c.ID == rid)).mappings().one()
        return _rel_dict(row)


@service
@requires_menu("report_model")
def delete_relationship(ctx: Ctx, rel_id: int) -> dict[str, Any]:
    """Xóa quan hệ khỏi bản Draft (không ảnh hưởng phiên bản ACTIVE cũ)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = (
            conn.execute(select(recon_rpt_model_rel).where(recon_rpt_model_rel.c.ID == rel_id))
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy quan hệ.")
        version_id = int(row["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)
        conn.execute(delete(recon_rpt_model_rel).where(recon_rpt_model_rel.c.ID == rel_id))
        _touch_draft_version(conn, version_id, ctx.username)
        return {"deleted_relationship_id": rel_id}


def _qualified_table(owner: str | None, table_name: str, db_type: str) -> str:
    clean_obj = quote_identifier(table_name)
    clean_owner = str(owner or "").strip()
    if db_type.upper() != "SQLITE" and clean_owner and clean_owner.upper() not in ("NONE", "MAIN"):
        return f"{quote_identifier(clean_owner)}.{clean_obj}"
    return clean_obj


def _run_profiling_queries(
    ds_info: dict[str, Any],
    from_tbl_sql: str,
    from_col_sql: str,
    to_tbl_sql: str,
    to_col_sql: str,
    sample_limit: int,
    timeout_sec: int,
) -> tuple[int, int, int, int, int]:
    """Trả (dim_non_null, dim_dup_groups, sample_rows, null_count, orphan_count)."""
    db_type = str(ds_info["db_type"]).upper()
    dim_sql = (
        f"SELECT COUNT({to_col_sql}) AS cnt_nn, "
        f"COUNT(DISTINCT {to_col_sql}) AS cnt_dist "
        f"FROM {to_tbl_sql}"
    )
    if db_type == "SQLITE":
        fact_sql = (
            f"SELECT COUNT(*) AS total_rows, "
            f"SUM(CASE WHEN f.{from_col_sql} IS NULL THEN 1 ELSE 0 END) AS null_cnt, "
            f"SUM(CASE WHEN f.{from_col_sql} IS NOT NULL AND NOT EXISTS ("
            f"SELECT 1 FROM {to_tbl_sql} d WHERE d.{to_col_sql} = f.{from_col_sql}) "
            f"THEN 1 ELSE 0 END) AS orphan_cnt "
            f"FROM (SELECT {from_col_sql} FROM {from_tbl_sql} LIMIT :lim) f"
        )
        with _sqlite_connection({"FILE_PATH": ds_info.get("file_path")}) as sconn:
            dim_row = sconn.execute(text(dim_sql)).one()
            fact_row = sconn.execute(text(fact_sql), {"lim": sample_limit}).one()
    else:
        fact_sql = (
            f"SELECT COUNT(*) AS total_rows, "
            f"SUM(CASE WHEN f.{from_col_sql} IS NULL THEN 1 ELSE 0 END) AS null_cnt, "
            f"SUM(CASE WHEN f.{from_col_sql} IS NOT NULL AND NOT EXISTS ("
            f"SELECT 1 FROM {to_tbl_sql} d WHERE d.{to_col_sql} = f.{from_col_sql}) "
            f"THEN 1 ELSE 0 END) AS orphan_cnt "
            f"FROM (SELECT {from_col_sql} FROM {from_tbl_sql} FETCH FIRST :lim ROWS ONLY) f"
        )
        ora_conn = open_source_connection(int(ds_info["id"]))
        ora_conn.call_timeout = int(timeout_sec) * 1000
        try:
            cur = ora_conn.cursor()
            cur.execute(dim_sql)
            dim_row = cur.fetchone()
            cur.execute(fact_sql, {"lim": sample_limit})
            fact_row = cur.fetchone()
            cur.close()
        finally:
            ora_conn.close()

    dim_non_null = int(dim_row[0] or 0)
    dim_distinct = int(dim_row[1] or 0)
    dim_dup_excess = max(0, dim_non_null - dim_distinct)
    sample_rows = int(fact_row[0] or 0)
    null_count = int(fact_row[1] or 0)
    orphan_count = int(fact_row[2] or 0)
    return dim_non_null, dim_dup_excess, sample_rows, null_count, orphan_count


@service
@requires_menu("report_model")
def profile_relationship_data(
    ctx: Ctx,
    rel_id: int,
    sample_limit: int = DEFAULT_PROFILING_SAMPLE,
    timeout_sec: int = DEFAULT_PROFILING_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Validation Tầng 2: Kiểm tra chất lượng dữ liệu mẫu của một quan hệ (có limit & timeout)."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        rel_row = (
            conn.execute(select(recon_rpt_model_rel).where(recon_rpt_model_rel.c.ID == rel_id))
            .mappings()
            .first()
        )
        if rel_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy quan hệ.")
        version_id = int(rel_row["MODEL_VERSION_ID"])
        bundle = load_version_bundle(conn, version_id)
        ds_row = (
            conn.execute(
                select(
                    recon_data_source.c.ID,
                    recon_data_source.c.DB_TYPE,
                    recon_data_source.c.FILE_PATH,
                ).where(recon_data_source.c.ID == bundle["model"]["data_source_id"])
            )
            .mappings()
            .first()
        )

    if ds_row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source của mô hình.")
    ds_info = {"id": int(ds_row["ID"]), "db_type": str(ds_row["DB_TYPE"]), "file_path": ds_row["FILE_PATH"]}

    tables_by_id = {t["id"]: t for t in bundle["tables"]}
    from_tbl = tables_by_id[int(rel_row["FROM_TABLE_ID"])]
    to_tbl = tables_by_id[int(rel_row["TO_TABLE_ID"])]
    from_col = str(rel_row["FROM_COLUMN"])
    to_col = str(rel_row["TO_COLUMN"])
    f_src = next(f for f in from_tbl["fields"] if f["source_column"].upper() == from_col.upper())
    f_tgt = next(f for f in to_tbl["fields"] if f["source_column"].upper() == to_col.upper())

    compat_status, compat_msg = _datatype_compat(f_src["data_type"], f_tgt["data_type"])
    graph_issues = [
        iss for iss in validate_relationship_structure(bundle) if iss.get("target_id") == rel_id
    ]
    loop_status = "ERROR" if any(i["severity"] == "ERROR" for i in graph_issues) else "PASS"
    loop_msg = graph_issues[0]["message"] if graph_issues else "Không tạo relationship loop hoặc đường đi nhập nhằng."

    from_tbl_sql = _qualified_table(from_tbl["source_owner"], from_tbl["source_object"], ds_info["db_type"])
    to_tbl_sql = _qualified_table(to_tbl["source_owner"], to_tbl["source_object"], ds_info["db_type"])
    dim_non_null, dim_dup, sample_rows, null_cnt, orphan_cnt = _run_profiling_queries(
        ds_info,
        from_tbl_sql,
        quote_identifier(from_col),
        to_tbl_sql,
        quote_identifier(to_col),
        sample_limit=max(1, int(sample_limit)),
        timeout_sec=max(1, int(timeout_sec)),
    )

    uniq_status = "ERROR" if dim_dup > 0 else "PASS"
    uniq_msg = (
        f"{to_tbl['alias']}.{to_col} có {dim_dup} giá trị trùng lặp (vi phạm *:1)."
        if dim_dup > 0
        else f"{to_tbl['alias']}.{to_col} duy nhất ({dim_non_null} giá trị)."
    )
    null_rate = (null_cnt / sample_rows) if sample_rows > 0 else 0.0
    null_status = "WARNING" if null_cnt > 0 else "PASS"
    null_msg = (
        f"{null_cnt} dòng ({null_rate:.1%}) ở {from_tbl['alias']}.{from_col} mang giá trị NULL."
        if null_cnt > 0
        else f"Không có giá trị NULL trong {sample_rows} dòng mẫu."
    )
    orphan_status = "WARNING" if orphan_cnt > 0 else "PASS"
    orphan_msg = (
        f"{orphan_cnt} dòng Fact mẫu không có khóa khớp ở {to_tbl['alias']}."
        if orphan_cnt > 0
        else "100% khóa Fact mẫu khớp với bảng đích."
    )
    matched_cnt = max(0, sample_rows - null_cnt - orphan_cnt)
    join_cov = (matched_cnt / sample_rows) if sample_rows > 0 else 1.0
    cov_status = "WARNING" if join_cov < 1.0 else "PASS"

    checks = [
        {"key": "datatype_compat", "status": compat_status, "message": compat_msg},
        {"key": "target_uniqueness", "status": uniq_status, "message": uniq_msg},
        {"key": "null_rate", "status": null_status, "message": null_msg},
        {"key": "orphan_fact_keys", "status": orphan_status, "message": orphan_msg},
        {"key": "join_coverage", "status": cov_status, "message": f"Độ phủ join trên mẫu: {join_cov:.1%}."},
        {"key": "loop_and_ambiguity", "status": loop_status, "message": loop_msg},
    ]
    if any(c["status"] == "ERROR" for c in checks):
        overall = "ERROR"
    elif any(c["status"] == "WARNING" for c in checks):
        overall = "WARNING"
    else:
        overall = "PASS"

    result = {
        "relationship_id": rel_id,
        "status": overall,
        "checks": checks,
        "metrics": {
            "sample_rows": sample_rows,
            "dim_non_null": dim_non_null,
            "dim_duplicate_excess": dim_dup,
            "null_count": null_cnt,
            "orphan_count": orphan_cnt,
            "join_coverage": round(join_cov, 4),
        },
    }
    with engine.begin() as conn:
        conn.execute(
            recon_rpt_model_rel.update()
            .where(recon_rpt_model_rel.c.ID == rel_id)
            .values(VALIDATION_STATUS=overall, VALIDATION_JSON=result)
        )
    return result


def _run_model_validation(
    conn: Any,
    version_id: int,
    *,
    check_physical: bool = True,
) -> dict[str, Any]:
    bundle = load_version_bundle(conn, version_id)
    issues: list[dict[str, Any]] = []
    tables = bundle["tables"]
    model_id = bundle["model"]["id"]
    ds_id = bundle["model"]["data_source_id"]

    if not tables:
        issues.append(
            {
                "severity": "ERROR",
                "code": ErrorCode.MODEL_INVALID,
                "message": "Mô hình chưa có bảng nào.",
                "target_type": "model",
                "target_id": model_id,
            }
        )

    # Kiểm tra trùng alias / trùng mã
    seen_aliases: set[str] = set()
    for tbl in tables:
        alias_u = tbl["alias"].upper()
        if alias_u in seen_aliases:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.CONFLICT,
                    "message": f"Trùng alias bảng '{tbl['alias']}'.",
                    "target_type": "table",
                    "target_id": tbl["id"],
                }
            )
        seen_aliases.add(alias_u)

        if tbl["table_role"] == "FACT":
            if not (tbl.get("grain_desc") or "").strip() or not tbl.get("grain_keys"):
                issues.append(
                    {
                        "severity": "ERROR",
                        "code": ErrorCode.GRAIN_REQUIRED,
                        "message": f"Bảng Fact '{tbl['alias']}' bắt buộc khai báo mô tả và khóa Grain.",
                        "target_type": "table",
                        "target_id": tbl["id"],
                    }
                )

    issues.extend(validate_relationship_structure(bundle))

    # Kiểm tra Measure & AST references
    fields_by_id = {f["id"]: f for t in tables for f in t["fields"]}
    measures_by_id = {m["id"]: m for m in bundle["measures"]}
    meas_deps: dict[int, set[int]] = {}
    for meas in bundle["measures"]:
        if meas["measure_type"] == "SIMPLE":
            if meas["base_field_id"] is not None:
                fld = fields_by_id.get(meas["base_field_id"])
                if fld is None:
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": ErrorCode.COLUMN_NOT_FOUND,
                            "message": f"Measure '{meas['code']}' tham chiếu trường không tồn tại.",
                            "target_type": "measure",
                            "target_id": meas["id"],
                        }
                    )
                elif meas["aggregation"] not in allowed_aggregations_for(fld["data_type"]):
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": ErrorCode.VALIDATION_ERROR,
                            "message": f"Measure '{meas['code']}' dùng hàm không hợp lệ cho kiểu {fld['data_type']}.",
                            "target_type": "measure",
                            "target_id": meas["id"],
                        }
                    )
        else:
            try:
                _validate_ast_expr(
                    meas["expr_json"],
                    fields_by_id,
                    measures_by_id,
                    editing_measure_id=meas["id"],
                )
                meas_deps[meas["id"]] = _extract_measure_refs(meas["expr_json"])
            except ServiceError as exc:
                issues.append(
                    {
                        "severity": "ERROR",
                        "code": exc.code,
                        "message": f"Measure '{meas['code']}': {exc.message}",
                        "target_type": "measure",
                        "target_id": meas["id"],
                    }
                )
    for mid in meas_deps:
        if _has_measure_cycle(meas_deps, mid):
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": f"Measure ID={mid} có vòng lặp phụ thuộc.",
                    "target_type": "measure",
                    "target_id": mid,
                }
            )

    # Kiểm tra RLS metadata
    tables_by_id = {t["id"]: t for t in tables}
    for pol in bundle["rls_policies"]:
        tbl = tables_by_id.get(pol["table_id"])
        if tbl is None:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.VALIDATION_ERROR,
                    "message": "Chính sách RLS trỏ tới bảng không còn trong mô hình.",
                    "target_type": "rls",
                    "target_id": pol["id"],
                }
            )
            continue
        col_set = {f["source_column"].upper() for f in tbl["fields"]}
        if pol["column_name"].upper() not in col_set:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": ErrorCode.COLUMN_NOT_FOUND,
                    "message": f"Cột RLS '{pol['column_name']}' không tồn tại trên '{tbl['alias']}'.",
                    "target_type": "rls",
                    "target_id": pol["id"],
                }
            )

    # Kiểm tra vật lý đối tượng/cột tại Data Source (chỉ đọc metadata)
    if check_physical:
        for tbl in tables:
            schema = str(tbl["source_owner"] or "")
            phys_cols = catalog_list_columns(ds_id, schema, tbl["source_object"])
            if not phys_cols:
                issues.append(
                    {
                        "severity": "ERROR",
                        "code": ErrorCode.TABLE_NOT_FOUND,
                        "message": f"Đối tượng nguồn '{tbl['source_object']}' không còn tồn tại trên Data Source.",
                        "target_type": "table",
                        "target_id": tbl["id"],
                    }
                )
                continue
            phys_names = {str(c["name"]).upper() for c in phys_cols}
            for fld in tbl["fields"]:
                if fld["source_column"].upper() not in phys_names:
                    issues.append(
                        {
                            "severity": "ERROR",
                            "code": ErrorCode.COLUMN_NOT_FOUND,
                            "message": f"Cột '{tbl['alias']}.{fld['source_column']}' không còn tồn tại ở nguồn.",
                            "target_type": "field",
                            "target_id": fld["id"],
                        }
                    )

    # So sánh breaking changes với version ACTIVE hiện tại
    breaking_changes: list[dict[str, Any]] = []
    active_ver_id = bundle["model"].get("active_version_id")
    if active_ver_id is not None and active_ver_id != version_id:
        diff = compute_version_diff(conn, version_id, active_ver_id)
        breaking_changes = diff["breaking_changes"]
        for bc in breaking_changes:
            issues.append(
                {
                    "severity": "WARNING",
                    "code": bc["change_type"],
                    "message": bc["message"],
                    "target_type": "model",
                    "target_id": model_id,
                }
            )

    err_cnt = sum(1 for i in issues if i["severity"] == "ERROR")
    warn_cnt = sum(1 for i in issues if i["severity"] == "WARNING")
    status = "INVALID" if err_cnt > 0 else ("WARNING" if warn_cnt > 0 else "VALID")

    return {
        "version_id": version_id,
        "status": status,
        "summary": {"error_count": err_cnt, "warning_count": warn_cnt},
        "issues": issues,
        "breaking_changes": breaking_changes,
    }


@service
@requires_menu("report_model")
def validate_model(ctx: Ctx, version_id: int, check_physical: bool = True) -> dict[str, Any]:
    """Chạy toàn bộ kiểm tra mô hình, lưu VALIDATION_JSON và cập nhật trạng thái VALIDATED/DRAFT."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        _require_editable_version(conn, version_id)
        report = _run_model_validation(conn, version_id, check_physical=check_physical)
        new_status = "VALIDATED" if report["summary"]["error_count"] == 0 else "DRAFT"
        conn.execute(
            recon_rpt_model_ver.update()
            .where(recon_rpt_model_ver.c.ID == version_id)
            .values(
                STATUS=new_status,
                VALIDATION_JSON=report,
                UPDATED_BY=ctx.username,
                UPDATED_AT=_now(),
            )
        )
        return report


def _parse_lock(value: str | None) -> datetime | None:
    if not value or value == "N":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _acquire_publish_lock(engine: Engine) -> bool:
    now = _now()
    try:
        with engine.begin() as conn:
            lock_row = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == _PUBLISH_LOCK_KEY)
            ).scalar_one_or_none()
            held_at = _parse_lock(lock_row)
            if held_at is not None and now - held_at < _PUBLISH_LOCK_TTL:
                return False
            if lock_row is None:
                conn.execute(
                    recon_app_setting.insert().values(
                        KEY=_PUBLISH_LOCK_KEY,
                        VALUE=now.isoformat(),
                        UPDATED_BY="system",
                        UPDATED_AT=now,
                    )
                )
            else:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == _PUBLISH_LOCK_KEY)
                    .values(VALUE=now.isoformat(), UPDATED_BY="system", UPDATED_AT=now)
                )
    except SQLAlchemyError:
        return False
    return True


def _release_publish_lock(engine: Engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                recon_app_setting.update()
                .where(recon_app_setting.c.KEY == _PUBLISH_LOCK_KEY)
                .values(VALUE="N", UPDATED_BY="system", UPDATED_AT=_now())
            )
    except SQLAlchemyError:
        pass


@service
@requires_menu("report_model")
def publish_model_version(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Phát hành phiên bản mô hình bất biến (ACTIVE), khóa bản cũ (ARCHIVED), ghi audit."""
    dto = PublishModelDTO(**payload)
    engine = get_recon_engine()
    if not _acquire_publish_lock(engine):
        raise ServiceError(ErrorCode.CONFLICT, "Đang có thao tác phát hành mô hình khác, vui lòng thử lại sau.")
    try:
        now = _now()
        with engine.begin() as conn:
            model, ver = _require_editable_version(conn, version_id)
            report = _run_model_validation(conn, version_id, check_physical=True)
            errors = [i for i in report["issues"] if i["severity"] == "ERROR"]
            if errors:
                first_err = errors[0]
                raise ServiceError(
                    first_err["code"],
                    first_err["message"],
                    details={"validation": report},
                )

            model_id = int(model["ID"])
            old_active_id = model["ACTIVE_VERSION_ID"]
            conn.execute(
                recon_rpt_model_ver.update()
                .where(
                    recon_rpt_model_ver.c.MODEL_ID == model_id,
                    recon_rpt_model_ver.c.STATUS == "ACTIVE",
                )
                .values(STATUS="ARCHIVED", UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
            conn.execute(
                recon_rpt_model_ver.update()
                .where(recon_rpt_model_ver.c.ID == version_id)
                .values(
                    STATUS="ACTIVE",
                    CHANGE_NOTE=dto.change_note.strip(),
                    VALIDATION_JSON=report,
                    PUBLISHED_BY=ctx.username,
                    PUBLISHED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(ver["ROW_VERSION"]) + 1,
                )
            )
            conn.execute(
                recon_rpt_model.update()
                .where(recon_rpt_model.c.ID == model_id)
                .values(
                    ACTIVE_VERSION_ID=version_id,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(model["ROW_VERSION"]) + 1,
                )
            )
            write_audit_log(
                conn,
                "RECON_RPT_MODEL_VER",
                version_id,
                "PUBLISH_MODEL_VERSION",
                ctx.username,
                old_data={"active_version_id": old_active_id},
                new_data={
                    "model_id": model_id,
                    "active_version_id": version_id,
                    "version_no": int(ver["VERSION_NO"]),
                    "change_note": dto.change_note.strip(),
                },
                now=now,
            )
            updated_model = conn.execute(select(recon_rpt_model).where(recon_rpt_model.c.ID == model_id)).mappings().one()
            ds_map = _ds_summary_map(conn, {int(updated_model["DATA_SOURCE_ID"])})
            return _build_model_response(conn, updated_model, ds_map)
    finally:
        _release_publish_lock(engine)
