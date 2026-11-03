"""app/services/lookup.py — Quản lý danh mục Lookup Type & Lookup Code dùng chung.

Phân quyền:
- Đọc danh sách: mọi vai trò (VIEWER, OPERATOR, TEMPLATE_OWNER, ADMIN).
- Tạo / Sửa / Xóa / Bật-Tắt: chỉ ADMIN.

Bảo vệ dữ liệu:
- Mã có IS_SYSTEM='Y' không được xóa cứng, chỉ có thể vô hiệu hóa.
- Mã đã được dùng trong RECON_ISSUE (REASON_CODE) cũng không được xóa cứng.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, delete, func, select, update

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_issue, recon_lookup_code, recon_lookup_type
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service

ALL_ROLES = (Role.VIEWER, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)
ADMIN_ONLY = (Role.ADMIN,)

# Cache đơn giản trong bộ nhớ, xóa sau mỗi write
_lookup_cache: dict[str, list[dict[str, Any]]] = {}

# ─── Dữ liệu mặc định khởi tạo ──────────────────────────────────────────────

_DEFAULT_TYPES = [
    ("ISSUE_STATUS", "Trạng thái đối soát", "Quản lý vòng đời xử lý chênh lệch", "Y"),
    ("ISSUE_REASON", "Nguyên nhân chênh lệch", "Phân loại nguyên nhân phát sinh chênh lệch", "Y"),
]

_DEFAULT_CODES: list[tuple[str, str, str, int, str, str, str, str]] = [
    # (lookup_type, code, meaning, order, color, icon, is_default, is_system)
    ("ISSUE_STATUS", "OPEN",        "Chưa đối soát (Chờ xử lý)",   1, "gray",   "lucide:clock",         "Y", "Y"),
    ("ISSUE_STATUS", "IN_PROGRESS", "Đang kiểm tra",                2, "blue",   "lucide:loader",        "N", "Y"),
    ("ISSUE_STATUS", "ACCEPTED",    "Xác nhận đối soát (Chấp nhận lệch)", 3, "teal", "lucide:check-circle", "N", "Y"),
    ("ISSUE_STATUS", "RESOLVED",    "Đã xử lý xong",               4, "teal",   "lucide:check-circle-2","N", "Y"),
    ("ISSUE_REASON", "ROUNDING",       "Lệch làm tròn số thập phân",             1, "blue",   "lucide:calculator",  "N", "Y"),
    ("ISSUE_REASON", "TIMING",         "Lệch thời điểm ghi nhận giao dịch",      2, "blue",   "lucide:clock",       "N", "Y"),
    ("ISSUE_REASON", "SYSTEM_BUG",     "Lỗi hệ thống tác nghiệp/billing",        3, "red",    "lucide:bug",         "N", "Y"),
    ("ISSUE_REASON", "DATA_INPUT",     "Sai sót nhập liệu thủ công",             4, "warn",   "lucide:pencil",      "N", "Y"),
    ("ISSUE_REASON", "POLICY_EXCEPTION","Ngoại lệ chính sách / Phê duyệt đặc biệt", 5, "purple","lucide:shield",   "N", "Y"),
    ("ISSUE_REASON", "OTHER",          "Nguyên nhân khác",                        6, "gray",   "lucide:more-horizontal","N","Y"),
]


def ensure_default_lookup_data(conn: Connection) -> None:
    """Nạp dữ liệu mặc định vào RECON_LOOKUP_TYPE và RECON_LOOKUP_CODE (idempotent)."""
    for lt, type_name, desc, is_sys in _DEFAULT_TYPES:
        exists = conn.execute(
            select(recon_lookup_type.c.LOOKUP_TYPE).where(recon_lookup_type.c.LOOKUP_TYPE == lt)
        ).scalar()
        if not exists:
            conn.execute(
                recon_lookup_type.insert().values(
                    LOOKUP_TYPE=lt,
                    TYPE_NAME=type_name,
                    DESCRIPTION=desc,
                    IS_SYSTEM=is_sys,
                    IS_ACTIVE="Y",
                )
            )

    for lt, code, meaning, order, color, icon, is_def, is_sys in _DEFAULT_CODES:
        exists = conn.execute(
            select(recon_lookup_code.c.LOOKUP_CODE).where(
                recon_lookup_code.c.LOOKUP_TYPE == lt,
                recon_lookup_code.c.LOOKUP_CODE == code,
            )
        ).scalar()
        if not exists:
            conn.execute(
                recon_lookup_code.insert().values(
                    LOOKUP_TYPE=lt,
                    LOOKUP_CODE=code,
                    MEANING=meaning,
                    DISPLAY_ORDER=order,
                    COLOR_BADGE=color,
                    ICON_NAME=icon,
                    IS_DEFAULT=is_def,
                    IS_SYSTEM=is_sys,
                    IS_ACTIVE="Y",
                )
            )


def _clear_cache() -> None:
    _lookup_cache.clear()


def _row_to_type_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    return {
        "lookup_type": d.get("LOOKUP_TYPE") or d.get("lookup_type"),
        "type_name": d.get("TYPE_NAME") or d.get("type_name"),
        "description": d.get("DESCRIPTION") or d.get("description"),
        "is_system": d.get("IS_SYSTEM") or d.get("is_system") or "N",
        "is_active": d.get("IS_ACTIVE") or d.get("is_active") or "Y",
    }


def _row_to_code_dict(r: Any) -> dict[str, Any]:
    d = dict(r)
    return {
        "lookup_type": d.get("LOOKUP_TYPE") or d.get("lookup_type"),
        "lookup_code": d.get("LOOKUP_CODE") or d.get("lookup_code"),
        "meaning": d.get("MEANING") or d.get("meaning"),
        "description": d.get("DESCRIPTION") or d.get("description"),
        "display_order": d.get("DISPLAY_ORDER") if d.get("DISPLAY_ORDER") is not None else d.get("display_order", 0),
        "color_badge": d.get("COLOR_BADGE") or d.get("color_badge"),
        "icon_name": d.get("ICON_NAME") or d.get("icon_name"),
        "is_default": d.get("IS_DEFAULT") or d.get("is_default") or "N",
        "is_system": d.get("IS_SYSTEM") or d.get("is_system") or "N",
        "is_active": d.get("IS_ACTIVE") or d.get("is_active") or "Y",
        "code_count": None,
    }


# ─── LIST ────────────────────────────────────────────────────────────────────

@service
def list_lookup_types(ctx: Ctx) -> list[dict[str, Any]]:
    """Trả danh sách tất cả Lookup Type đang hoạt động kèm số lượng mã con."""
    require_role(ctx, *ALL_ROLES)
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_lookup_type).order_by(recon_lookup_type.c.LOOKUP_TYPE)
            )
            .mappings()
            .all()
        )
        # Đếm số code active cho từng type
        counts_rows = conn.execute(
            select(
                recon_lookup_code.c.LOOKUP_TYPE,
                func.count(recon_lookup_code.c.LOOKUP_CODE).label("cnt"),
            )
            .where(recon_lookup_code.c.IS_ACTIVE == "Y")
            .group_by(recon_lookup_code.c.LOOKUP_TYPE)
        ).all()
        totals_rows = conn.execute(
            select(
                recon_lookup_code.c.LOOKUP_TYPE,
                func.count(recon_lookup_code.c.LOOKUP_CODE).label("cnt"),
            ).group_by(recon_lookup_code.c.LOOKUP_TYPE)
        ).all()
    counts = {r[0]: r[1] for r in counts_rows}
    totals = {r[0]: r[1] for r in totals_rows}
    result = []
    for r in rows:
        d = _row_to_type_dict(r)
        d["code_count"] = counts.get(d["lookup_type"], 0)
        # Tổng số giá trị, để thẻ loại hiển thị "X giá trị · Y đang dùng".
        d["code_total_count"] = totals.get(d["lookup_type"], 0)
        result.append(d)
    return result


@service
def list_lookup_codes(ctx: Ctx, *, lookup_type: str) -> list[dict[str, Any]]:
    """Trả danh sách các Lookup Code (kể cả inactive) theo Lookup Type."""
    require_role(ctx, *ALL_ROLES)
    # Không dùng cache nếu đang test (cache có thể chứa data từ DB khác)
    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_lookup_code)
                .where(recon_lookup_code.c.LOOKUP_TYPE == lookup_type)
                .order_by(recon_lookup_code.c.DISPLAY_ORDER, recon_lookup_code.c.LOOKUP_CODE)
            )
            .mappings()
            .all()
        )
    result = [_row_to_code_dict(r) for r in rows]
    # Cache theo engine URL để tránh nhiễu test
    cache_key = f"codes:{lookup_type}:{engine.url}"
    _lookup_cache[cache_key] = result
    return result


# ─── CREATE ──────────────────────────────────────────────────────────────────

@service
def create_lookup_type(
    ctx: Ctx,
    *,
    lookup_type: str,
    type_name: str,
    description: str | None = None,
    is_system: str = "N",
) -> dict[str, Any]:
    """Tạo mới Lookup Type. Mã phải là chữ hoa, không dấu, không trùng."""
    require_role(ctx, *ADMIN_ONLY)
    lookup_type = lookup_type.strip().upper()
    if not lookup_type:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Mã loại danh mục không được để trống.")
    engine = get_recon_engine()
    with engine.begin() as conn:
        exists = conn.execute(
            select(recon_lookup_type.c.LOOKUP_TYPE).where(recon_lookup_type.c.LOOKUP_TYPE == lookup_type)
        ).scalar()
        if exists:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã loại danh mục '{lookup_type}' đã tồn tại.")
        conn.execute(
            recon_lookup_type.insert().values(
                LOOKUP_TYPE=lookup_type,
                TYPE_NAME=type_name.strip(),
                DESCRIPTION=(description or "").strip() or None,
                IS_SYSTEM=is_system,
                IS_ACTIVE="Y",
            )
        )
    _clear_cache()
    return {"lookup_type": lookup_type}


@service
def create_lookup_code(
    ctx: Ctx,
    *,
    lookup_type: str,
    lookup_code: str,
    meaning: str,
    display_order: int = 0,
    description: str | None = None,
    color_badge: str | None = None,
    icon_name: str | None = None,
    is_default: str = "N",
) -> dict[str, Any]:
    """Tạo mới Lookup Code trong một Lookup Type. Mã không được trùng."""
    require_role(ctx, *ADMIN_ONLY)
    lookup_code = lookup_code.strip().upper()
    if not lookup_code:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Mã giá trị không được để trống.")
    engine = get_recon_engine()
    with engine.begin() as conn:
        type_exists = conn.execute(
            select(recon_lookup_type.c.LOOKUP_TYPE).where(recon_lookup_type.c.LOOKUP_TYPE == lookup_type)
        ).scalar()
        if not type_exists:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Loại danh mục '{lookup_type}' không tồn tại.")
        code_exists = conn.execute(
            select(recon_lookup_code.c.LOOKUP_CODE).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            )
        ).scalar()
        if code_exists:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã '{lookup_code}' đã tồn tại trong '{lookup_type}'.")
        conn.execute(
            recon_lookup_code.insert().values(
                LOOKUP_TYPE=lookup_type,
                LOOKUP_CODE=lookup_code,
                MEANING=meaning.strip(),
                DESCRIPTION=(description or "").strip() or None,
                DISPLAY_ORDER=display_order,
                COLOR_BADGE=color_badge,
                ICON_NAME=icon_name,
                IS_DEFAULT=is_default,
                IS_SYSTEM="N",
                IS_ACTIVE="Y",
            )
        )
    _clear_cache()
    return {"lookup_type": lookup_type, "lookup_code": lookup_code}


# ─── UPDATE ──────────────────────────────────────────────────────────────────

@service
def update_lookup_type(
    ctx: Ctx,
    *,
    lookup_type: str,
    type_name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """Sửa thông tin Lookup Type (tên, mô tả, trạng thái)."""
    require_role(ctx, *ADMIN_ONLY)
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(recon_lookup_type).where(recon_lookup_type.c.LOOKUP_TYPE == lookup_type)
        ).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Loại danh mục '{lookup_type}' không tồn tại.")
        vals: dict[str, Any] = {}
        if type_name is not None:
            vals["TYPE_NAME"] = type_name.strip()
        if description is not None:
            vals["DESCRIPTION"] = description.strip() or None
        if is_active is not None:
            vals["IS_ACTIVE"] = "Y" if is_active else "N"
        if vals:
            conn.execute(update(recon_lookup_type).where(recon_lookup_type.c.LOOKUP_TYPE == lookup_type).values(**vals))
    _clear_cache()
    return {"lookup_type": lookup_type}


@service
def update_lookup_code(
    ctx: Ctx,
    *,
    lookup_type: str,
    lookup_code: str,
    meaning: str | None = None,
    description: str | None = None,
    display_order: int | None = None,
    color_badge: str | None = None,
    icon_name: str | None = None,
    is_default: str | None = None,
) -> dict[str, Any]:
    """Sửa thông tin Lookup Code (nhãn, mô tả, thứ tự, màu, icon)."""
    require_role(ctx, *ADMIN_ONLY)
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(recon_lookup_code).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            )
        ).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Mã '{lookup_code}' không tồn tại trong '{lookup_type}'.")
        vals: dict[str, Any] = {}
        if meaning is not None:
            vals["MEANING"] = meaning.strip()
        if description is not None:
            vals["DESCRIPTION"] = description.strip() or None
        if display_order is not None:
            vals["DISPLAY_ORDER"] = display_order
        if color_badge is not None:
            vals["COLOR_BADGE"] = color_badge
        if icon_name is not None:
            vals["ICON_NAME"] = icon_name
        if is_default is not None:
            vals["IS_DEFAULT"] = is_default
        if vals:
            conn.execute(
                update(recon_lookup_code).where(
                    recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                    recon_lookup_code.c.LOOKUP_CODE == lookup_code,
                ).values(**vals)
            )
    _clear_cache()
    return {"lookup_type": lookup_type, "lookup_code": lookup_code}


# ─── TOGGLE / DELETE ─────────────────────────────────────────────────────────

@service
def toggle_lookup_code_status(
    ctx: Ctx,
    *,
    lookup_type: str,
    lookup_code: str,
    is_active: bool,
) -> dict[str, Any]:
    """Bật / Tắt trạng thái hoạt động của một Lookup Code (soft-delete)."""
    require_role(ctx, *ADMIN_ONLY)
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(recon_lookup_code).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            )
        ).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Mã '{lookup_code}' không tồn tại trong '{lookup_type}'.")
        conn.execute(
            update(recon_lookup_code).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            ).values(IS_ACTIVE="Y" if is_active else "N")
        )
    _clear_cache()
    return {"lookup_type": lookup_type, "lookup_code": lookup_code, "is_active": is_active}


@service
def delete_lookup_code(
    ctx: Ctx,
    *,
    lookup_type: str,
    lookup_code: str,
) -> dict[str, Any]:
    """Xóa cứng Lookup Code nếu chưa dùng và không phải mã hệ thống.

    Nếu là IS_SYSTEM='Y' hoặc đã được dùng trong RECON_ISSUE → trả lỗi,
    đề nghị vô hiệu hóa thay vì xóa.
    """
    require_role(ctx, *ADMIN_ONLY)
    engine = get_recon_engine()
    with engine.begin() as conn:
        row = conn.execute(
            select(recon_lookup_code).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            )
        ).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Mã '{lookup_code}' không tồn tại trong '{lookup_type}'.")

        is_sys = (row.get("IS_SYSTEM") or row.get("is_system") or "N") == "Y"
        if is_sys:
            raise ServiceError(
                ErrorCode.FORBIDDEN,
                f"Mã '{lookup_code}' là mã hệ thống, không thể xóa. Hãy vô hiệu hóa thay thế.",
            )

        # Kiểm tra xem mã đã dùng trong RECON_ISSUE chưa (chỉ áp dụng cho ISSUE_REASON)
        if lookup_type == "ISSUE_REASON":
            in_use = conn.execute(
                select(func.count(recon_issue.c.ID)).where(recon_issue.c.REASON_CODE == lookup_code)
            ).scalar()
            if in_use and in_use > 0:
                raise ServiceError(
                    ErrorCode.CONFLICT,
                    f"Mã '{lookup_code}' đã được dùng trong {in_use} bản ghi. Hãy vô hiệu hóa thay vì xóa.",
                )

        conn.execute(
            delete(recon_lookup_code).where(
                recon_lookup_code.c.LOOKUP_TYPE == lookup_type,
                recon_lookup_code.c.LOOKUP_CODE == lookup_code,
            )
        )
    _clear_cache()
    return {"lookup_type": lookup_type, "lookup_code": lookup_code}
