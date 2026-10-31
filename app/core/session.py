from __future__ import annotations

import time

from flask import session
from sqlalchemy import Engine, select

from app.core.auth import LoginData
from app.core.context import Ctx
from app.db.metadata import recon_user

# Cache in-memory: user_id -> (cached_at_timestamp, session_version, is_active, must_change_pw)
_SESSION_CACHE: dict[int, tuple[float, int, str, str]] = {}
CACHE_TTL_SECONDS = 60.0


def invalidate_user_session_cache(user_id: int | None = None) -> None:
    """Xóa bộ đệm phiên người dùng (cho 1 user hoặc toàn bộ)."""
    if user_id is not None:
        _SESSION_CACHE.pop(user_id, None)
    else:
        _SESSION_CACHE.clear()


def get_user_session_state(engine: Engine, user_id: int) -> tuple[int, str, str] | None:
    """Lấy trạng thái phiên hiện tại trong DB với bộ đệm 60s.

    Trả về (session_version, is_active, must_change_pw) hoặc None nếu không tồn tại.
    """
    now = time.monotonic()
    cached = _SESSION_CACHE.get(user_id)
    if cached is not None:
        cached_at, session_ver, is_active, must_change = cached
        if now - cached_at < CACHE_TTL_SECONDS:
            return session_ver, is_active, must_change

    with engine.connect() as conn:
        row = (
            conn.execute(
                select(
                    recon_user.c.SESSION_VERSION,
                    recon_user.c.IS_ACTIVE,
                    recon_user.c.MUST_CHANGE_PW,
                ).where(recon_user.c.ID == user_id)
            )
            .mappings()
            .first()
        )

        if row is None:
            _SESSION_CACHE.pop(user_id, None)
            return None

        state = (
            int(row["SESSION_VERSION"] or 1),
            str(row["IS_ACTIVE"]),
            str(row["MUST_CHANGE_PW"]),
        )
        _SESSION_CACHE[user_id] = (now, *state)
        return state


def get_current_ctx() -> Ctx | None:
    """Lấy Ctx của người dùng đang đăng nhập từ Flask session."""
    try:
        if "user_id" in session:
            return Ctx(
                user_id=int(session["user_id"]),
                username=str(session["username"]),
                full_name=str(session.get("full_name", "")),
                roles=list(session.get("roles", [])),
            )
    except Exception:
        pass
    return None


def login_session(data: LoginData) -> None:
    """Lưu thông tin xác thực vào Flask session."""
    session.permanent = True
    session["user_id"] = data.user_id
    session["username"] = data.username
    session["full_name"] = data.full_name
    session["roles"] = data.roles
    session["session_version"] = data.session_version
    session["must_change_pw"] = data.must_change_pw


def logout_session() -> None:
    """Xóa toàn bộ dữ liệu phiên người dùng."""
    user_id = session.get("user_id")
    if user_id is not None:
        invalidate_user_session_cache(int(user_id))
    session.clear()
