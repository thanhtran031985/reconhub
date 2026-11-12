"""Trung tâm thông báo trong app (task 78).

Thông báo lưu DB (RECON_NOTIFICATION), chuông + badge ở header, trang
/notifications xem tất cả + cài đặt từng loại sự kiện theo user
(RECON_NOTIFICATION_PREF; thiếu dòng = dùng mặc định: lỗi BẬT,
DONE TẮT — quyết định task 52: tự vào lịch xem, không thông báo).

- Hàm emit (notify_*) là hàm thuần, KHÔNG bao giờ raise: lỗi tạo
  thông báo không được làm hỏng run/export/batch (bọc try/except,
  chỉ log warn). Worker và app đều dùng được (chỉ cần engine).
- Hàm đọc/ghi theo user (@service) chặn bằng menu "notifications";
  chỉ thấy thông báo của mình.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_batch_run,
    recon_notification,
    recon_notification_pref,
    recon_report_run,
    recon_role,
    recon_rpt_export,
    recon_run,
    recon_user,
    recon_user_role,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import logger, service
from app.services.perm import requires_menu

# NOTE: worker_health KHÔNG import ở top-level — nó kéo export_retention
# -> report_export -> notification (vòng tròn). Import lười bên trong
# maybe_notify_worker_health (mẫu lazy import đã có ở worker/runner.py).

# Loại sự kiện: nhãn hiển thị, mặc định bật/tắt, phạm vi nhận.
# scope "owner": chủ run/export/batch; "admin": mọi ADMIN.
EVENT_TYPES: dict[str, dict[str, Any]] = {
    "RUN_FAILED": {"label": "Run đối soát lỗi", "default": True, "scope": "owner"},
    "RUN_DONE": {"label": "Run đối soát xong", "default": False, "scope": "owner"},
    "REPORT_RUN_FAILED": {"label": "Chạy báo cáo lỗi", "default": True, "scope": "owner"},
    "REPORT_RUN_DONE": {"label": "Chạy báo cáo xong", "default": False, "scope": "owner"},
    "EXPORT_FAILED": {"label": "Xuất Excel lỗi", "default": True, "scope": "owner"},
    "EXPORT_DONE": {"label": "Xuất Excel xong", "default": False, "scope": "owner"},
    "BATCH_FAILED": {"label": "Chạy bộ lỗi", "default": True, "scope": "owner"},
    "BATCH_DONE": {"label": "Chạy bộ xong", "default": False, "scope": "owner"},
    "WORKER_DOWN": {"label": "Worker ngừng hoạt động", "default": True, "scope": "admin"},
    "QUEUE_STUCK": {"label": "Hàng đợi có mục kẹt", "default": True, "scope": "admin"},
    "MIGRATION_DONE": {"label": "Chuyển Oracle xong", "default": True, "scope": "admin"},
    "MIGRATION_FAILED": {"label": "Chuyển Oracle lỗi", "default": True, "scope": "admin"},
}

# Chống spam thông báo hệ thống: tối đa 1 lần mỗi loại trong 60 phút.
SYSTEM_DEDUP_MINUTES = 60

# Nhóm hiển thị trên trang cài đặt.
EVENT_GROUPS: list[dict[str, Any]] = [
    {"label": "Run đối soát", "types": ["RUN_FAILED", "RUN_DONE"]},
    {"label": "Báo cáo", "types": ["REPORT_RUN_FAILED", "REPORT_RUN_DONE"]},
    {"label": "Xuất Excel", "types": ["EXPORT_FAILED", "EXPORT_DONE"]},
    {"label": "Chạy bộ", "types": ["BATCH_FAILED", "BATCH_DONE"]},
    {"label": "Hệ thống (chỉ ADMIN)", "types": ["WORKER_DOWN", "QUEUE_STUCK", "MIGRATION_DONE", "MIGRATION_FAILED"]},
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _notif_dict(row: Any) -> dict[str, Any]:
    created = row["CREATED_AT"]
    return {
        "id": int(row["ID"]),
        "type": str(row["TYPE"]),
        "type_label": str(EVENT_TYPES.get(str(row["TYPE"]), {}).get("label") or str(row["TYPE"])),
        "title": str(row["TITLE"]),
        "message": str(row["MESSAGE"] or ""),
        "link": str(row["LINK"] or ""),
        "is_read": str(row["IS_READ"]) == "Y",
        "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
    }


def insert_notification(
    engine: Any,
    user_id: int,
    event_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> int | None:
    """Chèn 1 thông báo; trả id, None khi lỗi (không raise)."""
    if event_type not in EVENT_TYPES:
        logger.warn("Loại thông báo không hỗ trợ", event_type=event_type)
        return None
    try:
        with engine.begin() as conn:
            res = conn.execute(
                recon_notification.insert().values(
                    USER_ID=int(user_id),
                    TYPE=event_type,
                    TITLE=str(title)[:200],
                    MESSAGE=str(message or "")[:1000] or None,
                    LINK=str(link or "")[:500] or None,
                    IS_READ="N",
                    CREATED_AT=_now(),
                )
            )
            return int(res.lastrowid)
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không tạo được thông báo", event_type=event_type, error=str(exc))
        return None


def is_enabled(engine: Any, user_id: int, event_type: str) -> bool:
    """User có bật loại sự kiện này không (thiếu dòng = mặc định)."""
    default = bool(EVENT_TYPES.get(event_type, {}).get("default", False))
    try:
        with engine.connect() as conn:
            row = conn.execute(
                select(recon_notification_pref.c.ENABLED).where(
                    recon_notification_pref.c.USER_ID == int(user_id),
                    recon_notification_pref.c.EVENT_TYPE == event_type,
                )
            ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 — lỗi đọc thì dùng mặc định
        logger.warn("Không đọc được pref thông báo", event_type=event_type, error=str(exc))
        return default
    if row is None:
        return default
    return str(row) == "Y"


def _user_id_by_username(conn: Any, username: str) -> int | None:
    row = conn.execute(
        select(recon_user.c.ID).where(
            recon_user.c.USERNAME == username,
            recon_user.c.IS_ACTIVE == "Y",
        )
    ).scalar_one_or_none()
    return int(row) if row is not None else None


def notify_user(
    engine: Any,
    username: str,
    event_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> bool:
    """Báo cho 1 user theo username (kiểm tra pref); không raise."""
    try:
        with engine.connect() as conn:
            user_id = _user_id_by_username(conn, username)
        if user_id is None:
            return False
        if not is_enabled(engine, user_id, event_type):
            return False
        return insert_notification(engine, user_id, event_type, title, message, link) is not None
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không gửi được thông báo", username=username, event_type=event_type, error=str(exc))
        return False


def _admin_user_ids(conn: Any) -> list[int]:
    rows = conn.execute(
        select(recon_user.c.ID)
        .join(recon_user_role, recon_user_role.c.USER_ID == recon_user.c.ID)
        .join(recon_role, recon_role.c.ID == recon_user_role.c.ROLE_ID)
        .where(
            recon_role.c.CODE == "ADMIN",
            recon_user.c.IS_ACTIVE == "Y",
            recon_role.c.IS_ACTIVE == "Y",
        )
        .distinct()
    ).all()
    return [int(r[0]) for r in rows]


def notify_admins(
    engine: Any,
    event_type: str,
    title: str,
    message: str,
    link: str | None = None,
    dedup_minutes: int = SYSTEM_DEDUP_MINUTES,
) -> int:
    """Báo cho mọi ADMIN (kiểm tra pref từng người); không raise.

    dedup_minutes > 0: đã có thông báo cùng loại trong khoảng đó thì
    không tạo thêm (chống spam WORKER_DOWN/QUEUE_STUCK).
    """
    try:
        if dedup_minutes > 0:
            cutoff = _now() - timedelta(minutes=dedup_minutes)
            with engine.connect() as conn:
                recent = conn.execute(
                    select(func.count())
                    .select_from(recon_notification)
                    .where(
                        recon_notification.c.TYPE == event_type,
                        recon_notification.c.CREATED_AT >= cutoff,
                    )
                ).scalar_one()
            if int(recent or 0) > 0:
                return 0
        with engine.connect() as conn:
            admin_ids = _admin_user_ids(conn)
        created = 0
        for user_id in admin_ids:
            if not is_enabled(engine, user_id, event_type):
                continue
            if insert_notification(engine, user_id, event_type, title, message, link) is not None:
                created += 1
        return created
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không gửi được thông báo hệ thống", event_type=event_type, error=str(exc))
        return 0


def _owner_link(
    engine: Any,
    table: Any,
    row_id: int,
    link_template: str,
) -> tuple[str, str] | None:
    """(owner username, link) của 1 dòng run/export/batch; None nếu không thấy."""
    try:
        with engine.connect() as conn:
            row = conn.execute(select(table).where(table.c.ID == int(row_id))).mappings().first()
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không đọc được dòng để báo", table=str(table.name), error=str(exc))
        return None
    if row is None:
        return None
    return str(row["CREATED_BY"]), link_template.format(id=int(row_id), row=dict(row))


def notify_for_run(engine: Any, run_id: int, event_type: str, title: str, message: str) -> bool:
    """Báo cho chủ run đối soát; link /runs/<id>."""
    found = _owner_link(engine, recon_run, run_id, "/runs/{id}")
    if found is None:
        return False
    owner, link = found
    return notify_user(engine, owner, event_type, title, message, link)


def notify_for_report_run(engine: Any, run_id: int, event_type: str, title: str, message: str) -> bool:
    """Báo cho chủ run báo cáo; link viewer ?run=<id>."""
    try:
        with engine.connect() as conn:
            row = conn.execute(select(recon_report_run).where(recon_report_run.c.ID == int(run_id))).mappings().first()
    except Exception as exc:  # noqa: BLE001 — emit không được raise
        logger.warn("Không đọc được run báo cáo để báo", error=str(exc))
        return False
    if row is None:
        return False
    link = f"/reports/{int(row['REPORT_ID'])}?run={int(run_id)}"
    return notify_user(engine, str(row["CREATED_BY"]), event_type, title, message, link)


def notify_for_export(engine: Any, export_id: int, event_type: str, title: str, message: str) -> bool:
    """Báo cho chủ export; link /report-runs."""
    found = _owner_link(engine, recon_rpt_export, export_id, "/report-runs")
    if found is None:
        return False
    owner, link = found
    return notify_user(engine, owner, event_type, title, message, link)


def notify_for_batch(engine: Any, batch_run_id: int, event_type: str, title: str, message: str) -> bool:
    """Báo cho chủ lần chạy bộ; link trang kết quả của bộ."""
    found = _owner_link(engine, recon_batch_run, batch_run_id, "/batch-runs/{id}/result")
    if found is None:
        return False
    owner, link = found
    return notify_user(engine, owner, event_type, title, message, link)


def count_unread(engine: Any, user_id: int) -> int:
    """Số thông báo chưa đọc của user (badge chuông); lỗi -> 0."""
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    select(func.count())
                    .select_from(recon_notification)
                    .where(
                        recon_notification.c.USER_ID == int(user_id),
                        recon_notification.c.IS_READ == "N",
                    )
                ).scalar_one()
            )
    except Exception as exc:  # noqa: BLE001 — badge không được vỡ
        logger.warn("Không đếm được thông báo chưa đọc", error=str(exc))
        return 0


def _count_stuck_items(engine: Any, stale_running_seconds: int, stuck_queued_minutes: int) -> int:
    """Số mục kẹt toàn hệ thống (cùng điều kiện danh sách kẹt task 62).

    Export QUEUED quá 30 phút, export RUNNING quá hạn heartbeat 300s,
    run báo cáo QUEUED quá 30 phút.
    """
    now = _now()
    queued_cutoff = now - timedelta(minutes=stuck_queued_minutes)
    stale_threshold = now - timedelta(seconds=stale_running_seconds)
    with engine.connect() as conn:
        n_exp_queued = int(
            conn.execute(
                select(func.count())
                .select_from(recon_rpt_export)
                .where(
                    recon_rpt_export.c.STATUS == "QUEUED",
                    recon_rpt_export.c.CREATED_AT < queued_cutoff,
                )
            ).scalar_one()
        )
        n_exp_running = int(
            conn.execute(
                select(func.count())
                .select_from(recon_rpt_export)
                .where(
                    recon_rpt_export.c.STATUS == "RUNNING",
                    (recon_rpt_export.c.HEARTBEAT_AT < stale_threshold)
                    | (recon_rpt_export.c.HEARTBEAT_AT.is_(None) & (recon_rpt_export.c.LOCKED_AT < stale_threshold)),
                )
            ).scalar_one()
        )
        n_run_queued = int(
            conn.execute(
                select(func.count())
                .select_from(recon_report_run)
                .where(
                    recon_report_run.c.STATUS == "QUEUED",
                    recon_report_run.c.CREATED_AT < queued_cutoff,
                )
            ).scalar_one()
        )
    return n_exp_queued + n_exp_running + n_run_queued


def maybe_notify_worker_health(engine: Any) -> dict[str, Any]:
    """Kiểm tra sức khỏe worker + hàng đợi, báo ADMIN khi có vấn đề.

    Chạy ở tiến trình app (callback Interval đếm badge) vì worker chết
    thì không tự báo được. Dedup 1 lần/60 phút mỗi loại. Không raise.
    """
    # Lazy import (xem NOTE ở đầu file): tránh vòng tròn import.
    from app.services.worker_health import STALE_RUNNING_SECONDS, STUCK_QUEUED_MINUTES, get_worker_health

    out: dict[str, Any] = {"worker_down": False, "queue_stuck": False, "notified": 0}
    try:
        health = get_worker_health(engine)
        if str(health.get("status")) == "down":
            out["worker_down"] = True
            out["notified"] += notify_admins(
                engine,
                "WORKER_DOWN",
                "Worker ngừng hoạt động",
                "Không thấy nhịp tim worker trong 30 giây qua. Kiểm tra tiến trình worker.",
                link="/queue-health",
            )
        stuck = _count_stuck_items(engine, STALE_RUNNING_SECONDS, STUCK_QUEUED_MINUTES)
        if stuck > 0:
            out["queue_stuck"] = True
            out["notified"] += notify_admins(
                engine,
                "QUEUE_STUCK",
                "Hàng đợi có mục kẹt",
                f"Có {stuck} mục kẹt quá hạn trong hàng đợi. Xem trang Hàng đợi & worker.",
                link="/queue-health",
            )
    except Exception as exc:  # noqa: BLE001 — kiểm tra nền không được raise
        logger.warn("Không kiểm tra được sức khỏe worker để báo", error=str(exc))
    return out


# --- API theo user (menu "notifications") ---------------------------------


def _effective_prefs(engine: Any, user_id: int) -> dict[str, bool]:
    prefs = {code: bool(info["default"]) for code, info in EVENT_TYPES.items()}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                select(recon_notification_pref.c.EVENT_TYPE, recon_notification_pref.c.ENABLED).where(
                    recon_notification_pref.c.USER_ID == int(user_id)
                )
            ).all()
    except Exception as exc:  # noqa: BLE001 — lỗi đọc thì dùng mặc định
        logger.warn("Không đọc được pref thông báo", error=str(exc))
        return prefs
    for code, enabled in rows:
        if code in prefs:
            prefs[str(code)] = str(enabled) == "Y"
    return prefs


@service
@requires_menu("notifications")
def list_notifications(ctx: Ctx, page: int = 1, page_size: int = 20, unread_only: bool = False) -> dict[str, Any]:
    """Liệt kê thông báo của mình: chưa đọc trước, mới nhất trước."""
    if page < 1:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page phải ≥ 1.")
    if page_size < 1 or page_size > 100:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "page_size phải trong khoảng 1..100.")
    engine = get_recon_engine()
    with engine.connect() as conn:
        total_stmt = (
            select(func.count()).select_from(recon_notification).where(recon_notification.c.USER_ID == ctx.user_id)
        )
        stmt = select(recon_notification).where(recon_notification.c.USER_ID == ctx.user_id)
        if unread_only:
            total_stmt = total_stmt.where(recon_notification.c.IS_READ == "N")
            stmt = stmt.where(recon_notification.c.IS_READ == "N")
        total = int(conn.execute(total_stmt).scalar_one())
        rows = (
            conn.execute(
                stmt.order_by(
                    recon_notification.c.IS_READ.asc(),
                    recon_notification.c.CREATED_AT.desc(),
                    recon_notification.c.ID.desc(),
                )
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .mappings()
            .all()
        )
    return {
        "items": [_notif_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "unread": count_unread(engine, ctx.user_id),
    }


@service
@requires_menu("notifications")
def unread_count(ctx: Ctx) -> dict[str, Any]:
    """Số thông báo chưa đọc của mình (badge chuông)."""
    return {"unread": count_unread(get_recon_engine(), ctx.user_id)}


@service
@requires_menu("notifications")
def mark_read(ctx: Ctx, notification_id: int) -> dict[str, Any]:
    """Đánh dấu 1 thông báo của mình là đã đọc."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        res = conn.execute(
            recon_notification.update()
            .where(
                recon_notification.c.ID == int(notification_id),
                recon_notification.c.USER_ID == ctx.user_id,
            )
            .values(IS_READ="Y")
        )
        if res.rowcount == 0:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy thông báo.")
    return {"id": int(notification_id)}


