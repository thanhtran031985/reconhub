from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, desc, func, select, update

from app.core.audit import write_audit_log
from app.core.auth import hash_password, verify_password
from app.core.context import Ctx, require_role
from app.core.session import invalidate_user_session_cache
from app.db.engine import get_recon_engine
from app.db.metadata import recon_login_log, recon_role, recon_user, recon_user_role
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.user import UserCreateDTO, UserResponse, UserUpdateDTO
from app.services import service
from app.services.perm import require_admin, requires_menu


def _count_active_admins(conn: Connection) -> int:
    """Đếm số lượng quản trị viên ADMIN đang kích hoạt trong hệ thống."""
    stmt = (
        select(recon_user.c.ID)
        .join(recon_user_role, recon_user.c.ID == recon_user_role.c.USER_ID)
        .join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID)
        .where(recon_role.c.CODE == "ADMIN")
        .where(recon_user.c.IS_ACTIVE == "Y")
    )
    return len(conn.execute(stmt).scalars().all())


def _get_user_roles(conn: Connection, user_id: int) -> list[str]:
    """Lấy danh sách mã vai trò của một người dùng."""
    return list(
        conn.execute(
            select(recon_role.c.CODE)
            .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
            .where(recon_user_role.c.USER_ID == user_id)
        )
        .scalars()
        .all()
    )


def _role_ids_by_code(conn: Connection, codes: list[str]) -> dict[str, int]:
    """Tra ID vai trò theo mã; mã không tồn tại thì báo lỗi rõ."""
    rows = conn.execute(select(recon_role.c.ID, recon_role.c.CODE).where(recon_role.c.CODE.in_(codes))).all()
    found = {str(code): int(role_id) for role_id, code in rows}
    missing = [code for code in codes if code not in found]
    if missing:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Vai trò không tồn tại: {', '.join(missing)}",
        )
    return found


def _assign_roles(
    conn: Connection,
    user_id: int,
    role_codes: list[str],
    assigned_by: str,
    now: datetime,
) -> None:
    """Gán lại toàn bộ vai trò cho user (xóa cũ, thêm mới theo ROLE_ID)."""
    conn.execute(recon_user_role.delete().where(recon_user_role.c.USER_ID == user_id))
    role_ids = _role_ids_by_code(conn, role_codes)
    for code in role_codes:
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=user_id,
                ROLE_ID=role_ids[code],
                ASSIGNED_BY=assigned_by,
                ASSIGNED_AT=now,
                CREATED_AT=now,
            )
        )


def _build_user_response(user_row: Any, roles: list[str]) -> UserResponse:
    """Tạo đối tượng UserResponse từ dữ liệu dòng DB."""
    return UserResponse(
        id=int(user_row["ID"]),
        username=str(user_row["USERNAME"]),
        full_name=str(user_row["FULL_NAME"]),
        email=user_row["EMAIL"],
        is_active=(user_row["IS_ACTIVE"] == "Y"),
        must_change_pw=(user_row["MUST_CHANGE_PW"] == "Y"),
        roles=roles,
        failed_count=int(user_row["FAILED_COUNT"] or 0),
        locked_until=user_row["LOCKED_UNTIL"],
        last_login_at=user_row["LAST_LOGIN_AT"],
        pw_changed_at=user_row["PW_CHANGED_AT"],
        created_at=user_row["CREATED_AT"],
        created_by=str(user_row["CREATED_BY"]),
    )


@service
@requires_menu("user")
def list_users(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    active: bool | None = None,
) -> list[UserResponse]:
    """Danh sách người dùng cho Admin, hỗ trợ tìm kiếm và lọc."""
    engine = get_recon_engine()
    require_admin(ctx, engine)

    with engine.connect() as conn:
        stmt = select(recon_user).order_by(recon_user.c.USERNAME)

        if active is not None:
            stmt = stmt.where(recon_user.c.IS_ACTIVE == ("Y" if active else "N"))

        if q:
            term = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(recon_user.c.USERNAME).like(term))
                | (func.lower(recon_user.c.FULL_NAME).like(term))
                | (func.lower(recon_user.c.EMAIL).like(term))
            )

        rows = conn.execute(stmt).mappings().all()

        results: list[UserResponse] = []
        for row in rows:
            u_id = int(row["ID"])
            roles = _get_user_roles(conn, u_id)
            if role and role.upper() not in [r.upper() for r in roles]:
                continue
            results.append(_build_user_response(row, roles))

        return results


