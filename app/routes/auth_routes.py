from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from flask import Blueprint, redirect, request, session, url_for

from app.core.auth import _record_login_log
from app.core.config import get_settings
from app.core.session import login_session, logout_session
from app.db.engine import get_recon_engine
from app.services.sso_client import sync_sso_user, verify_sso_code

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout() -> Any:
    """Đăng xuất người dùng và chuyển về trang đăng nhập."""
    logout_session()
    return redirect("/login")


@auth_bp.route("/auth/sso/login")
def sso_login() -> Any:
    """Khởi tạo luồng đăng nhập SSO: Chuyển hướng sang máy chủ SSO kèm callback URL và CSRF state."""
    settings = get_settings()
    if not settings.SSO_ENABLED:
        return redirect("/login")

    # Xác định callback URL đầy đủ
    try:
        callback_url = url_for("auth.sso_callback", _external=True)
    except Exception:
        callback_url = f"{request.host_url.rstrip('/')}/auth/sso/callback"

    # Sinh CSRF state token ngẫu nhiên lưu vào session
    state = secrets.token_urlsafe(32)
    session["sso_state"] = state

    target_url = (
        f"{settings.SSO_SERVER_URL.rstrip('/')}/login"
        f"?redirect_uri={quote(callback_url)}"
        f"&state={quote(state)}"
    )
    return redirect(target_url)


@auth_bp.route("/auth/sso/callback")
def sso_callback() -> Any:
    """Nhận mã xác thực từ máy chủ SSO, xác minh CSRF state và cấp phiên đăng nhập ReconHub."""
    settings = get_settings()
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ip = request.remote_addr

    # 1. Xác thực tham số CSRF state
    expected_state = session.pop("sso_state", None)
    returned_state = request.args.get("state")
    if not expected_state or not returned_state or not hmac.compare_digest(expected_state, returned_state):
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_CSRF_STATE_MISMATCH", ip, now)
        msg = quote("Lỗi xác thực phiên SSO (CSRF detected). Vui lòng thử lại.")
        return redirect(f"/login?error={msg}")

    code = request.args.get("code")
    if not code:
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_MISSING_CODE", ip, now)
        return redirect("/login?error=sso_missing_code")

    # 2. Gọi ngầm sang máy chủ SSO để đổi mã code lấy profile
    verify_res = verify_sso_code(
        sso_server_url=settings.SSO_SERVER_URL,
        code=code,
        client_secret=settings.SSO_CLIENT_SECRET,
    )
    if not verify_res.ok or not verify_res.data:
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_VERIFY_FAILED", ip, now)
        msg = quote(verify_res.message or "Xác thực SSO thất bại")
        return redirect(f"/login?error={msg}")

    # 3. Đồng bộ người dùng vào RECON_USER (JIT Provisioning)
    sync_res = sync_sso_user(engine, verify_res.data)
    if not sync_res.ok or not sync_res.data:
        uname = str(verify_res.data.get("username", "sso_user"))
        with engine.begin() as conn:
            _record_login_log(conn, uname, None, False, "SSO_SYNC_FAILED", ip, now)
        msg = quote(sync_res.message or "Không thể kích hoạt tài khoản SSO")
        return redirect(f"/login?error={msg}")

    # 4. Ghi nhận đăng nhập thành công vào RECON_LOGIN_LOG
    with engine.begin() as conn:
        _record_login_log(
            conn=conn,
            username=sync_res.data.username,
            user_id=sync_res.data.user_id,
            success=True,
            reason="SSO_LOGIN_SUCCESS",
            ip=ip,
            now=now,
        )

    # 5. Kích hoạt phiên đăng nhập Flask
    login_session(sync_res.data)

    return redirect("/")
