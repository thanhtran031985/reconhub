"""Script chụp màn hình giao diện Báo cáo động để so sánh đối chiếu với thiết kế preview.html."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("docs/tasks/29-reporting-fluent-ui/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DESIGN_FILE = Path("designs/components/Screen16-DynamicReporting/preview.html").resolve()

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Chụp bản thiết kế gốc từ preview.html
        print("Đang chụp bản thiết kế gốc từ preview.html...")
        page.goto(f"file:///{DESIGN_FILE.as_posix()}")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "00_design_center_catalog.png"))

        # Click nút xem báo cáo trong prototype để chụp report view
        btn_open = page.locator(".open").first
        if btn_open.count() > 0:
            btn_open.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT_DIR / "00_design_report_view.png"))

        # Click tab Quản trị báo cáo trong prototype
        btn_nav_wiz = page.locator("button:has-text('Quản trị báo cáo')")
        if btn_nav_wiz.count() > 0:
            btn_nav_wiz.click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT_DIR / "00_design_wizard_step1.png"))

            # Bấm tiếp theo 2 lần để tới bước 3
            btn_next = page.locator("#next")
            if btn_next.count() > 0:
                # Phân tích SQL ở bước 2 nếu cần
                page.evaluate("""() => {
                    const el = document.getElementById('v-wizard');
                    if (el) {
                        const stepBtns = document.querySelectorAll('.step');
                        // Bật step 3
                        const s3 = document.querySelector('[data-s="3"]');
                        if (s3) { s3.removeAttribute('disabled'); s3.click(); }
                    }
                }""")
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT_DIR / "00_design_wizard_step3_canvas.png"))

        # 2. Đăng nhập ứng dụng
        print("Đang đăng nhập vào ReconHub http://127.0.0.1:8050...")
        page.goto("http://127.0.0.1:8050/login")
        page.wait_for_selector("#login-username")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "admin123")
        page.click("#login-submit-btn")
        page.wait_for_timeout(1500)
        print("Đăng nhập xong, chuyển sang chụp các màn hình ứng dụng...")

        # 3. Chụp /report-admin (Danh sách Quản trị báo cáo chuẩn Fluent Compact tương tự /batches)
        print("Chụp /report-admin (Danh sách)...")
        page.goto("http://127.0.0.1:8050/report-admin")
        page.wait_for_selector("#admin-list-container", timeout=10000)
        page.wait_for_selector("#admin-filter-search", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "01_app_report_admin_list.png"))

        # 4. Chụp /reports (Trung tâm báo cáo - Bảng gom nhóm danh mục .rlist)
        print("Chụp /reports (Trung tâm báo cáo)...")
        page.goto("http://127.0.0.1:8050/reports")
        page.wait_for_selector("#reports-cards-container", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "02_app_reports_center.png"))

        # 5. Mở xem một báo cáo để chụp Xem báo cáo (/reports/5)
        print("Mở xem báo cáo chi tiết /reports/5...")
        page.goto("http://127.0.0.1:8050/reports/5")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "03_app_report_viewer.png"))

        # 6. Chụp /report-admin?new=1 (Wizard Bước 1)
        print("Chụp /report-admin?new=1 (Wizard Bước 1)...")
        page.goto("http://127.0.0.1:8050/report-admin?new=1")
        page.wait_for_selector("#admin-stepper", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "04_app_wizard_step1.png"))

        browser.close()
        print("Hoàn tất chụp màn hình! Tất cả file đã được lưu trong:", OUT_DIR)

if __name__ == "__main__":
    capture()
