"""Tính quyền hiệu lực theo menu và kiểm tra quyền (task 19, spec 11).

Quyền được tính từ DB, không từ `ctx.roles` trong phiên (phiên có thể
cũ tới lúc đăng nhập):
- User có vai trò ADMIN đang kích hoạt → mọi menu chưa bị gỡ, kể cả menu
  đang ẩn.
- Vai trò thường → hợp các menu của các vai trò đang kích hoạt của user,
  trừ menu bị gỡ và menu đang ẩn.
- User không có trong DB (ctx nội bộ của CLI/worker: `cli_admin`,
  `system`) → tính menu từ `ctx.roles` theo đúng bảng seed 11a mục 7,
  vì ctx chỉ được tạo ở server, không từ input người dùng.
- User bị vô hiệu → không có menu nào.
- DB chưa có bảng menu (trước migration) → cho qua mọi menu để app cũ
  vẫn chạy được; sau migration bảng luôn tồn tại.

Cache: revision đọc tối đa 1 lần/giây; menu hiệu lực cache theo
`(user_id, PERM_REVISION)` tối đa 5 giây, nên đổi vai trò/menu có hiệu
lực chậm nhất 5 giây (spec 11 mục 4).
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, ParamSpec, TypeVar, cast

from sqlalchemy import Connection, Engine, Table, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_menu,
    recon_role,
    recon_role_menu,
    recon_user,
    recon_user_role,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.ui.menus import MENU_BY_CODE, ROLE_MENUS_SEED

P = ParamSpec("P")
R = TypeVar("R")

_REVISION_CACHE: dict[str, Any] = {"value": 0, "at": 0.0}
_REVISION_TTL_S = 1.0
_MENUS_CACHE: dict[tuple[int, int], tuple[set[str], float]] = {}
_MENUS_TTL_S = 5.0


def clear_perm_cache() -> None:
    """Xóa cache quyền (dùng trong test)."""
    _REVISION_CACHE["value"] = 0
    _REVISION_CACHE["at"] = 0.0
    _MENUS_CACHE.clear()


def _tables_exist(engine: Engine) -> bool:
    try:
        names = inspect(engine).get_table_names()
    except SQLAlchemyError:
        return False
    return "RECON_MENU" in names and "RECON_ROLE" in names and "RECON_USER_ROLE" in names


def get_perm_revision(engine: Engine | None = None) -> int:
    """Đọc PERM_REVISION, tối đa 1 lần/giây."""
    now = time.monotonic()
    if now - float(_REVISION_CACHE["at"]) < _REVISION_TTL_S:
        return int(_REVISION_CACHE["value"])
    engine = engine or get_recon_engine()
    value = 0
    if _tables_exist(engine):
        try:
            with engine.connect() as conn:
                raw = conn.execute(
                    select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "PERM_REVISION")
                ).scalar_one_or_none()
                value = int(raw) if raw is not None else 0
        except (SQLAlchemyError, ValueError):
            value = 0
    _REVISION_CACHE["value"] = value
    _REVISION_CACHE["at"] = now
    return value


def _legacy_menus_for_roles(roles: list[str]) -> set[str]:
    """Menu theo bảng seed, dùng khi ctx không phải user trong DB."""
    menus: set[str] = set()
    for role in roles:
        code = str(role).upper()
        if code == "ADMIN":
            return set(MENU_BY_CODE)
        menus.update(ROLE_MENUS_SEED.get(code, []))
    return menus


def effective_menus(ctx: Ctx | None, engine: Engine | None = None) -> set[str]:
    """Tập menu user được dùng (đã trừ menu ẩn/gỡ, trừ ADMIN)."""
    if ctx is None:
        return set()
    engine = engine or get_recon_engine()
    if not _tables_exist(engine):
        return set(MENU_BY_CODE)
    revision = get_perm_revision(engine)
    key = (int(ctx.user_id), revision)
    cached = _MENUS_CACHE.get(key)
    if cached is not None and time.monotonic() - cached[1] < _MENUS_TTL_S:
        return set(cached[0])

    menus: set[str] = set()
    with engine.connect() as conn:
        user = (
            conn.execute(select(recon_user.c.IS_ACTIVE).where(recon_user.c.ID == int(ctx.user_id))).mappings().first()
        )
        if user is None:
            menus = _legacy_menus_for_roles(list(ctx.roles))
            _MENUS_CACHE[key] = (set(menus), time.monotonic())
            return set(menus)
        if user["IS_ACTIVE"] != "Y":
            _MENUS_CACHE[key] = (set(), time.monotonic())
            return set()
        is_admin = (
            conn.execute(
                select(recon_role.c.ID)
                .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
                .where(recon_user_role.c.USER_ID == int(ctx.user_id))
                .where(recon_role.c.CODE == "ADMIN")
                .where(recon_role.c.IS_ACTIVE == "Y")
            ).first()
            is not None
        )
        if is_admin:
            rows = conn.execute(select(recon_menu.c.CODE).where(recon_menu.c.IS_REMOVED == "N")).scalars().all()
            menus = {str(code) for code in rows}
        else:
            rows = (
                conn.execute(
                    select(recon_menu.c.CODE)
                    .select_from(
                        recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID)
                        .join(recon_role_menu, recon_role_menu.c.ROLE_ID == recon_role.c.ID)
                        .join(recon_menu, recon_menu.c.CODE == recon_role_menu.c.MENU_CODE)
                    )
                    .where(recon_user_role.c.USER_ID == int(ctx.user_id))
                    .where(recon_role.c.IS_ACTIVE == "Y")
                    .where(recon_menu.c.IS_REMOVED == "N")
                    .where(recon_menu.c.IS_HIDDEN == "N")
                )
                .scalars()
                .all()
            )
            menus = {str(code) for code in rows}
    _MENUS_CACHE[key] = (set(menus), time.monotonic())
    return set(menus)


def bump_perm_revision(conn: Connection, actor: str = "system") -> int:
    """Tăng PERM_REVISION trong cùng transaction đang mở (ghi audit kèm).

    Gọi sau mỗi lần đổi vai trò/menu/gán vai trò để các process khác thấy
    quyền mới trong tối đa 5 giây. Trả về revision mới.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw = conn.execute(
        select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "PERM_REVISION")
    ).scalar_one_or_none()
    try:
        revision = int(raw) + 1 if raw is not None else 1
    except (TypeError, ValueError):
        revision = 1
    if raw is None:
        conn.execute(
            recon_app_setting.insert().values(
                KEY="PERM_REVISION", VALUE=str(revision), UPDATED_BY=actor, UPDATED_AT=now
            )
        )
    else:
        conn.execute(
            recon_app_setting.update()
            .where(recon_app_setting.c.KEY == "PERM_REVISION")
            .values(VALUE=str(revision), UPDATED_BY=actor, UPDATED_AT=now)
        )
    clear_perm_cache()
    return revision


