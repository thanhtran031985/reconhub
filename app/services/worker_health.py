"""Sức khỏe hàng đợi & worker (task 62).

- Nhịp tim worker: mỗi vòng poll, cả 2 luồng worker (đối soát + export)
  ghi worker_id + thời gian vào RECON_APP_SETTING (không cần migration,
  đúng pattern setting EXPORT_MAX_CONCURRENT/retention). Dashboard coi
  worker "Đang chạy" khi nhịp tim mới hơn 30 giây.
- Thống kê hàng đợi + danh sách kẹt: đếm export/run theo trạng thái
  (owner scope như list_exports/list_report_runs), danh sách kẹt gồm
  export/run QUEUED quá 30 phút chưa được nhận và export RUNNING quá
  hạn heartbeat 300s (chỉ liệt kê — reset_stale đã tự FAILED).
  Follow-up task 66 trả thêm "active": mọi export QUEUED/RUNNING +
  mọi run QUEUED (tối đa 50) để tab hiện hàng đợi đang hoạt động.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_report,
    recon_report_run,
    recon_rpt_export,
)
from app.services import service
from app.services.export_retention import get_export_max_concurrent
from app.services.perm import is_admin, requires_menu

HEARTBEAT_STALE_SECONDS = 30
STUCK_QUEUED_MINUTES = 30
STALE_RUNNING_SECONDS = 300
STUCK_LIST_LIMIT = 20
# Follow-up task 66: bảng Đang chạy / Đang chờ liệt kê tối đa 50 mục.
ACTIVE_LIST_LIMIT = 50

HEARTBEAT_KEYS = {"recon": "WORKER_HEARTBEAT_RECON", "export": "WORKER_HEARTBEAT_EXPORT"}
WORKER_KIND_LABELS = {"recon": "Đối soát", "export": "Export"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _upsert_setting(conn: Any, key: str, value: str, updated_by: str) -> None:
    """Ghi đè 1 key RECON_APP_SETTING (mẫu set_export_retention)."""
    now = _now()
    existing = conn.execute(select(recon_app_setting.c.KEY).where(recon_app_setting.c.KEY == key)).scalar_one_or_none()
    if existing is None:
        conn.execute(recon_app_setting.insert().values(KEY=key, VALUE=value, UPDATED_BY=updated_by, UPDATED_AT=now))
    else:
        conn.execute(
            recon_app_setting.update()
            .where(recon_app_setting.c.KEY == key)
            .values(VALUE=value, UPDATED_BY=updated_by, UPDATED_AT=now)
        )


def write_worker_heartbeat(engine: Any, worker_id: str, kind: str, now: datetime | None = None) -> dict[str, Any]:
    """Ghi nhịp tim của 1 luồng worker (worker dùng, không cần ctx).

    kind: "recon" (worker đối soát) hoặc "export" (worker export).
    VALUE = thời gian ISO (UTC, naive); UPDATED_BY = worker_id.
    """
    if kind not in HEARTBEAT_KEYS:
        raise ValueError(f"Loại worker không hỗ trợ: {kind}")
    ts = now or _now()
    with engine.begin() as conn:
        _upsert_setting(conn, HEARTBEAT_KEYS[kind], ts.isoformat(), str(worker_id))
    return {"kind": kind, "worker_id": str(worker_id), "last_seen": ts.isoformat()}


def _read_heartbeat(engine: Any, kind: str) -> tuple[datetime | None, str | None]:
    with engine.connect() as conn:
        row = (
            conn.execute(select(recon_app_setting).where(recon_app_setting.c.KEY == HEARTBEAT_KEYS[kind]))
            .mappings()
            .first()
        )
    if row is None:
        return None, None
    try:
        last_seen = datetime.fromisoformat(str(row["VALUE"]))
    except ValueError:
        return None, None
    return last_seen, str(row["UPDATED_BY"])


def get_worker_health(engine: Any, now: datetime | None = None) -> dict[str, Any]:
    """Trạng thái worker theo nhịp tim (worker + dashboard dùng).

    status: "running" (cả 2 luồng đều mới), "partial" (1 luồng mới),
    "down" (không luồng nào mới — gồm cả chưa từng chạy).
    """
    now = now or _now()
    workers: dict[str, Any] = {}
    fresh: list[bool] = []
    for kind in ("recon", "export"):
        last_seen, worker_id = _read_heartbeat(engine, kind)
        alive = last_seen is not None and (now - last_seen).total_seconds() <= HEARTBEAT_STALE_SECONDS
        workers[kind] = {
            "alive": alive,
            "last_seen": last_seen.isoformat() if last_seen is not None else None,
            "worker_id": worker_id,
        }
        fresh.append(alive)
    if all(fresh):
        status = "running"
    elif any(fresh):
        status = "partial"
    else:
        status = "down"
    return {"status": status, "workers": workers}


def _counts_by_status(conn: Any, table: Any, owner: str | None) -> dict[str, int]:
    stmt = select(table.c.STATUS, func.count()).group_by(table.c.STATUS)
    if owner is not None:
        stmt = stmt.where(table.c.CREATED_BY == owner)
    return {str(status): int(count) for status, count in conn.execute(stmt).all()}


def _queue_item(
    kind: str,
    row: Any,
    now: datetime,
    *,
    admin: bool,
    username: str,
    stale_heartbeat: bool = False,
) -> dict[str, Any]:
    """1 mục hàng đợi (export/run) theo đúng shape của danh sách kẹt.

    Dùng chung cho cả "active" (mọi export QUEUED/RUNNING + run QUEUED,
    follow-up task 66) và "stuck". can_cancel theo đúng luật service hủy:
    export chỉ chủ mới hủy được (kể cả ADMIN cũng chỉ hủy của mình);
    run thì ADMIN hoặc chủ mới hủy được.
    """
    return {
        "kind": kind,
        "id": int(row["ID"]),
        "run_id": int(row["RUN_ID"]) if kind == "export" else int(row["ID"]),
        "report_name": str(row["report_name"] or ""),
        "created_by": str(row["CREATED_BY"]),
        "created_at": row["CREATED_AT"].isoformat(),
        "age_minutes": int((now - row["CREATED_AT"]).total_seconds() // 60),
        "status": str(row["STATUS"]),
        "stale_heartbeat": stale_heartbeat,
        "can_cancel": bool(row["CREATED_BY"] == username)
        if kind == "export"
        else bool(admin or row["CREATED_BY"] == username),
    }


@service
@requires_menu("queue_health")
def get_queue_health(ctx: Ctx, now: datetime | None = None) -> dict[str, Any]:
    """Thống kê hàng đợi + danh sách kẹt cho trang Hàng đợi & worker (task 66,
    tách khỏi dashboard — trước task 66 là thẻ dashboard, menu "dashboard").

    Owner scope như list_exports/list_report_runs: không phải ADMIN chỉ
    thấy mục của mình. Danh sách kẹt (tối đa 20, cũ nhất trước):
    - export/run QUEUED quá 30 phút chưa được nhận (theo CREATED_AT);
    - export RUNNING quá hạn heartbeat 300s (cùng điều kiện reset_stale).
    Run RUNNING không liệt kê kẹt vì RECON_REPORT_RUN không có cột
    heartbeat để đánh giá. Follow-up task 66 trả thêm "active": mọi
    export QUEUED/RUNNING + mọi run QUEUED (cũ nhất trước, tối đa 50),
    để tab hiện cả hàng đợi đang hoạt động, không chỉ mục kẹt.
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    now = now or _now()
    owner = None if admin else ctx.username
    queued_cutoff = now - timedelta(minutes=STUCK_QUEUED_MINUTES)
    stale_threshold = now - timedelta(seconds=STALE_RUNNING_SECONDS)

    with engine.connect() as conn:
        export_counts = _counts_by_status(conn, recon_rpt_export, owner)
        run_counts = _counts_by_status(conn, recon_report_run, owner)

        exp_stmt = (
            select(recon_rpt_export, recon_report.c.NAME.label("report_name"))
            .join(recon_report_run, recon_report_run.c.ID == recon_rpt_export.c.RUN_ID)
            .join(recon_report, recon_report.c.ID == recon_report_run.c.REPORT_ID)
            .where(recon_rpt_export.c.STATUS.in_(("QUEUED", "RUNNING")))
            .order_by(recon_rpt_export.c.CREATED_AT.asc())
        )
        if owner is not None:
            exp_stmt = exp_stmt.where(recon_rpt_export.c.CREATED_BY == owner)
        exp_rows = conn.execute(exp_stmt).mappings().all()

        run_stmt = (
            select(recon_report_run, recon_report.c.NAME.label("report_name"))
            .join(recon_report, recon_report.c.ID == recon_report_run.c.REPORT_ID)
            .where(recon_report_run.c.STATUS == "QUEUED")
            .order_by(recon_report_run.c.CREATED_AT.asc())
        )
        if owner is not None:
            run_stmt = run_stmt.where(recon_report_run.c.CREATED_BY == owner)
        run_rows = conn.execute(run_stmt).mappings().all()

    stuck: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for row in exp_rows:
        created = row["CREATED_AT"]
        heartbeat_at = row["HEARTBEAT_AT"]
        locked_at = row["LOCKED_AT"]
        if row["STATUS"] == "QUEUED":
            is_stuck = created < queued_cutoff
            stale_hb = False
        else:  # RUNNING: cùng điều kiện reset_stale_exports
            is_stuck = (heartbeat_at is not None and heartbeat_at < stale_threshold) or (
                heartbeat_at is None and locked_at is not None and locked_at < stale_threshold
            )
            stale_hb = bool(is_stuck)
        item = _queue_item(
            "export", row, now, admin=admin, username=ctx.username, stale_heartbeat=stale_hb
        )
        if is_stuck:
            stuck.append(item)
        active.append(item)
    for row in run_rows:
        created = row["CREATED_AT"]
        item = _queue_item("run", row, now, admin=admin, username=ctx.username)
        if created < queued_cutoff:
            stuck.append(item)
        active.append(item)
    stuck.sort(key=lambda item: item["created_at"])
    stuck = stuck[:STUCK_LIST_LIMIT]
    active.sort(key=lambda item: item["created_at"])
    active = active[:ACTIVE_LIST_LIMIT]
    return {
        "worker": get_worker_health(engine, now=now),
        "max_concurrent": get_export_max_concurrent(engine),
        "exports": export_counts,
        "runs": run_counts,
        "stuck": stuck,
        "active": active,
    }
