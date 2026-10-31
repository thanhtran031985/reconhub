#!/usr/bin/env python3
"""Chạy Dash web server và Worker nền song song trong môi trường dev.

Dừng đồng thời cả hai tiến trình khi nhận Ctrl+C.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    print("=== Khởi chạy ReconHub Dev Server (Dash + Worker) ===")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Khởi chạy Dash
    web_proc = subprocess.Popen(
        [sys.executable, "-m", "app.ui.app"],
        env=env,
    )
    print(f"-> Dash server khởi động (PID: {web_proc.pid})")

    # Khởi chạy Worker
    worker_proc = subprocess.Popen(
        [sys.executable, "-m", "worker"],
        env=env,
    )
    print(f"-> Worker khởi động (PID: {worker_proc.pid})")

    def shutdown(signum: int | None = None, frame: object = None) -> None:
        print("\n=== Đang dừng Dash server và Worker... ===")
        for proc, _name in [(web_proc, "Dash server"), (worker_proc, "Worker")]:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        # Chờ tiến trình kết thúc
        for proc, _name in [(web_proc, "Dash server"), (worker_proc, "Worker")]:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("=== Đã dừng toàn bộ dịch vụ dev ===")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    try:
        while True:
            time.sleep(1)
            # Nếu 1 trong 2 tiến trình chết, thông báo và dừng cả hai
            if web_proc.poll() is not None:
                print("Dash server đã kết thúc đột ngột.")
                shutdown()
            if worker_proc.poll() is not None:
                print("Worker đã kết thúc đột ngột.")
                shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
