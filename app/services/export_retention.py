"""Cài đặt + dọn file export chạy ngầm (task 52, thêm song song task 57).

Lưu trong RECON_APP_SETTING (không cần migration):
- EXPORT_RETENTION_MODE: "manual" (mặc định, không tự xóa) | "scheduler"
  (worker tự xóa file quá hạn).
- EXPORT_RETENTION_DAYS: số ngày giữ file khi mode=scheduler (mặc định 30).
- EXPORT_MAX_CONCURRENT: số export chạy song song tối đa (mỗi user)
  của worker (mặc định 10, kẹp 1..50).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, or_, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting, recon_rpt_export
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_export import MAX_RUNNING_PER_USER, _delete_export_files

MODE_KEY = "EXPORT_RETENTION_MODE"
DAYS_KEY = "EXPORT_RETENTION_DAYS"
DEFAULT_MODE = "manual"
DEFAULT_DAYS = 30
MAX_DAYS = 365
SWEEP_INTERVAL_SECONDS = 3600  # worker sweep tối đa 1 lần/giờ

# Task 57: số export chạy song song tối đa (mỗi user). Mặc định lấy từ
# MAX_RUNNING_PER_USER (10) để 1 con số duy nhất cho cả code và setting.
CONCURRENCY_KEY = "EXPORT_MAX_CONCURRENT"
DEFAULT_CONCURRENT = MAX_RUNNING_PER_USER
MIN_CONCURRENT = 1
MAX_CONCURRENT = 50

TERMINAL_STATUSES = ("DONE", "FAILED", "CANCELLED")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_export_retention(engine: Any) -> dict[str, Any]:
    """Đọc cài đặt dọn file (không cần ctx — worker dùng)."""
    with engine.connect() as conn:
        rows = dict(
            conn.execute(
                select(recon_app_setting.c.KEY, recon_app_setting.c.VALUE).where(
                    recon_app_setting.c.KEY.in_([MODE_KEY, DAYS_KEY])
                )
            ).all()
        )
    mode = str(rows.get(MODE_KEY) or DEFAULT_MODE)
    if mode not in ("manual", "scheduler"):
        mode = DEFAULT_MODE
    try:
        days = int(rows.get(DAYS_KEY) or DEFAULT_DAYS)
    except (TypeError, ValueError):
        days = DEFAULT_DAYS
    if days < 1 or days > MAX_DAYS:
        days = DEFAULT_DAYS
    return {"mode": mode, "days": days}


@service
@requires_menu("system_settings")
def get_export_retention_settings(ctx: Ctx) -> dict[str, Any]:
    """Đọc cài đặt dọn file (chỉ ADMIN)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN xem được cài đặt hệ thống.")
    return get_export_retention(engine)


@service
@requires_menu("system_settings")
def set_export_retention(ctx: Ctx, mode: str, days: int) -> dict[str, Any]:
    """Lưu cài đặt dọn file (chỉ ADMIN)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN đổi được cài đặt hệ thống.")
    mode = (mode or "").strip()
    if mode not in ("manual", "scheduler"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Chế độ dọn file phải là manual hoặc scheduler."
        )
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Số ngày phải là số nguyên.") from None
    if days < 1 or days > MAX_DAYS:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, f"Số ngày phải trong khoảng 1..{MAX_DAYS}."
        )
    now = _now()
    with engine.begin() as conn:
        for key, value in ((MODE_KEY, mode), (DAYS_KEY, str(days))):
            existing = conn.execute(
                select(recon_app_setting.c.KEY).where(recon_app_setting.c.KEY == key)
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(
                    recon_app_setting.insert().values(
                        KEY=key, VALUE=value, UPDATED_BY=ctx.username, UPDATED_AT=now
                    )
                )
            else:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == key)
                    .values(VALUE=value, UPDATED_BY=ctx.username, UPDATED_AT=now)
                )
    return {"mode": mode, "days": days}


def get_export_max_concurrent(engine: Any) -> int:
    """Số export chạy song song tối đa (mỗi user) — worker dùng.

    Đọc key EXPORT_MAX_CONCURRENT, thiếu/sai/vượt khoảng → mặc định 10.
    """
    with engine.connect() as conn:
        row = conn.execute(
            select(recon_app_setting.c.VALUE).where(
                recon_app_setting.c.KEY == CONCURRENCY_KEY
            )
        ).scalar_one_or_none()
    try:
        value = int(row) if row is not None else DEFAULT_CONCURRENT
    except (TypeError, ValueError):
        value = DEFAULT_CONCURRENT
    if value < MIN_CONCURRENT or value > MAX_CONCURRENT:
        value = DEFAULT_CONCURRENT
    return value


@service
@requires_menu("system_settings")
def get_export_concurrency_settings(ctx: Ctx) -> dict[str, Any]:
    """Đọc cài đặt song song export (chỉ ADMIN)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN xem được cài đặt hệ thống.")
    return {"max_concurrent": get_export_max_concurrent(engine)}