def user_role_codes(ctx: Ctx | None, engine: Engine | None = None) -> set[str]:
    """Mã các vai trò đang kích hoạt của user, tra từ DB (không dùng phiên).

    User không có trong DB (ctx nội bộ CLI/worker) thì dùng `ctx.roles`
    vì ctx đó chỉ được tạo ở server.
    """
    if ctx is None:
        return set()
    engine = engine or get_recon_engine()
    if not _tables_exist(engine):
        return {str(r) for r in ctx.roles}
    with engine.connect() as conn:
        row = (
            conn.execute(select(recon_user.c.ID, recon_user.c.IS_ACTIVE).where(recon_user.c.ID == ctx.user_id))
            .mappings()
            .first()
        )
        if row is None:
            return {str(r) for r in ctx.roles}
        if row["IS_ACTIVE"] != "Y":
            return set()
        roles = (
            conn.execute(
                select(recon_role.c.CODE)
                .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
                .where(recon_user_role.c.USER_ID == ctx.user_id)
                .where(recon_role.c.IS_ACTIVE == "Y")
            )
            .scalars()
            .all()
        )
    return {str(r) for r in roles}


def has_role(ctx: Ctx | None, *codes: str, engine: Engine | None = None) -> bool:
    """User có ít nhất một trong các vai trò (tra DB)."""
    return bool(user_role_codes(ctx, engine) & {str(c) for c in codes})


def is_admin(ctx: Ctx | None, engine: Engine | None = None) -> bool:
    """User có vai trò ADMIN đang kích hoạt không."""
    if ctx is None:
        return False
    engine = engine or get_recon_engine()
    if not _tables_exist(engine):
        return ctx.has_role("ADMIN")
    with engine.connect() as conn:
        user = (
            conn.execute(select(recon_user.c.IS_ACTIVE).where(recon_user.c.ID == int(ctx.user_id))).mappings().first()
        )
        if user is None:
            return ctx.has_role("ADMIN")
        if user["IS_ACTIVE"] != "Y":
            return False
        return (
            conn.execute(
                select(recon_role.c.ID)
                .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
                .where(recon_user_role.c.USER_ID == int(ctx.user_id))
                .where(recon_role.c.CODE == "ADMIN")
                .where(recon_role.c.IS_ACTIVE == "Y")
            ).first()
            is not None
        )


