"""Service Report execution — task 25, spec 12 §5/§Bước 5, 12b luồng C/G.

REPORT_RUN snapshot + thực thi bind/whitelist (bước 1), phân trang server-side
(bước 2), cancel/timeout/metrics (bước 3), history/preset/favorite (bước 4).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Connection, func, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_report,
    recon_report_run,
    recon_report_template,
    recon_rpt_column,
    recon_rpt_param,
    recon_rpt_preset,
    recon_rpt_tpl_ver,
)
from app.engine.sql_dialect import quote_identifier
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_query import QueryFilter
from app.services import service
from app.services.lookup import get_db_column_mappings
from app.services.notification import notify_for_report_run
from app.services.perm import is_admin, requires_menu
from app.services.report import load_report_row
from app.services.report_param import resolve_param_values
from app.services.report_source import (
    build_report_query,
    effective_column_label,
    open_checked_connection,
)
from app.services.report_timeouts import get_report_timeouts

# Lưu ý: KHÔNG import report_studio/semantic_query ở module-level —
# semantic_query import _check_prod_admin/map_oracle_error từ module này
# nên import trên sẽ tạo vòng. Các hàm semantic import lười trong hàm.


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── Loaders ────────────────────────────────────────────────────────────────


def _check_prod_admin(conn: Connection, data_source_id: int | None, admin: bool) -> None:
    """Spec 11 D4: chạy truy vấn trên Data Source PROD chỉ ADMIN.

    Rào chắn đặt ở các điểm thực thi mà operator gọi được (create/execute/
    get_report_page). Dry-run/activate đã report_admin-only nên không cần.
    """
    if admin or data_source_id is None:
        return
    env = conn.execute(
        select(recon_data_source.c.ENV).where(recon_data_source.c.ID == data_source_id)
    ).scalar_one_or_none()
    if env is not None and str(env).upper() == "PROD":
        raise ServiceError(
            ErrorCode.FORBIDDEN,
            "Chỉ ADMIN được chạy trên Data Source PROD.",
        )


def load_version_detail(conn: Connection, version_id: int) -> dict[str, Any]:
    """Chi tiết version đủ cho thực thi: nguồn + params + columns."""
    row = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    params = (
        conn.execute(
            select(recon_rpt_param)
            .where(recon_rpt_param.c.VERSION_ID == version_id)
            .order_by(recon_rpt_param.c.DISPLAY_ORDER, recon_rpt_param.c.CODE)
        )
        .mappings()
        .all()
    )
    columns = (
        conn.execute(
            select(recon_rpt_column)
            .where(recon_rpt_column.c.VERSION_ID == version_id)
            .order_by(recon_rpt_column.c.DISPLAY_ORDER, recon_rpt_column.c.FIELD_NAME)
        )
        .mappings()
        .all()
    )
    lookup_map = get_db_column_mappings(conn)
    return {
        "id": int(row["ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "status": str(row["STATUS"]),
        "data_source_id": row["DATA_SOURCE_ID"],
        "model_version_id": row["MODEL_VERSION_ID"],
        "source_type": row["SOURCE_TYPE"],
        "sql_text": row["SQL_TEXT"],
        "source_owner": row["SOURCE_OWNER"],
        "source_object": row["SOURCE_OBJECT"],
        "timeout_sec": int(row["TIMEOUT_SEC"]),
        "preview_max_rows": int(row["PREVIEW_MAX_ROWS"]),
        "export_max_rows": int(row["EXPORT_MAX_ROWS"]),
        "params": [
            {
                "id": int(p["ID"]),
                "code": str(p["CODE"]),
                "data_type": str(p["DATA_TYPE"]),
                "required": p["REQUIRED"] == "Y",
                "filter_column": p["FILTER_COLUMN"],
                "filter_operator": p["FILTER_OPERATOR"],
                "is_visible": p["IS_VISIBLE"] == "Y",
            }
            for p in params
        ],
        "columns": [
            {
                "field_name": str(c["FIELD_NAME"]),
                "label": effective_column_label(str(c["FIELD_NAME"]), str(c["LABEL"]), lookup_map),
                "data_type": str(c["DATA_TYPE"]),
                "display_order": int(c["DISPLAY_ORDER"]),
                "web_visible": c["WEB_VISIBLE"] == "Y",
                "excel_visible": c["EXCEL_VISIBLE"] == "Y",
                "format_mask": c["FORMAT_MASK"],
                "alignment": str(c["ALIGNMENT"]),
                "width": c["WIDTH"],
                "is_total": c["IS_TOTAL"] == "Y",
            }
            for c in columns
        ],
    }


def _load_run_row(conn: Connection, run_id: int, ctx: Ctx, admin: bool) -> Any:
    """Đọc run; người thường chỉ thấy run của mình (luồng G)."""
    row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
    if not admin and row["CREATED_BY"] != ctx.username:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy run.")
    return row


def _run_dict(row: Any) -> dict[str, Any]:
    params = row["PARAMS_JSON"]
    # report_name/category_code chỉ có khi query JOIN RECON_REPORT
    # (list_report_runs); các loader khác (get/execute) không JOIN.
    mapping = row if isinstance(row, dict) else dict(row)
    return {
        "id": int(row["ID"]),
        "report_id": int(row["REPORT_ID"]),
        "report_name": mapping.get("report_name"),
        "category_code": mapping.get("category_code"),
        "template_id": int(row["TEMPLATE_ID"]),
        "version_id": int(row["VERSION_ID"]),
        "visual_id": mapping.get("VISUAL_ID"),
        "query_spec": dict(mapping["QUERY_SPEC_JSON"]) if isinstance(mapping.get("QUERY_SPEC_JSON"), dict) else {},
        "params": dict(params) if isinstance(params, dict) else {},
        "status": str(row["STATUS"]),
        "row_count": row["ROW_COUNT"],
        "query_ms": row["QUERY_MS"],
        "error_code": row["ERROR_CODE"],
        "error_message": row["ERROR_MESSAGE"],
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"],
        "finished_at": row["FINISHED_AT"],
    }


def _active_version_id(conn: Connection, report_id: int, template_id: int | None) -> tuple[int, int]:
    """(template_id, version_id ACTIVE) — template_id bỏ trống thì lấy template
    đầu tiên theo display order có ACTIVE version."""
    if template_id is not None:
        tpl = (
            conn.execute(
                select(recon_report_template).where(
                    recon_report_template.c.ID == template_id,
                    recon_report_template.c.REPORT_ID == report_id,
                )
            )
            .mappings()
            .first()
        )
        if tpl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy template.")
        if tpl["ACTIVE_VERSION_ID"] is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Template chưa có version ACTIVE; cần dry-run rồi activate trước.",
            )
        return int(tpl["ID"]), int(tpl["ACTIVE_VERSION_ID"])
    rows = (
        conn.execute(
            select(recon_report_template)
            .where(recon_report_template.c.REPORT_ID == report_id)
            .order_by(recon_report_template.c.DISPLAY_ORDER)
        )
        .mappings()
        .all()
    )
    for tpl in rows:
        if tpl["ACTIVE_VERSION_ID"] is not None:
            return int(tpl["ID"]), int(tpl["ACTIVE_VERSION_ID"])
    raise ServiceError(
        ErrorCode.VALIDATION_ERROR,
        "Báo cáo chưa có template nào ACTIVE; cần dry-run rồi activate trước.",
    )


# ─── Xây truy vấn ───────────────────────────────────────────────────────────


def build_count_query(sql: str) -> str:
    """SELECT COUNT(*) bọc ngoài câu truy vấn gốc (cùng binds)."""
    return f"SELECT COUNT(*) AS total FROM (\n{sql}\n)"


def build_paged_query(sql: str, page: int, page_size: int, order_by: str, db_type: str = "ORACLE") -> str:
    """Trang dữ liệu: ORDER BY + OFFSET/FETCH (Oracle 12c+) hoặc LIMIT/OFFSET (SQLite)."""
    offset = (page - 1) * page_size
    if str(db_type).upper() == "SQLITE":
        return f"SELECT * FROM (\n{sql}\n) ORDER BY {order_by} LIMIT {page_size} OFFSET {offset}"
    return f"SELECT * FROM (\n{sql}\n) ORDER BY {order_by} OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"


def _validate_sorts(sorts: list[dict[str, Any]] | None, field_names: list[str]) -> list[dict[str, str]]:
    """Sorts whitelist theo cột của version; field lạ → SQL_NOT_ALLOWED."""
    allowed = {name.upper() for name in field_names}
    out: list[dict[str, str]] = []
    for item in sorts or []:
        field = str(item.get("field", "")).strip().upper()
        direction = str(item.get("direction", "ASC")).strip().upper()
        if field not in allowed:
            raise ServiceError(
                ErrorCode.SQL_NOT_ALLOWED,
                f"Cột sort không có trong kết quả: {field!r}.",
            )
        if direction not in ("ASC", "DESC"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Hướng sort phải là ASC hoặc DESC: {direction!r}.",
            )
        out.append({"field": field, "direction": direction})
    return out


def stable_order_by(detail: dict[str, Any], sorts: list[dict[str, str]]) -> str:
    """ORDER BY: sorts người dùng + cột đầu tiên làm tiebreaker (Q6)."""
    parts = [f"{quote_identifier(s['field'])} {s['direction']}" for s in sorts]
    fields = [c["field_name"] for c in detail["columns"]]
    if fields:
        first = fields[0].upper()
        if first not in {s["field"] for s in sorts}:
            parts.append(f"{quote_identifier(first)} ASC")
    if not parts:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Version chưa có cột nào để sắp xếp kết quả.",
        )
    return ", ".join(parts)


def build_run_query(detail: dict[str, Any], resolved: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(sql, binds) cho một lần chạy: CUSTOM_SQL dùng snapshot, VIEW/TABLE
    dùng query builder whitelist (T22-03)."""
    source_type = detail["source_type"]
    if source_type == "CUSTOM_SQL":
        sql_text = detail["sql_text"]
        if not sql_text:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version CUSTOM_SQL chưa có SQL_TEXT.")
        # Bind đủ mọi tham số đã khai báo: tham số không bắt buộc vắng giá
        # trị thì bind NULL (thay vì vắng mặt) để SQL dạng
        # (:P_ORG IS NULL OR ORG = :P_ORG) chạy được; vắng bind thì driver
        # Oracle báo DPY-4010. Bind thừa không có trong SQL được driver bỏ
        # qua nên an toàn.
        binds = {str(p["code"]): resolved.get(str(p["code"])) for p in detail.get("params", [])}
        return str(sql_text), binds
    if source_type in ("VIEW", "TABLE"):
        columns = [{"name": c["field_name"]} for c in detail["columns"]]
        selected = [c["field_name"] for c in detail["columns"] if c["web_visible"]]
        by_code = {p["code"]: p for p in detail["params"]}
        filters = []
        for code, value in resolved.items():
            param = by_code.get(code)
            if param is None or not param["filter_column"]:
                continue
            filters.append(
                {
                    "column": str(param["filter_column"]),
                    "operator": str(param["filter_operator"] or "="),
                    "code": code,
                    "value": value,
                }
            )
        owner_val = detail.get("source_owner")
        owner_str = str(owner_val) if owner_val and str(owner_val).upper() != "NONE" else ""
        return build_report_query(
            source_type,
            owner_str or None,
            str(detail["source_object"]),
            columns,
            selected=selected or None,
            filters=filters,
        )
    raise ServiceError(
        ErrorCode.VALIDATION_ERROR,
        f"Version chưa có nguồn dữ liệu hợp lệ: {source_type!r}.",
    )


