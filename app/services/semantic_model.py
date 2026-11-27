"""Service Semantic Model — Task 106 (REPORT-STUDIO-01A).

Quản lý Semantic Model, Versioning bất biến, Clone, Archive, Optimistic
Concurrency (ROW_VERSION), cấu hình Table/Grain/Field/Measure/RLS và
Impact Analysis.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, delete, func, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_rpt_model,
    recon_rpt_model_field,
    recon_rpt_model_measure,
    recon_rpt_model_rel,
    recon_rpt_model_rls,
    recon_rpt_model_table,
    recon_rpt_model_ver,
)
from app.engine.catalog import (
    estimate_table_rows,
    list_schema_table_stats,
    list_table_constraints,
)
from app.engine.catalog import (
    list_columns as catalog_list_columns,
)
from app.engine.catalog import (
    list_tables as catalog_list_tables,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_model import (
    AST_AGG_OPS,
    AST_ALL_OPS,
    DraftSaveDTO,
    FieldUpdateDTO,
    MeasureUpsertDTO,
    ModelCloneDTO,
    ModelCreateDTO,
    RlsPolicyUpsertDTO,
    TableAddDTO,
    TableUpdateDTO,
    allowed_aggregations_for,
)
from app.services import service
from app.services.lookup import get_db_column_mappings
from app.services.perm import requires_menu
from app.services.report_source import effective_column_label, map_oracle_type


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pk_from_insert(res: Any) -> int:
    """Lấy khóa chính int sau khi thực thi INSERT đơn dòng."""
    pk = res.inserted_primary_key
    if not pk:
        raise RuntimeError("Insert did not return primary key")
    return int(pk[0])


# ─── Serializers & Loaders ───────────────────────────────────────────────────


def _ds_summary_map(conn: Connection, ds_ids: set[int]) -> dict[int, dict[str, Any]]:
    """Chỉ lấy metadata an toàn của Data Source (không lấy PASSWORD_ENC/secret)."""
    if not ds_ids:
        return {}
    rows = (
        conn.execute(
            select(
                recon_data_source.c.ID,
                recon_data_source.c.NAME,
                recon_data_source.c.ENV,
                recon_data_source.c.DB_TYPE,
                recon_data_source.c.DEFAULT_SCHEMA,
                recon_data_source.c.USERNAME,
                recon_data_source.c.IS_ACTIVE,
            ).where(recon_data_source.c.ID.in_(sorted(ds_ids)))
        )
        .mappings()
        .all()
    )
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        out[int(r["ID"])] = {
            "id": int(r["ID"]),
            "name": str(r["NAME"]),
            "env": str(r["ENV"]),
            "db_type": str(r["DB_TYPE"]),
            "default_schema": r["DEFAULT_SCHEMA"] or r["USERNAME"],
            "is_active": r["IS_ACTIVE"] == "Y",
        }
    return out


def _ver_summary(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "model_id": int(row["MODEL_ID"]),
        "version_no": int(row["VERSION_NO"]),
        "status": str(row["STATUS"]),
        "change_note": row["CHANGE_NOTE"],
        "validation": row["VALIDATION_JSON"],
        "published_by": row["PUBLISHED_BY"],
        "published_at": row["PUBLISHED_AT"],
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"],
        "updated_by": str(row["UPDATED_BY"]),
        "updated_at": row["UPDATED_AT"],
        "row_version": int(row["ROW_VERSION"]),
    }


def _field_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "table_id": int(row["TABLE_ID"]),
        "source_column": str(row["SOURCE_COLUMN"]),
        "field_code": str(row["FIELD_CODE"]),
        "display_name": str(row["DISPLAY_NAME"]),
        "description": row["DESCRIPTION"],
        "data_type": str(row["DATA_TYPE"]),
        "field_role": str(row["FIELD_ROLE"]),
        "default_agg": str(row["DEFAULT_AGG"]),
        "format_mask": row["FORMAT_MASK"],
        "is_visible": row["IS_VISIBLE"] == "Y",
        "is_filterable": row["IS_FILTERABLE"] == "Y",
        "is_pk": row["IS_PK"] == "Y",
        "is_fk": row["IS_FK"] == "Y",
        "sort_by_field_id": int(row["SORT_BY_FIELD_ID"]) if row["SORT_BY_FIELD_ID"] is not None else None,
        "folder": row["FOLDER"],
        "enable_date_hierarchy": row["ENABLE_DATE_HIERARCHY"] == "Y",
        "sensitivity": str(row["SENSITIVITY"]),
        "display_order": int(row["DISPLAY_ORDER"]),
    }


def _table_dict(row: Any, fields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "model_version_id": int(row["MODEL_VERSION_ID"]),
        "source_owner": row["SOURCE_OWNER"],
        "source_object": str(row["SOURCE_OBJECT"]),
        "object_type": str(row["OBJECT_TYPE"]),
        "alias": str(row["ALIAS"]),
        "display_name": str(row["DISPLAY_NAME"]),
        "table_role": str(row["TABLE_ROLE"]),
        "grain_desc": row["GRAIN_DESC"],
        "grain_keys": list(row["GRAIN_KEYS_JSON"]) if isinstance(row["GRAIN_KEYS_JSON"], list) else [],
        "default_date_field": row["DEFAULT_DATE_FIELD"],
        "is_hidden": row["IS_HIDDEN"] == "Y",
        "pos_x": int(row["POS_X"] or 0),
        "pos_y": int(row["POS_Y"] or 0),
        "row_estimate": int(row["ROW_ESTIMATE"]) if row["ROW_ESTIMATE"] is not None else None,
        "description": row["DESCRIPTION"],
        "fields": fields if fields is not None else [],
    }


def _rel_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "model_version_id": int(row["MODEL_VERSION_ID"]),
        "name": str(row["NAME"]),
        "from_table_id": int(row["FROM_TABLE_ID"]),
        "from_column": str(row["FROM_COLUMN"]),
        "to_table_id": int(row["TO_TABLE_ID"]),
        "to_column": str(row["TO_COLUMN"]),
        "cardinality": str(row["CARDINALITY"]),
        "join_type": str(row["JOIN_TYPE"]),
        "cross_filter": str(row["CROSS_FILTER"]),
        "is_active": row["IS_ACTIVE"] == "Y",
        "validation_status": row["VALIDATION_STATUS"],
        "validation": row["VALIDATION_JSON"],
    }


def _measure_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "model_version_id": int(row["MODEL_VERSION_ID"]),
        "table_id": int(row["TABLE_ID"]) if row["TABLE_ID"] is not None else None,
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "measure_type": str(row["MEASURE_TYPE"]),
        "base_field_id": int(row["BASE_FIELD_ID"]) if row["BASE_FIELD_ID"] is not None else None,
        "aggregation": row["AGGREGATION"],
        "expr_json": row["EXPR_JSON"],
        "format_mask": row["FORMAT_MASK"],
        "folder": row["FOLDER"],
        "description": row["DESCRIPTION"],
    }


def _rls_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "model_version_id": int(row["MODEL_VERSION_ID"]),
        "table_id": int(row["TABLE_ID"]),
        "column_name": str(row["COLUMN_NAME"]),
        "policy_type": str(row["POLICY_TYPE"]),
        "scope_attr": row["SCOPE_ATTR"],
        "admin_bypass": row["ADMIN_BYPASS"] == "Y",
        "is_active": row["IS_ACTIVE"] == "Y",
        "description": row["DESCRIPTION"],
    }


def _load_model_row(conn: Connection, model_id: int) -> Any:
    row = conn.execute(select(recon_rpt_model).where(recon_rpt_model.c.ID == model_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.MODEL_NOT_FOUND, "Không tìm thấy mô hình dữ liệu.")
    return row


def _load_version_row(conn: Connection, version_id: int) -> Any:
    row = conn.execute(select(recon_rpt_model_ver).where(recon_rpt_model_ver.c.ID == version_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy phiên bản mô hình.")
    return row


def _require_editable_version(conn: Connection, version_id: int) -> tuple[Any, Any]:
    """Đảm bảo version có thể sửa (DRAFT hoặc VALIDATED); chặn ACTIVE/ARCHIVED."""
    ver = _load_version_row(conn, version_id)
    if str(ver["STATUS"]) not in ("DRAFT", "VALIDATED"):
        raise ServiceError(
            ErrorCode.MODEL_VERSION_LOCKED,
            "Phiên bản đã phát hành hoặc lưu trữ là bất biến; hãy tạo bản nháp mới để chỉnh sửa.",
        )
    model = _load_model_row(conn, int(ver["MODEL_ID"]))
    if model["IS_ARCHIVED"] == "Y":
        raise ServiceError(ErrorCode.MODEL_ARCHIVED, "Mô hình đã lưu trữ, không thể chỉnh sửa.")
    return model, ver


def _touch_draft_version(conn: Connection, version_id: int, actor: str, *, reset_status: bool = True) -> int:
    """Cập nhật UPDATED_BY/AT, tăng ROW_VERSION; đưa VALIDATED về DRAFT khi có thay đổi cấu trúc."""
    ver = _load_version_row(conn, version_id)
    new_rv = int(ver["ROW_VERSION"]) + 1
    values: dict[str, Any] = {
        "UPDATED_BY": actor,
        "UPDATED_AT": _now(),
        "ROW_VERSION": new_rv,
    }
    if reset_status and ver["STATUS"] == "VALIDATED":
        values["STATUS"] = "DRAFT"
        values["VALIDATION_JSON"] = None
    conn.execute(recon_rpt_model_ver.update().where(recon_rpt_model_ver.c.ID == version_id).values(**values))
    return new_rv


def load_version_bundle(conn: Connection, version_id: int) -> dict[str, Any]:
    """Đọc trọn gói metadata của một phiên bản mô hình (dùng chung cho Studio & Planner)."""
    ver = _load_version_row(conn, version_id)
    model = _load_model_row(conn, int(ver["MODEL_ID"]))
    ds_map = _ds_summary_map(conn, {int(model["DATA_SOURCE_ID"])})
    ds_info = ds_map.get(int(model["DATA_SOURCE_ID"]))

    table_rows = (
        conn.execute(
            select(recon_rpt_model_table)
            .where(recon_rpt_model_table.c.MODEL_VERSION_ID == version_id)
            .order_by(recon_rpt_model_table.c.ID)
        )
        .mappings()
        .all()
    )
    table_ids = [int(t["ID"]) for t in table_rows]
    fields_by_table: dict[int, list[dict[str, Any]]] = {tid: [] for tid in table_ids}
    if table_ids:
        field_rows = (
            conn.execute(
                select(recon_rpt_model_field)
                .where(recon_rpt_model_field.c.TABLE_ID.in_(table_ids))
                .order_by(recon_rpt_model_field.c.DISPLAY_ORDER, recon_rpt_model_field.c.ID)
            )
            .mappings()
            .all()
        )
        for fr in field_rows:
            fields_by_table[int(fr["TABLE_ID"])].append(_field_dict(fr))

    tables = [_table_dict(tr, fields_by_table.get(int(tr["ID"]), [])) for tr in table_rows]
    rel_rows = (
        conn.execute(
            select(recon_rpt_model_rel)
            .where(recon_rpt_model_rel.c.MODEL_VERSION_ID == version_id)
            .order_by(recon_rpt_model_rel.c.ID)
        )
        .mappings()
        .all()
    )
    measure_rows = (
        conn.execute(
            select(recon_rpt_model_measure)
            .where(recon_rpt_model_measure.c.MODEL_VERSION_ID == version_id)
            .order_by(recon_rpt_model_measure.c.ID)
        )
        .mappings()
        .all()
    )
    rls_rows = (
        conn.execute(
            select(recon_rpt_model_rls)
            .where(recon_rpt_model_rls.c.MODEL_VERSION_ID == version_id)
            .order_by(recon_rpt_model_rls.c.ID)
        )
        .mappings()
        .all()
    )

    active_vno: int | None = None
    if model["ACTIVE_VERSION_ID"] is not None:
        if int(model["ACTIVE_VERSION_ID"]) == version_id:
            active_vno = int(ver["VERSION_NO"])
        else:
            av = conn.execute(
                select(recon_rpt_model_ver.c.VERSION_NO).where(
                    recon_rpt_model_ver.c.ID == int(model["ACTIVE_VERSION_ID"])
                )
            ).scalar_one_or_none()
            active_vno = int(av) if av is not None else None

    return {
        "model": {
            "id": int(model["ID"]),
            "code": str(model["CODE"]),
            "name": str(model["NAME"]),
            "description": model["DESCRIPTION"],
            "data_source_id": int(model["DATA_SOURCE_ID"]),
            "data_source": ds_info,
            "active_version_id": int(model["ACTIVE_VERSION_ID"]) if model["ACTIVE_VERSION_ID"] is not None else None,
            "active_version_no": active_vno,
            "is_archived": model["IS_ARCHIVED"] == "Y",
            "row_version": int(model["ROW_VERSION"]),
        },
        "version": _ver_summary(ver),
        "tables": tables,
        "relationships": [_rel_dict(r) for r in rel_rows],
        "measures": [_measure_dict(m) for m in measure_rows],
        "rls_policies": [_rls_dict(p) for p in rls_rows],
    }


def _build_model_response(conn: Connection, model_row: Any, ds_map: dict[int, dict[str, Any]]) -> dict[str, Any]:
    model_id = int(model_row["ID"])
    vers = (
        conn.execute(
            select(recon_rpt_model_ver)
            .where(recon_rpt_model_ver.c.MODEL_ID == model_id)
            .order_by(recon_rpt_model_ver.c.VERSION_NO.desc())
        )
        .mappings()
        .all()
    )
    ver_list = [_ver_summary(v) for v in vers]
    draft_ver = next((v for v in ver_list if v["status"] in ("DRAFT", "VALIDATED")), None)
    active_ver = next((v for v in ver_list if v["id"] == model_row["ACTIVE_VERSION_ID"]), None)
    target_ver_id = (
        active_ver["id"]
        if active_ver is not None
        else (draft_ver["id"] if draft_ver is not None else (ver_list[0]["id"] if ver_list else None))
    )

    fact_count = 0
    dim_count = 0
    bridge_count = 0
    rel_count = 0
    if target_ver_id is not None:
        role_rows = conn.execute(
            select(recon_rpt_model_table.c.TABLE_ROLE, func.count(recon_rpt_model_table.c.ID))
            .where(recon_rpt_model_table.c.MODEL_VERSION_ID == target_ver_id)
            .group_by(recon_rpt_model_table.c.TABLE_ROLE)
        ).all()
        for role, cnt in role_rows:
            if role == "FACT":
                fact_count = int(cnt)
            elif role == "DIMENSION":
                dim_count = int(cnt)
            elif role == "BRIDGE":
                bridge_count = int(cnt)
        rel_count = int(
            conn.execute(
                select(func.count(recon_rpt_model_rel.c.ID)).where(
                    recon_rpt_model_rel.c.MODEL_VERSION_ID == target_ver_id
                )
            ).scalar_one()
        )

    if model_row["IS_ARCHIVED"] == "Y":
        overall_status = "ARCHIVED"
    elif active_ver is not None:
        overall_status = "ACTIVE"
    elif draft_ver is not None:
        overall_status = str(draft_ver["status"])
    else:
        overall_status = "DRAFT"

    return {
        "id": model_id,
        "code": str(model_row["CODE"]),
        "name": str(model_row["NAME"]),
        "description": model_row["DESCRIPTION"],
        "data_source_id": int(model_row["DATA_SOURCE_ID"]),
        "data_source": ds_map.get(int(model_row["DATA_SOURCE_ID"])),
        "active_version_id": int(model_row["ACTIVE_VERSION_ID"]) if model_row["ACTIVE_VERSION_ID"] is not None else None,
        "active_version_no": active_ver["version_no"] if active_ver else None,
        "draft_version": draft_ver,
        "versions": ver_list,
        "status": overall_status,
        "is_archived": model_row["IS_ARCHIVED"] == "Y",
        "fact_count": fact_count,
        "dimension_count": dim_count,
        "bridge_count": bridge_count,
        "relationship_count": rel_count,
        "created_by": str(model_row["CREATED_BY"]),
        "created_at": model_row["CREATED_AT"],
        "updated_by": str(model_row["UPDATED_BY"]),
        "updated_at": model_row["UPDATED_AT"],
        "row_version": int(model_row["ROW_VERSION"]),
    }


def _remap_expr_ids(
    expr: Any,
    field_id_map: dict[int, int],
    measure_id_map: dict[int, int],
) -> Any:
    """Ánh xạ lại field_id/measure_id trong AST Calculated Measure khi clone version."""
    if isinstance(expr, list):
        return [_remap_expr_ids(item, field_id_map, measure_id_map) for item in expr]
    if not isinstance(expr, dict):
        return expr
    out = copy.deepcopy(expr)
    if "field_id" in out and isinstance(out["field_id"], int):
        out["field_id"] = field_id_map.get(out["field_id"], out["field_id"])
    if "measure_id" in out and isinstance(out["measure_id"], int):
        out["measure_id"] = measure_id_map.get(out["measure_id"], out["measure_id"])
    for key in ("args", "left", "right", "when", "then", "else", "value", "branches"):
        if key in out:
            out[key] = _remap_expr_ids(out[key], field_id_map, measure_id_map)
    return out


def _clone_version_contents(conn: Connection, src_ver_id: int, dst_ver_id: int) -> None:
    """Sao chép toàn bộ tables, fields, relationships, measures, RLS từ src_ver_id sang dst_ver_id."""
    src_tables = (
        conn.execute(
            select(recon_rpt_model_table)
            .where(recon_rpt_model_table.c.MODEL_VERSION_ID == src_ver_id)
            .order_by(recon_rpt_model_table.c.ID)
        )
        .mappings()
        .all()
    )
    table_id_map: dict[int, int] = {}
    field_id_map: dict[int, int] = {}
    pending_sort_links: list[tuple[int, int]] = []

    for tbl in src_tables:
        old_tid = int(tbl["ID"])
        res = conn.execute(
            recon_rpt_model_table.insert().values(
                MODEL_VERSION_ID=dst_ver_id,
                SOURCE_OWNER=tbl["SOURCE_OWNER"],
                SOURCE_OBJECT=tbl["SOURCE_OBJECT"],
                OBJECT_TYPE=tbl["OBJECT_TYPE"],
                ALIAS=tbl["ALIAS"],
                DISPLAY_NAME=tbl["DISPLAY_NAME"],
                TABLE_ROLE=tbl["TABLE_ROLE"],
                GRAIN_DESC=tbl["GRAIN_DESC"],
                GRAIN_KEYS_JSON=tbl["GRAIN_KEYS_JSON"],
                DEFAULT_DATE_FIELD=tbl["DEFAULT_DATE_FIELD"],
                IS_HIDDEN=tbl["IS_HIDDEN"],
                POS_X=tbl["POS_X"],
                POS_Y=tbl["POS_Y"],
                ROW_ESTIMATE=tbl["ROW_ESTIMATE"],
                DESCRIPTION=tbl["DESCRIPTION"],
            )
        )
        new_tid = _pk_from_insert(res)
        table_id_map[old_tid] = new_tid

        src_fields = (
            conn.execute(
                select(recon_rpt_model_field)
                .where(recon_rpt_model_field.c.TABLE_ID == old_tid)
                .order_by(recon_rpt_model_field.c.ID)
            )
            .mappings()
            .all()
        )
        for fld in src_fields:
            old_fid = int(fld["ID"])
            f_res = conn.execute(
                recon_rpt_model_field.insert().values(
                    TABLE_ID=new_tid,
                    SOURCE_COLUMN=fld["SOURCE_COLUMN"],
                    FIELD_CODE=fld["FIELD_CODE"],
                    DISPLAY_NAME=fld["DISPLAY_NAME"],
                    DESCRIPTION=fld["DESCRIPTION"],
                    DATA_TYPE=fld["DATA_TYPE"],
                    FIELD_ROLE=fld["FIELD_ROLE"],
                    DEFAULT_AGG=fld["DEFAULT_AGG"],
                    FORMAT_MASK=fld["FORMAT_MASK"],
                    IS_VISIBLE=fld["IS_VISIBLE"],
                    IS_FILTERABLE=fld["IS_FILTERABLE"],
                    IS_PK=fld["IS_PK"],
                    IS_FK=fld["IS_FK"],
                    SORT_BY_FIELD_ID=None,
                    FOLDER=fld["FOLDER"],
                    ENABLE_DATE_HIERARCHY=fld["ENABLE_DATE_HIERARCHY"],
                    SENSITIVITY=fld["SENSITIVITY"],
                    DISPLAY_ORDER=fld["DISPLAY_ORDER"],
                )
            )
            new_fid = _pk_from_insert(f_res)
            field_id_map[old_fid] = new_fid
            if fld["SORT_BY_FIELD_ID"] is not None:
                pending_sort_links.append((new_fid, int(fld["SORT_BY_FIELD_ID"])))

    for new_fid, old_sort_fid in pending_sort_links:
        mapped = field_id_map.get(old_sort_fid)
        if mapped is not None:
            conn.execute(
                recon_rpt_model_field.update()
                .where(recon_rpt_model_field.c.ID == new_fid)
                .values(SORT_BY_FIELD_ID=mapped)
            )

    src_rels = (
        conn.execute(
            select(recon_rpt_model_rel)
            .where(recon_rpt_model_rel.c.MODEL_VERSION_ID == src_ver_id)
            .order_by(recon_rpt_model_rel.c.ID)
        )
        .mappings()
        .all()
    )
    for rel in src_rels:
        conn.execute(
            recon_rpt_model_rel.insert().values(
                MODEL_VERSION_ID=dst_ver_id,
                NAME=rel["NAME"],
                FROM_TABLE_ID=table_id_map[int(rel["FROM_TABLE_ID"])],
                FROM_COLUMN=rel["FROM_COLUMN"],
                TO_TABLE_ID=table_id_map[int(rel["TO_TABLE_ID"])],
                TO_COLUMN=rel["TO_COLUMN"],
                CARDINALITY=rel["CARDINALITY"],
                JOIN_TYPE=rel["JOIN_TYPE"],
                CROSS_FILTER=rel["CROSS_FILTER"],
                IS_ACTIVE=rel["IS_ACTIVE"],
                VALIDATION_STATUS=rel["VALIDATION_STATUS"],
                VALIDATION_JSON=rel["VALIDATION_JSON"],
            )
        )

    src_measures = (
        conn.execute(
            select(recon_rpt_model_measure)
            .where(recon_rpt_model_measure.c.MODEL_VERSION_ID == src_ver_id)
            .order_by(recon_rpt_model_measure.c.ID)
        )
        .mappings()
        .all()
    )
    measure_id_map: dict[int, int] = {}
    pending_expr_updates: list[tuple[int, Any]] = []
    # Hai lượt: SIMPLE trước, CALCULATED sau (hoặc remap lại EXPR_JSON ở cuối)
    for meas in src_measures:
        old_mid = int(meas["ID"])
        mapped_tid = table_id_map.get(int(meas["TABLE_ID"])) if meas["TABLE_ID"] is not None else None
        mapped_fid = field_id_map.get(int(meas["BASE_FIELD_ID"])) if meas["BASE_FIELD_ID"] is not None else None
        m_res = conn.execute(
            recon_rpt_model_measure.insert().values(
                MODEL_VERSION_ID=dst_ver_id,
                TABLE_ID=mapped_tid,
                CODE=meas["CODE"],
                NAME=meas["NAME"],
                MEASURE_TYPE=meas["MEASURE_TYPE"],
                BASE_FIELD_ID=mapped_fid,
                AGGREGATION=meas["AGGREGATION"],
                EXPR_JSON=meas["EXPR_JSON"],
                FORMAT_MASK=meas["FORMAT_MASK"],
                FOLDER=meas["FOLDER"],
                DESCRIPTION=meas["DESCRIPTION"],
            )
        )
        new_mid = _pk_from_insert(m_res)
        measure_id_map[old_mid] = new_mid
        if meas["EXPR_JSON"] is not None:
            pending_expr_updates.append((new_mid, meas["EXPR_JSON"]))

    for new_mid, expr in pending_expr_updates:
        remapped = _remap_expr_ids(expr, field_id_map, measure_id_map)
        conn.execute(
            recon_rpt_model_measure.update()
            .where(recon_rpt_model_measure.c.ID == new_mid)
            .values(EXPR_JSON=remapped)
        )

    src_rls = (
        conn.execute(
            select(recon_rpt_model_rls)
            .where(recon_rpt_model_rls.c.MODEL_VERSION_ID == src_ver_id)
            .order_by(recon_rpt_model_rls.c.ID)
        )
        .mappings()
        .all()
    )
    for pol in src_rls:
        conn.execute(
            recon_rpt_model_rls.insert().values(
                MODEL_VERSION_ID=dst_ver_id,
                TABLE_ID=table_id_map[int(pol["TABLE_ID"])],
                COLUMN_NAME=pol["COLUMN_NAME"],
                POLICY_TYPE=pol["POLICY_TYPE"],
                SCOPE_ATTR=pol["SCOPE_ATTR"],
                ADMIN_BYPASS=pol["ADMIN_BYPASS"],
                IS_ACTIVE=pol["IS_ACTIVE"],
                DESCRIPTION=pol["DESCRIPTION"],
            )
        )


# ─── Service CRUD / Versioning / Clone / Archive ─────────────────────────────


@service
@requires_menu("report_model")
def list_models(
    ctx: Ctx,
    query: str | None = None,
    data_source_id: int | None = None,
    status: str | None = None,
    include_archived: bool = True,
) -> list[dict[str, Any]]:
    """Danh sách Semantic Model cho Model Center."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        stmt = select(recon_rpt_model).order_by(recon_rpt_model.c.UPDATED_AT.desc(), recon_rpt_model.c.CODE)
        if not include_archived:
            stmt = stmt.where(recon_rpt_model.c.IS_ARCHIVED == "N")
        if data_source_id is not None:
            stmt = stmt.where(recon_rpt_model.c.DATA_SOURCE_ID == int(data_source_id))
        rows = conn.execute(stmt).mappings().all()
        ds_ids = {int(r["DATA_SOURCE_ID"]) for r in rows}
        ds_map = _ds_summary_map(conn, ds_ids)
        items = [_build_model_response(conn, r, ds_map) for r in rows]

    q_norm = (query or "").strip().lower()
    st_norm = (status or "").strip().upper()
    out: list[dict[str, Any]] = []
    for item in items:
        if st_norm and st_norm != "ALL" and item["status"] != st_norm:
            continue
        if q_norm:
            hay = f"{item['code']} {item['name']} {item.get('description') or ''}".lower()
            if q_norm not in hay:
                continue
        out.append(item)
    return out