@service
@requires_menu("user")
def create_user(ctx: Ctx, dto: UserCreateDTO) -> UserResponse:
    """Tạo người dùng mới (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    norm_username = dto.username.strip().lower()

    with engine.begin() as conn:
        existing = conn.execute(
            select(recon_user.c.ID).where(recon_user.c.USERNAME == norm_username)
        ).scalar_one_or_none()

        if existing is not None:
            raise ServiceError(
                ErrorCode.USERNAME_EXISTS,
                f"Tên đăng nhập '{dto.username}' đã tồn tại trong hệ thống",
            )

        pw_hash = hash_password(dto.password)

        ins_res = conn.execute(
            recon_user.insert().values(
                USERNAME=norm_username,
                FULL_NAME=dto.full_name.strip(),
                EMAIL=dto.email.strip() if dto.email else None,
                PASSWORD_HASH=pw_hash,
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="Y" if dto.must_change_pw else "N",
                FAILED_COUNT=0,
                SESSION_VERSION=1,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        if ins_res.inserted_primary_key is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không lấy được ID người dùng vừa tạo")
        user_id = int(ins_res.inserted_primary_key[0])

        assigned_roles = [r.upper() for r in dto.roles] if dto.roles else ["VIEWER"]
        _assign_roles(conn, user_id, assigned_roles, ctx.username, now)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="CREATE_USER",
            actor=ctx.username,
            new_data={
                "username": norm_username,
                "full_name": dto.full_name,
                "email": dto.email,
                "roles": assigned_roles,
                "must_change_pw": dto.must_change_pw,
                "password_hash": "***",
            },
            now=now,
        )

        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().one()
        return _build_user_response(user_row, assigned_roles)


@service
@requires_menu("user")
def update_user(ctx: Ctx, user_id: int, dto: UserUpdateDTO) -> UserResponse:
    """Cập nhật thông tin và vai trò của người dùng (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().first()

        if user_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy người dùng")

        current_roles = _get_user_roles(conn, user_id)

        # Bảo vệ LAST_ADMIN: Nếu bỏ vai trò Admin của admin duy nhất
        if dto.roles is not None:
            new_roles_norm = [r.upper() for r in dto.roles]
            if "ADMIN" in current_roles and "ADMIN" not in new_roles_norm:
                if user_row["IS_ACTIVE"] == "Y" and _count_active_admins(conn) <= 1:
                    raise ServiceError(
                        ErrorCode.LAST_ADMIN,
                        "Không thể xóa vai trò Admin của quản trị viên cuối cùng đang hoạt động",
                    )

        update_values: dict[str, Any] = {"UPDATED_AT": now}
        if dto.full_name is not None:
            update_values["FULL_NAME"] = dto.full_name.strip()
        if dto.email is not None:
            update_values["EMAIL"] = dto.email.strip() if dto.email else None

        roles_changed = False
        if dto.roles is not None:
            new_roles = [r.upper() for r in dto.roles]
            if set(new_roles) != set(current_roles):
                roles_changed = True
                _assign_roles(conn, user_id, new_roles, ctx.username, now)
                update_values["SESSION_VERSION"] = int(user_row["SESSION_VERSION"] or 1) + 1

        conn.execute(update(recon_user).where(recon_user.c.ID == user_id).values(**update_values))

        if roles_changed:
            invalidate_user_session_cache(user_id)

        final_roles = _get_user_roles(conn, user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="UPDATE_USER",
            actor=ctx.username,
            old_data={
                "full_name": user_row["FULL_NAME"],
                "email": user_row["EMAIL"],
                "roles": current_roles,
            },
            new_data={
                "full_name": update_values.get("FULL_NAME", user_row["FULL_NAME"]),
                "email": update_values.get("EMAIL", user_row["EMAIL"]),
                "roles": final_roles,
            },
            now=now,
        )

        updated_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().one()
        return _build_user_response(updated_row, final_roles)


@service
@requires_menu("user")
def set_active(ctx: Ctx, user_id: int, is_active: bool) -> UserResponse:
    """Kích hoạt hoặc vô hiệu hóa tài khoản (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().first()

        if user_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy người dùng")

        roles = _get_user_roles(conn, user_id)

        # Bảo vệ LAST_ADMIN: không được vô hiệu hóa admin duy nhất
        if not is_active and "ADMIN" in roles and user_row["IS_ACTIVE"] == "Y":
            if _count_active_admins(conn) <= 1:
                raise ServiceError(
                    ErrorCode.LAST_ADMIN,
                    "Không thể vô hiệu hóa quản trị viên cuối cùng đang hoạt động",
                )

        new_status = "Y" if is_active else "N"
        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == user_id)
            .values(
                IS_ACTIVE=new_status,
                SESSION_VERSION=int(user_row["SESSION_VERSION"] or 1) + 1,
                UPDATED_AT=now,
            )
        )

        invalidate_user_session_cache(user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="ACTIVATE_USER" if is_active else "DEACTIVATE_USER",
            actor=ctx.username,
            old_data={"is_active": user_row["IS_ACTIVE"]},
            new_data={"is_active": new_status},
            now=now,
        )

        updated_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().one()
        return _build_user_response(updated_row, roles)


@service
@requires_menu("user")
def unlock_user(ctx: Ctx, user_id: int) -> UserResponse:
    """Mở khóa thủ công cho tài khoản bị khóa tạm (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().first()

        if user_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy người dùng")

        roles = _get_user_roles(conn, user_id)

        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == user_id)
            .values(
                FAILED_COUNT=0,
                LOCKED_UNTIL=None,
                UPDATED_AT=now,
            )
        )

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="UNLOCK_USER",
            actor=ctx.username,
            old_data={
                "failed_count": user_row["FAILED_COUNT"],
                "locked_until": (user_row["LOCKED_UNTIL"].isoformat() if user_row["LOCKED_UNTIL"] else None),
            },
            new_data={"failed_count": 0, "locked_until": None},
            now=now,
        )

        updated_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().one()
        return _build_user_response(updated_row, roles)