# ─── Thực thi trên Oracle ───────────────────────────────────────────────────


def map_oracle_error(exc: Exception, timeout_sec: int) -> ServiceError:
    """Map lỗi Oracle theo mẫu app/engine/fetch.py."""
    err_str = str(exc).upper()
    if isinstance(exc, TimeoutError) or "ORA-01013" in err_str or "TIMEOUT" in err_str:
        return ServiceError(
            ErrorCode.SOURCE_TIMEOUT,
            f"Truy vấn Oracle bị quá thời gian cho phép ({timeout_sec} giây).",
        )
    if (
        any(ora in err_str for ora in ["ORA-03113", "ORA-03114", "ORA-03135", "DPI-1010", "DPI-1080"])
        or "CONNECTION LOST" in err_str
        or "NOT CONNECTED" in err_str
    ):
        return ServiceError(
            ErrorCode.SOURCE_CONNECTION_LOST,
            "Mất kết nối tới cơ sở dữ liệu Oracle (VPN bị gián đoạn).",
        )
    return ServiceError(
        ErrorCode.SOURCE_QUERY_FAILED,
        f"Lỗi thực thi truy vấn nguồn Oracle: {exc}",
    )


def _prepare_query_binds(detail: dict[str, Any], binds: dict[str, Any]) -> dict[str, Any]:
    """Chuyển đổi các tham số DATE/DATETIME sang Python datetime object cho driver Oracle Thin."""
    params = detail.get("params", [])
    type_map = {str(p.get("code")): str(p.get("data_type", "STRING")).upper() for p in params}
    out = dict(binds)
    for code, val in list(out.items()):
        dtype = type_map.get(code)
        if dtype == "DATE" and isinstance(val, str) and val.strip():
            try:
                out[code] = datetime.strptime(val.strip(), "%Y-%m-%d")
            except ValueError:
                pass
        elif dtype == "DATETIME" and isinstance(val, str) and val.strip():
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    out[code] = datetime.strptime(val.strip(), fmt)
                    break
                except ValueError:
                    pass
    return out


