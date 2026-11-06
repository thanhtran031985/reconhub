from __future__ import annotations

import signal
import threading
from typing import Any

import structlog

from worker.export_runner import ReportExportWorker
from worker.runner import ReconWorker

logger = structlog.get_logger("worker")


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
    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        logger.info("Bắt được KeyboardInterrupt, đang dừng...")
        stop_event.set()
    recon_thread.join()
    export_thread.join()


if __name__ == "__main__":
    main()
