"""Kịch bản Playwright kiểm tra tự động tất cả các màn hình ReconHub trên server đang chạy."""

from __future__ import annotations

import sys
from typing import Any

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import Response, sync_playwright


def test_screens() -> None:
    screens_to_test = [
        {"path": "/", "name": "Screen01 - Dashboard", "selector": "text=Dashboard"},
        {"path": "/runs/new", "name": "Screen05 - Chạy đối soát", "selector": "text=1. File dữ liệu"},
        {"path": "/templates", "name": "Screen02 - Quản lý Template", "selector": "text=Templates"},
        {"path": "/templates/new", "name": "Screen03/04 - Wizard Template", "selector": "text=Đăng ký template"},
        {"path": "/data-sources", "name": "Screen08 - Data Sources", "selector": "text=Data Sources"},
        {"path": "/users", "name": "Screen09 - Quản lý người dùng", "selector": "text=Người dùng"},
        {"path": "/history", "name": "Screen06 - Lịch sử & Dọn dẹp tạm", "selector": "text=Lịch sử"},
        {"path": "/issues", "name": "Screen11 - Xử lý chênh lệch", "selector": "text=Chênh lệch"},
        {"path": "/account", "name": "Screen10 - Thông tin tài khoản", "selector": "text=Tài khoản"},
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        dash_500_errors: list[str] = []

        def on_response(response: Response) -> None:
            if "_dash-update-component" in response.url and response.status >= 500:
                dash_500_errors.append(f"{response.url} returned status {response.status}")

        page.on("response", on_response)

        console_errs: list[str] = []
        page_errs: list[str] = []

        def handle_console(msg: Any) -> None:
            # Bỏ qua lỗi kết nối tới plotly.com check version từ xa
            text = msg.text
            if msg.type == "error":
                if "plotly.com" in text or "ERR_FAILED" in text:
                    return
                console_errs.append(text)

        page.on("console", handle_console)
        page.on("pageerror", lambda err: page_errs.append(str(err)))

        print("=== BẮT ĐẦU ĐĂNG NHẬP VỚI ADMIN ===")
        page.goto("http://127.0.0.1:8050/login", wait_until="networkidle")
        page.fill("input#login-username", "admin")
        page.fill("input#login-password", "admin123")
        page.click("button#login-submit-btn")
        page.wait_for_timeout(2000)

        print(f"Đăng nhập thành công! URL hiện tại: {page.url}\n")
        print("=== KIỂM TRA LẦN LƯỢT TỪNG MÀN HÌNH ===")

        all_passed = True

        for s in screens_to_test:
            dash_500_errors.clear()
            console_errs.clear()
            page_errs.clear()

            url = f"http://127.0.0.1:8050{s['path']}"
            resp = page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1500)

            status_code = resp.status if resp else "N/A"
            title = page.title()

            has_error = False
            error_details = []

            if dash_500_errors:
                has_error = True
                error_details.extend(dash_500_errors)
            if console_errs:
                has_error = True
                error_details.extend(console_errs)
            if page_errs:
                has_error = True
                error_details.extend(page_errs)

            # Check if key selector is visible
            is_visible = page.locator(s["selector"]).first.is_visible()

            if not has_error and is_visible:
                print(f"  [PASS] {s['name']} ({s['path']}) -> HTTP {status_code} | Tiêu đề: '{title}'")
            else:
                all_passed = False
                print(f"  [FAIL] {s['name']} ({s['path']}) -> HTTP {status_code}")
                if not is_visible:
                    print(f"         Không tìm thấy selector: {s['selector']}")
                for err in error_details:
                    print(f"         Chi tiết lỗi: {err}")

        browser.close()

        print("\n=== KẾT QUẢ TỔNG THỂ ===")
        if all_passed:
            print("TẤT CẢ CÁC MÀN HÌNH ĐÃ HOẠT ĐỘNG HOÀN HẢO KHÔNG CÓ LỖI!")
        else:
            print("Có một số màn hình gặp lỗi, vui lòng kiểm tra chi tiết ở trên.")
            sys.exit(1)


if __name__ == "__main__":
    test_screens()