def _execute_count_page(
    detail: dict[str, Any],
    resolved: dict[str, Any],
    page: int,
    page_size: int,
    sorts: list[dict[str, str]],
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Chạy count (timeout riêng) + một trang dữ liệu; trả (total, rows, columns)."""
    sql, raw_binds = build_run_query(detail, resolved)
    binds = _prepare_query_binds(detail, raw_binds)
    order_by = stable_order_by(detail, sorts)
    ds_id = detail["data_source_id"]
    if ds_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version chưa gắn Data Source.")
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = conn.execute(
            select(recon_data_source.c.DB_TYPE).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()
    db_type = str(ds_row.get("DB_TYPE") if ds_row else "ORACLE").upper()
    # Task 71: timeout câu COUNT + câu dữ liệu cấu hình trên /settings
    # (mặc định 300s mỗi cái); bỏ chặn cứng min(..., 30) của câu COUNT.
    timeouts = get_report_timeouts(engine)
    count_timeout = int(timeouts["count_timeout_sec"])
    data_timeout = int(timeouts["data_timeout_sec"])
    try:
        with open_checked_connection(ds_id, count_timeout) as ora_conn:
            cursor = ora_conn.cursor()
            cursor.execute(build_count_query(sql), binds)
            row = cursor.fetchone()
            total = int(row[0]) if row else 0
    except ServiceError:
        raise
    except Exception as exc:
        raise map_oracle_error(exc, count_timeout) from exc
    try:
        with open_checked_connection(ds_id, data_timeout) as ora_conn:
            cursor = ora_conn.cursor()
            cursor.execute(build_paged_query(sql, page, page_size, order_by, db_type=db_type), binds)
            col_names = [str(d[0]) for d in (cursor.description or [])]
            rows = [dict(zip(col_names, tuple(r), strict=False)) for r in cursor.fetchmany(page_size)]
    except ServiceError:
        raise
    except Exception as exc:
        raise map_oracle_error(exc, data_timeout) from exc
    return total, rows, col_names


def _resolve_or_raise(ctx: Ctx, version_id: int, values: dict[str, Any] | None) -> dict[str, Any]:
    res = resolve_param_values(ctx, version_id, values or {})
    if not res.ok or res.data is None:
        raise ServiceError(
            res.code or ErrorCode.VALIDATION_ERROR,
            res.message or "Giá trị tham số không hợp lệ.",
        )
    return dict(res.data)


# ─── Bước 1: REPORT_RUN ─────────────────────────────────────────────────────


@service
@requires_menu("report_center")
def create_report_run(
    ctx: Ctx,
    report_id: int,
    template_id: int | None = None,
    values: dict[str, Any] | None = None,
    visual_id: int | None = None,
    query_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tạo REPORT_RUN QUEUED, snapshot ACTIVE version + params đã resolve (T25-01).

    Báo cáo Studio (SEMANTIC_MODEL): bắt buộc visual_id (1 run = 1 visual);
    query_spec mang filter bổ sung của lần chạy (vd từ thanh lọc preview).
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        load_report_row(conn, report_id, admin)
        tpl_id, version_id = _active_version_id(conn, report_id, template_id)
        ds_id = conn.execute(
            select(recon_rpt_tpl_ver.c.DATA_SOURCE_ID).where(recon_rpt_tpl_ver.c.ID == version_id)
        ).scalar_one_or_none()
        _check_prod_admin(conn, ds_id, admin)
        source_type = conn.execute(
            select(recon_rpt_tpl_ver.c.SOURCE_TYPE).where(recon_rpt_tpl_ver.c.ID == version_id)
        ).scalar_one_or_none()
        source_type = str(source_type or "")
        if source_type == "SEMANTIC_MODEL":
            if visual_id is None:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Báo cáo Studio chạy theo từng visual; cần chọn visual để chạy.",
                )
            from app.services.report_studio import load_visual_by_id

            visual = load_visual_by_id(conn, int(visual_id))
            if int(visual["version_id"]) != int(version_id):
                raise ServiceError(
                    ErrorCode.NOT_FOUND,
                    f"Visual #{visual_id} không thuộc phiên bản báo cáo này.",
                )
        elif visual_id is not None or query_spec is not None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "visual_id/query_spec chỉ dùng cho báo cáo Studio (SEMANTIC_MODEL).",
            )
    if query_spec is not None:
        _validate_query_spec(query_spec)
    resolved = _resolve_or_raise(ctx, version_id, values)
    with engine.begin() as conn:
        now = _now()
        res = conn.execute(
            recon_report_run.insert().values(
                REPORT_ID=report_id,
                TEMPLATE_ID=tpl_id,
                VERSION_ID=version_id,
                VISUAL_ID=visual_id,
                QUERY_SPEC_JSON=dict(query_spec) if query_spec is not None else {},
                PARAMS_JSON=resolved,
                STATUS="QUEUED",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        run_id = int(res.lastrowid)
        write_audit_log(
            conn,
            "RECON_REPORT_RUN",
            run_id,
            "CREATE_REPORT_RUN",
            ctx.username,
            new_data={
                "report_id": report_id,
                "template_id": tpl_id,
                "version_id": version_id,
                "visual_id": visual_id,
            },
        )
        row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
        return _run_dict(row)


def _validate_query_spec(query_spec: dict[str, Any]) -> None:
    """Kiểm tra hình dạng query_spec trước khi lưu (filter phải đúng QueryFilter)."""
    if not isinstance(query_spec, dict):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "query_spec phải là dict.")
    filters = query_spec.get("filters")
    if filters is None:
        return
    if not isinstance(filters, list):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "query_spec.filters phải là danh sách.")
    for item in filters:
        if not isinstance(item, dict):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Mỗi filter trong query_spec phải là dict.")
        try:
            QueryFilter(**item)
        except Exception as exc:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Filter trong query_spec không hợp lệ: {exc}",
            ) from exc


def _execute_semantic_page(
    ctx: Ctx,
    run: Any,
    detail: dict[str, Any],
    resolved: dict[str, Any],
    page: int,
    page_size: int,
    sorts: list[dict[str, Any]] | None,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Chạy 1 trang của run Studio qua Query Planner 108.

    Trả (total, rows, columns_meta [{name, label, data_type}]) — semantic
    trả columns dạng meta (khác classic list[str]) để Viewer vẽ visual
    đúng label/kiểu dữ liệu.
    """
    from app.services.report_studio import build_visual_run_intent
    from app.services.semantic_query import execute_semantic_query_for_run

    visual_id = run["VISUAL_ID"]
    if visual_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Run báo cáo Studio thiếu visual_id.")
    model_version_id = detail.get("model_version_id")
    if model_version_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version Studio thiếu MODEL_VERSION_ID.")
    query_spec = dict(run["QUERY_SPEC_JSON"]) if isinstance(run["QUERY_SPEC_JSON"], dict) else {}
    engine = get_recon_engine()
    with engine.connect() as conn:
        intent, pinned_id = build_visual_run_intent(
            conn,
            int(run["VERSION_ID"]),
            int(visual_id),
            resolved,
            query_spec,
            sorts=sorts,
        )
    if int(pinned_id) != int(model_version_id):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "MODEL_VERSION_ID của run không khớp version đã snapshot.",
        )
    result = execute_semantic_query_for_run(ctx, int(model_version_id), intent, page=page, page_size=page_size)
    if not result.ok or not isinstance(result.data, dict):
        raise ServiceError(
            result.code or ErrorCode.INTERNAL_ERROR,
            result.message or "Chạy semantic query lỗi.",
        )
    data = result.data
    columns = [
        {
            "name": str(c["name"]),
            "label": str(c.get("label") or c["name"]),
            "data_type": str(c.get("data_type") or "STRING"),
        }
        for c in (data.get("columns") or [])
    ]
    return int(data.get("total") or 0), list(data.get("rows") or []), columns


