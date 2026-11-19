from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting
from app.engine.mailer import send_smtp_email
from app.schemas.errors import ErrorCode, ServiceError
from app.services import logger, service
from app.services.perm import is_admin, requires_menu

SMTP_HOST_KEY = "SMTP_HOST"
SMTP_PORT_KEY = "SMTP_PORT"
SMTP_SECURITY_KEY = "SMTP_SECURITY"
SMTP_USERNAME_KEY = "SMTP_USERNAME"
SMTP_PASSWORD_KEY = "SMTP_PASSWORD_ENC"
SMTP_FROM_EMAIL_KEY = "SMTP_FROM_EMAIL"
SMTP_FROM_NAME_KEY = "SMTP_FROM_NAME"
APP_BASE_URL_KEY = "APP_BASE_URL"
DEFAULT_APP_BASE_URL = "http://127.0.0.1:8050"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_setting(engine: Any, key: str) -> str | None:
    with engine.connect() as conn:
        value = conn.execute(
            select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == key)
        ).scalar_one_or_none()
    return str(value) if value is not None else None


def get_app_base_url() -> str:
    """Lấy địa chỉ URL gốc của hệ thống (Base URL) từ cấu hình, fallback 127.0.0.1:8050."""
    try:
        engine = get_recon_engine()
        raw = _get_setting(engine, APP_BASE_URL_KEY)
        if raw and raw.strip():
            url = raw.strip().rstrip("/")
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"http://{url}"
            return url
    except Exception:
        pass
    return DEFAULT_APP_BASE_URL


def build_app_url(path: str = "") -> str:
    """Sinh URL tuyệt đối hoàn chỉnh có host cho email và liên kết an toàn."""
    p = (path or "").strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    base = get_app_base_url()
    clean_path = "/" + p.lstrip("/") if p else ""
    return f"{base}{clean_path}"


def _upsert_setting(conn: Any, key: str, value: str, username: str, now: datetime) -> None:
    existing = conn.execute(select(recon_app_setting.c.KEY).where(recon_app_setting.c.KEY == key)).scalar_one_or_none()
    if existing is None:
        conn.execute(recon_app_setting.insert().values(KEY=key, VALUE=value, UPDATED_BY=username, UPDATED_AT=now))
    else:
        conn.execute(
            recon_app_setting.update()
            .where(recon_app_setting.c.KEY == key)
            .values(VALUE=value, UPDATED_BY=username, UPDATED_AT=now)
        )


def get_smtp_config_internal() -> dict[str, Any]:
    """Hàm nội bộ đọc cấu hình SMTP thực tế (đã giải mã password) cho mailer.

    Không kiểm tra quyền admin vì được gọi ngầm bởi các service gửi mail nghiệp vụ.
    """
    engine = get_recon_engine()
    host = _get_setting(engine, SMTP_HOST_KEY) or ""
    port_str = _get_setting(engine, SMTP_PORT_KEY) or "587"
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    security = _get_setting(engine, SMTP_SECURITY_KEY) or "STARTTLS"
    username = _get_setting(engine, SMTP_USERNAME_KEY) or ""

    raw_pass = _get_setting(engine, SMTP_PASSWORD_KEY)
    password = ""
    if raw_pass:
        try:
            password = decrypt_secret(raw_pass)
        except Exception as exc:
            logger.warn("Không giải mã được mật khẩu SMTP", error=str(exc))

    from_email = _get_setting(engine, SMTP_FROM_EMAIL_KEY) or ""
    from_name = _get_setting(engine, SMTP_FROM_NAME_KEY) or "ReconHub"

    return {
        "host": host,
        "port": port,
        "security": security,
        "username": username,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
    }


