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
from app.services.sso_client import (
    build_oidc_authorize_url,
    exchange_oidc_code,
    generate_pkce_pair,
    sync_sso_user,
    verify_sso_code,
)
from app.services.sso_provider import get_sso_provider_for_auth

auth_bp = Blueprint("auth", __name__)


def build_sso_callback_url(provider_code: str | None = None) -> str:
    """Xác định Callback URL chuẩn (ưu tiên PUBLIC_BASE_URL nếu chạy sau reverse proxy)."""
    settings = get_settings()
    base = settings.PUBLIC_BASE_URL.strip().rstrip("/")
    if base:
        if provider_code:
            return f"{base}/auth/sso/{provider_code}/callback"
        return f"{base}/auth/sso/callback"

    if provider_code:
        try:
            return url_for("auth.sso_provider_callback", provider_code=provider_code, _external=True)
        except Exception:
            return f"{request.host_url.rstrip('/')}/auth/sso/{provider_code}/callback"
    try:
        return url_for("auth.sso_callback", _external=True)
    except Exception:
        return f"{request.host_url.rstrip('/')}/auth/sso/callback"


def _initiate_sso_login(provider_code: str, legacy: bool = False) -> Any:
    settings = get_settings()
    if not settings.SSO_ENABLED:
        return redirect("/login")

    engine = get_recon_engine()
    provider = get_sso_provider_for_auth(engine, provider_code)
    if provider is None:
        msg = quote(f"Nhà cung cấp SSO '{provider_code}' không tồn tại hoặc đang bị tắt")
        return redirect(f"/login?error={msg}")

    callback_url = build_sso_callback_url(None if legacy else provider.code)
    state = secrets.token_urlsafe(32)
    session["sso_state"] = state
    session["sso_provider"] = provider.code
    session["sso_redirect_uri"] = callback_url

    if provider.provider_type == "INTERNAL":
        auth_url = provider.auth_url or f"{settings.SSO_SERVER_URL.rstrip('/')}/login"
        sep = "&" if "?" in auth_url else "?"
        target_url = f"{auth_url}{sep}redirect_uri={quote(callback_url)}&state={quote(state)}"
        return redirect(target_url)

    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce_pair()
    session["sso_nonce"] = nonce
    session["sso_code_verifier"] = code_verifier
    target_url = build_oidc_authorize_url(
        provider=provider,
        redirect_uri=callback_url,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    return redirect(target_url)


def _handle_sso_callback(route_provider_code: str | None = None) -> Any:
    settings = get_settings()
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ip = request.remote_addr

    # 1. Xác thực tham số CSRF state và dọn dữ liệu phiên tạm
    expected_state = session.pop("sso_state", None)
    expected_nonce = session.pop("sso_nonce", None)
    code_verifier = session.pop("sso_code_verifier", None)
    session_provider = session.pop("sso_provider", None)
    stored_redirect_uri = session.pop("sso_redirect_uri", None)

    returned_state = request.args.get("state")
    if not expected_state or not returned_state or not hmac.compare_digest(expected_state, returned_state):
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_CSRF_STATE_MISMATCH", ip, now)
        msg = quote("Lỗi xác thực phiên SSO (CSRF detected). Vui lòng thử lại.")
        return redirect(f"/login?error={msg}")

    idp_error = request.args.get("error")
    if idp_error:
        err_desc = request.args.get("error_description") or idp_error
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_IDP_ERROR", ip, now)
        return redirect(f"/login?error={quote(str(err_desc))}")

    code = request.args.get("code")
    if not code:
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_MISSING_CODE", ip, now)
        return redirect("/login?error=sso_missing_code")

    provider_code = (route_provider_code or session_provider or "internal").strip().lower()
    provider = get_sso_provider_for_auth(engine, provider_code)
    if provider is None:
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_PROVIDER_INACTIVE", ip, now)
        msg = quote(f"Nhà cung cấp SSO '{provider_code}' không khả dụng")
        return redirect(f"/login?error={msg}")

    # 2. Xác minh code qua INTERNAL hoặc OIDC back-channel
    if provider.provider_type == "INTERNAL":
        verify_res = verify_sso_code(
            sso_server_url=settings.SSO_SERVER_URL,
            code=code,
            client_secret=provider.client_secret or settings.SSO_CLIENT_SECRET,
            endpoint_url=provider.token_url,
        )
    else:
        callback_url = str(stored_redirect_uri or build_sso_callback_url(provider.code))
        verify_res = exchange_oidc_code(
            provider=provider,
            code=code,
            redirect_uri=callback_url,
            code_verifier=str(code_verifier or ""),
            expected_nonce=str(expected_nonce or ""),
        )

    if not verify_res.ok or not verify_res.data:
        with engine.begin() as conn:
            _record_login_log(conn, "sso_unknown", None, False, "SSO_VERIFY_FAILED", ip, now)
        msg = quote(verify_res.message or "Xác thực SSO thất bại")
        return redirect(f"/login?error={msg}")

    # 3. Đồng bộ người dùng vào RECON_USER (Email làm tài khoản + Tự động liên kết)
    sync_res = sync_sso_user(engine, verify_res.data, provider=provider)
    if not sync_res.ok or not sync_res.data:
        uname = str(verify_res.data.get("email") or verify_res.data.get("username") or "sso_user")[:60]
        with engine.begin() as conn:
            _record_login_log(conn, uname, None, False, "SSO_SYNC_FAILED", ip, now)
        msg = quote(sync_res.message or "Không thể kích hoạt tài khoản SSO")
        return redirect(f"/login?error={msg}")

    # 4. Ghi nhận đăng nhập thành công vào RECON_LOGIN_LOG
    with engine.begin() as conn:
        _record_login_log(
            conn=conn,
            username=sync_res.data.username[:60],
            user_id=sync_res.data.user_id,
            success=True,
            reason="SSO_LOGIN_SUCCESS",
            ip=ip,
            now=now,
        )

    # 5. Kích hoạt phiên đăng nhập Flask
    login_session(sync_res.data)
    return redirect("/")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout() -> Any:
    """Đăng xuất người dùng và chuyển về trang đăng nhập."""
    logout_session()
    return redirect("/login")


@auth_bp.route("/auth/sso/login")
def sso_login() -> Any:
    """Khởi tạo luồng SSO mặc định (tương thích ngược với 'internal')."""
    return _initiate_sso_login("internal", legacy=True)


@auth_bp.route("/auth/sso/callback")
def sso_callback() -> Any:
    """Callback SSO mặc định (tương thích ngược)."""
    return _handle_sso_callback(None)


@auth_bp.route("/auth/sso/<provider_code>/login")
def sso_provider_login(provider_code: str) -> Any:
    """Khởi tạo luồng đăng nhập SSO theo mã nhà cung cấp (Google, Microsoft, OIDC, Internal)."""
    return _initiate_sso_login(provider_code, legacy=False)


@auth_bp.route("/auth/sso/<provider_code>/callback")
def sso_provider_callback(provider_code: str) -> Any:
    """Nhận callback từ nhà cung cấp SSO cụ thể."""
    return _handle_sso_callback(provider_code)
