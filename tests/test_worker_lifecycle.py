from __future__ import annotations

import threading
import time


def test_worker_starts_and_stops_cleanly() -> None:
    from worker.runner import ReconWorker

    worker = ReconWorker(poll_interval=0.1)
    stop_event = threading.Event()

    t = threading.Thread(target=worker.run, args=(stop_event,), daemon=True)
    t.start()

    # Để worker chạy ít nhất 1 chu kỳ heartbeat
    time.sleep(0.3)
    assert t.is_alive()

    # Ra lệnh dừng
    stop_event.set()
    t.join(timeout=2.0)

    # Đảm bảo thread đã dừng hoàn toàn
    assert not t.is_alive(), "Worker phải dừng sạch sau khi nhận stop_event"
