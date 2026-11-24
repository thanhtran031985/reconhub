from __future__ import annotations

from typing import Any
from urllib.parse import quote

from flask import Blueprint, redirect, request, url_for

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
    """Khởi tạo luồng đăng nhập SSO: Chuyển hướng sang máy chủ SSO kèm callback URL."""
    settings = get_settings()
    if not settings.SSO_ENABLED:
        return redirect("/login")

    # Xác định callback URL đầy đủ
    try:
        callback_url = url_for("auth.sso_callback", _external=True)
    except Exception:
        callback_url = f"{request.host_url.rstrip('/')}/auth/sso/callback"

    target_url = f"{settings.SSO_SERVER_URL.rstrip('/')}/login?redirect_uri={quote(callback_url)}"
    return redirect(target_url)


@auth_bp.route("/auth/sso/callback")
def sso_callback() -> Any:
    """Nhận mã xác thực từ máy chủ SSO, xác minh và cấp phiên đăng nhập ReconHub."""
    settings = get_settings()
    code = request.args.get("code")
    if not code:
        return redirect("/login?error=sso_missing_code")

    # 1. Gọi ngầm sang máy chủ SSO để đổi mã code lấy profile
    verify_res = verify_sso_code(
        sso_server_url=settings.SSO_SERVER_URL,
        code=code,
        client_secret=settings.SSO_CLIENT_SECRET,
    )
    if not verify_res.ok or not verify_res.data:
        msg = quote(verify_res.message or "Xác thực SSO thất bại")
        return redirect(f"/login?error={msg}")

    # 2. Đồng bộ người dùng vào RECON_USER (JIT Provisioning)
    engine = get_recon_engine()
    sync_res = sync_sso_user(engine, verify_res.data)
    if not sync_res.ok or not sync_res.data:
        msg = quote(sync_res.message or "Không thể kích hoạt tài khoản SSO")
        return redirect(f"/login?error={msg}")

    # 3. Kích hoạt phiên đăng nhập Flask
    login_session(sync_res.data)

    return redirect("/")
