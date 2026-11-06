"""Worker xử lý hàng đợi export RECON_RPT_EXPORT — task 26.

Theo mẫu worker/runner.py (ReconWorker): claim nguyên tử, heartbeat,
reset stale, vòng poll.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.db.dialect import get_dialect
from app.db.engine import get_db_engine
from app.db.metadata import recon_rpt_export
from app.services.report_export import MAX_RUNNING_PER_USER, execute_export

logger = structlog.get_logger("export-worker")


class ReportExportWorker:
    """Worker xử lý hàng đợi RECON_RPT_EXPORT."""

    def __init__(
        self,
        poll_interval: float | None = None,
        max_per_user: int = MAX_RUNNING_PER_USER,
        engine: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else float(settings.WORKER_POLL_SECONDS)
        )
        self.max_per_user = max_per_user
        self.engine = engine or get_db_engine()
        self.dialect = get_dialect(self.engine)
        self.worker_id = f"export-worker-{int(time.time())}"

    def reset_stale_exports(self, timeout_seconds: int = 300) -> int:
        """Export RUNNING quá hạn heartbeat → FAILED (worker trước bị ngắt)."""
        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=timeout_seconds
        )
        reset_count = 0
        with self.engine.begin() as conn:
            stmt = select(recon_rpt_export.c.ID).where(
                recon_rpt_export.c.STATUS == "RUNNING",
                (recon_rpt_export.c.HEARTBEAT_AT < threshold)
                | (
                    recon_rpt_export.c.HEARTBEAT_AT.is_(None)
                    & (recon_rpt_export.c.LOCKED_AT < threshold)
                ),
            )
            stale_ids = [int(r[0]) for r in conn.execute(stmt).fetchall()]
            for export_id in stale_ids:
                logger.warn(
                    "Phát hiện export bị treo quá hạn, chuyển sang FAILED",
                    export_id=export_id,
                )
                conn.execute(
                    recon_rpt_export.update()
                    .where(recon_rpt_export.c.ID == export_id)
                    .values(
                        STATUS="FAILED",
                        ERROR_MESSAGE="Worker bị ngắt đột ngột, export bị treo.",
                        FINISHED_AT=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )
                reset_count += 1
        return reset_count

    def _start_heartbeat(
        self, export_id: int, stop_ev: threading.Event
    ) -> threading.Thread:
        """Thread gửi tín hiệu nhịp tim định kỳ trong lúc export đang chạy."""

        def hb_worker() -> None:
            while not stop_ev.wait(timeout=3.0):
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                try:
                    with self.engine.begin() as conn:
                        conn.execute(
                            recon_rpt_export.update()
                            .where(recon_rpt_export.c.ID == export_id)
                            .values(HEARTBEAT_AT=now)
                        )
                except Exception as exc:
                    logger.warn(
                        "Không thể cập nhật heartbeat export",
                        export_id=export_id,
                        error=str(exc),
                    )

        t = threading.Thread(target=hb_worker, daemon=True)
        t.start()
        return t

    def poll_once(self) -> bool:
        """Nhận 1 export từ hàng đợi nếu có (tôn trọng giới hạn mỗi user)."""
        try:
            export_id = self.dialect.claim_next_queued_export(
                locked_by=self.worker_id, max_per_user=self.max_per_user
            )
            if export_id is not None:
                logger.info(
                    "Nhận export từ hàng đợi",
                    export_id=export_id,
                    worker_id=self.worker_id,
                )
                stop_hb = threading.Event()
                hb_thread = self._start_heartbeat(export_id, stop_hb)
                try:
                    execute_export(export_id, engine=self.engine)
                finally:
                    stop_hb.set()
                    hb_thread.join(timeout=1.0)
                return True
        except Exception as exc:
            logger.error(
                "Lỗi khi kiểm tra hoặc thực thi export từ hàng đợi",
                error=str(exc),
            )
        return False

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Vòng lặp chính của worker export."""
        logger.info(
            "Worker export khởi động",
            worker_id=self.worker_id,
            poll_interval=self.poll_interval,
        )
        while stop_event is None or not stop_event.is_set():
            self.reset_stale_exports()
            self.poll_once()
            if stop_event is not None:
                if stop_event.wait(timeout=self.poll_interval):
                    break
            else:
                time.sleep(self.poll_interval)
        logger.info("Worker export đã dừng sạch sẽ", worker_id=self.worker_id)
