"""Báo run đối soát DONE/FAILED qua Telegram cho người chạy (task 94).

Kênh gửi độc lập với pref thông báo trong app (task 78): Telegram có
cổng riêng `is_telegram_enabled` (đã liên kết chat_id + pref TELEGRAM
trong RECON_NOTIFICATION_PREF, thiếu dòng = mặc định riêng theo sự
kiện: RUN_DONE/RUN_FAILED đều BẬT).

- Gửi bằng Bot API (`api.telegram.org`) qua `urllib` chuẩn của Python,
  không thêm package ngoài Stack (D2).
- Mọi hàm gửi/poll đều KHÔNG raise: lỗi chỉ log warn + trả False/0,
  không chặn luồng chạy (D7).
- Token bot là bí mật: lưu mã hóa Fernet trong RECON_APP_SETTING,
  không ghi vào log/audit, không hiện lại dạng rõ trên UI (D4).
- Liên kết bằng mã qua /start, không dùng webhook (app không có URL
  công khai): worker poll `getUpdates` 30s/lần (D6).
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_notification_pref,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_user,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import logger, service
from app.services.perm import is_admin, requires_menu

TELEGRAM_BOT_TOKEN_KEY = "TELEGRAM_BOT_TOKEN"
TELEGRAM_BOT_USERNAME_KEY = "TELEGRAM_BOT_USERNAME"
TELEGRAM_UPDATE_OFFSET_KEY = "TELEGRAM_UPDATE_OFFSET"
TELEGRAM_PREF_EVENT = "TELEGRAM"
TELEGRAM_EVENT_DEFAULTS = {"RUN_DONE": True, "RUN_FAILED": True}
HTTP_TIMEOUT_S = 10
LINK_CODE_TTL_MINUTES = 15
TELEGRAM_API_BASE = "https://api.telegram.org"

LINK_GUIDANCE_TEXT = (
    "Để liên kết Telegram, vào trang Tài khoản trong ReconHub, bấm 'Lấy mã liên kết' rồi nhắn /start <mã> cho bot này."
)
TEST_MESSAGE_TEXT = "Tin thử từ ReconHub — bot Telegram đã nối."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fmt_num(value: Any) -> str:
    """Số đếm dạng Việt Nam (6.114); lỗi → '—'."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _format_period(p_from: Any, p_to: Any) -> str:
    """Kỳ của run dạng '2026-07' (cùng tháng) hoặc '01/07/2026–31/08/2026'."""
    try:
        if p_from is None or p_to is None:
            return "—"
        if p_from.year == p_to.year and p_from.month == p_to.month:
            return f"{p_from:%Y-%m}"
        return f"{p_from:%d/%m/%Y}–{p_to:%d/%m/%Y}"
    except Exception:
        return "—"


def _get_setting(engine: Any, key: str) -> str | None:
    with engine.connect() as conn:
        value = conn.execute(
            select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == key)
        ).scalar_one_or_none()
    return str(value) if value is not None else None


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


def _upsert_pref(conn: Any, user_id: int, event_type: str, enabled: str, now: datetime) -> None:
    existing = conn.execute(
        select(recon_notification_pref.c.USER_ID).where(
            recon_notification_pref.c.USER_ID == int(user_id),
            recon_notification_pref.c.EVENT_TYPE == event_type,
        )
    ).scalar_one_or_none()
    if existing is None:
        conn.execute(
            recon_notification_pref.insert().values(
                USER_ID=int(user_id), EVENT_TYPE=event_type, ENABLED=enabled, UPDATED_AT=now
            )
        )
    else:
        conn.execute(
            recon_notification_pref.update()
            .where(
                recon_notification_pref.c.USER_ID == int(user_id),
                recon_notification_pref.c.EVENT_TYPE == event_type,
            )
            .values(ENABLED=enabled, UPDATED_AT=now)
        )


def _get_token(engine: Any) -> str | None:
    """Token bot đã giải mã; thiếu/hỏng → None (không raise)."""
    try:
        raw = _get_setting(engine, TELEGRAM_BOT_TOKEN_KEY)
        if not raw:
            return None
        return decrypt_secret(raw)
    except Exception as exc:  # noqa: BLE001 — token hỏng thì coi như chưa cấu hình
        logger.warn("Không đọc được token bot Telegram", error=str(exc))
        return None


