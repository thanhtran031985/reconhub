from __future__ import annotations

import signal
import threading
from typing import Any

import structlog

from worker.export_runner import ReportExportWorker
from worker.runner import ReconWorker

logger = structlog.get_logger("worker")


def _telegram_poller(stop_event: threading.Event, interval_seconds: float = 30.0) -> threading.Thread:
    """Poll getUpdates của bot Telegram để liên kết tài khoản (task 94).

    Vòng lặp 30s; lỗi 1 vòng không giết worker (bọc try/except quanh
    mỗi vòng, poll_telegram_updates_once bản thân nó cũng không raise).
    """

    def _run() -> None:
        from app.db.engine import get_db_engine
        from app.services.telegram_notify import poll_telegram_updates_once

        engine = get_db_engine()
        while not stop_event.is_set():
            try:
                poll_telegram_updates_once(engine)
            except Exception as exc:  # noqa: BLE001 — lỗi poll không giết worker
                logger.warn("Lỗi vòng poll Telegram", error=str(exc))
            stop_event.wait(timeout=interval_seconds)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def main() -> None:
    stop_event = threading.Event()

    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Nhận tín hiệu dừng tiến trình", signum=signum)
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if hasattr(signal, "SIGBREAK"):
        # Hỗ trợ Ctrl+Break trên Windows
        signal.signal(signal.SIGBREAK, signal_handler)

    # Hai worker chạy cùng tiến trình (task 26 Q3): recon + report export.
    recon_worker = ReconWorker()
    export_worker = ReportExportWorker()
    recon_thread = threading.Thread(
        target=recon_worker.run, args=(stop_event,), daemon=True
    )
    export_thread = threading.Thread(
        target=export_worker.run, args=(stop_event,), daemon=True
    )
    recon_thread.start()
    export_thread.start()
    # Task 94: poller Telegram (daemon, 30s/vòng) để liên kết tài khoản.
    telegram_thread = _telegram_poller(stop_event)
    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        logger.info("Bắt được KeyboardInterrupt, đang dừng...")
        stop_event.set()
    recon_thread.join()
    export_thread.join()
    telegram_thread.join()


if __name__ == "__main__":
    main()
