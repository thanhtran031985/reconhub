from __future__ import annotations

import hashlib
import html
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Engine, func, select, update

from app.core.audit import write_audit_log
from app.core.auth import hash_password
from app.core.session import invalidate_user_session_cache
from app.db.metadata import recon_password_reset_token, recon_user
from app.engine.mailer import send_smtp_email
from app.schemas.errors import ErrorCode, ServiceResult
from app.services.smtp_settings import get_smtp_config_internal

RESET_TOKEN_TTL_MINUTES = 20
_SSO_PASSWORD_PREFIX = "!sso_managed_"


def _is_sso_managed_user(user_row: Any) -> bool:
    """Kiểm tra tài khoản do SSO quản lý (không cho phép đặt lại mật khẩu cục bộ)."""
    pw_hash = str(user_row["PASSWORD_HASH"] or "")
    return pw_hash.startswith(_SSO_PASSWORD_PREFIX)


def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> bool:
    """Gửi email chứa liên kết đặt lại mật khẩu an toàn."""
    smtp_cfg = get_smtp_config_internal()
    if not smtp_cfg.get("host"):
        # Nếu chưa cấu hình máy chủ SMTP, không raise error để tránh làm sập flow
        return False

    sender_name = smtp_cfg.get("from_name") or "ReconHub Security"
    sender_email = smtp_cfg.get("from_email") or smtp_cfg.get("username") or "no-reply@reconhub.local"
    from_addr = f"{sender_name} <{sender_email}>" if sender_name else sender_email

    safe_name = html.escape(full_name)
    safe_url = html.escape(reset_url, quote=True)
    subject = "[ReconHub] Yêu cầu đặt lại mật khẩu"
    body_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 8px; background: #ffffff;">
        <h2 style="color: #106ebe; margin-top: 0;">ReconHub — Đặt lại mật khẩu</h2>
        <p>Xin chào <strong>{safe_name}</strong>,</p>
        <p>Hệ thống nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn trên ReconHub. Vui lòng bấm vào liên kết bên dưới để thiết lập mật khẩu mới:</p>
        <div style="margin: 24px 0; text-align: center;">
            <a href="{safe_url}" style="background-color: #106ebe; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">Đặt lại mật khẩu</a>
        </div>
        <p style="font-size: 13px; color: #6b7280;">Liên kết này có hiệu lực trong vòng <strong>{RESET_TOKEN_TTL_MINUTES} phút</strong> và chỉ sử dụng được 1 lần duy nhất.</p>
        <p style="font-size: 13px; color: #6b7280;">Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email hoặc liên hệ với Quản trị viên hệ thống để được hỗ trợ.</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;" />
        <p style="font-size: 12px; color: #9ca3af; text-align: center;">ReconHub — Hệ thống Đối soát Dữ liệu Nội bộ</p>
    </div>
    """

    try:
        res = send_smtp_email(
            host=str(smtp_cfg["host"]),
            port=int(smtp_cfg.get("port", 587)),
            security=str(smtp_cfg.get("security", "STARTTLS")),
            username=str(smtp_cfg.get("username", "")),
            password=str(smtp_cfg.get("password", "")),
            from_addr=from_addr,
            to_addrs=[to_email],
            subject=subject,
            body_html=body_html,
        )
        return bool(res.get("success", False))
    except Exception:
        return False


def request_password_reset(
    engine: Engine,
    username: str,
    email: str,
    ip: str | None = None,
    base_url: str = "http://127.0.0.1:8050",
) -> ServiceResult[dict[str, Any]]:
    """Tiếp nhận yêu cầu quên mật khẩu và gửi email đặt lại nếu thông tin khớp.

    Yêu cầu nhập đồng thời cả tên đăng nhập và email để xác định chính xác tài khoản
    khi nhiều tài khoản dùng chung một địa chỉ email.
    Tuân thủ quy chuẩn Anti-Enumeration: luôn trả về thông báo thành công chung.
    """
    clean_user = username.strip().lower()
    clean_email = email.strip().lower()
    success_msg = "Nếu thông tin tài khoản và email hợp lệ, liên kết đặt lại mật khẩu đã được gửi đến email đã đăng ký của bạn."

    if not clean_user or not clean_email:
        return ServiceResult.fail(
            ErrorCode.VALIDATION_ERROR,
            "Vui lòng nhập đầy đủ tên đăng nhập và địa chỉ email",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        # Tìm user khớp đồng thời cả username và email
        user = conn.execute(
            select(recon_user).where(
                (func.lower(recon_user.c.USERNAME) == clean_user)
                & (func.lower(recon_user.c.EMAIL) == clean_email)
            )
        ).mappings().first()

        # Nếu không tìm thấy, bị khóa vĩnh viễn, thiếu email hoặc tài khoản SSO -> Vẫn trả về thông báo an toàn
        if user is None or user["IS_ACTIVE"] != "Y" or not user["EMAIL"] or _is_sso_managed_user(user):
            return ServiceResult.success({"sent": True, "message": success_msg})

        user_id = int(user["ID"])
        user_email = str(user["EMAIL"])
        full_name = str(user["FULL_NAME"] or user["USERNAME"])

        # Hủy các token chưa dùng trước đó của user này
        conn.execute(
            update(recon_password_reset_token)
            .where(
                recon_password_reset_token.c.USER_ID == user_id,
                recon_password_reset_token.c.IS_USED == "N",
            )
            .values(IS_USED="Y")
        )

        # Sinh token mới
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)

        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH=token_hash,
                EXPIRES_AT=expires_at,
                IS_USED="N",
                CREATED_AT=now,
                CREATED_IP=ip,
            )
        )

    # Gửi email kèm link đặt lại mật khẩu
    reset_url = f"{base_url.rstrip('/')}/reset-password?token={raw_token}"
    send_password_reset_email(to_email=user_email, full_name=full_name, reset_url=reset_url)

    return ServiceResult.success({
        "sent": True,
        "message": success_msg,
    })


def validate_reset_token(engine: Engine, raw_token: str) -> ServiceResult[dict[str, Any]]:
    """Xác minh tính hợp lệ và thời hạn của Reset Token."""
    if not raw_token or not raw_token.strip():
        return ServiceResult.fail(ErrorCode.VALIDATION_ERROR, "Mã xác thực không hợp lệ")

    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.connect() as conn:
        row = conn.execute(
            select(
                recon_password_reset_token.c.ID,
                recon_password_reset_token.c.USER_ID,
                recon_password_reset_token.c.EXPIRES_AT,
                recon_password_reset_token.c.IS_USED,
                recon_user.c.USERNAME,
                recon_user.c.FULL_NAME,
                recon_user.c.IS_ACTIVE,
                recon_user.c.PASSWORD_HASH,
            )
            .select_from(
                recon_password_reset_token.join(
                    recon_user, recon_password_reset_token.c.USER_ID == recon_user.c.ID
                )
            )
            .where(recon_password_reset_token.c.TOKEN_HASH == token_hash)
        ).mappings().first()

        if row is None or row["IS_USED"] == "Y":
            return ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR,
                "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã được sử dụng",
            )

        if row["EXPIRES_AT"] < now:
            return ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR,
                "Liên kết đặt lại mật khẩu đã hết hạn (quá 20 phút)",
            )

        if row["IS_ACTIVE"] != "Y":
            return ServiceResult.fail(
                ErrorCode.ACCOUNT_INACTIVE,
                "Tài khoản hiện đang bị vô hiệu hóa trong hệ thống",
            )

        if _is_sso_managed_user(row):
            return ServiceResult.fail(
                ErrorCode.VALIDATION_ERROR,
                "Tài khoản SSO Doanh nghiệp không hỗ trợ đặt lại mật khẩu cục bộ",
            )

        return ServiceResult.success({
            "token_id": int(row["ID"]),
            "user_id": int(row["USER_ID"]),
            "username": str(row["USERNAME"]),
            "full_name": str(row["FULL_NAME"]),
        })


def perform_password_reset(
    engine: Engine,
    raw_token: str,
    new_password: str,
    ip: str | None = None,
) -> ServiceResult[dict[str, Any]]:
    """Thực hiện cập nhật mật khẩu mới khi token hợp lệ."""
    val_res = validate_reset_token(engine, raw_token)
    if not val_res.ok or not val_res.data:
        return ServiceResult.fail(
            val_res.code or ErrorCode.VALIDATION_ERROR,
            val_res.message or "Liên kết đặt lại mật khẩu không hợp lệ",
        )

    user_info = val_res.data
    user_id = user_info["user_id"]
    username = user_info["username"]

    clean_pw = new_password.strip()
    if len(clean_pw) < 6:
        return ServiceResult.fail(ErrorCode.VALIDATION_ERROR, "Mật khẩu mới phải có tối thiểu 6 ký tự")

    pw_hash = hash_password(clean_pw)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    with engine.begin() as conn:
        # 1. Cập nhật mật khẩu và thu hồi phiên đăng nhập cũ
        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == user_id)
            .values(
                PASSWORD_HASH=pw_hash,
                SESSION_VERSION=recon_user.c.SESSION_VERSION + 1,
                FAILED_COUNT=0,
                LOCKED_UNTIL=None,
                MUST_CHANGE_PW="N",
                PW_CHANGED_AT=now,
                UPDATED_AT=now,
            )
        )

        # 2. Đánh dấu token đã được sử dụng
        conn.execute(
            update(recon_password_reset_token)
            .where(recon_password_reset_token.c.TOKEN_HASH == token_hash)
            .values(IS_USED="Y")
        )

        # 3. Ghi vết kiểm toán an toàn
        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=user_id,
            action="PASSWORD_RESET_SELF",
            actor=username,
            new_data={"method": "email_token", "ip": ip},
            now=now,
        )

    invalidate_user_session_cache(user_id)

    return ServiceResult.success({
        "username": username,
        "message": "Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.",
    })
