"""Service Report execution — task 25, spec 12 §5/§Bước 5, 12b luồng C/G.

REPORT_RUN snapshot + thực thi bind/whitelist (bước 1), phân trang server-side
(bước 2), cancel/timeout/metrics (bước 3), history/preset/favorite (bước 4).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_report_run,
    recon_report_template,
    recon_rpt_column,
    recon_rpt_param,
    recon_rpt_preset,
    recon_rpt_tpl_ver,
)
from app.engine.sql_dialect import quote_identifier
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report import load_report_row
from app.services.report_param import resolve_param_values
from app.services.report_source import build_report_query, open_checked_connection


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
    return {
        "id": int(row["ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "status": str(row["STATUS"]),
        "data_source_id": row["DATA_SOURCE_ID"],
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
                "label": str(c["LABEL"]),
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
    return {
        "id": int(row["ID"]),
        "report_id": int(row["REPORT_ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "version_id": int(row["VERSION_ID"]),
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
        return str(sql_text), dict(resolved)
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


def _execute_count_page(
    detail: dict[str, Any],
    resolved: dict[str, Any],
    page: int,
    page_size: int,
    sorts: list[dict[str, str]],
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Chạy count (timeout riêng) + một trang dữ liệu; trả (total, rows, columns)."""
    sql, binds = build_run_query(detail, resolved)
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
    count_timeout = min(int(detail["timeout_sec"]), 30)  # Q3
    data_timeout = int(detail["timeout_sec"])
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
) -> dict[str, Any]:
    """Tạo REPORT_RUN QUEUED, snapshot ACTIVE version + params đã resolve (T25-01)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.begin() as conn:
        load_report_row(conn, report_id, admin)
        tpl_id, version_id = _active_version_id(conn, report_id, template_id)
        ds_id = conn.execute(
            select(recon_rpt_tpl_ver.c.DATA_SOURCE_ID).where(recon_rpt_tpl_ver.c.ID == version_id)
        ).scalar_one_or_none()
        _check_prod_admin(conn, ds_id, admin)
    resolved = _resolve_or_raise(ctx, version_id, values)
    with engine.begin() as conn:
        now = _now()
        res = conn.execute(
            recon_report_run.insert().values(
                REPORT_ID=report_id,
                TEMPLATE_ID=tpl_id,
                VERSION_ID=version_id,
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
            },
        )
        row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == run_id)).mappings().first()
        return _run_dict(row)


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
    return {
        "run": _run_dict(row),
        "total": total,
        "rows": rows,
        "columns": col_names,
        "page": page,
        "page_size": page_size,
    }


@service
@requires_menu("report_admin")
def dry_run_version(ctx: Ctx, version_id: int, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dry-run version DRAFT tối đa preview_max_rows; thành công → DRY_RUN_OK (Q7).

    Đóng vòng T21-04: activate yêu cầu DRY_RUN_OK nhưng trước task 25 chưa có
    đường nào tới đó. Lỗi → version giữ DRAFT.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        detail = load_version_detail(conn, version_id)
    if detail["status"] != "DRAFT":
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chỉ dry-run được version DRAFT.",
        )
    resolved = _resolve_or_raise(ctx, version_id, values)
    started = time.monotonic()
    total, rows, col_names = _execute_count_page(
        detail,
        resolved,
        page=1,
        page_size=int(detail["preview_max_rows"]),
        sorts=[],
    )
    query_ms = int((time.monotonic() - started) * 1000)
    with engine.begin() as conn:
        conn.execute(recon_rpt_tpl_ver.update().where(recon_rpt_tpl_ver.c.ID == version_id).values(STATUS="DRY_RUN_OK"))
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "DRY_RUN_VERSION",
            ctx.username,
            new_data={"total": total, "query_ms": query_ms},
        )
    return {
        "version_id": version_id,
        "total": total,
        "rows": rows,
        "columns": col_names,
        "query_ms": query_ms,
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


@service
@requires_menu("report_center")
def list_report_runs(
    ctx: Ctx,
    report_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Lịch sử run theo owner scope (luồng G, T25-09/10)."""
    if page < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải ≥ 1.")
    if page_size < 1 or page_size > 200:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page_size phải trong khoảng 1..200.")
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        base = select(recon_report_run)
        if not admin:
            base = base.where(recon_report_run.c.CREATED_BY == ctx.username)
        if report_id is not None:
            base = base.where(recon_report_run.c.REPORT_ID == report_id)
        if status is not None:
            base = base.where(recon_report_run.c.STATUS == status)
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
def get_report_run(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Chi tiết một run; run người khác → NOT_FOUND (T25-09)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = _load_run_row(conn, run_id, ctx, admin)
        return _run_dict(row)


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