@service
@requires_menu("report_center")
def execute_report_run(ctx: Ctx, run_id: int, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """Chạy run QUEUED đồng bộ: count + trang dữ liệu → DONE/FAILED (T25-02/03).

    Lỗi truy vấn không raise — run chuyển FAILED kèm ERROR_CODE/MESSAGE.
    """
    if page < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải ≥ 1.")
    if page_size < 1 or page_size > 200:  # Q5
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page_size phải trong khoảng 1..200.")
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        run = _load_run_row(conn, run_id, ctx, admin)
        if run["STATUS"] != "QUEUED":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ chạy được run QUEUED; run đã chạy thì tạo run mới.",
            )
        detail = load_version_detail(conn, int(run["VERSION_ID"]))
        _check_prod_admin(conn, detail["data_source_id"], admin)
        resolved = dict(run["PARAMS_JSON"] or {})
        conn.execute(recon_report_run.update().where(recon_report_run.c.ID == run_id).values(STATUS="RUNNING"))
    started = time.monotonic()
    try:
        col_names: list[Any] = []
        if detail["source_type"] == "SEMANTIC_MODEL":
            total, rows, col_names = _execute_semantic_page(ctx, run, detail, resolved, page, page_size, sorts=[])
        else:
            total, rows, col_names = _execute_count_page(detail, resolved, page, page_size, sorts=[])
    except ServiceError as exc:
        with engine.begin() as conn:
            conn.execute(
                recon_report_run.update()
                .where(recon_report_run.c.ID == run_id)
                .values(
                    STATUS="FAILED",
                    ERROR_CODE=str(exc.code),
                    ERROR_MESSAGE=exc.message[:500],
                    FINISHED_AT=_now(),
                )
            )
            write_audit_log(
                conn,
                "RECON_REPORT_RUN",
                run_id,
                "EXECUTE_REPORT_RUN",
                ctx.username,
                new_data={
                    "status": "FAILED",
                    "error_code": str(exc.code),
                    "error_message": exc.message[:500],
                },
            )
            row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
        # Task 78: báo chủ run khi lỗi.
        notify_for_report_run(engine, run_id, "REPORT_RUN_FAILED", f"Chạy báo cáo #{run_id} lỗi", exc.message[:500])
        return {"run": _run_dict(row), "total": 0, "rows": [], "columns": []}
    query_ms = int((time.monotonic() - started) * 1000)
    with engine.begin() as conn:
        conn.execute(
            recon_report_run.update()
            .where(recon_report_run.c.ID == run_id)
            .values(
                STATUS="DONE",
                ROW_COUNT=total,
                QUERY_MS=query_ms,
                FINISHED_AT=_now(),
            )
        )
        write_audit_log(
            conn,
            "RECON_REPORT_RUN",
            run_id,
            "EXECUTE_REPORT_RUN",
            ctx.username,
            new_data={"status": "DONE", "total": total, "query_ms": query_ms},
        )
        row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
    # Task 78: báo chủ run khi xong (DONE chỉ khi chủ bật REPORT_RUN_DONE).
    notify_for_report_run(engine, run_id, "REPORT_RUN_DONE", f"Chạy báo cáo #{run_id} đã xong", f"Đã chạy xong: {total} dòng.")
    return {
        "run": _run_dict(row),
        "total": total,
        "rows": rows,
        "columns": col_names,
        "page": page,
        "page_size": page_size,
    }


