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
from app.services.export_retention import (
    SWEEP_INTERVAL_SECONDS,
    get_export_max_concurrent,
    sweep_old_exports,
)
from app.services.notification import notify_for_export
from app.services.report_export import MAX_RUNNING_PER_USER, execute_export
from app.services.worker_health import write_worker_heartbeat

logger = structlog.get_logger("export-worker")


class ReportExportWorker:
    """Worker xử lý hàng đợi RECON_RPT_EXPORT.

    Task 57: chạy song song tối đa N export (mặc định 10, theo setting
    EXPORT_MAX_CONCURRENT) — mỗi export chạy trong 1 thread riêng, vòng
    poll claim thêm việc tới khi đủ N. Giới hạn mỗi user trong claim
    cũng = N (cùng 1 con số, tránh 2 cài đặt lệch nhau).
    """

    def __init__(
        self,
        poll_interval: float | None = None,
        max_per_user: int | None = None,
        engine: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else float(settings.WORKER_POLL_SECONDS)
        )
        # None = đọc setting EXPORT_MAX_CONCURRENT mỗi vòng poll; số
        # truyền vào (chủ yếu cho test) thắng setting.
        self.max_per_user = max_per_user
        self.engine = engine or get_db_engine()
        self.dialect = get_dialect(self.engine)
        self.worker_id = f"export-worker-{int(time.time())}"
        self._last_sweep_at: datetime | None = None
        # Thread đang chạy export — chỉ vòng poll chính động vào list
        # này (prune + thêm), thread con không chạm tới nên không cần lock.
        self._threads: list[threading.Thread] = []

    def maybe_sweep_old_exports(self) -> int:
        """Dọn file export quá hạn (task 52): tối đa 1 lần/giờ, chỉ khi
        mode=scheduler. Trả số file đã xóa."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if (
            self._last_sweep_at is not None
            and (now - self._last_sweep_at).total_seconds() < SWEEP_INTERVAL_SECONDS
        ):
            return 0
        self._last_sweep_at = now
        try:
            deleted = sweep_old_exports(self.engine)
        except Exception as exc:
            logger.warn("Không thể dọn file export cũ", error=str(exc))
            return 0
        if deleted:
            logger.info("Đã dọn file export quá hạn", deleted=deleted)
        return deleted

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
        # Task 78: báo chủ export bị treo (mỗi export chỉ reset 1 lần nên không spam).
        for export_id in stale_ids:
            notify_for_export(
                self.engine,
                export_id,
                "EXPORT_FAILED",
                f"Xuất Excel #{export_id} lỗi",
                "Worker bị ngắt đột ngột, export bị treo.",
            )
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

    def _current_limit(self) -> int:
        """Giới hạn song song hiện tại: tham số khởi tạo (nếu có), rồi
        tới setting EXPORT_MAX_CONCURRENT, lỗi đọc thì về mặc định 10."""
        if self.max_per_user is not None:
            return max(1, int(self.max_per_user))
        try:
            return get_export_max_concurrent(self.engine)
        except Exception as exc:
            logger.warn("Không đọc được cài đặt song song export", error=str(exc))
            return MAX_RUNNING_PER_USER

    def _prune_threads(self) -> None:
        self._threads = [t for t in self._threads if t.is_alive()]

    def _run_export(self, export_id: int) -> None:
        """Chạy 1 export trong thread riêng (heartbeat + execute)."""
        stop_hb = threading.Event()
        hb_thread = self._start_heartbeat(export_id, stop_hb)
        try:
            execute_export(export_id, engine=self.engine)
        finally:
            stop_hb.set()
            hb_thread.join(timeout=1.0)

    def poll_once(self) -> bool:
        """Nhận 1 export từ hàng đợi và chạy trong thread riêng (task 57).

        Trả True nếu đã nhận việc (thread đang chạy); False nếu không có
        việc trong hàng đợi hoặc đã đủ số luồng song song. Lỗi claim thì
        False (ghi log, vòng sau thử lại).
        """
        self._prune_threads()
        limit = self._current_limit()
        if len(self._threads) >= limit:
            return False
        try:
            export_id = self.dialect.claim_next_queued_export(
                locked_by=self.worker_id, max_per_user=limit
            )
            if export_id is None:
                return False
            logger.info(
                "Nhận export từ hàng đợi",
                export_id=export_id,
                worker_id=self.worker_id,
            )
            thread = threading.Thread(
                target=self._run_export, args=(export_id,), daemon=True
            )
            thread.start()
            self._threads.append(thread)
            return True
        except Exception as exc:
            logger.error(
                "Lỗi khi kiểm tra hoặc thực thi export từ hàng đợi",
                error=str(exc),
            )
        return False

    def wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Chờ mọi thread export xong (cho test). Trả False nếu hết giờ."""
        deadline = time.monotonic() + timeout
        while True:
            self._prune_threads()
            if not self._threads:
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.1)

    def run(self, stop_event: threading.Event | None = None) -> None:
        """Vòng lặp chính của worker export."""
        logger.info(
            "Worker export khởi động",
            worker_id=self.worker_id,
            poll_interval=self.poll_interval,
        )
        while stop_event is None or not stop_event.is_set():
            # Task 62: nhịp tim worker — ghi mỗi vòng poll để dashboard
            # biết worker còn sống; lỗi ghi không được làm chết worker.
            try:
                write_worker_heartbeat(self.engine, self.worker_id, "export")
            except Exception as exc:  # noqa: BLE001 - nhịp tim là phụ
                logger.warn("Không ghi được nhịp tim worker", error=str(exc))
            self.reset_stale_exports()
            self.maybe_sweep_old_exports()
            # Task 57: claim thêm việc tới khi đủ N luồng (hoặc hết hàng).
            while self.poll_once():
                pass
            if stop_event is not None:
                if stop_event.wait(timeout=self.poll_interval):
                    break
            else:
                time.sleep(self.poll_interval)
        logger.info("Worker export đã dừng sạch sẽ", worker_id=self.worker_id)
