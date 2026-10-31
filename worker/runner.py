from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.dialect import get_dialect
from app.db.engine import get_db_engine
from app.db.metadata import recon_run, recon_run_queue
from app.services.run_executor import execute_run

logger = structlog.get_logger("worker")


class ReconWorker:
    """Worker xử lý hàng đợi RECON_RUN_QUEUE."""

    def __init__(self, poll_interval: float | None = None) -> None:
        settings = get_settings()
        self.poll_interval = poll_interval if poll_interval is not None else float(settings.WORKER_POLL_SECONDS)
        self.engine = get_db_engine()
        self.dialect = get_dialect(self.engine)
        self.worker_id = f"worker-{int(time.time())}"

    def reset_stale_jobs(self, timeout_seconds: int = 300) -> int:
        """Kiểm tra và phục hồi/hủy các job bị treo khi worker trước đó bị ngắt đột ngột."""
        threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=timeout_seconds)
        reset_count = 0

        with self.engine.begin() as conn:
            stmt = select(recon_run_queue.c.RUN_ID).where(
                recon_run_queue.c.STATUS == "PROCESSING",
                (recon_run_queue.c.HEARTBEAT_AT < threshold)
                | (recon_run_queue.c.HEARTBEAT_AT.is_(None) & (recon_run_queue.c.LOCKED_AT < threshold)),
            )
            stale_run_ids = [int(r[0]) for r in conn.execute(stmt).fetchall()]

            for r_id in stale_run_ids:
                logger.warn("Phát hiện job bị treo quá hạn, chuyển sang ERROR", run_id=r_id)
                conn.execute(
                    recon_run_queue.update()
                    .where(recon_run_queue.c.RUN_ID == r_id)
                    .values(STATUS="ERROR")
                )
                conn.execute(
                    recon_run.update()
                    .where(recon_run.c.ID == r_id)
                    .values(
                        STATUS="FAILED",
                        STAGE="ERROR",
                        ERROR_CODE="INTERNAL_ERROR",
                        ERROR_MSG="Worker bị ngắt đột ngột, job bị treo.",
                        FINISHED_AT=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )
                reset_count += 1

        return reset_count

    def _start_heartbeat(self, run_id: int, stop_ev: threading.Event) -> threading.Thread:
        """Tạo thread gửi tín hiệu nhịp tim định kỳ trong lúc job đang chạy."""
        def hb_worker() -> None:
            while not stop_ev.wait(timeout=3.0):
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                try:
                    with self.engine.begin() as conn:
                        conn.execute(
                            recon_run_queue.update()
                            .where(recon_run_queue.c.RUN_ID == run_id)
                            .values(HEARTBEAT_AT=now)
                        )
                except Exception as exc:
                    logger.warn("Không thể cập nhật heartbeat job", run_id=run_id, error=str(exc))

        t = threading.Thread(target=hb_worker, daemon=True)
        t.start()
        return t

    def poll_once(self) -> bool:
        """Kiểm tra và nhận 1 job từ hàng đợi nếu có."""
        try:
            job_id = self.dialect.claim_next_queued_job(locked_by=self.worker_id)
            if job_id is not None:
                logger.info("Nhận job từ hàng đợi", run_id=job_id, worker_id=self.worker_id)
                stop_hb = threading.Event()
                hb_thread = self._start_heartbeat(job_id, stop_hb)
                try:
                    execute_run(job_id)
                finally:
                    stop_hb.set()
                    hb_thread.join(timeout=1.0)
                return True
        except Exception as exc:
            logger.error("Lỗi khi kiểm tra hoặc thực thi job từ hàng đợi", error=str(exc))
        return False

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Vòng lặp chính của worker."""
        setup_logging()
        logger.info("Worker khởi động", worker_id=self.worker_id, poll_interval=self.poll_interval)

        heartbeat_counter = 0
        while stop_event is None or not stop_event.is_set():
            self.reset_stale_jobs()
            self.poll_once()

            heartbeat_counter += 1
            if heartbeat_counter >= 5:
                logger.info("Heartbeat worker hoạt động", worker_id=self.worker_id)
                heartbeat_counter = 0

            # Chờ poll_interval hoặc thức dậy ngay khi stop_event được set
            if stop_event is not None:
                if stop_event.wait(timeout=self.poll_interval):
                    break
            else:
                time.sleep(self.poll_interval)

        logger.info("Worker đã dừng sạch sẽ", worker_id=self.worker_id)