# Task 36: dry-run chỉ xem trước tối đa 10 dòng — không chạy COUNT toàn bộ
# (COUNT quét hết dữ liệu nên dry-run 5509 dòng mất ~10 giây trên Oracle).
DRY_RUN_PREVIEW_ROWS = 10


def _execute_preview(
    detail: dict[str, Any],
    resolved: dict[str, Any],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Chạy 1 query lấy tối đa `limit` dòng đầu; KHÔNG đếm tổng (trả rows, columns)."""
    sql, raw_binds = build_run_query(detail, resolved)
    binds = _prepare_query_binds(detail, raw_binds)
    order_by = stable_order_by(detail, [])
    ds_id = detail["data_source_id"]
    if ds_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version chưa gắn Data Source.")
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = conn.execute(
            select(recon_data_source.c.DB_TYPE).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()
    db_type = str(ds_row.get("DB_TYPE") if ds_row else "ORACLE").upper()
    # Task 71: timeout câu dữ liệu lấy từ setting trên /settings.
    data_timeout = int(get_report_timeouts(engine)["data_timeout_sec"])
    try:
        with open_checked_connection(ds_id, data_timeout) as ora_conn:
            cursor = ora_conn.cursor()
            cursor.execute(build_paged_query(sql, 1, limit, order_by, db_type=db_type), binds)
            col_names = [str(d[0]) for d in (cursor.description or [])]
            rows = [dict(zip(col_names, tuple(r), strict=False)) for r in cursor.fetchmany(limit)]
    except ServiceError:
        raise
    except Exception as exc:
        raise map_oracle_error(exc, data_timeout) from exc
    return rows, col_names


@service
@requires_menu("report_admin")
def dry_run_version(ctx: Ctx, version_id: int, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dry-run version DRAFT tối đa 10 dòng xem trước; thành công → DRY_RUN_OK (Q7).

    Đóng vòng T21-04: activate yêu cầu DRY_RUN_OK nhưng trước task 25 chưa có
    đường nào tới đó. Lỗi → version giữ DRAFT. Task 34: version ACTIVE dry-run
    được dạng xem trước thuần túy, không đổi trạng thái. Task 36: không chạy
    COUNT toàn bộ nên `total` là None (không biết tổng).
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        detail = load_version_detail(conn, version_id)
    if detail["status"] not in ("DRAFT", "DRY_RUN_OK", "ACTIVE"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chỉ dry-run được version DRAFT, DRY_RUN_OK hoặc ACTIVE.",
        )
    resolved = _resolve_or_raise(ctx, version_id, values)
    started = time.monotonic()
    # Task 36: chỉ fetch tối đa 10 dòng xem trước, không COUNT toàn bộ.
    rows, col_names = _execute_preview(
        detail,
        resolved,
        limit=min(DRY_RUN_PREVIEW_ROWS, int(detail["preview_max_rows"])),
    )
    query_ms = int((time.monotonic() - started) * 1000)
    # Task 34: version ACTIVE chỉ xem trước, không đổi trạng thái; DRAFT /
    # DRY_RUN_OK thành công thì chuyển DRY_RUN_OK để đủ điều kiện kích hoạt.
    result_status = str(detail["status"])
    with engine.begin() as conn:
        if result_status in ("DRAFT", "DRY_RUN_OK"):
            conn.execute(recon_rpt_tpl_ver.update().where(recon_rpt_tpl_ver.c.ID == version_id).values(STATUS="DRY_RUN_OK"))
            result_status = "DRY_RUN_OK"
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "DRY_RUN_VERSION",
            ctx.username,
            new_data={"preview_rows": len(rows), "query_ms": query_ms, "status": result_status},
        )
    return {
        "version_id": version_id,
        "total": None,
        "rows": rows,
        "columns": col_names,
        "query_ms": query_ms,
        "status": result_status,
    }


# ─── Bước 2: Server-side count/page/filter/sort ─────────────────────────────


@service
@requires_menu("report_center")
def get_report_page(
    ctx: Ctx,
    run_id: int,
    page: int = 1,
    page_size: int = 50,
    sorts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Lấy một trang kết quả từ snapshot của run (T25-04/05).

    Chạy lại count + page từ PARAMS_JSON + VERSION_ID đã snapshot — không
    dùng version hiện tại, nên activate sau này không đổi kết quả run cũ.
    """
    if page < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải ≥ 1.")
    if page_size < 1 or page_size > 200:  # Q5
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page_size phải trong khoảng 1..200.")
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        run = _load_run_row(conn, run_id, ctx, admin)
        # Chặn sớm trên run đã kết thúc lỗi/hủy thay vì chạy lại query rồi
        # trả "Lỗi hệ thống nội bộ" (task 27 bước 2 — Viewer mở run FAILED).
        # QUEUED/RUNNING vẫn chạy lại query theo hợp đồng task 25.
        status = str(run["STATUS"])
        if status == "FAILED":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Run đã lỗi: {run['ERROR_MESSAGE'] or run['ERROR_CODE'] or 'không rõ nguyên nhân'}.",
            )
        if status == "CANCELLED":
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Run đã bị hủy.")
        detail = load_version_detail(conn, int(run["VERSION_ID"]))
        _check_prod_admin(conn, detail["data_source_id"], admin)
        resolved = dict(run["PARAMS_JSON"] or {})
    if detail["source_type"] == "SEMANTIC_MODEL":
        total, rows, columns_meta = _execute_semantic_page(ctx, run, detail, resolved, page, page_size, sorts)
        return {
            "run_id": run_id,
            "total": total,
            "rows": rows,
            "columns": columns_meta,
            "page": page,
            "page_size": page_size,
        }
    field_names = [c["field_name"] for c in detail["columns"]]
    valid_sorts = _validate_sorts(sorts, field_names)
    total, rows, col_names = _execute_count_page(detail, resolved, page, page_size, valid_sorts)
    return {
        "run_id": run_id,
        "total": total,
        "rows": rows,
        "columns": col_names,
        "page": page,
        "page_size": page_size,
    }


