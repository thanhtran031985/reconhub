"""Service Column mapping — task 24, spec 12/12a.

Mapping cột kết quả: auto-discover (bước 1), grid sửa/xếp (bước 2),
rule format/alignment/width/visibility/total (bước 3), preview (bước 4).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from sqlalchemy import Connection, select

from app.core.audit import write_audit_log
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


# ─── Grid sửa/xếp (bước 2) ───────────────────────────────────────────────────


class ColumnUpdate(BaseModel):
    """Payload sửa một cột mapping (FIELD_NAME/DATA_TYPE/DISPLAY_ORDER readonly)."""

    label: str | None = Field(default=None, min_length=1, max_length=200)
    format_mask: str | None = Field(default=None, max_length=100)
    alignment: Literal["LEFT", "CENTER", "RIGHT"] | None = None
    width: int | None = None
    web_visible: bool | None = None
    excel_visible: bool | None = None
    is_total: bool | None = None
    # Trường readonly: có mặt trong payload là lỗi (không lặng lẽ bỏ qua).
    field_name: str | None = None
    data_type: str | None = None
    display_order: int | None = None


def _validate_column_update(dto: ColumnUpdate) -> None:
    """Kiểm tra cấu trúc payload sửa cột (rule nghiệp vụ ở bước 3)."""
    if (
        dto.field_name is not None
        or dto.data_type is not None
        or dto.display_order is not None
    ):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "FIELD_NAME, DATA_TYPE và DISPLAY_ORDER là readonly; "
            "đổi thứ tự bằng move/reorder.",
        )
    if "label" in dto.model_fields_set and (
        dto.label is None or not dto.label.strip()
    ):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "LABEL cột không được để trống."
        )
    for field in ("web_visible", "excel_visible", "is_total"):
        if field in dto.model_fields_set and getattr(dto, field) is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, f"{field} phải là true/false."
            )


def _column_update_values(dto: ColumnUpdate) -> dict[str, Any]:
    """Chuyển payload đã validate thành dict cột DB (chỉ field có mặt)."""
    values: dict[str, Any] = {}
    if "label" in dto.model_fields_set:
        values["LABEL"] = str(dto.label).strip()
    if "format_mask" in dto.model_fields_set:
        values["FORMAT_MASK"] = (
            str(dto.format_mask).strip() if dto.format_mask is not None else None
        )
    if "alignment" in dto.model_fields_set:
        values["ALIGNMENT"] = dto.alignment
    if "width" in dto.model_fields_set:
        values["WIDTH"] = dto.width
    for field in ("web_visible", "excel_visible", "is_total"):
        if field in dto.model_fields_set:
            values[field.upper()] = "Y" if getattr(dto, field) else "N"
    return values


def _load_column_row(conn: Connection, version_id: int, column_id: int) -> Any:
    row = (
        conn.execute(
            select(recon_rpt_column).where(
                recon_rpt_column.c.ID == column_id,
                recon_rpt_column.c.VERSION_ID == version_id,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy cột.")
    return row


@service
@requires_menu("report_admin")
def update_column(
    ctx: Ctx, version_id: int, column_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Sửa một cột mapping của version DRAFT (một transaction + audit)."""
    dto = ColumnUpdate(**payload)
    _validate_column_update(dto)
    values = _column_update_values(dto)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        _load_column_row(conn, version_id, column_id)
        if values:
            conn.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == column_id)
                .values(**values)
            )
        write_audit_log(
            conn,
            "RECON_RPT_COLUMN",
            column_id,
            "UPDATE_COLUMN",
            ctx.username,
            new_data={"version_id": version_id, **values},
        )
        updated = _load_column_row(conn, version_id, column_id)
        return _column_dict(updated)


@service
@requires_menu("report_admin")
def update_columns(
    ctx: Ctx, version_id: int, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Lưu cả grid mapping một lần — validate toàn bộ rồi mới ghi (T24-02)."""
    dtos: list[tuple[int, dict[str, Any]]] = []
    for item in rows:
        column_id = item.get("id")
        if not isinstance(column_id, int):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "Mỗi dòng grid cần có id cột."
            )
        dto = ColumnUpdate(**{k: v for k, v in item.items() if k != "id"})
        _validate_column_update(dto)
        dtos.append((column_id, _column_update_values(dto)))
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        for column_id, _values in dtos:
            _load_column_row(conn, version_id, column_id)
        for column_id, values in dtos:
            if values:
                conn.execute(
                    recon_rpt_column.update()
                    .where(recon_rpt_column.c.ID == column_id)
                    .values(**values)
                )
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "UPDATE_COLUMN_LAYOUT",
            ctx.username,
            new_data={"column_ids": [cid for cid, _ in dtos]},
        )
        return {"columns": _load_columns(conn, version_id)}


@service
@requires_menu("report_admin")
def move_column(
    ctx: Ctx, version_id: int, column_id: int, to_index: int
) -> dict[str, Any]:
    """Kéo-thả một cột sang vị trí khác trong grid (T24-02)."""
    if to_index < 0:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Vị trí đích phải ≥ 0."
        )
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        _load_column_row(conn, version_id, column_id)
        columns = _load_columns(conn, version_id)
        ids = [c["id"] for c in columns if c["id"] != column_id]
        ids.insert(min(to_index, len(ids)), column_id)
        for i, cid in enumerate(ids):
            conn.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == cid)
                .values(DISPLAY_ORDER=(i + 1) * 10)
            )
        write_audit_log(
            conn,
            "RECON_RPT_COLUMN",
            column_id,
            "UPDATE_COLUMN",
            ctx.username,
            new_data={"version_id": version_id, "index": to_index},
        )
        updated = _load_column_row(conn, version_id, column_id)
        return _column_dict(updated)


@service
@requires_menu("report_admin")
def reorder_columns(
    ctx: Ctx, version_id: int, ordered_ids: list[int]
) -> dict[str, Any]:
    """Xếp lại toàn bộ grid từ danh sách id theo thứ tự (T24-02)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        columns = _load_columns(conn, version_id)
        current_ids = {c["id"] for c in columns}
        if len(ordered_ids) != len(set(ordered_ids)):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "Danh sách xếp lại có cột trùng."
            )
        if set(ordered_ids) != current_ids:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Danh sách xếp lại phải gồm đủ các cột, không thừa không thiếu.",
            )
        for i, cid in enumerate(ordered_ids):
            conn.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == cid)
                .values(DISPLAY_ORDER=(i + 1) * 10)
            )
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "UPDATE_COLUMN_LAYOUT",
            ctx.username,
            new_data={"column_ids": list(ordered_ids)},
        )
        return {"columns": _load_columns(conn, version_id)}