@service
@requires_menu("system_settings")
def set_export_concurrency(ctx: Ctx, max_concurrent: int) -> dict[str, Any]:
    """Lưu cài đặt song song export (chỉ ADMIN, 1..50)."""
    engine = get_recon_engine()
    if not is_admin(ctx, engine):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ ADMIN đổi được cài đặt hệ thống.")
    try:
        value = int(max_concurrent)
    except (TypeError, ValueError):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Số export song song phải là số nguyên."
        ) from None
    if value < MIN_CONCURRENT or value > MAX_CONCURRENT:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Số export song song phải trong khoảng {MIN_CONCURRENT}..{MAX_CONCURRENT}.",
        )
    now = _now()
    with engine.begin() as conn:
        existing = conn.execute(
            select(recon_app_setting.c.KEY).where(
                recon_app_setting.c.KEY == CONCURRENCY_KEY
            )
        ).scalar_one_or_none()
        if existing is None:
            conn.execute(
                recon_app_setting.insert().values(
                    KEY=CONCURRENCY_KEY, VALUE=str(value),
                    UPDATED_BY=ctx.username, UPDATED_AT=now,
                )
            )
        else:
            conn.execute(
                recon_app_setting.update()
                .where(recon_app_setting.c.KEY == CONCURRENCY_KEY)
                .values(VALUE=str(value), UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
    return {"max_concurrent": value}


def sweep_old_exports(engine: Any, now: datetime | None = None) -> int:
    """Xóa file + dòng export đã kết thúc quá N ngày (chỉ khi mode=scheduler).

    Không động tới export đang QUEUED/RUNNING, không xóa run. Mốc tính là
    FINISHED_AT (hoặc CREATED_AT nếu chưa có). Ghi audit DELETE_EXPORT
    với actor "worker".
    """
    settings = get_export_retention(engine)
    if settings["mode"] != "scheduler":
        return 0
    now = now or _now()
    cutoff = now - timedelta(days=int(settings["days"]))
    deleted = 0
    with engine.begin() as conn:
        rows = (
            conn.execute(
                select(recon_rpt_export)
                .where(
                    recon_rpt_export.c.STATUS.in_(TERMINAL_STATUSES),
                    or_(
                        recon_rpt_export.c.FINISHED_AT < cutoff,
                        and_(
                            recon_rpt_export.c.FINISHED_AT.is_(None),
                            recon_rpt_export.c.CREATED_AT < cutoff,
                        ),
                    ),
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            export_id = int(row["ID"])
            _delete_export_files(export_id)
            conn.execute(delete(recon_rpt_export).where(recon_rpt_export.c.ID == export_id))
            write_audit_log(
                conn,
                "RECON_RPT_EXPORT",
                export_id,
                "DELETE_EXPORT",
                "worker",
                new_data={"reason": "retention-sweep", "days": int(settings["days"])},
            )
            deleted += 1
    return deleted