@service
@requires_menu("notifications")
def mark_all_read(ctx: Ctx) -> dict[str, Any]:
    """Đánh dấu tất cả thông báo của mình là đã đọc."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        res = conn.execute(
            recon_notification.update()
            .where(
                recon_notification.c.USER_ID == ctx.user_id,
                recon_notification.c.IS_READ == "N",
            )
            .values(IS_READ="Y")
        )
    return {"updated": int(res.rowcount)}


@service
@requires_menu("notifications")
def delete_notification(ctx: Ctx, notification_id: int) -> dict[str, Any]:
    """Xóa 1 thông báo của mình."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        res = conn.execute(
            recon_notification.delete().where(
                recon_notification.c.ID == int(notification_id),
                recon_notification.c.USER_ID == ctx.user_id,
            )
        )
        if res.rowcount == 0:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy thông báo.")
    return {"id": int(notification_id)}


@service
@requires_menu("notifications")
def get_prefs(ctx: Ctx) -> dict[str, Any]:
    """Cài đặt nhận thông báo của mình (mọi loại + giá trị hiệu lực)."""
    engine = get_recon_engine()
    return {
        "prefs": _effective_prefs(engine, ctx.user_id),
        "types": [
            {"code": code, "label": str(info["label"]), "default": bool(info["default"]), "scope": str(info["scope"])}
            for code, info in EVENT_TYPES.items()
        ],
        "groups": EVENT_GROUPS,
    }


