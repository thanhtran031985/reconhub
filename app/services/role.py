"""Service vai trò — task 19, spec 11 mục 6.

Vai trò hệ thống (IS_SYSTEM='Y', mã ADMIN) không được đổi tên/mã,
không được đổi menu, không được xóa. Đổi menu của vai trò thì tăng
PERM_REVISION để quyền có hiệu lực trong tối đa 5 giây.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, func, select
from sqlalchemy.exc import IntegrityError

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_menu, recon_role, recon_role_menu, recon_user, recon_user_role
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import bump_perm_revision, effective_menus, require_admin, requires_menu

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,29}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _role_row(conn: Connection, role_id: int) -> Any:
    row = conn.execute(select(recon_role).where(recon_role.c.ID == role_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy vai trò với ID {role_id}.")
    return row


def _menus_of_role(conn: Connection, role_id: int) -> list[str]:
    rows = (
        conn.execute(
            select(recon_role_menu.c.MENU_CODE)
            .where(recon_role_menu.c.ROLE_ID == role_id)
            .order_by(recon_role_menu.c.MENU_CODE)
        )
        .scalars()
        .all()
    )
    return [str(code) for code in rows]


def _validate_menus(conn: Connection, menus: list[str]) -> list[str]:
    """Chuẩn hóa và kiểm tra menu được gán cho vai trò."""
    codes = sorted({str(m) for m in menus})
    if not codes:
        return []
    rows = conn.execute(select(recon_menu.c.CODE, recon_menu.c.IS_REMOVED).where(recon_menu.c.CODE.in_(codes))).all()
    found = {str(code): removed for code, removed in rows}
    unknown = [c for c in codes if c not in found]
    if unknown:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Menu không tồn tại: {', '.join(unknown)}",
        )
    removed = [c for c in codes if found.get(c) == "Y"]
    if removed:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Menu đã bị gỡ khỏi hệ thống, không thể gán: {', '.join(removed)}",
        )
    return codes


def _check_code(code: str) -> str:
    norm = str(code).strip().upper()
    if not _CODE_RE.match(norm):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Mã vai trò chỉ gồm chữ hoa, số và dấu gạch dưới, bắt đầu bằng chữ cái (tối đa 30 ký tự).",
        )
    return norm


def _role_dict(row: Any, menus: list[str], user_count: int) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "description": row["DESCRIPTION"],
        "is_system": row["IS_SYSTEM"] == "Y",
        "is_active": row["IS_ACTIVE"] == "Y",
        "menus": menus,
        "user_count": user_count,
        "row_version": int(row["ROW_VERSION"] or 1),
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"].isoformat() if row["CREATED_AT"] else None,
        "updated_at": row["UPDATED_AT"].isoformat() if row["UPDATED_AT"] else None,
    }


def _user_count(conn: Connection, role_id: int) -> int:
    return (
        conn.execute(
            select(func.count()).select_from(recon_user_role).where(recon_user_role.c.ROLE_ID == role_id)
        ).scalar()
        or 0
    )


def _set_menus(conn: Connection, role_id: int, menus: list[str], actor: str, now: datetime) -> None:
    conn.execute(recon_role_menu.delete().where(recon_role_menu.c.ROLE_ID == role_id))
    for code in menus:
        conn.execute(
            recon_role_menu.insert().values(
                ROLE_ID=role_id,
                MENU_CODE=code,
                GRANTED_BY=actor,
                GRANTED_AT=now,
            )
        )


@service
@requires_menu("role")
def list_roles(ctx: Ctx, include_inactive: bool = False) -> list[dict[str, Any]]:
    """Danh sách vai trò kèm menu và số người dùng đang mang vai trò đó."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        stmt = select(recon_role).order_by(recon_role.c.CODE)
        if not include_inactive:
            stmt = stmt.where(recon_role.c.IS_ACTIVE == "Y")
        rows = conn.execute(stmt).mappings().all()
        return [
            _role_dict(row, _menus_of_role(conn, int(row["ID"])), _user_count(conn, int(row["ID"]))) for row in rows
        ]