# ─── Bước 3: Cancel/timeout/metrics ─────────────────────────────────────────


@service
@requires_menu("report_center")
def cancel_report_run(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Hủy run QUEUED/RUNNING → CANCELLED (T25-07, Q4)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        run = _load_run_row(conn, run_id, ctx, admin)
        if run["STATUS"] not in ("QUEUED", "RUNNING"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ hủy được run QUEUED hoặc RUNNING.",
            )
        conn.execute(
            recon_report_run.update()
            .where(recon_report_run.c.ID == run_id)
            .values(STATUS="CANCELLED", FINISHED_AT=_now())
        )
        write_audit_log(conn, "RECON_REPORT_RUN", run_id, "CANCEL_REPORT_RUN", ctx.username)
        row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
        return _run_dict(row)


@service
@requires_menu("report_center")
def report_run_metrics(ctx: Ctx) -> dict[str, Any]:
    """Metrics lịch sử run theo owner scope (T25-11)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        stmt = select(recon_report_run)
        if not admin:
            stmt = stmt.where(recon_report_run.c.CREATED_BY == ctx.username)
        rows = conn.execute(stmt).mappings().all()
    by_status: dict[str, int] = {}
    query_ms_values: list[int] = []
    total_rows = 0
    for row in rows:
        status = str(row["STATUS"])
        by_status[status] = by_status.get(status, 0) + 1
        if row["QUERY_MS"] is not None:
            query_ms_values.append(int(row["QUERY_MS"]))
        if row["ROW_COUNT"] is not None:
            total_rows += int(row["ROW_COUNT"])
    return {
        "total_runs": len(rows),
        "by_status": by_status,
        "avg_query_ms": (sum(query_ms_values) // len(query_ms_values) if query_ms_values else None),
        "total_rows": total_rows,
    }


# ─── Bước 4: History, preset, favorite, owner scope ─────────────────────────


def _parse_run_date(value: str | None, field: str) -> datetime | None:
    """Ngày 'YYYY-MM-DD' → datetime; rỗng → None; sai định dạng → lỗi."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d")
    except ValueError:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, f"{field} phải có định dạng YYYY-MM-DD."
        ) from None


