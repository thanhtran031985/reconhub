from __future__ import annotations

import threading
import time

import structlog

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.dialect import get_dialect
from app.db.engine import get_db_engine

logger = structlog.get_logger("worker")


class ReconWorker:
    """Worker xử lý hàng đợi RECON_RUN_QUEUE."""

    def __init__(self, poll_interval: float | None = None) -> None:
        settings = get_settings()
        self.poll_interval = poll_interval if poll_interval is not None else float(settings.WORKER_POLL_SECONDS)
        self.engine = get_db_engine()
        self.dialect = get_dialect(self.engine)
        self.worker_id = f"worker-{int(time.time())}"

    def poll_once(self) -> bool:
        """Kiểm tra và nhận 1 job từ hàng đợi nếu có."""
        try:
            job_id = self.dialect.claim_next_queued_job(locked_by=self.worker_id)
            if job_id is not None:
                logger.info("Nhận job từ hàng đợi", run_id=job_id, worker_id=self.worker_id)
                # Nghiệp vụ xử lý run sẽ được tích hợp ở task 07
                return True
        except Exception as exc:
            logger.error("Lỗi khi kiểm tra hàng đợi", error=str(exc))
        return False

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Vòng lặp chính của worker."""
        setup_logging()
        logger.info("Worker khởi động", worker_id=self.worker_id, poll_interval=self.poll_interval)

        heartbeat_counter = 0
        while stop_event is None or not stop_event.is_set():
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
