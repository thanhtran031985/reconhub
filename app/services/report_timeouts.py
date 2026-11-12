"""Timeout truy vấn báo cáo cấu hình trên /settings (task 71).

Lưu trong RECON_APP_SETTING (không cần migration):
- REPORT_COUNT_TIMEOUT_SEC: timeout câu COUNT khi xem báo cáo (mặc định 300).
- REPORT_DATA_TIMEOUT_SEC: timeout câu dữ liệu (trang + xem trước) (mặc định 300).

Kẹp 1..3600 giây. Chỉ ADMIN xem/sửa (qua menu system_settings).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu

COUNT_TIMEOUT_KEY = "REPORT_COUNT_TIMEOUT_SEC"
DATA_TIMEOUT_KEY = "REPORT_DATA_TIMEOUT_SEC"
DEFAULT_TIMEOUT_SEC = 300
MIN_TIMEOUT_SEC = 1
MAX_TIMEOUT_SEC = 3600


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_timeout(value: Any) -> int:
    """Đọc giá trị setting: thiếu/sai/vượt khoảng → mặc định 300."""
    try:
        parsed = int(value) if value is not None else DEFAULT_TIMEOUT_SEC
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SEC
    if parsed < MIN_TIMEOUT_SEC or parsed > MAX_TIMEOUT_SEC:
        return DEFAULT_TIMEOUT_SEC
    return parsed


def get_report_timeouts(engine: Any) -> dict[str, int]:
    """Đọc timeout câu COUNT + câu dữ liệu (không cần ctx — report_run dùng)."""
    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                select(recon_app_setting.c.KEY, recon_app_setting.c.VALUE).where(
                    recon_app_setting.c.KEY.in_([COUNT_TIMEOUT_KEY, DATA_TIMEOUT_KEY])
                )
            ).all()
        )
    return {
        "count_timeout_sec": _parse_timeout(rows.get(COUNT_TIMEOUT_KEY)),
        "data_timeout_sec": _parse_timeout(rows.get(DATA_TIMEOUT_KEY)),
    }


def _upsert_setting(conn: Any, key: str, value: int, username: str, now: datetime) -> None:
    existing = conn.execute(select(recon_app_setting.c.KEY).where(recon_app_setting.c.KEY == key)).scalar_one_or_none()
    if existing is None:
        conn.execute(recon_app_setting.insert().values(KEY=key, VALUE=str(value), UPDATED_BY=username, UPDATED_AT=now))
    else:
        conn.execute(
            recon_app_setting.update()
            .where(recon_app_setting.c.KEY == key)
            .values(VALUE=str(value), UPDATED_BY=username, UPDATED_AT=now)
        )


def _validate_timeout(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"{label} phải là số nguyên.") from None
    if parsed < MIN_TIMEOUT_SEC or parsed > MAX_TIMEOUT_SEC:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"{label} phải trong khoảng {MIN_TIMEOUT_SEC}..{MAX_TIMEOUT_SEC}.",
        )
    return parsed


@service
@requires_menu("system_settings")
def get_report_timeout_settings(ctx: Ctx) -> dict[str, Any]:
    """Đọc timeout truy vấn báo cáo (chỉ ADMIN)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN xem được cài đặt hệ thống.")
    return get_report_timeouts(engine)


@service
@requires_menu("system_settings")
def set_report_timeouts(ctx: Ctx, count_timeout_sec: int, data_timeout_sec: int) -> dict[str, Any]:
    """Lưu timeout truy vấn báo cáo (chỉ ADMIN, 1..3600 giây)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN đổi được cài đặt hệ thống.")
    count = _validate_timeout(count_timeout_sec, "Timeout câu COUNT")
    data = _validate_timeout(data_timeout_sec, "Timeout câu dữ liệu")
    now = _now()
    with engine.begin() as conn:
        _upsert_setting(conn, COUNT_TIMEOUT_KEY, count, ctx.username, now)
        _upsert_setting(conn, DATA_TIMEOUT_KEY, data, ctx.username, now)
    return {"count_timeout_sec": count, "data_timeout_sec": data}
