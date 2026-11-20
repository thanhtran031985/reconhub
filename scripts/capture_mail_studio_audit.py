"""Script tự động chụp ảnh màn hình trang Mail Template Studio để rà soát UI/UX theo ReconHub Audit Rubric."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("tests/e2e/__screens__")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def is_server_ready(url: str = "http://127.0.0.1:8050/login", timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_for_server(url: str = "http://127.0.0.1:8050/login", max_wait: float = 25.0) -> bool:
    start = time.time()
    while time.time() - start < max_wait:
        if is_server_ready(url):
            return True
        time.sleep(0.5)
    return False


def capture_screens(prefix: str = "before") -> None:
    server_proc = None
    started_by_us = False

    if not is_server_ready():
        print("Đang khởi động Dash server nội bộ trên port 8050...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "app.ui.app"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started_by_us = True
        if not wait_for_server():
            print("Lỗi: Không thể kết nối tới server 8050 sau 25s.")
            if server_proc:
                server_proc.kill()
            sys.exit(1)
        print("-> Server 8050 đã sẵn sàng.")
    else:
        print("-> Server 8050 đang chạy sẵn.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            viewports = [
                (1440, 900, "1440x900"),
                (1366, 768, "1366x768"),
            ]

            for width, height, vp_label in viewports:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()

                # 1. Đăng nhập
                page.goto("http://127.0.0.1:8050/login", wait_until="networkidle")
                page.wait_for_selector("#login-username", timeout=10000)
                page.fill("#login-username", "admin")
                page.fill("#login-password", "admin123")
                page.click("#login-submit-btn")
                page.wait_for_timeout(2000)

                # 2. Truy cập /mail-template-studio
                page.goto("http://127.0.0.1:8050/mail-template-studio", wait_until="networkidle")
                page.wait_for_selector("#mail-studio-canvas-content", timeout=15000)
                page.wait_for_timeout(2000)

                # Kiểm tra scrollHeight vs innerHeight
                scroll_h = page.evaluate("() => document.documentElement.scrollHeight")
                inner_h = page.evaluate("() => window.innerHeight")
                print(f"[{vp_label}] Light mode: scrollHeight={scroll_h}, innerHeight={inner_h}")

                # Chụp Light mode
                light_file = OUT_DIR / f"99-mail-studio-{prefix}-{vp_label}-light.png"
                page.screenshot(path=str(light_file))
                print(f"-> Đã lưu ảnh: {light_file.name}")

                # 3. Chuyển sang Dark mode
                page.evaluate("""() => {
                    document.documentElement.setAttribute('data-mantine-color-scheme', 'dark');
                    const toggle = document.getElementById('app-color-scheme-toggle');
                    if (toggle) toggle.click();
                }""")
                page.wait_for_timeout(1000)

                # Chụp Dark mode
                dark_file = OUT_DIR / f"99-mail-studio-{prefix}-{vp_label}-dark.png"
                page.screenshot(path=str(dark_file))
                print(f"-> Đã lưu ảnh: {dark_file.name}")

                context.close()

            browser.close()
    finally:
        if started_by_us and server_proc:
            print("Đang dừng Dash server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("-> Đã dừng Dash server.")


if __name__ == "__main__":
    prefix = sys.argv[1] if len(sys.argv) > 1 else "before"
    capture_screens(prefix)