@service
@requires_menu("role")
def get_role(ctx: Ctx, role_id: int) -> dict[str, Any]:
    """Chi tiết một vai trò."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        row = _role_row(conn, role_id)
        return _role_dict(row, _menus_of_role(conn, role_id), _user_count(conn, role_id))


@service
@requires_menu("role")
def create_role(
    ctx: Ctx,
    code: str,
    name: str,
    description: str | None = None,
    menus: list[str] | None = None,
) -> dict[str, Any]:
    """Tạo vai trò mới (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    norm_code = _check_code(code)
    name = str(name).strip()
    if not name:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tên vai trò không được để trống.")
    now = _now()
    with engine.begin() as conn:
        menu_codes = _validate_menus(conn, list(menus or []))
        dup_code = conn.execute(select(recon_role.c.ID).where(recon_role.c.CODE == norm_code)).scalar_one_or_none()
        if dup_code is not None:
            raise ServiceError(ErrorCode.ROLE_CODE_EXISTS, f"Mã vai trò '{norm_code}' đã tồn tại.")
        dup_name = conn.execute(select(recon_role.c.ID).where(recon_role.c.NAME == name)).scalar_one_or_none()
        if dup_name is not None:
            raise ServiceError(ErrorCode.ROLE_NAME_EXISTS, f"Tên vai trò '{name}' đã tồn tại.")
        try:
            res = conn.execute(
                recon_role.insert().values(
                    CODE=norm_code,
                    NAME=name,
                    DESCRIPTION=description,
                    IS_SYSTEM="N",
                    IS_ACTIVE="Y",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
        except IntegrityError:
            raise ServiceError(ErrorCode.ROLE_CODE_EXISTS, f"Mã vai trò '{norm_code}' đã tồn tại.") from None
        pk = res.inserted_primary_key
        if pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không tạo được vai trò.")
        role_id = int(pk[0])
        _set_menus(conn, role_id, menu_codes, ctx.username, now)
        bump_perm_revision(conn, ctx.username)
        write_audit_log(
            conn=conn,
            entity="ROLE",
            entity_id=role_id,
            action="CREATE_ROLE",
            actor=ctx.username,
            new_data={"code": norm_code, "name": name, "menus": menu_codes},
            now=now,
        )
        row = _role_row(conn, role_id)
        return _role_dict(row, menu_codes, 0)


@service
@requires_menu("role")
def update_role(
    ctx: Ctx,
    role_id: int,
    name: str | None = None,
    description: str | None = None,
    menus: list[str] | None = None,
    row_version: int | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """Cập nhật vai trò (khóa lạc quan ROW_VERSION).

    Vai trò hệ thống không được đổi tên, không được đổi menu, không được tắt.
    """
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = _now()
    with engine.begin() as conn:
        row = _role_row(conn, role_id)
        current_version = int(row["ROW_VERSION"] or 1)
        if row_version is not None and int(row_version) != current_version:
            raise ServiceError(
                ErrorCode.STALE_DATA,
                "Vai trò đã bị thay đổi bởi người khác, vui lòng tải lại rồi sửa tiếp.",
            )
        is_system = row["IS_SYSTEM"] == "Y"
        old_menus = _menus_of_role(conn, role_id)
        if is_system and (
            name is not None and str(name).strip() != str(row["NAME"]) or menus is not None or is_active is False
        ):
            raise ServiceError(
                ErrorCode.ROLE_SYSTEM_LOCKED,
                "Vai trò hệ thống không được đổi tên, đổi menu hay tắt.",
            )
        new_name = str(name).strip() if name is not None else str(row["NAME"])
        if not new_name:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tên vai trò không được để trống.")
        if new_name != str(row["NAME"]):
            dup = conn.execute(
                select(recon_role.c.ID).where(recon_role.c.NAME == new_name).where(recon_role.c.ID != role_id)
            ).scalar_one_or_none()
            if dup is not None:
                raise ServiceError(ErrorCode.ROLE_NAME_EXISTS, f"Tên vai trò '{new_name}' đã tồn tại.")
        new_menus = _validate_menus(conn, list(menus)) if menus is not None else old_menus
        new_active = row["IS_ACTIVE"] == "Y" if is_active is None else bool(is_active)
        conn.execute(
            recon_role.update()
            .where(recon_role.c.ID == role_id)
            .values(
                NAME=new_name,
                DESCRIPTION=description if description is not None else row["DESCRIPTION"],
                IS_ACTIVE="Y" if new_active else "N",
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=current_version + 1,
            )
        )
        menus_changed = sorted(new_menus) != sorted(old_menus)
        if menus_changed or (is_active is not None and new_active != (row["IS_ACTIVE"] == "Y")):
            _set_menus(conn, role_id, new_menus, ctx.username, now)
            bump_perm_revision(conn, ctx.username)
        write_audit_log(
            conn=conn,
            entity="ROLE",
            entity_id=role_id,
            action="UPDATE_ROLE",
            actor=ctx.username,
            old_data={"code": str(row["CODE"]), "name": str(row["NAME"]), "menus": old_menus},
            new_data={"code": str(row["CODE"]), "name": new_name, "menus": new_menus},
            now=now,
        )
        new_row = _role_row(conn, role_id)
        return _role_dict(new_row, new_menus, _user_count(conn, role_id))


@service
@requires_menu("role")
def clone_role(ctx: Ctx, role_id: int, new_code: str, new_name: str) -> dict[str, Any]:
    """Nhân bản một vai trò cùng toàn bộ menu của nó."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        row = _role_row(conn, role_id)
        menus = _menus_of_role(conn, role_id)
        description = row["DESCRIPTION"]
    res = create_role(ctx, code=new_code, name=new_name, description=description, menus=menus)
    if not res.ok:
        raise ServiceError(res.code or ErrorCode.INTERNAL_ERROR, res.message or "Lỗi hệ thống nội bộ")
    return res.data if res.data is not None else {}


@service
@requires_menu("role")
def delete_role(ctx: Ctx, role_id: int) -> dict[str, Any]:
    """Xóa vai trò (không xóa vai trò hệ thống, không xóa vai trò đang có người dùng)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = _now()
    with engine.begin() as conn:
        row = _role_row(conn, role_id)
        if row["IS_SYSTEM"] == "Y":
            raise ServiceError(ErrorCode.ROLE_SYSTEM_LOCKED, "Không được xóa vai trò hệ thống.")
        count = _user_count(conn, role_id)
        if count > 0:
            raise ServiceError(
                ErrorCode.ROLE_IN_USE,
                f"Vai trò đang gán cho {count} người dùng, gỡ vai trò khỏi họ trước khi xóa.",
            )
        menus = _menus_of_role(conn, role_id)
        conn.execute(recon_role_menu.delete().where(recon_role_menu.c.ROLE_ID == role_id))
        conn.execute(recon_role.delete().where(recon_role.c.ID == role_id))
        bump_perm_revision(conn, ctx.username)
        write_audit_log(
            conn=conn,
            entity="ROLE",
            entity_id=role_id,
            action="DELETE_ROLE",
            actor=ctx.username,
            old_data={"code": str(row["CODE"]), "name": str(row["NAME"]), "menus": menus},
            now=now,
        )
    return {"id": role_id, "code": str(row["CODE"]), "deleted": True}


@service
@requires_menu("role")
def users_of(ctx: Ctx, role_id: int) -> list[dict[str, Any]]:
    """Danh sách người dùng đang mang vai trò."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        _role_row(conn, role_id)
        rows = (
            conn.execute(
                select(recon_user.c.ID, recon_user.c.USERNAME, recon_user.c.FULL_NAME, recon_user.c.IS_ACTIVE)
                .select_from(recon_user.join(recon_user_role, recon_user.c.ID == recon_user_role.c.USER_ID))
                .where(recon_user_role.c.ROLE_ID == role_id)
                .order_by(recon_user.c.USERNAME)
            )
            .mappings()
            .all()
        )
    return [
        {
            "id": int(r["ID"]),
            "username": str(r["USERNAME"]),
            "full_name": str(r["FULL_NAME"]),
            "is_active": r["IS_ACTIVE"] == "Y",
        }
        for r in rows
    ]


@service
@requires_menu("role")
def effective_of_user(ctx: Ctx, user_id: int) -> dict[str, Any]:
    """Quyền thực tế của một người dùng: vai trò + menu hiệu lực."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        user = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().first()
        if user is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy người dùng với ID {user_id}.")
        roles = (
            conn.execute(
                select(recon_role.c.CODE)
                .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
                .where(recon_user_role.c.USER_ID == user_id)
                .where(recon_role.c.IS_ACTIVE == "Y")
            )
            .scalars()
            .all()
        )
    user_ctx = Ctx(
        user_id=int(user["ID"]),
        username=str(user["USERNAME"]),
        full_name=str(user["FULL_NAME"]),
        roles=[str(r) for r in roles],
    )
    menus = sorted(effective_menus(user_ctx, engine))
    return {
        "user_id": int(user["ID"]),
        "username": str(user["USERNAME"]),
        "full_name": str(user["FULL_NAME"]),
        "is_active": user["IS_ACTIVE"] == "Y",
        "roles": [str(r) for r in roles],
        "menus": menus,
        "is_admin": "ADMIN" in [str(r) for r in roles],
    }
