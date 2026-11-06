"""Service Column mapping — task 24, spec 12/12a.

Mapping cột kết quả: auto-discover (bước 1), grid sửa/xếp (bước 2),
rule format/alignment/width/visibility/total (bước 3), preview (bước 4).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_report,
    recon_report_template,
    recon_rpt_column,
    recon_rpt_tpl_ver,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_source import analyze_version_source, apply_source_diff


def _load_version_row(conn: Connection, version_id: int, admin: bool) -> Any:
    """Đọc version; người thường chỉ thấy version của report hiển thị."""
    row = (
        conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    if not admin:
        report_row = (
            conn.execute(
                select(recon_report)
                .join(
                    recon_report_template,
                    recon_report_template.c.REPORT_ID == recon_report.c.ID,
                )
                .where(recon_report_template.c.ID == int(row["TEMPLATE_ID"]))
            )
            .mappings()
            .first()
        )
        if (
            report_row is None
            or report_row["IS_VISIBLE"] != "Y"
            or report_row["IS_ACTIVE"] != "Y"
        ):
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    return row


def _load_version_draft(conn: Connection, version_id: int) -> Any:
    """Đọc version; chỉ DRAFT mới sửa được mapping cột."""
    row = (
        conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    if row["STATUS"] != "DRAFT":
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chỉ version DRAFT mới sửa được mapping cột; version đã khóa cần clone mới.",
        )
    return row


def _column_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "field_name": str(row["FIELD_NAME"]),
        "label": str(row["LABEL"]),
        "data_type": str(row["DATA_TYPE"]),
        "display_order": int(row["DISPLAY_ORDER"]),
        "web_visible": row["WEB_VISIBLE"] == "Y",
        "excel_visible": row["EXCEL_VISIBLE"] == "Y",
        "format_mask": row["FORMAT_MASK"],
        "alignment": str(row["ALIGNMENT"]),
        "width": row["WIDTH"],
        "is_total": row["IS_TOTAL"] == "Y",
    }


def _load_columns(conn: Connection, version_id: int) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            select(recon_rpt_column)
            .where(recon_rpt_column.c.VERSION_ID == version_id)
            .order_by(recon_rpt_column.c.DISPLAY_ORDER, recon_rpt_column.c.FIELD_NAME)
        )
        .mappings()
        .all()
    )
    return [_column_dict(row) for row in rows]


@service
@requires_menu("report_center")
def list_columns(ctx: Ctx, version_id: int) -> list[dict[str, Any]]:
    """Grid mapping cột của version: đủ 11 trường, theo DISPLAY_ORDER (T24-01)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        _load_version_row(conn, version_id, admin)
        return _load_columns(conn, version_id)


@service
@requires_menu("report_admin")
def refresh_columns(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Chạy lại analyze + apply diff nguồn cho version DRAFT (T22-08, bước 1).

    Trả diff {added, removed, type_changed} + số lượng đã áp + grid hiện tại.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        _load_version_draft(conn, version_id)
    diff_res = analyze_version_source(ctx, version_id)
    if not diff_res.ok or diff_res.data is None:
        raise ServiceError(
            diff_res.code or ErrorCode.INTERNAL_ERROR,
            diff_res.message or "Không phân tích được nguồn dữ liệu.",
        )
    apply_res = apply_source_diff(ctx, version_id, diff_res.data)
    if not apply_res.ok or apply_res.data is None:
        raise ServiceError(
            apply_res.code or ErrorCode.INTERNAL_ERROR,
            apply_res.message or "Không áp dụng được diff nguồn.",
        )
    with engine.connect() as conn:
        columns = _load_columns(conn, version_id)
    return {
        "diff": diff_res.data,
        "applied": apply_res.data,
        "columns": columns,
    }