@service
@requires_menu("system_settings")
def get_smtp_settings(ctx: Ctx) -> dict[str, Any]:
    """Lấy cấu hình máy chủ SMTP (chỉ ADMIN). Mật khẩu chỉ trả về cờ has_password."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN mới có quyền xem cấu hình SMTP.")

    cfg = get_smtp_config_internal()
    return {
        "host": cfg["host"],
        "port": cfg["port"],
        "security": cfg["security"],
        "username": cfg["username"],
        "has_password": bool(cfg["password"]),
        "from_email": cfg["from_email"],
        "from_name": cfg["from_name"],
        "app_base_url": get_app_base_url(),
    }


@service
@requires_menu("system_settings")
def set_smtp_settings(
    ctx: Ctx,
    host: str,
    port: int = 587,
    security: str = "STARTTLS",
    username: str = "",
    password: str | None = None,
    from_email: str = "",
    from_name: str = "",
    app_base_url: str = DEFAULT_APP_BASE_URL,
) -> dict[str, Any]:
    """Lưu cấu hình máy chủ SMTP và URL hệ thống (chỉ ADMIN). Mật khẩu được mã hóa Fernet."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN mới có quyền thay đổi cấu hình SMTP.")

    h = (host or "").strip()
    if not h:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Địa chỉ máy chủ SMTP (Host) không được để trống.")

    p = int(port)
    if p < 1 or p > 65535:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Cổng SMTP phải nằm trong khoảng 1 đến 65535.")

    sec = (security or "STARTTLS").strip().upper()
    if sec not in ("STARTTLS", "SSL", "NONE"):
        sec = "STARTTLS"

    u = (username or "").strip()
    f_email = (from_email or "").strip()
    f_name = (from_name or "").strip()
    b_url = (app_base_url or "").strip().rstrip("/")
    if b_url and not b_url.startswith("http://") and not b_url.startswith("https://"):
        b_url = f"http://{b_url}"
    if not b_url:
        b_url = DEFAULT_APP_BASE_URL

    now = _now()

    with engine.begin() as conn:
        _upsert_setting(conn, SMTP_HOST_KEY, h, ctx.username, now)
        _upsert_setting(conn, SMTP_PORT_KEY, str(p), ctx.username, now)
        _upsert_setting(conn, SMTP_SECURITY_KEY, sec, ctx.username, now)
        _upsert_setting(conn, SMTP_USERNAME_KEY, u, ctx.username, now)
        _upsert_setting(conn, SMTP_FROM_EMAIL_KEY, f_email, ctx.username, now)
        _upsert_setting(conn, SMTP_FROM_NAME_KEY, f_name, ctx.username, now)
        _upsert_setting(conn, APP_BASE_URL_KEY, b_url, ctx.username, now)

        # Cập nhật mật khẩu nếu được truyền vào
        if password is not None and str(password).strip():
            enc_pass = encrypt_secret(str(password).strip())
            _upsert_setting(conn, SMTP_PASSWORD_KEY, enc_pass, ctx.username, now)

        write_audit_log(
            conn=conn,
            entity="SMTP_SETTINGS",
            entity_id=1,
            action="UPDATE_SMTP_SETTINGS",
            actor=ctx.username,
            old_data=None,
            new_data={"host": h, "port": p, "security": sec, "username": u, "from_email": f_email},
            now=now,
        )

    return {"saved": True}


@service
@requires_menu("system_settings")
def test_smtp_connection(
    ctx: Ctx,
    to_email: str,
    override_password: str | None = None,
    override_host: str | None = None,
    override_port: int | None = None,
    override_security: str | None = None,
    override_username: str | None = None,
) -> dict[str, Any]:
    """Gửi email kiểm tra kết nối SMTP (chỉ ADMIN)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN mới có quyền kiểm tra kết nối SMTP.")

    recipient = (to_email or "").strip()
    if not recipient or "@" not in recipient:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Địa chỉ email nhận thử nghiệm không hợp lệ.")

    cfg = get_smtp_config_internal()
    host = (override_host or "").strip() or cfg["host"]
    if not host:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chưa cấu hình máy chủ SMTP. Hãy điền Host và Lưu cấu hình trước khi kiểm tra.",
        )

    port = override_port if override_port is not None else cfg["port"]
    security = override_security or cfg["security"]
    username = override_username if override_username is not None else cfg["username"]
    password = override_password if (override_password is not None and str(override_password).strip()) else cfg["password"]

    sender_name = cfg["from_name"] or "ReconHub"
    sender_email = cfg["from_email"] or username or "no-reply@reconhub.local"
    from_full = f"{sender_name} <{sender_email}>"

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family: Segoe UI, sans-serif; color: #1e293b; line-height: 1.5;">
    <h2 style="color: #0284c7;">Kiểm tra kết nối gửi email ReconHub</h2>
    <p>Xin chào <strong>{recipient}</strong>,</p>
    <p>Đây là email thử nghiệm gửi từ hệ thống ReconHub để xác nhận cấu hình máy chủ SMTP hoạt động bình thường.</p>
    <ul>
        <li><strong>Máy chủ SMTP:</strong> {host}:{port}</li>
        <li><strong>Giao thức bảo mật:</strong> {security}</li>
        <li><strong>Thời gian gửi:</strong> {now_str}</li>
        <li><strong>Người gửi thử nghiệm:</strong> @{ctx.username}</li>
    </ul>
    <p style="color: #64748b; font-size: 12px; margin-top: 20px;">Email tự động từ hệ thống đối soát ReconHub.</p>
</body>
</html>"""

    res = send_smtp_email(
        host=host,
        port=port,
        security=security,
        username=username,
        password=password,
        from_addr=from_full,
        to_addrs=[recipient],
        subject="[ReconHub] Kiểm tra kết nối máy chủ gửi email SMTP",
        body_html=body_html,
        timeout=10,
    )

    if not res.get("ok"):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, str(res.get("message") or "Không thể gửi email thử nghiệm."))

    return {"sent": True, "message": str(res.get("message") or "Đã gửi email thử nghiệm thành công.")}