def _pref_row(engine: Any, user_id: int, event_type: str) -> str | None:
    """Giá trị pref ('Y'/'N') hoặc None khi chưa có dòng."""
    with engine.connect() as conn:
        value = conn.execute(
            select(recon_notification_pref.c.ENABLED).where(
                recon_notification_pref.c.USER_ID == int(user_id),
                recon_notification_pref.c.EVENT_TYPE == event_type,
            )
        ).scalar_one_or_none()
    return str(value) if value is not None else None


def send_telegram_message(chat_id: Any, text: str, engine: Any = None) -> bool:
    """Gửi 1 tin text thuần qua Bot API; lỗi → False, không raise."""
    try:
        eng = engine if engine is not None else get_recon_engine()
        token = _get_token(eng)
        if not token:
            logger.warn("Chưa cấu hình token bot Telegram, không gửi được tin")
            return False
        payload = json.dumps({"chat_id": chat_id, "text": str(text)}).encode("utf-8")
        req = urllib.request.Request(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            logger.warn("Telegram API trả lỗi khi gửi tin", response=str(data)[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — gửi không được raise
        logger.warn("Không gửi được tin Telegram", error=str(exc))
        return False


def is_telegram_enabled(engine: Any, user_id: int, event_type: str) -> bool:
    """User có nhận tin Telegram cho loại sự kiện này không.

    Cần: đã liên kết (có TELEGRAM_CHAT_ID) + pref TELEGRAM (thiếu dòng
    = mặc định riêng theo sự kiện, RUN_DONE/RUN_FAILED đều BẬT).
    """
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == int(user_id)))
                .mappings()
                .first()
            )
        if row is None or not row["TELEGRAM_CHAT_ID"]:
            return False
        try:
            pref = _pref_row(engine, int(user_id), TELEGRAM_PREF_EVENT)
        except Exception as exc:  # noqa: BLE001 — lỗi đọc pref thì dùng mặc định
            logger.warn("Không đọc được pref Telegram", error=str(exc))
            pref = None
        if pref is not None:
            return str(pref) == "Y"
        return bool(TELEGRAM_EVENT_DEFAULTS.get(event_type, True))
    except Exception as exc:  # noqa: BLE001 — lỗi thì coi như tắt
        logger.warn("Không kiểm tra được cổng Telegram", error=str(exc))
        return False


def _build_run_message(engine: Any, run: Any, event_type: str) -> str | None:
    """Build tin nhắn cho run DONE/FAILED (D8: chỉ số liệu, không link)."""
    run_id = int(run["ID"])
    if event_type == "RUN_FAILED":
        reason = str(run["ERROR_MSG"] or "Không rõ lý do")
        return f"Run #{run_id} lỗi — {reason[:500]}."
    if event_type != "RUN_DONE":
        return None
    with engine.connect() as conn:
        tmpl_name = conn.execute(
            select(recon_template.c.NAME).where(recon_template.c.ID == int(run["TEMPLATE_ID"]))
        ).scalar_one_or_none()
        summary = conn.execute(select(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id)).mappings().first()
    name = str(tmpl_name) if tmpl_name else f"Template #{int(run['TEMPLATE_ID'])}"
    period = _format_period(run["P_FROM"], run["P_TO"])
    if summary is None:
        return f"Run #{run_id} đã xong — {name}, kỳ {period}."
    return (
        f"Run #{run_id} đã xong — {name}, kỳ {period}: "
        f"Khớp {_fmt_num(summary['CNT_MATCHED'])} · "
        f"Lệch {_fmt_num(summary['CNT_MISMATCH'])} · "
        f"Thiếu trong DB {_fmt_num(summary['CNT_MISSING_IN_DB'])} · "
        f"Thiếu trong Excel {_fmt_num(summary['CNT_MISSING_IN_EXCEL'])}."
    )