def require_admin(ctx: Ctx | None, engine: Engine | None = None) -> None:
    """Chặn nếu không phải ADMIN (spec 11 D4: thao tác đặc biệt)."""
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    if not is_admin(ctx, engine=engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ quản trị viên mới thực hiện được hành động này")


def _menu_states(codes: list[str], engine: Engine) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    if not _tables_exist(engine):
        return states
    with engine.connect() as conn:
        rows = conn.execute(
            select(recon_menu.c.CODE, recon_menu.c.IS_REMOVED, recon_menu.c.IS_HIDDEN).where(
                recon_menu.c.CODE.in_(codes)
            )
        ).all()
    for code, removed, hidden in rows:
        states[str(code)] = {"removed": removed == "Y", "hidden": hidden == "Y"}
    return states


def _check_menus(ctx: Ctx, codes: list[str], any_of: bool, engine: Engine) -> None:
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    menus = effective_menus(ctx, engine=engine)
    granted = any(code in menus for code in codes) if any_of else all(code in menus for code in codes)
    if granted:
        return
    states = _menu_states(codes, engine)
    if any(states.get(code, {}).get("removed") for code in codes):
        raise ServiceError(ErrorCode.MENU_REMOVED, "Chức năng đã bị gỡ khỏi hệ thống")
    if any(states.get(code, {}).get("hidden") for code in codes):
        raise ServiceError(ErrorCode.MENU_HIDDEN, "Chức năng đang tạm ẩn")
    raise ServiceError(ErrorCode.FORBIDDEN, "Bạn không có quyền thực hiện hành động này")


def _engine_for(func: Callable[..., Any]) -> Engine:
    """Engine của module chứa hàm service.

    Mỗi module service import `get_recon_engine` vào namespace của nó và
    test monkeypatch đúng namespace đó, nên decorator phải lấy engine từ
    module của hàm, không dùng engine mặc định của module perm.
    """
    import sys

    mod = sys.modules.get(func.__module__)
    getter = getattr(mod, "get_recon_engine", None) if mod is not None else None
    if callable(getter):
        return cast(Engine, getter())
    return get_recon_engine()


def requires_menu(*codes: str, any_of: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator gắn và kiểm tra menu_code cho hàm service.

    Dùng dưới @service. Đặt `menu_codes`/`menu_any_of` lên hàm để test
    registry quét được.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx: Any = None
            if args:
                ctx = args[0]
            if ctx is None:
                ctx = kwargs.get("ctx")
            _check_menus(ctx, list(codes), any_of, _engine_for(func))
            return func(*args, **kwargs)

        wrapper.menu_codes = list(codes)  # type: ignore[attr-defined]
        wrapper.menu_any_of = any_of  # type: ignore[attr-defined]
        return wrapper

    return decorator


def owner_filter(ctx: Ctx | None, engine: Engine | None = None) -> dict[str, Any]:
    """Phạm vi dữ liệu: ADMIN thấy tất cả, còn lại chỉ thấy dữ liệu của mình.

    Trả về {"is_admin": bool, "username": str | None} để service tự thêm
    điều kiện CREATED_BY = username khi không phải ADMIN.
    """
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    admin = is_admin(ctx, engine=engine)
    return {"is_admin": admin, "username": None if admin else ctx.username}


def check_owned(
    conn: Connection,
    table: Table,
    id_column: str,
    record_id: int,
    ctx: Ctx,
    owner_column: str = "CREATED_BY",
    engine: Engine | None = None,
) -> Any:
    """Trả về dòng theo ID, hoặc lỗi NOT_FOUND nếu không tồn tại / không phải của mình.

    Dùng cho mọi đường truy cập run theo ID (chi tiết, rows, export...).
    ADMIN bỏ qua kiểm tra chủ sở hữu.
    """
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    row = conn.execute(select(table).where(table.c[id_column] == record_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy dữ liệu yêu cầu")
    if not is_admin(ctx, engine=engine):
        owner = row.get(owner_column)
        if owner is not None and str(owner) != ctx.username:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy dữ liệu yêu cầu")
    return row


def page_gate(ctx: Ctx | None, menu_code: str, engine: Engine | None = None) -> str | None:
    """Kiểm tra quyền vào một page. Trả về None nếu được vào, ngược lại
    trả về đường dẫn chuyển hướng: /login, /forbidden hoặc /suspended."""
    if ctx is None:
        return "/login"
    engine = engine or get_recon_engine()
    if menu_code in effective_menus(ctx, engine=engine):
        return None
    states = _menu_states([menu_code], engine)
    state = states.get(menu_code, {})
    if state.get("hidden"):
        return "/suspended"
    return "/forbidden"


def menu_state(code: str, engine: Engine | None = None) -> dict[str, Any] | None:
    """Trạng thái một menu (dùng cho trang /suspended và sidebar)."""
    engine = engine or get_recon_engine()
    if not _tables_exist(engine):
        return None
    with engine.connect() as conn:
        row = conn.execute(select(recon_menu).where(recon_menu.c.CODE == code)).mappings().first()
    return dict(row) if row else None