@service
@requires_menu("notifications")
def set_prefs(ctx: Ctx, prefs: dict[str, Any]) -> dict[str, Any]:
    """Lưu cài đặt nhận thông báo của mình (chỉ loại đã biết)."""
    if not isinstance(prefs, dict):
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "prefs phải là dict.")
    cleaned: dict[str, bool] = {}
    for code, value in prefs.items():
        if code not in EVENT_TYPES:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Loại thông báo không hỗ trợ: {code}.")
        if not isinstance(value, bool):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Giá trị của {code} phải là true/false.")
        cleaned[str(code)] = bool(value)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        for code, enabled in cleaned.items():
            existing = conn.execute(
                select(recon_notification_pref.c.USER_ID).where(
                    recon_notification_pref.c.USER_ID == ctx.user_id,
                    recon_notification_pref.c.EVENT_TYPE == code,
                )
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(
                    recon_notification_pref.insert().values(
                        USER_ID=ctx.user_id, EVENT_TYPE=code, ENABLED="Y" if enabled else "N", UPDATED_AT=now
                    )
                )
            else:
                conn.execute(
                    recon_notification_pref.update()
                    .where(
                        recon_notification_pref.c.USER_ID == ctx.user_id,
                        recon_notification_pref.c.EVENT_TYPE == code,
                    )
                    .values(ENABLED="Y" if enabled else "N", UPDATED_AT=now)
                )
    return {"prefs": _effective_prefs(engine, ctx.user_id)}