@service
@requires_menu("report_model")
def get_model(ctx: Ctx, model_id: int) -> dict[str, Any]:
    """Chi tiết tổng quan một Semantic Model."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = _load_model_row(conn, model_id)
        ds_map = _ds_summary_map(conn, {int(row["DATA_SOURCE_ID"])})
        return _build_model_response(conn, row, ds_map)


@service
@requires_menu("report_model")
def get_model_version_detail(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Chi tiết đầy đủ một phiên bản model (bảng, cột, quan hệ, measure, RLS)."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        return load_version_bundle(conn, version_id)


@service
@requires_menu("report_model")
def create_model(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo Semantic Model mới kèm version 1 DRAFT (không tự publish)."""
    dto = ModelCreateDTO(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        ds = (
            conn.execute(
                select(recon_data_source.c.ID, recon_data_source.c.IS_ACTIVE).where(
                    recon_data_source.c.ID == dto.data_source_id
                )
            )
            .mappings()
            .first()
        )
        if ds is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source đã chọn.")
        if ds["IS_ACTIVE"] != "Y":
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Data Source đang bị vô hiệu hóa.")

        dup = conn.execute(
            select(recon_rpt_model.c.ID).where(recon_rpt_model.c.CODE == dto.code)
        ).scalar_one_or_none()
        if dup is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã mô hình '{dto.code}' đã tồn tại.")

        try:
            res = conn.execute(
                recon_rpt_model.insert().values(
                    CODE=dto.code,
                    NAME=dto.name.strip(),
                    DESCRIPTION=dto.description.strip() if dto.description else None,
                    DATA_SOURCE_ID=dto.data_source_id,
                    ACTIVE_VERSION_ID=None,
                    IS_ARCHIVED="N",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            model_id = _pk_from_insert(res)
        except IntegrityError as exc:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã mô hình '{dto.code}' đã tồn tại.") from exc

        ver_res = conn.execute(
            recon_rpt_model_ver.insert().values(
                MODEL_ID=model_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        ver_id = _pk_from_insert(ver_res)

        write_audit_log(
            conn,
            "RECON_RPT_MODEL",
            model_id,
            "CREATE_MODEL",
            ctx.username,
            new_data={"code": dto.code, "name": dto.name, "data_source_id": dto.data_source_id, "version_id": ver_id},
            now=now,
        )
        row = _load_model_row(conn, model_id)
        ds_map = _ds_summary_map(conn, {dto.data_source_id})
        return _build_model_response(conn, row, ds_map)


@service
@requires_menu("report_model")
def open_or_create_draft(ctx: Ctx, model_id: int) -> dict[str, Any]:
    """Trả về version DRAFT hiện có hoặc clone từ ACTIVE sang DRAFT mới."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        model = _load_model_row(conn, model_id)
        existing_draft = (
            conn.execute(
                select(recon_rpt_model_ver)
                .where(
                    recon_rpt_model_ver.c.MODEL_ID == model_id,
                    recon_rpt_model_ver.c.STATUS.in_(("DRAFT", "VALIDATED")),
                )
                .order_by(recon_rpt_model_ver.c.VERSION_NO.desc())
            )
            .mappings()
            .first()
        )
        if existing_draft is not None:
            return load_version_bundle(conn, int(existing_draft["ID"]))

        if model["IS_ARCHIVED"] == "Y":
            raise ServiceError(ErrorCode.MODEL_ARCHIVED, "Mô hình đã lưu trữ, không thể tạo bản nháp mới.")

        max_ver = conn.execute(
            select(func.max(recon_rpt_model_ver.c.VERSION_NO)).where(recon_rpt_model_ver.c.MODEL_ID == model_id)
        ).scalar_one()
        next_no = int(max_ver or 0) + 1
        src_ver_id = int(model["ACTIVE_VERSION_ID"]) if model["ACTIVE_VERSION_ID"] is not None else None

        res = conn.execute(
            recon_rpt_model_ver.insert().values(
                MODEL_ID=model_id,
                VERSION_NO=next_no,
                STATUS="DRAFT",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_ver_id = _pk_from_insert(res)
        if src_ver_id is not None:
            _clone_version_contents(conn, src_ver_id, new_ver_id)

        write_audit_log(
            conn,
            "RECON_RPT_MODEL_VER",
            new_ver_id,
            "CREATE_DRAFT_VERSION",
            ctx.username,
            new_data={"model_id": model_id, "version_no": next_no, "from_version_id": src_ver_id},
            now=now,
        )
        return load_version_bundle(conn, new_ver_id)


@service
@requires_menu("report_model")
def save_draft_state(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Lưu thông tin chung và vị trí canvas của bản Draft, kiểm tra optimistic concurrency."""
    dto = DraftSaveDTO(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        model, ver = _require_editable_version(conn, version_id)
        if dto.code is not None and dto.code.strip() != str(model["CODE"]):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Mã mô hình (CODE) là bất biến sau lần lưu đầu tiên.",
            )
        if dto.expected_row_version is not None and int(ver["ROW_VERSION"]) != int(dto.expected_row_version):
            raise ServiceError(
                ErrorCode.STALE_DATA,
                "Bản nháp đã được cập nhật bởi phiên khác. Vui lòng tải lại trước khi lưu.",
                details={"server_row_version": int(ver["ROW_VERSION"])},
            )

        if dto.name is not None or "description" in dto.model_fields_set:
            upd_model: dict[str, Any] = {
                "UPDATED_BY": ctx.username,
                "UPDATED_AT": now,
                "ROW_VERSION": int(model["ROW_VERSION"]) + 1,
            }
            if dto.name is not None:
                upd_model["NAME"] = dto.name.strip()
            if "description" in dto.model_fields_set:
                upd_model["DESCRIPTION"] = dto.description.strip() if dto.description else None
            conn.execute(recon_rpt_model.update().where(recon_rpt_model.c.ID == int(model["ID"])).values(**upd_model))

        if dto.positions:
            valid_ids = {
                int(r[0])
                for r in conn.execute(
                    select(recon_rpt_model_table.c.ID).where(recon_rpt_model_table.c.MODEL_VERSION_ID == version_id)
                ).all()
            }
            for pos in dto.positions:
                if pos.table_id not in valid_ids:
                    raise ServiceError(ErrorCode.NOT_FOUND, f"Bảng ID={pos.table_id} không thuộc bản nháp này.")
                conn.execute(
                    recon_rpt_model_table.update()
                    .where(recon_rpt_model_table.c.ID == pos.table_id)
                    .values(POS_X=pos.pos_x, POS_Y=pos.pos_y)
                )

        _touch_draft_version(conn, version_id, ctx.username, reset_status=False)
        row = _load_model_row(conn, int(model["ID"]))
        ds_map = _ds_summary_map(conn, {int(row["DATA_SOURCE_ID"])})
        return _build_model_response(conn, row, ds_map)


@service
@requires_menu("report_model")
def clone_model(ctx: Ctx, source_model_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Nhân bản cấu trúc mô hình thành Model + Draft mới (không clone report, không auto-publish)."""
    dto = ModelCloneDTO(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        src_model = _load_model_row(conn, source_model_id)
        dup = conn.execute(
            select(recon_rpt_model.c.ID).where(recon_rpt_model.c.CODE == dto.code)
        ).scalar_one_or_none()
        if dup is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã mô hình '{dto.code}' đã tồn tại.")

        # Ưu tiên clone bản ACTIVE nếu có, ngược lại lấy bản version mới nhất
        src_ver_id = int(src_model["ACTIVE_VERSION_ID"]) if src_model["ACTIVE_VERSION_ID"] is not None else None
        if src_ver_id is None:
            latest = (
                conn.execute(
                    select(recon_rpt_model_ver.c.ID)
                    .where(recon_rpt_model_ver.c.MODEL_ID == source_model_id)
                    .order_by(recon_rpt_model_ver.c.VERSION_NO.desc())
                )
                .scalar_one_or_none()
            )
            src_ver_id = int(latest) if latest is not None else None

        res = conn.execute(
            recon_rpt_model.insert().values(
                CODE=dto.code,
                NAME=dto.name.strip(),
                DESCRIPTION=dto.description.strip() if dto.description else src_model["DESCRIPTION"],
                DATA_SOURCE_ID=int(src_model["DATA_SOURCE_ID"]),
                ACTIVE_VERSION_ID=None,
                IS_ARCHIVED="N",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_model_id = _pk_from_insert(res)

        ver_res = conn.execute(
            recon_rpt_model_ver.insert().values(
                MODEL_ID=new_model_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_ver_id = _pk_from_insert(ver_res)
        if src_ver_id is not None:
            _clone_version_contents(conn, src_ver_id, new_ver_id)

        write_audit_log(
            conn,
            "RECON_RPT_MODEL",
            new_model_id,
            "CLONE_MODEL",
            ctx.username,
            new_data={"source_model_id": source_model_id, "code": dto.code, "source_version_id": src_ver_id},
            now=now,
        )
        new_row = _load_model_row(conn, new_model_id)
        ds_map = _ds_summary_map(conn, {int(new_row["DATA_SOURCE_ID"])})
        return _build_model_response(conn, new_row, ds_map)


@service
@requires_menu("report_model")
def archive_model(ctx: Ctx, model_id: int) -> dict[str, Any]:
    """Lưu trữ mô hình (không xóa dữ liệu vật lý, không làm mất report đã pin version)."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        model = _load_model_row(conn, model_id)
        if model["IS_ARCHIVED"] == "Y":
            ds_map = _ds_summary_map(conn, {int(model["DATA_SOURCE_ID"])})
            return _build_model_response(conn, model, ds_map)

        conn.execute(
            recon_rpt_model.update()
            .where(recon_rpt_model.c.ID == model_id)
            .values(
                IS_ARCHIVED="Y",
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=int(model["ROW_VERSION"]) + 1,
            )
        )
        write_audit_log(
            conn,
            "RECON_RPT_MODEL",
            model_id,
            "ARCHIVE_MODEL",
            ctx.username,
            old_data={"is_archived": False},
            new_data={"is_archived": True},
            now=now,
        )
        updated = _load_model_row(conn, model_id)
        ds_map = _ds_summary_map(conn, {int(updated["DATA_SOURCE_ID"])})
        return _build_model_response(conn, updated, ds_map)


# ─── Table / Field / Measure / RLS Management (Bước 4) ───────────────────────


_EXTRA_TYPE_MAP: dict[str, str] = {
    "INT": "NUMBER",
    "INTEGER": "NUMBER",
    "BIGINT": "NUMBER",
    "SMALLINT": "NUMBER",
    "NUMERIC": "NUMBER",
    "DECIMAL": "NUMBER",
    "DOUBLE": "NUMBER",
    "REAL": "NUMBER",
    "DATETIME": "DATETIME",
    "BOOL": "BOOLEAN",
    "BOOLEAN": "BOOLEAN",
    "BIT": "BOOLEAN",
}


def _normalize_column_type(raw_type: str) -> str:
    base = str(raw_type or "STRING").strip().upper().split("(")[0].strip()
    if base in _EXTRA_TYPE_MAP:
        return _EXTRA_TYPE_MAP[base]
    return map_oracle_type(base)


def _suggest_table_role(object_name: str, fk_cols: set[str], fields_spec: list[dict[str, Any]]) -> str:
    upper = object_name.upper()
    if upper.startswith("FACT_") or upper.startswith("F_"):
        return "FACT"
    if upper.startswith("DIM_") or upper.startswith("D_"):
        return "DIMENSION"
    if upper.startswith("BRG_") or upper.startswith("BRIDGE_"):
        return "BRIDGE"
    has_numeric = any(f["data_type"] == "NUMBER" and not f["is_pk"] and not f["is_fk"] for f in fields_spec)
    if fk_cols and has_numeric:
        return "FACT"
    if any(f["is_pk"] for f in fields_spec) and not fk_cols:
        return "DIMENSION"
    return "UNCLASSIFIED"


def _load_table_with_fields(conn: Connection, table_id: int) -> dict[str, Any]:
    row = conn.execute(select(recon_rpt_model_table).where(recon_rpt_model_table.c.ID == table_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy bảng trong mô hình.")
    fields = (
        conn.execute(
            select(recon_rpt_model_field)
            .where(recon_rpt_model_field.c.TABLE_ID == table_id)
            .order_by(recon_rpt_model_field.c.DISPLAY_ORDER, recon_rpt_model_field.c.ID)
        )
        .mappings()
        .all()
    )
    return _table_dict(row, [_field_dict(f) for f in fields])


def _unique_alias(conn: Connection, version_id: int, base_alias: str) -> str:
    existing = {
        str(r[0]).upper()
        for r in conn.execute(
            select(recon_rpt_model_table.c.ALIAS).where(recon_rpt_model_table.c.MODEL_VERSION_ID == version_id)
        ).all()
    }
    candidate = base_alias[:60]
    if candidate.upper() not in existing:
        return candidate
    idx = 2
    while True:
        suffix = f"_{idx}"
        cand = f"{base_alias[: 60 - len(suffix)]}{suffix}"
        if cand.upper() not in existing:
            return cand
        idx += 1


@service
@requires_menu("report_model")
def add_table_to_draft(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Thêm bảng/view từ Data Source vào bản Draft, tự nạp cột & gợi ý vai trò/nhãn."""
    dto = TableAddDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        model, _ = _require_editable_version(conn, version_id)
        ds_id = int(model["DATA_SOURCE_ID"])
        ds_info = _ds_summary_map(conn, {ds_id}).get(ds_id)
        if ds_info is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source của mô hình.")

        db_type = str(ds_info["db_type"]).upper()
        schema = (
            dto.source_owner.strip().upper()
            if dto.source_owner and dto.source_owner.strip()
            else ("main" if db_type == "SQLITE" else str(ds_info.get("default_schema") or "").upper())
        )
        obj_name = dto.source_object.strip().upper() if db_type != "SQLITE" else dto.source_object.strip()

        existing_tables = (
            conn.execute(
                select(recon_rpt_model_table.c.SOURCE_OWNER, recon_rpt_model_table.c.SOURCE_OBJECT).where(
                    recon_rpt_model_table.c.MODEL_VERSION_ID == version_id
                )
            )
            .mappings()
            .all()
        )
        for et in existing_tables:
            if (str(et["SOURCE_OWNER"] or "").upper(), str(et["SOURCE_OBJECT"]).upper()) == (
                schema.upper(),
                obj_name.upper(),
            ):
                raise ServiceError(ErrorCode.CONFLICT, f"Bảng '{obj_name}' đã có trong mô hình.")

        cols = catalog_list_columns(ds_id, schema, obj_name)
        if not cols:
            raise ServiceError(ErrorCode.TABLE_NOT_FOUND, f"Không tìm thấy cột nào cho đối tượng '{obj_name}'.")

        constraints = list_table_constraints(ds_id, schema, obj_name)
        pk_cols = {c.upper() for c in constraints.get("primary_key", [])}
        fk_cols = {c.upper() for fk in constraints.get("foreign_keys", []) for c in fk.get("columns", [])}
        row_est = estimate_table_rows(ds_id, schema, obj_name)
        lookup_map = get_db_column_mappings(conn)

        fields_spec: list[dict[str, Any]] = []
        for idx, col in enumerate(cols):
            cname = str(col["name"])
            c_upper = cname.upper()
            dtype = _normalize_column_type(str(col.get("data_type") or "STRING"))
            is_pk = c_upper in pk_cols
            is_fk = c_upper in fk_cols
            if is_pk or is_fk:
                role = "KEY"
                default_agg = "NONE"
            elif dtype == "NUMBER":
                role = "MEASURE_CANDIDATE"
                default_agg = "SUM"
            else:
                role = "DIMENSION"
                default_agg = "NONE"
            fields_spec.append(
                {
                    "source_column": cname,
                    "field_code": cname,
                    "display_name": effective_column_label(cname, None, lookup_map),
                    "data_type": dtype,
                    "field_role": role,
                    "default_agg": default_agg,
                    "is_pk": is_pk,
                    "is_fk": is_fk,
                    "display_order": (idx + 1) * 10,
                }
            )

        role = dto.table_role or _suggest_table_role(obj_name, fk_cols, fields_spec)
        alias = dto.alias or _unique_alias(conn, version_id, obj_name)
        display_name = dto.display_name.strip() if dto.display_name else obj_name

        t_res = conn.execute(
            recon_rpt_model_table.insert().values(
                MODEL_VERSION_ID=version_id,
                SOURCE_OWNER=schema,
                SOURCE_OBJECT=obj_name,
                OBJECT_TYPE=dto.object_type,
                ALIAS=alias,
                DISPLAY_NAME=display_name,
                TABLE_ROLE=role,
                IS_HIDDEN="N",
                POS_X=dto.pos_x,
                POS_Y=dto.pos_y,
                ROW_ESTIMATE=row_est,
                DESCRIPTION=dto.description,
            )
        )
        table_id = _pk_from_insert(t_res)

        for f in fields_spec:
            conn.execute(
                recon_rpt_model_field.insert().values(
                    TABLE_ID=table_id,
                    SOURCE_COLUMN=f["source_column"],
                    FIELD_CODE=f["field_code"],
                    DISPLAY_NAME=f["display_name"],
                    DATA_TYPE=f["data_type"],
                    FIELD_ROLE=f["field_role"],
                    DEFAULT_AGG=f["default_agg"],
                    IS_VISIBLE="Y",
                    IS_FILTERABLE="Y",
                    IS_PK="Y" if f["is_pk"] else "N",
                    IS_FK="Y" if f["is_fk"] else "N",
                    ENABLE_DATE_HIERARCHY="N",
                    SENSITIVITY="NORMAL",
                    DISPLAY_ORDER=f["display_order"],
                )
            )

        _touch_draft_version(conn, version_id, ctx.username)
        return _load_table_with_fields(conn, table_id)


@service
@requires_menu("report_model")
def remove_table_from_draft(ctx: Ctx, table_id: int) -> dict[str, Any]:
    """Xóa bảng khỏi bản Draft và dọn các trường/quan hệ/measure/RLS liên quan."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        tbl = (
            conn.execute(select(recon_rpt_model_table).where(recon_rpt_model_table.c.ID == table_id))
            .mappings()
            .first()
        )
        if tbl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy bảng trong mô hình.")
        version_id = int(tbl["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)

        field_ids = [
            int(r[0])
            for r in conn.execute(
                select(recon_rpt_model_field.c.ID).where(recon_rpt_model_field.c.TABLE_ID == table_id)
            ).all()
        ]
        if field_ids:
            conn.execute(
                recon_rpt_model_field.update()
                .where(recon_rpt_model_field.c.SORT_BY_FIELD_ID.in_(field_ids))
                .values(SORT_BY_FIELD_ID=None)
            )
            conn.execute(
                delete(recon_rpt_model_measure).where(recon_rpt_model_measure.c.BASE_FIELD_ID.in_(field_ids))
            )
        conn.execute(delete(recon_rpt_model_measure).where(recon_rpt_model_measure.c.TABLE_ID == table_id))
        conn.execute(delete(recon_rpt_model_rls).where(recon_rpt_model_rls.c.TABLE_ID == table_id))
        conn.execute(
            delete(recon_rpt_model_rel).where(
                or_(
                    recon_rpt_model_rel.c.FROM_TABLE_ID == table_id,
                    recon_rpt_model_rel.c.TO_TABLE_ID == table_id,
                )
            )
        )
        conn.execute(delete(recon_rpt_model_field).where(recon_rpt_model_field.c.TABLE_ID == table_id))
        conn.execute(delete(recon_rpt_model_table).where(recon_rpt_model_table.c.ID == table_id))
        _touch_draft_version(conn, version_id, ctx.username)
        return {"deleted_table_id": table_id, "version_id": version_id}


@service
@requires_menu("report_model")
def update_table_props(ctx: Ctx, table_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Cập nhật thuộc tính bảng (Role, Grain, Default Date Field, Hidden, Position)."""
    dto = TableUpdateDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        tbl = (
            conn.execute(select(recon_rpt_model_table).where(recon_rpt_model_table.c.ID == table_id))
            .mappings()
            .first()
        )
        if tbl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy bảng trong mô hình.")
        version_id = int(tbl["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)

        fields = (
            conn.execute(select(recon_rpt_model_field).where(recon_rpt_model_field.c.TABLE_ID == table_id))
            .mappings()
            .all()
        )
        col_by_upper = {str(f["SOURCE_COLUMN"]).upper(): f for f in fields}

        updates: dict[str, Any] = {}
        if dto.alias is not None:
            dup = conn.execute(
                select(recon_rpt_model_table.c.ID).where(
                    recon_rpt_model_table.c.MODEL_VERSION_ID == version_id,
                    func.upper(recon_rpt_model_table.c.ALIAS) == dto.alias.upper(),
                    recon_rpt_model_table.c.ID != table_id,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise ServiceError(ErrorCode.CONFLICT, f"Alias '{dto.alias}' đã tồn tại trong bản nháp.")
            updates["ALIAS"] = dto.alias
        if dto.display_name is not None:
            updates["DISPLAY_NAME"] = dto.display_name.strip()
        if dto.table_role is not None:
            updates["TABLE_ROLE"] = dto.table_role
        if "grain_desc" in dto.model_fields_set:
            updates["GRAIN_DESC"] = dto.grain_desc.strip() if dto.grain_desc else None
        if "grain_keys" in dto.model_fields_set:
            keys = [k.strip() for k in (dto.grain_keys or []) if k.strip()]
            for k in keys:
                if k.upper() not in col_by_upper:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Cột Grain '{k}' không tồn tại trên bảng.")
            updates["GRAIN_KEYS_JSON"] = keys
        if "default_date_field" in dto.model_fields_set:
            ddf = dto.default_date_field.strip() if dto.default_date_field else None
            if ddf is not None:
                f_row = col_by_upper.get(ddf.upper())
                if f_row is None:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Cột ngày mặc định '{ddf}' không thuộc bảng.")
                if f_row["DATA_TYPE"] not in ("DATE", "DATETIME"):
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, "Default Date Field phải có kiểu DATE hoặc DATETIME.")
            updates["DEFAULT_DATE_FIELD"] = ddf
        if dto.is_hidden is not None:
            updates["IS_HIDDEN"] = "Y" if dto.is_hidden else "N"
        if dto.pos_x is not None:
            updates["POS_X"] = dto.pos_x
        if dto.pos_y is not None:
            updates["POS_Y"] = dto.pos_y
        if "description" in dto.model_fields_set:
            updates["DESCRIPTION"] = dto.description.strip() if dto.description else None

        if updates:
            conn.execute(recon_rpt_model_table.update().where(recon_rpt_model_table.c.ID == table_id).values(**updates))
            _touch_draft_version(conn, version_id, ctx.username, reset_status=set(updates) - {"POS_X", "POS_Y"} != set())
        return _load_table_with_fields(conn, table_id)


@service
@requires_menu("report_model")
def update_field_props(ctx: Ctx, field_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Cập nhật thuộc tính cột/trường trên bản Draft theo quy tắc aggregation & hierarchy."""
    dto = FieldUpdateDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        fld = (
            conn.execute(select(recon_rpt_model_field).where(recon_rpt_model_field.c.ID == field_id))
            .mappings()
            .first()
        )
        if fld is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy trường dữ liệu.")
        tbl = (
            conn.execute(select(recon_rpt_model_table).where(recon_rpt_model_table.c.ID == int(fld["TABLE_ID"])))
            .mappings()
            .first()
        )
        assert tbl is not None
        version_id = int(tbl["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)

        dtype = str(fld["DATA_TYPE"]).upper()
        updates: dict[str, Any] = {}
        if dto.field_code is not None:
            dup = conn.execute(
                select(recon_rpt_model_field.c.ID).where(
                    recon_rpt_model_field.c.TABLE_ID == int(fld["TABLE_ID"]),
                    func.upper(recon_rpt_model_field.c.FIELD_CODE) == dto.field_code.upper(),
                    recon_rpt_model_field.c.ID != field_id,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise ServiceError(ErrorCode.CONFLICT, f"Mã trường '{dto.field_code}' đã tồn tại trên bảng.")
            updates["FIELD_CODE"] = dto.field_code
        if dto.display_name is not None:
            updates["DISPLAY_NAME"] = dto.display_name.strip()
        if "description" in dto.model_fields_set:
            updates["DESCRIPTION"] = dto.description.strip() if dto.description else None
        if dto.field_role is not None:
            updates["FIELD_ROLE"] = dto.field_role
            if dto.field_role == "HIDDEN":
                updates["IS_VISIBLE"] = "N"
        if dto.default_agg is not None:
            allowed_aggs = allowed_aggregations_for(dtype)
            if dto.default_agg not in allowed_aggs:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Hàm tổng hợp '{dto.default_agg}' không hợp lệ với kiểu dữ liệu {dtype}.",
                )
            updates["DEFAULT_AGG"] = dto.default_agg
        if "format_mask" in dto.model_fields_set:
            updates["FORMAT_MASK"] = dto.format_mask.strip() if dto.format_mask else None
        if dto.is_visible is not None:
            updates["IS_VISIBLE"] = "Y" if dto.is_visible else "N"
        if dto.is_filterable is not None:
            updates["IS_FILTERABLE"] = "Y" if dto.is_filterable else "N"
        if "folder" in dto.model_fields_set:
            updates["FOLDER"] = dto.folder.strip() if dto.folder else None
        if dto.enable_date_hierarchy is not None:
            if dto.enable_date_hierarchy and dtype not in ("DATE", "DATETIME"):
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Chỉ cột kiểu DATE hoặc DATETIME mới bật được Virtual Date Hierarchy.",
                )
            updates["ENABLE_DATE_HIERARCHY"] = "Y" if dto.enable_date_hierarchy else "N"
        if dto.sensitivity is not None:
            updates["SENSITIVITY"] = dto.sensitivity
        if dto.clear_sort_by:
            updates["SORT_BY_FIELD_ID"] = None
        elif dto.sort_by_field_id is not None:
            if dto.sort_by_field_id == field_id:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Không thể sắp xếp trường theo chính nó.")
            target_fld = (
                conn.execute(
                    select(recon_rpt_model_field.c.ID)
                    .select_from(
                        recon_rpt_model_field.join(
                            recon_rpt_model_table, recon_rpt_model_field.c.TABLE_ID == recon_rpt_model_table.c.ID
                        )
                    )
                    .where(
                        recon_rpt_model_field.c.ID == dto.sort_by_field_id,
                        recon_rpt_model_table.c.MODEL_VERSION_ID == version_id,
                    )
                )
                .scalar_one_or_none()
            )
            if target_fld is None:
                raise ServiceError(ErrorCode.NOT_FOUND, "Trường dùng để Sort By không thuộc cùng mô hình.")
            updates["SORT_BY_FIELD_ID"] = dto.sort_by_field_id

        if updates:
            conn.execute(recon_rpt_model_field.update().where(recon_rpt_model_field.c.ID == field_id).values(**updates))
            _touch_draft_version(conn, version_id, ctx.username)
        updated = conn.execute(select(recon_rpt_model_field).where(recon_rpt_model_field.c.ID == field_id)).mappings().one()
        return _field_dict(updated)


def _extract_measure_refs(expr: Any) -> set[int]:
    refs: set[int] = set()
    if isinstance(expr, list):
        for item in expr:
            refs |= _extract_measure_refs(item)
    elif isinstance(expr, dict):
        if expr.get("op") == "MEASURE" and isinstance(expr.get("measure_id"), int):
            refs.add(int(expr["measure_id"]))
        for k in ("args", "left", "right", "when", "then", "else", "value", "branches"):
            if k in expr:
                refs |= _extract_measure_refs(expr[k])
    return refs


def _validate_ast_expr(
    expr: Any,
    fields_by_id: dict[int, dict[str, Any]],
    measures_by_id: dict[int, dict[str, Any]],
    *,
    editing_measure_id: int | None = None,
    depth: int = 0,
) -> None:
    if depth > 8:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Biểu thức Measure vượt quá độ sâu cho phép (tối đa 8 cấp).")
    if not isinstance(expr, dict):
        raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, "Biểu thức Measure phải là cấu trúc JSON AST hợp lệ.")
    op = str(expr.get("op") or "").upper()
    if op not in AST_ALL_OPS:
        raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử '{op}' không nằm trong danh sách cho phép.")

    if op == "FIELD":
        fid = expr.get("field_id")
        if not isinstance(fid, int) or fid not in fields_by_id:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "FIELD trong biểu thức không tồn tại trong mô hình.")
        return

    if op == "MEASURE":
        mid = expr.get("measure_id")
        if not isinstance(mid, int) or mid not in measures_by_id:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "MEASURE tham chiếu không tồn tại trong mô hình.")
        if editing_measure_id is not None and mid == editing_measure_id:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Measure không thể tự tham chiếu chính nó.")
        return

    if op == "CONST":
        val = expr.get("value")
        if val is not None and not isinstance(val, (int, float, str, bool)):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Hằng số CONST trong biểu thức không hợp lệ.")
        return

    if op in AST_AGG_OPS:
        arg = expr.get("arg")
        if arg is None:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Hàm {op} thiếu tham số 'arg'.")
        _validate_ast_expr(arg, fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
        if op in ("SUM", "AVG") and isinstance(arg, dict) and arg.get("op") == "FIELD":
            f_meta = fields_by_id.get(int(arg["field_id"]))
            if f_meta and str(f_meta["data_type"]).upper() != "NUMBER":
                raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Hàm {op} chỉ áp dụng cho trường kiểu NUMBER.")
        return

    if op in ("ADD", "SUB", "MUL", "DIV", "DIVIDE"):
        if "left" in expr and "right" in expr:
            _validate_ast_expr(expr["left"], fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
            _validate_ast_expr(expr["right"], fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
            return
        args = expr.get("args")
        if not isinstance(args, list) or len(args) < 2:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Phép toán {op} cần đủ 'left'/'right' hoặc 'args'.")
        for a in args:
            _validate_ast_expr(a, fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
        return

    if op == "ROUND":
        _validate_ast_expr(expr.get("value"), fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
        digits = expr.get("digits", 0)
        if not isinstance(digits, int) or not 0 <= digits <= 6:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "ROUND.digits phải là số nguyên từ 0 đến 6.")
        return

    if op == "COALESCE":
        args = expr.get("args")
        if not isinstance(args, list) or len(args) < 2:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "COALESCE cần ít nhất 2 tham số.")
        for a in args:
            _validate_ast_expr(a, fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
        return

    if op == "CASE":
        branches = expr.get("branches")
        if not isinstance(branches, list) or not branches:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "CASE cần ít nhất một nhánh when/then.")
        for br in branches:
            if not isinstance(br, dict) or "when" not in br or "then" not in br:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Mỗi nhánh CASE cần đủ 'when' và 'then'.")
            _validate_ast_expr(br["when"], fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
            _validate_ast_expr(br["then"], fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)
        if "else" in expr and expr["else"] is not None:
            _validate_ast_expr(expr["else"], fields_by_id, measures_by_id, editing_measure_id=editing_measure_id, depth=depth + 1)


def _has_measure_cycle(measures_deps: dict[int, set[int]], start_id: int) -> bool:
    visiting: set[int] = set()
    visited: set[int] = set()

    def _dfs(node: int) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in measures_deps.get(node, set()):
            if _dfs(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return _dfs(start_id)


@service
@requires_menu("report_model")
def upsert_measure(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo hoặc cập nhật Simple/Calculated Measure trên bản Draft."""
    dto = MeasureUpsertDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _require_editable_version(conn, version_id)
        bundle = load_version_bundle(conn, version_id)
        tables_by_id = {t["id"]: t for t in bundle["tables"]}
        fields_by_id = {f["id"]: f for t in bundle["tables"] for f in t["fields"]}
        measures_by_id = {m["id"]: m for m in bundle["measures"]}

        if dto.table_id is not None and dto.table_id not in tables_by_id:
            raise ServiceError(ErrorCode.NOT_FOUND, "Bảng gắn với Measure không thuộc mô hình.")

        for m in bundle["measures"]:
            if dto.id is not None and m["id"] == dto.id:
                continue
            if m["code"].upper() == dto.code.upper():
                raise ServiceError(ErrorCode.CONFLICT, f"Mã Measure '{dto.code}' đã tồn tại trong mô hình.")
            if m["name"].strip().lower() == dto.name.strip().lower():
                raise ServiceError(ErrorCode.CONFLICT, f"Tên Measure '{dto.name}' đã tồn tại trong mô hình.")

        table_id = dto.table_id
        if dto.measure_type == "SIMPLE":
            if dto.aggregation is None:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Simple Measure bắt buộc chọn hàm tổng hợp.")
            if dto.base_field_id is None and dto.aggregation != "COUNT":
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Simple Measure cần chọn trường dữ liệu gốc.")
            if dto.base_field_id is not None:
                fld = fields_by_id.get(dto.base_field_id)
                if fld is None:
                    raise ServiceError(ErrorCode.NOT_FOUND, "Trường dữ liệu gốc của Measure không tồn tại.")
                allowed = allowed_aggregations_for(fld["data_type"])
                if dto.aggregation not in allowed:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Hàm {dto.aggregation} không hợp lệ với kiểu dữ liệu {fld['data_type']}.",
                    )
                if table_id is None:
                    table_id = int(fld["table_id"])
            expr_json = None
        else:
            if dto.expr_json is None:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Calculated Measure bắt buộc có biểu thức AST.")
            _validate_ast_expr(
                dto.expr_json,
                fields_by_id,
                measures_by_id,
                editing_measure_id=dto.id,
            )
            deps: dict[int, set[int]] = {
                m["id"]: _extract_measure_refs(m["expr_json"]) for m in bundle["measures"] if m["expr_json"]
            }
            check_id = dto.id if dto.id is not None else -1
            deps[check_id] = _extract_measure_refs(dto.expr_json)
            if _has_measure_cycle(deps, check_id):
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Biểu thức Calculated Measure tạo vòng lặp phụ thuộc.",
                )
            expr_json = dto.expr_json

        values = {
            "MODEL_VERSION_ID": version_id,
            "TABLE_ID": table_id,
            "CODE": dto.code,
            "NAME": dto.name.strip(),
            "MEASURE_TYPE": dto.measure_type,
            "BASE_FIELD_ID": dto.base_field_id if dto.measure_type == "SIMPLE" else None,
            "AGGREGATION": dto.aggregation if dto.measure_type == "SIMPLE" else None,
            "EXPR_JSON": expr_json,
            "FORMAT_MASK": dto.format_mask.strip() if dto.format_mask else None,
            "FOLDER": dto.folder.strip() if dto.folder else None,
            "DESCRIPTION": dto.description.strip() if dto.description else None,
        }
        if dto.id is not None:
            if dto.id not in measures_by_id:
                raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Measure cần sửa.")
            conn.execute(
                recon_rpt_model_measure.update()
                .where(recon_rpt_model_measure.c.ID == dto.id)
                .values(**values)
            )
            mid = dto.id
        else:
            res = conn.execute(recon_rpt_model_measure.insert().values(**values))
            mid = _pk_from_insert(res)

        _touch_draft_version(conn, version_id, ctx.username)
        row = conn.execute(select(recon_rpt_model_measure).where(recon_rpt_model_measure.c.ID == mid)).mappings().one()
        return _measure_dict(row)


@service
@requires_menu("report_model")
def delete_measure(ctx: Ctx, measure_id: int) -> dict[str, Any]:
    """Xóa Measure khỏi bản Draft (chặn nếu có Calculated Measure khác đang tham chiếu)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = (
            conn.execute(select(recon_rpt_model_measure).where(recon_rpt_model_measure.c.ID == measure_id))
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Measure.")
        version_id = int(row["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)

        others = (
            conn.execute(
                select(recon_rpt_model_measure).where(
                    recon_rpt_model_measure.c.MODEL_VERSION_ID == version_id,
                    recon_rpt_model_measure.c.ID != measure_id,
                )
            )
            .mappings()
            .all()
        )
        for other in others:
            if measure_id in _extract_measure_refs(other["EXPR_JSON"]):
                raise ServiceError(
                    ErrorCode.CONFLICT,
                    f"Không thể xóa vì Measure '{other['CODE']}' đang tham chiếu tới Measure này.",
                )

        conn.execute(delete(recon_rpt_model_measure).where(recon_rpt_model_measure.c.ID == measure_id))
        _touch_draft_version(conn, version_id, ctx.username)
        return {"deleted_measure_id": measure_id}


@service
@requires_menu("report_model")
def upsert_rls_policy(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Khai báo khung metadata RLS V1 cho một bảng/cột trên bản Draft."""
    dto = RlsPolicyUpsertDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _require_editable_version(conn, version_id)
        tbl = (
            conn.execute(
                select(recon_rpt_model_table).where(
                    recon_rpt_model_table.c.ID == dto.table_id,
                    recon_rpt_model_table.c.MODEL_VERSION_ID == version_id,
                )
            )
            .mappings()
            .first()
        )
        if tbl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Bảng RLS không thuộc phiên bản mô hình này.")

        fld = (
            conn.execute(
                select(recon_rpt_model_field).where(
                    recon_rpt_model_field.c.TABLE_ID == dto.table_id,
                    func.upper(recon_rpt_model_field.c.SOURCE_COLUMN) == dto.column_name.upper(),
                )
            )
            .mappings()
            .first()
        )
        if fld is None:
            raise ServiceError(
                ErrorCode.COLUMN_NOT_FOUND,
                f"Cột '{dto.column_name}' không tồn tại trên bảng '{tbl['ALIAS']}'.",
            )

        values = {
            "MODEL_VERSION_ID": version_id,
            "TABLE_ID": dto.table_id,
            "COLUMN_NAME": str(fld["SOURCE_COLUMN"]),
            "POLICY_TYPE": dto.policy_type,
            "SCOPE_ATTR": dto.scope_attr.strip() if dto.scope_attr else None,
            "ADMIN_BYPASS": "Y" if dto.admin_bypass else "N",
            "IS_ACTIVE": "Y" if dto.is_active else "N",
            "DESCRIPTION": dto.description.strip() if dto.description else None,
        }
        if dto.id is not None:
            conn.execute(recon_rpt_model_rls.update().where(recon_rpt_model_rls.c.ID == dto.id).values(**values))
            pid = dto.id
        else:
            dup = conn.execute(
                select(recon_rpt_model_rls.c.ID).where(
                    recon_rpt_model_rls.c.MODEL_VERSION_ID == version_id,
                    recon_rpt_model_rls.c.TABLE_ID == dto.table_id,
                    func.upper(recon_rpt_model_rls.c.COLUMN_NAME) == dto.column_name.upper(),
                )
            ).scalar_one_or_none()
            if dup is not None:
                conn.execute(recon_rpt_model_rls.update().where(recon_rpt_model_rls.c.ID == int(dup)).values(**values))
                pid = int(dup)
            else:
                res = conn.execute(recon_rpt_model_rls.insert().values(**values))
                pid = _pk_from_insert(res)

        _touch_draft_version(conn, version_id, ctx.username)
        row = conn.execute(select(recon_rpt_model_rls).where(recon_rpt_model_rls.c.ID == pid)).mappings().one()
        return _rls_dict(row)


@service
@requires_menu("report_model")
def delete_rls_policy(ctx: Ctx, policy_id: int) -> dict[str, Any]:
    """Xóa cấu hình metadata RLS khỏi bản Draft."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = (
            conn.execute(select(recon_rpt_model_rls).where(recon_rpt_model_rls.c.ID == policy_id))
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy chính sách RLS.")
        version_id = int(row["MODEL_VERSION_ID"])
        _require_editable_version(conn, version_id)
        conn.execute(delete(recon_rpt_model_rls).where(recon_rpt_model_rls.c.ID == policy_id))
        _touch_draft_version(conn, version_id, ctx.username)
        return {"deleted_policy_id": policy_id}


# ─── Model Diff & Impact Analysis (Bước 5) ───────────────────────────────────


def compute_version_diff(conn: Connection, draft_ver_id: int, active_ver_id: int) -> dict[str, Any]:
    """So sánh Draft version với Active version để phát hiện breaking changes."""
    draft = load_version_bundle(conn, draft_ver_id)
    active = load_version_bundle(conn, active_ver_id)

    breaking: list[dict[str, Any]] = []
    non_breaking: list[dict[str, Any]] = []

    d_tables = {t["alias"].upper(): t for t in draft["tables"]}
    a_tables = {t["alias"].upper(): t for t in active["tables"]}

    for alias, atbl in sorted(a_tables.items()):
        dtbl = d_tables.get(alias)
        if dtbl is None or (dtbl["is_hidden"] and not atbl["is_hidden"]):
            breaking.append(
                {
                    "change_type": "TABLE_REMOVED_OR_HIDDEN",
                    "entity": atbl["alias"],
                    "message": f"Bảng '{atbl['alias']}' bị xóa hoặc ẩn so với bản đang phát hành.",
                }
            )
            continue

        if atbl["table_role"] != dtbl["table_role"] or list(atbl["grain_keys"]) != list(dtbl["grain_keys"]):
            breaking.append(
                {
                    "change_type": "GRAIN_CHANGED",
                    "entity": atbl["alias"],
                    "message": f"Vai trò hoặc Grain của bảng '{atbl['alias']}' đã thay đổi.",
                }
            )

        a_fields = {f["field_code"].upper(): f for f in atbl["fields"]}
        d_fields = {f["field_code"].upper(): f for f in dtbl["fields"]}
        for fcode, afld in sorted(a_fields.items()):
            dfld = d_fields.get(fcode)
            if dfld is None or (
                (not dfld["is_visible"] or dfld["field_role"] == "HIDDEN")
                and (afld["is_visible"] and afld["field_role"] != "HIDDEN")
            ):
                breaking.append(
                    {
                        "change_type": "FIELD_HIDDEN_OR_REMOVED",
                        "entity": f"{atbl['alias']}.{afld['field_code']}",
                        "field_id": afld["id"],
                        "message": f"Trường '{atbl['alias']}.{afld['field_code']}' bị xóa hoặc ẩn.",
                    }
                )
                continue
            if afld["data_type"] != dfld["data_type"]:
                breaking.append(
                    {
                        "change_type": "FIELD_DATATYPE_CHANGED",
                        "entity": f"{atbl['alias']}.{afld['field_code']}",
                        "field_id": afld["id"],
                        "message": f"Kiểu dữ liệu '{afld['field_code']}' đổi từ {afld['data_type']} sang {dfld['data_type']}.",
                    }
                )
        for fcode, dfld in sorted(d_fields.items()):
            if fcode not in a_fields:
                non_breaking.append(
                    {
                        "change_type": "FIELD_ADDED",
                        "entity": f"{dtbl['alias']}.{dfld['field_code']}",
                        "message": f"Thêm trường mới '{dtbl['alias']}.{dfld['field_code']}'.",
                    }
                )

    for alias, dtbl in sorted(d_tables.items()):
        if alias not in a_tables:
            non_breaking.append(
                {
                    "change_type": "TABLE_ADDED",
                    "entity": dtbl["alias"],
                    "message": f"Thêm bảng mới '{dtbl['alias']}'.",
                }
            )

    def _rel_sig(bundle: dict[str, Any]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        tmap = {t["id"]: t["alias"].upper() for t in bundle["tables"]}
        out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for r in bundle["relationships"]:
            sig = (
                tmap.get(r["from_table_id"], ""),
                r["from_column"].upper(),
                tmap.get(r["to_table_id"], ""),
                r["to_column"].upper(),
            )
            out[sig] = r
        return out

    a_rels = _rel_sig(active)
    d_rels = _rel_sig(draft)
    for sig, arel in sorted(a_rels.items()):
        drel = d_rels.get(sig)
        if drel is None or (
            arel["cardinality"],
            arel["join_type"],
            arel["is_active"],
        ) != (
            drel["cardinality"],
            drel["join_type"],
            drel["is_active"],
        ):
            breaking.append(
                {
                    "change_type": "RELATIONSHIP_CHANGED",
                    "entity": arel["name"],
                    "message": f"Quan hệ '{arel['name']}' ({sig[0]}.{sig[1]} → {sig[2]}.{sig[3]}) bị xóa hoặc thay đổi.",
                }
            )

    a_meas = {m["code"].upper(): m for m in active["measures"]}
    d_meas = {m["code"].upper(): m for m in draft["measures"]}
    for mcode, am in sorted(a_meas.items()):
        dm = d_meas.get(mcode)
        if dm is None or (
            am["measure_type"],
            am["aggregation"],
            am["expr_json"],
        ) != (
            dm["measure_type"],
            dm["aggregation"],
            dm["expr_json"],
        ):
            breaking.append(
                {
                    "change_type": "MEASURE_CHANGED",
                    "entity": am["code"],
                    "measure_id": am["id"],
                    "message": f"Measure '{am['code']}' bị xóa hoặc thay đổi công thức.",
                }
            )
    for mcode, dm in sorted(d_meas.items()):
        if mcode not in a_meas:
            non_breaking.append(
                {
                    "change_type": "MEASURE_ADDED",
                    "entity": dm["code"],
                    "message": f"Thêm Measure mới '{dm['code']}'.",
                }
            )

    def _rls_sig(bundle: dict[str, Any]) -> set[tuple[str, str, str, str, bool, bool]]:
        tmap = {t["id"]: t["alias"].upper() for t in bundle["tables"]}
        return {
            (
                tmap.get(p["table_id"], ""),
                p["column_name"].upper(),
                p["policy_type"],
                str(p.get("scope_attr") or ""),
                bool(p["admin_bypass"]),
                bool(p["is_active"]),
            )
            for p in bundle["rls_policies"]
        }

    if _rls_sig(active) != _rls_sig(draft):
        breaking.append(
            {
                "change_type": "RLS_CHANGED",
                "entity": active["model"]["code"],
                "message": "Chính sách metadata RLS của mô hình đã thay đổi.",
            }
        )

    return {
        "draft_version_id": draft_ver_id,
        "active_version_id": active_ver_id,
        "breaking_changes": breaking,
        "non_breaking_changes": non_breaking,
    }


@service
@requires_menu("report_model")
def diff_model_versions(ctx: Ctx, draft_version_id: int, active_version_id: int) -> dict[str, Any]:
    """So sánh sự khác biệt giữa hai phiên bản mô hình."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        return compute_version_diff(conn, draft_version_id, active_version_id)


@service
@requires_menu("report_model")
def impact_analysis(ctx: Ctx, model_id: int, target_version_id: int | None = None) -> dict[str, Any]:
    """Phân tích ảnh hưởng lên Reports / Visuals / Exports (read-only)."""
    _ = ctx
    engine = get_recon_engine()
    with engine.connect() as conn:
        model = _load_model_row(conn, model_id)
        active_ver_id = int(model["ACTIVE_VERSION_ID"]) if model["ACTIVE_VERSION_ID"] is not None else None
        breaking_changes: list[dict[str, Any]] = []
        if target_version_id is not None and active_ver_id is not None and target_version_id != active_ver_id:
            diff = compute_version_diff(conn, target_version_id, active_ver_id)
            breaking_changes = diff["breaking_changes"]

        ver_ids = [
            int(r[0])
            for r in conn.execute(
                select(recon_rpt_model_ver.c.ID).where(recon_rpt_model_ver.c.MODEL_ID == model_id)
            ).all()
        ]
        reports: list[dict[str, Any]] = []
        visuals: list[dict[str, Any]] = []

        insp = inspect(conn)
        table_names = set(insp.get_table_names())
        if ver_ids and "RECON_RPT_TPL_VER" in table_names:
            tpl_ver_cols = {c["name"].upper() for c in insp.get_columns("RECON_RPT_TPL_VER")}
            if "MODEL_VERSION_ID" in tpl_ver_cols:
                placeholders = ", ".join(f":vid_{i}" for i in range(len(ver_ids)))
                params = {f"vid_{i}": vid for i, vid in enumerate(ver_ids)}
                rpt_rows = (
                    conn.execute(
                        text(
                            f"""
                            SELECT DISTINCT
                                r.ID AS report_id,
                                r.CODE AS report_code,
                                r.NAME AS report_name,
                                t.CODE AS template_code,
                                v.ID AS tpl_ver_id,
                                v.VERSION_NO AS tpl_ver_no,
                                v.STATUS AS tpl_status,
                                v.MODEL_VERSION_ID AS model_version_id
                            FROM RECON_RPT_TPL_VER v
                            JOIN RECON_REPORT_TEMPLATE t ON t.ID = v.TEMPLATE_ID
                            JOIN RECON_REPORT r ON r.ID = t.REPORT_ID
                            WHERE v.MODEL_VERSION_ID IN ({placeholders})
                              AND v.STATUS IN ('DRAFT', 'DRY_RUN_OK', 'ACTIVE')
                            ORDER BY r.CODE, v.VERSION_NO DESC
                            """
                        ),
                        params,
                    )
                    .mappings()
                    .all()
                )
                reports = [dict(r) for r in rpt_rows]

                if (
                    reports
                    and "RECON_RPT_VISUAL" in table_names
                    and "RECON_RPT_VISUAL_FIELD" in table_names
                ):
                    vis_rows = (
                        conn.execute(
                            text(
                                f"""
                                SELECT
                                    vis.ID AS visual_id,
                                    vis.TITLE AS visual_title,
                                    r.CODE AS report_code,
                                    r.NAME AS report_name,
                                    v.MODEL_VERSION_ID AS model_version_id,
                                    vf.FIELD_ID AS field_id,
                                    vf.MEASURE_ID AS measure_id
                                FROM RECON_RPT_VISUAL vis
                                JOIN RECON_RPT_TPL_VER v ON v.ID = vis.VERSION_ID
                                JOIN RECON_REPORT_TEMPLATE t ON t.ID = v.TEMPLATE_ID
                                JOIN RECON_REPORT r ON r.ID = t.REPORT_ID
                                LEFT JOIN RECON_RPT_VISUAL_FIELD vf ON vf.VISUAL_ID = vis.ID
                                WHERE v.MODEL_VERSION_ID IN ({placeholders})
                                  AND v.STATUS IN ('DRAFT', 'DRY_RUN_OK', 'ACTIVE')
                                ORDER BY vis.ID
                                """
                            ),
                            params,
                        )
                        .mappings()
                        .all()
                    )
                    affected_field_ids = {b["field_id"] for b in breaking_changes if "field_id" in b}
                    affected_meas_ids = {b["measure_id"] for b in breaking_changes if "measure_id" in b}
                    seen_vis: set[int] = set()
                    for vr in vis_rows:
                        vid_int = int(vr["visual_id"])
                        if vid_int in seen_vis:
                            continue
                        if breaking_changes:
                            if vr["field_id"] not in affected_field_ids and vr["measure_id"] not in affected_meas_ids:
                                continue
                        seen_vis.add(vid_int)
                        visuals.append(
                            {
                                "visual_id": vid_int,
                                "visual_title": vr["visual_title"],
                                "report_code": vr["report_code"],
                                "report_name": vr["report_name"],
                                "model_version_id": vr["model_version_id"],
                            }
                        )

        return {
            "model_id": model_id,
            "active_version_id": active_ver_id,
            "target_version_id": target_version_id,
            "reports": reports,
            "visuals": visuals,
            "scheduled_exports": [],
            "breaking_changes": breaking_changes,
        }


@service
@requires_menu("report_model")
def discover_source_objects(
    ctx: Ctx,
    data_source_id: int,
    schema: str | None = None,
    q: str | None = None,
    object_type: str | None = None,
    *,
    enrich: bool = True,
    enrich_limit: int = 40,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Liệt kê bảng/view của Data Source kèm thông tin PK/FK và ước lượng dòng (1 query batch + cache 10 phút)."""
    _ = ctx
    _ = enrich_limit
    norm_type = object_type.strip().upper() if object_type and object_type.strip().upper() in ("TABLE", "VIEW") else None
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_map = _ds_summary_map(conn, {int(data_source_id)})
    ds_info = ds_map.get(int(data_source_id))
    if ds_info is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy Data Source đã chọn.")

    target_schema = (schema or ds_info.get("default_schema") or "").strip() or None
    q_norm = (q or "").strip().lower()

    if enrich:
        all_items = list_schema_table_stats(
            int(data_source_id),
            schema=target_schema,
            force_refresh=force_refresh,
        )
    else:
        raw_tables = catalog_list_tables(
            int(data_source_id),
            schema=target_schema,
        )
        all_items = [
            {
                "name": str(tbl["name"]),
                "type": str(tbl.get("type") or "TABLE").upper(),
                "schema": str(tbl.get("schema") or target_schema or ""),
                "pk_count": 0,
                "fk_count": 0,
                "row_estimate": None,
            }
            for tbl in raw_tables
        ]

    items = [
        item
        for item in all_items
        if (norm_type is None or str(item.get("type") or "").upper() == norm_type)
        and (not q_norm or q_norm in str(item.get("name") or "").lower())
    ]
    return {
        "data_source": ds_info,
        "schema": target_schema or "",
        "objects": items,
        "total_count": len(items),
    }