def notify_telegram_for_run(engine: Any, run_id: int, event_type: str) -> bool:
    """Gửi tin Telegram cho chủ run khi DONE/FAILED; không raise."""
    try:
        if event_type not in TELEGRAM_EVENT_DEFAULTS:
            logger.warn("Loại sự kiện Telegram không hỗ trợ", event_type=event_type)
            return False
        with engine.connect() as conn:
            run = conn.execute(select(recon_run).where(recon_run.c.ID == int(run_id))).mappings().first()
        if run is None:
            return False
        owner = str(run["CREATED_BY"])
        with engine.connect() as conn:
            user_row = (
                conn.execute(
                    select(recon_user.c.ID, recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.USERNAME == owner)
                )
                .mappings()
                .first()
            )
        if user_row is None:
            return False
        user_id = int(user_row["ID"])
        if not is_telegram_enabled(engine, user_id, event_type):
            return False
        chat_id = user_row["TELEGRAM_CHAT_ID"]
        if not chat_id:
            return False
        text = _build_run_message(engine, run, event_type)
        if text is None:
            return False
        return send_telegram_message(chat_id, text, engine)
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không gửi được tin Telegram cho run", run_id=run_id, event_type=event_type, error=str(exc))
        return False


@service
@requires_menu("system_settings")
def get_telegram_settings(ctx: Ctx) -> dict[str, Any]:
    """Đọc cấu hình bot Telegram (chỉ ADMIN; không trả token)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN xem được cài đặt hệ thống.")
    username = _get_setting(engine, TELEGRAM_BOT_USERNAME_KEY)
    return {"configured": bool(_get_token(engine)), "username": username or None}


@service
@requires_menu("system_settings")
def set_telegram_settings(ctx: Ctx, token: str | None, username: str | None) -> dict[str, Any]:
    """Lưu cấu hình bot Telegram (chỉ ADMIN).

    Token rỗng = giữ token đã lưu (UI không hiện lại token cũ).
    Username được strip và bỏ '@' đầu.
    """
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN đổi được cài đặt hệ thống.")
    new_token = (token or "").strip()
    new_username = (username or "").strip().lstrip("@")
    now = _now()
    with engine.begin() as conn:
        if new_token:
            if len(new_token) < 10 or ":" not in new_token:
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "Token bot không hợp lệ.")
            _upsert_setting(conn, TELEGRAM_BOT_TOKEN_KEY, encrypt_secret(new_token), ctx.username, now)
        _upsert_setting(conn, TELEGRAM_BOT_USERNAME_KEY, new_username, ctx.username, now)
    return {"configured": bool(new_token or _get_token(engine)), "username": new_username or None}


@service
def generate_link_code(ctx: Ctx) -> dict[str, Any]:
    """Cấp mã liên kết Telegram cho chính user (hạn 15 phút)."""
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    engine = get_recon_engine()
    username = _get_setting(engine, TELEGRAM_BOT_USERNAME_KEY)
    if not username:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chưa cấu hình username bot Telegram (trang /settings).",
        )
    code = secrets.token_urlsafe(6)
    expires_at = _now() + timedelta(minutes=LINK_CODE_TTL_MINUTES)
    with engine.begin() as conn:
        conn.execute(
            recon_user.update()
            .where(recon_user.c.ID == int(ctx.user_id))
            .values(TELEGRAM_LINK_CODE=code, TELEGRAM_LINK_EXPIRES_AT=expires_at)
        )
    return {
        "code": code,
        "link": f"https://t.me/{username}?start={code}",
        "expires_at": expires_at.isoformat(),
        "expires_minutes": LINK_CODE_TTL_MINUTES,
    }


@service
def get_telegram_link_status(ctx: Ctx) -> dict[str, Any]:
    """Trạng thái liên kết Telegram của chính user (cho trang /account)."""
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == int(ctx.user_id)))
            .mappings()
            .first()
        )
    chat_id = str(row["TELEGRAM_CHAT_ID"]) if row and row["TELEGRAM_CHAT_ID"] else None
    return {
        "linked": chat_id is not None,
        "chat_id": chat_id,
        "enabled": is_telegram_enabled(engine, int(ctx.user_id), "RUN_DONE"),
    }


@service
def unlink_telegram(ctx: Ctx) -> dict[str, Any]:
    """Hủy liên kết Telegram của chính user (xóa chat_id + mã, tắt nhận)."""
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    engine = get_recon_engine()
    with engine.begin() as conn:
        conn.execute(
            recon_user.update()
            .where(recon_user.c.ID == int(ctx.user_id))
            .values(TELEGRAM_CHAT_ID=None, TELEGRAM_LINK_CODE=None, TELEGRAM_LINK_EXPIRES_AT=None)
        )
        _upsert_pref(conn, int(ctx.user_id), TELEGRAM_PREF_EVENT, "N", _now())
    return {"linked": False}


@service
def set_telegram_enabled(ctx: Ctx, enabled: bool) -> dict[str, Any]:
    """Bật/tắt nhận thông báo Telegram của chính user."""
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")
    engine = get_recon_engine()
    with engine.begin() as conn:
        _upsert_pref(conn, int(ctx.user_id), TELEGRAM_PREF_EVENT, "Y" if enabled else "N", _now())
    return {"enabled": bool(enabled)}


@service
@requires_menu("system_settings")
def send_telegram_test(ctx: Ctx) -> dict[str, Any]:
    """Gửi tin thử tới Telegram đã liên kết của chính ADMIN."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN gửi tin thử Telegram.")
    with engine.connect() as conn:
        row = (
            conn.execute(select(recon_user.c.TELEGRAM_CHAT_ID).where(recon_user.c.ID == int(ctx.user_id)))
            .mappings()
            .first()
        )
    chat_id = str(row["TELEGRAM_CHAT_ID"]) if row and row["TELEGRAM_CHAT_ID"] else None
    if not chat_id:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Bạn chưa liên kết Telegram. Nhắn /start cho bot trước rồi thử lại.",
        )
    if not send_telegram_message(chat_id, TEST_MESSAGE_TEXT, engine):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Không gửi được tin thử. Kiểm tra token bot ở trang /settings.",
        )
    return {"sent": True}