@service
@requires_menu("user")
def reset_password(ctx: Ctx, user_id: int, new_pw: str) -> bool:
    """Admin đặt lại mật khẩu cho người dùng và bật cờ MUST_CHANGE_PW."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    new_hash = hash_password(new_pw)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == user_id)).mappings().first()

        if user_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy người dùng")

        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == user_id)
            .values(
                PASSWORD_HASH=new_hash,
                MUST_CHANGE_PW="Y",
                PW_CHANGED_AT=now,
                SESSION_VERSION=int(user_row["SESSION_VERSION"] or 1) + 1,
                UPDATED_AT=now,
            )
        )

        invalidate_user_session_cache(user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="RESET_PASSWORD",
            actor=ctx.username,
            new_data={"password_hash": "***", "must_change_pw": "Y"},
            now=now,
        )

        return True


@service
def change_password(ctx: Ctx, old_pw: str, new_pw: str) -> bool:
    """Người dùng tự đổi mật khẩu cá nhân."""
    require_role(ctx)  # Yêu cầu đã đăng nhập
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        user_row = conn.execute(select(recon_user).where(recon_user.c.ID == ctx.user_id)).mappings().first()

        if user_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy người dùng")

        if not verify_password(user_row["PASSWORD_HASH"], old_pw):
            raise ServiceError(ErrorCode.LOGIN_FAILED, "Mật khẩu hiện tại không đúng")

        new_hash = hash_password(new_pw)

        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == ctx.user_id)
            .values(
                PASSWORD_HASH=new_hash,
                MUST_CHANGE_PW="N",
                PW_CHANGED_AT=now,
                SESSION_VERSION=int(user_row["SESSION_VERSION"] or 1) + 1,
                UPDATED_AT=now,
            )
        )

        invalidate_user_session_cache(ctx.user_id)

        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=ctx.user_id,
            action="CHANGE_PASSWORD",
            actor=ctx.username,
            new_data={"password_hash": "***", "must_change_pw": "N"},
            now=now,
        )

        return True


@service
@requires_menu("user")
def get_login_log(
    ctx: Ctx,
    user_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lấy danh sách nhật ký đăng nhập (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)

    with engine.connect() as conn:
        stmt = select(recon_login_log).order_by(desc(recon_login_log.c.CREATED_AT)).limit(limit)
        if user_id is not None:
            stmt = stmt.where(recon_login_log.c.USER_ID == user_id)

        rows = conn.execute(stmt).mappings().all()
        return [dict(r) for r in rows]