@service
@requires_menu("report_center")
def list_report_runs(
    ctx: Ctx,
    report_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    from_date: str | None = None,
    to_date: str | None = None,
    category_code: str | None = None,
    report_name: str | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Lịch sử run theo owner scope (luồng G, T25-09/10) — task 43: JOIN
    RECON_REPORT lấy tên + nhóm báo cáo, lọc theo ngày chạy / nhóm / tên /
    người chạy."""
    if page < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải ≥ 1.")
    if page_size < 1 or page_size > 200:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page_size phải trong khoảng 1..200.")
    start = _parse_run_date(from_date, "Từ ngày")
    end = _parse_run_date(to_date, "Đến ngày")
    if start is not None and end is not None and start > end:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Từ ngày phải ≤ đến ngày.")
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        base = (
            select(
                recon_report_run,
                recon_report.c.NAME.label("report_name"),
                recon_report.c.CATEGORY_CODE.label("category_code"),
            )
            .select_from(recon_report_run)
            .join(recon_report, recon_report.c.ID == recon_report_run.c.REPORT_ID)
        )
        if not admin:
            base = base.where(recon_report_run.c.CREATED_BY == ctx.username)
        if report_id is not None:
            base = base.where(recon_report_run.c.REPORT_ID == report_id)
        if status is not None:
            base = base.where(recon_report_run.c.STATUS == status)
        if start is not None:
            base = base.where(recon_report_run.c.CREATED_AT >= start)
        if end is not None:
            base = base.where(recon_report_run.c.CREATED_AT < end + timedelta(days=1))
        if category_code is not None and str(category_code).strip() != "":
            base = base.where(recon_report.c.CATEGORY_CODE == str(category_code).strip())
        if report_name is not None and str(report_name).strip() != "":
            escaped = (
                str(report_name)
                .strip()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            base = base.where(func.lower(recon_report.c.NAME).like(f"%{escaped.lower()}%"))
        if created_by is not None and str(created_by).strip() != "":
            base = base.where(recon_report_run.c.CREATED_BY == str(created_by).strip())
        total = len(conn.execute(base).mappings().all())
        rows = (
            conn.execute(
                base.order_by(
                    recon_report_run.c.CREATED_AT.desc(),
                    recon_report_run.c.ID.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .mappings()
            .all()
        )
    return {
        "runs": [_run_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@service
@requires_menu("report_center")
def list_run_creators(ctx: Ctx) -> list[str]:
    """Danh sách người đã chạy (cho ô chọn Người chạy) — theo owner scope:
    người thường chỉ thấy chính mình."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        query = select(recon_report_run.c.CREATED_BY).distinct()
        if not admin:
            query = query.where(recon_report_run.c.CREATED_BY == ctx.username)
        rows = conn.execute(query.order_by(recon_report_run.c.CREATED_BY)).scalars().all()
    return [str(r) for r in rows]


@service
@requires_menu("report_center")
def get_report_run(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Chi tiết một run; run người khác → NOT_FOUND (T25-09)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = _load_run_row(conn, run_id, ctx, admin)
        return _run_dict(row)


def _get_semantic_run_sql(
    ctx: Ctx,
    run: Any,
    detail: dict[str, Any],
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """SQL đã biên dịch của run Studio — chỉ ADMIN (get_run_sql đã chặn).

    Chỉ trả TÊN bind (không lộ giá trị, theo get_semantic_sql_debug task
    108) + RLS/tables/output columns; không có câu COUNT/phân trang riêng
    vì planner đã nhúng LIMIT/OFFSET vào câu đã biên dịch.
    """
    from app.services.report_studio import build_visual_run_intent
    from app.services.semantic_query import get_semantic_sql_debug

    visual_id = run["VISUAL_ID"]
    if visual_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Run báo cáo Studio thiếu visual_id.")
    model_version_id = detail.get("model_version_id")
    if model_version_id is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Version Studio thiếu MODEL_VERSION_ID.")
    query_spec = dict(run["QUERY_SPEC_JSON"]) if isinstance(run["QUERY_SPEC_JSON"], dict) else {}
    engine = get_recon_engine()
    with engine.connect() as conn:
        intent, pinned_id = build_visual_run_intent(
            conn,
            int(run["VERSION_ID"]),
            int(visual_id),
            resolved,
            query_spec,
        )
    if int(pinned_id) != int(model_version_id):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "MODEL_VERSION_ID của run không khớp version đã snapshot.",
        )
    debug = get_semantic_sql_debug(ctx, intent)
    if not debug.ok or not isinstance(debug.data, dict):
        raise ServiceError(
            debug.code or ErrorCode.INTERNAL_ERROR,
            debug.message or "Không lấy được SQL debug.",
        )
    data = debug.data
    warnings = list(data.get("warnings") or [])
    return {
        "run_id": int(run["ID"]),
        "version_id": int(run["VERSION_ID"]),
        "source_type": "SEMANTIC_MODEL",
        "sql_text": str(data.get("sql") or ""),
        "binds": {},
        "bind_names": list(data.get("binds") or []),
        "count_sql": "",
        "paged_sql": "",
        "null_guard_missing": [],
        "warning": "; ".join(str(w) for w in warnings),
        "rls_applied": bool(data.get("rls_applied")),
        "tables_used": list(data.get("tables_used") or []),
        "output_columns": list(data.get("output_columns") or []),
        "dialect": str(data.get("dialect") or ""),
    }


def _format_bind_value(value: Any) -> Any:
    """Bind hiển thị ở tab SQL: datetime → chuỗi ISO, còn lại giữ nguyên."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@service
@requires_menu("report_center")
def get_run_sql(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """SQL đã thực hiện của một run — task 40, CHỈ ADMIN.

    Trả SQL_TEXT gốc của version đã snapshot, binds đã resolve (tham số
    không bắt buộc vắng giá trị → None, tức bind NULL như task 39), câu
    COUNT và câu phân trang thực thi. Không ADMIN → FORBIDDEN (không rò
    rỉ SQL). Cảnh báo `null_guard_missing` khi CUSTOM_SQL dùng bind mà
    không có điều kiện IS NULL/NVL/COALESCE: để trống tham số đó thì bind
    NULL và `cột = NULL` cho 0 dòng (đúng ca Org trống ở /reports/5).
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    if not admin:
        raise ServiceError(
            ErrorCode.FORBIDDEN,
            "Chỉ ADMIN mới xem được SQL thực hiện.",
        )
    with engine.connect() as conn:
        run = _load_run_row(conn, run_id, ctx, admin)
        detail = load_version_detail(conn, int(run["VERSION_ID"]))
        resolved = dict(run["PARAMS_JSON"] or {})
        ds_id = detail["data_source_id"]
        db_type = "ORACLE"
        if ds_id is not None:
            ds_row = (
                conn.execute(select(recon_data_source.c.DB_TYPE).where(recon_data_source.c.ID == ds_id))
                .mappings()
                .first()
            )
            if ds_row is not None:
                db_type = str(ds_row.get("DB_TYPE") or "ORACLE").upper()
    if detail["source_type"] == "SEMANTIC_MODEL":
        return _get_semantic_run_sql(ctx, run, detail, resolved)
    sql, raw_binds = build_run_query(detail, resolved)
    binds = {str(k): _format_bind_value(v) for k, v in _prepare_query_binds(detail, raw_binds).items()}
    order_by = stable_order_by(detail, [])
    missing: list[str] = []
    if detail["source_type"] == "CUSTOM_SQL":
        upper = str(sql).upper()
        # Chỉ tham số KHÔNG bắt buộc mới có thể vắng giá trị (bind NULL)
        # nên mới cần điều kiện bảo vệ; tham số bắt buộc luôn có giá trị.
        for param in detail.get("params", []):
            if param.get("required"):
                continue
            code = str(param["code"])
            placeholder = f":{code.upper()}"
            if placeholder not in upper:
                continue
            guarded = (
                f"{placeholder} IS NULL" in upper
                or f"NVL({placeholder}" in upper
                or f"COALESCE({placeholder}" in upper
                or f"{placeholder} IS NOT NULL" in upper
            )
            if not guarded:
                missing.append(code)
    warning = ""
    if missing:
        warning = (
            "Tham số " + ", ".join(missing) + " không có điều kiện IS NULL/NVL trong SQL: để trống sẽ bind "
            "NULL và có thể ra 0 dòng. Sửa SQL của version ở /report-admin "
            "nếu muốn để trống = lấy mọi giá trị."
        )
    return {
        "run_id": int(run["ID"]),
        "version_id": int(run["VERSION_ID"]),
        "source_type": str(detail["source_type"]),
        "sql_text": str(sql),
        "binds": binds,
        "count_sql": build_count_query(str(sql)),
        "paged_sql": build_paged_query(str(sql), 1, 50, order_by, db_type=db_type),
        "null_guard_missing": missing,
        "warning": warning,
    }


def _preset_dict(row: Any) -> dict[str, Any]:
    params = row["PARAMS_JSON"]
    return {
        "id": int(row["ID"]),
        "report_id": int(row["REPORT_ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "name": str(row["NAME"]),
        "params": dict(params) if isinstance(params, dict) else {},
        "is_default": row["IS_DEFAULT"] == "Y",
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"],
    }


@service
@requires_menu("report_center")
def create_preset(
    ctx: Ctx,
    report_id: int,
    template_id: int,
    name: str,
    values: dict[str, Any] | None = None,
    is_default: bool = False,
) -> dict[str, Any]:
    """Lưu preset tham số (cá nhân); IS_DEFAULT duy nhất theo user+template (T25-08)."""
    if not name or not name.strip() or len(name.strip()) > 200:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Tên preset không được để trống và tối đa 200 ký tự.",
        )
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        load_report_row(conn, report_id, admin)
        _tpl_id, version_id = _active_version_id(conn, report_id, template_id)
    resolved = _resolve_or_raise(ctx, version_id, values)
    with engine.begin() as conn:
        now = _now()
        if is_default:
            conn.execute(
                recon_rpt_preset.update()
                .where(
                    recon_rpt_preset.c.USER_ID == ctx.user_id,
                    recon_rpt_preset.c.TEMPLATE_ID == template_id,
                    recon_rpt_preset.c.IS_DEFAULT == "Y",
                )
                .values(IS_DEFAULT="N", UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
        res = conn.execute(
            recon_rpt_preset.insert().values(
                USER_ID=ctx.user_id,
                REPORT_ID=report_id,
                TEMPLATE_ID=template_id,
                NAME=name.strip(),
                PARAMS_JSON=resolved,
                IS_DEFAULT="Y" if is_default else "N",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
            )
        )
        preset_id = int(res.lastrowid)
        write_audit_log(
            conn,
            "RECON_RPT_PRESET",
            preset_id,
            "CREATE_PRESET",
            ctx.username,
            new_data={
                "report_id": report_id,
                "template_id": template_id,
                "name": name.strip(),
            },
        )
        row = conn.execute(select(recon_rpt_preset).where(recon_rpt_preset.c.ID == preset_id)).mappings().first()
        return _preset_dict(row)


@service
@requires_menu("report_center")
def list_presets(ctx: Ctx, report_id: int, template_id: int) -> list[dict[str, Any]]:
    """Preset của chính người dùng cho một template (mặc định lên trước)."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_rpt_preset)
                .where(
                    recon_rpt_preset.c.USER_ID == ctx.user_id,
                    recon_rpt_preset.c.REPORT_ID == report_id,
                    recon_rpt_preset.c.TEMPLATE_ID == template_id,
                )
                .order_by(
                    recon_rpt_preset.c.IS_DEFAULT.desc(),
                    recon_rpt_preset.c.CREATED_AT.desc(),
                )
            )
            .mappings()
            .all()
        )
    return [_preset_dict(row) for row in rows]


@service
@requires_menu("report_center")
def delete_preset(ctx: Ctx, preset_id: int) -> dict[str, Any]:
    """Xóa preset của mình; preset người khác → NOT_FOUND (preset là cá nhân)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(recon_rpt_preset).where(
                    recon_rpt_preset.c.ID == preset_id,
                    recon_rpt_preset.c.USER_ID == ctx.user_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy preset.")
        conn.execute(recon_rpt_preset.delete().where(recon_rpt_preset.c.ID == preset_id))
        write_audit_log(
            conn,
            "RECON_RPT_PRESET",
            preset_id,
            "DELETE_PRESET",
            ctx.username,
            old_data={"name": str(row["NAME"])},
        )
        return {"deleted": True, "preset_id": preset_id}


@service
@requires_menu("report_center")
def apply_preset(
    ctx: Ctx,
    preset_id: int,
    values_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lấy values của preset (ghi đè nếu có) đã resolve theo ACTIVE version hiện tại."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_rpt_preset).where(
                    recon_rpt_preset.c.ID == preset_id,
                    recon_rpt_preset.c.USER_ID == ctx.user_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy preset.")
        load_report_row(conn, int(row["REPORT_ID"]), admin)
        _tpl_id, version_id = _active_version_id(conn, int(row["REPORT_ID"]), int(row["TEMPLATE_ID"]))
    merged = dict(row["PARAMS_JSON"] or {})
    merged.update(values_override or {})
    resolved = _resolve_or_raise(ctx, version_id, merged)
    return {
        "report_id": int(row["REPORT_ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "values": resolved,
    }