def poll_telegram_updates_once(engine: Any) -> int:
    """Poll getUpdates 1 lần, xử lý /start <mã> để liên kết; không raise.

    Trả số update đã xử lý (0 khi chưa cấu hình token hoặc lỗi).
    """
    try:
        token = _get_token(engine)
        if not token:
            return 0
        raw_offset = _get_setting(engine, TELEGRAM_UPDATE_OFFSET_KEY)
        try:
            offset = int(raw_offset) if raw_offset is not None else 0
        except (TypeError, ValueError):
            offset = 0
        url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates?offset={offset + 1}&timeout=0"
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — lỗi mạng thì trả 0
            logger.warn("Không poll được Telegram getUpdates", error=str(exc))
            return 0
        if not data.get("ok"):
            logger.warn("Telegram API trả lỗi khi poll getUpdates", response=str(data)[:200])
            return 0
        updates = data.get("result") or []
        max_update_id = offset
        for update in updates:
            try:
                update_id = int(update.get("update_id") or 0)
                if update_id > max_update_id:
                    max_update_id = update_id
                _handle_update(engine, update)
            except Exception as exc:  # noqa: BLE001 — 1 update lỗi không chặn batch
                logger.warn("Không xử lý được 1 update Telegram", error=str(exc))
        if updates:
            with engine.begin() as conn:
                _upsert_setting(conn, TELEGRAM_UPDATE_OFFSET_KEY, str(max_update_id), "system", _now())
        return len(updates)
    except Exception as exc:  # noqa: BLE001 — poll không được raise
        logger.warn("Lỗi poll Telegram", error=str(exc))
        return 0


def _handle_update(engine: Any, update: dict[str, Any]) -> None:
    """Xử lý 1 update getUpdates: chỉ quan tâm message bắt đầu bằng /start."""
    message = update.get("message") or {}
    text = str(message.get("text") or "")
    if not text.startswith("/start"):
        return
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    code = text[len("/start") :].strip().split()[0] if text[len("/start") :].strip() else ""
    if not code:
        send_telegram_message(chat_id, LINK_GUIDANCE_TEXT, engine)
        return
    now = _now()
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_user.c.ID, recon_user.c.USERNAME).where(
                    recon_user.c.TELEGRAM_LINK_CODE == code,
                    recon_user.c.TELEGRAM_LINK_EXPIRES_AT > now,
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        send_telegram_message(chat_id, LINK_GUIDANCE_TEXT, engine)
        return
    with engine.begin() as conn:
        conn.execute(
            recon_user.update()
            .where(recon_user.c.ID == int(row["ID"]))
            .values(
                TELEGRAM_CHAT_ID=str(chat_id),
                TELEGRAM_LINK_CODE=None,
                TELEGRAM_LINK_EXPIRES_AT=None,
            )
        )
    send_telegram_message(
        chat_id,
        f"Đã liên kết Telegram với tài khoản {row['USERNAME']}. Run đối soát xong/lỗi sẽ báo về đây.",
        engine,
    )
