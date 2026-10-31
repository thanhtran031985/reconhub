from __future__ import annotations

import signal
import threading
from typing import Any

import structlog

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

    worker = ReconWorker()
    try:
        worker.run(stop_event)
    except KeyboardInterrupt:
        logger.info("Bắt được KeyboardInterrupt, đang dừng...")
        stop_event.set()


if __name__ == "__main__":
    main()
