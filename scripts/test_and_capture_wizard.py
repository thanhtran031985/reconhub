"""Tự động kiểm tra và chụp ảnh toàn bộ Wizard Quản trị báo cáo."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("docs/tasks/29-reporting-fluent-ui/screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def log(msg: str):
    print(msg, flush=True)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        log("1. Đăng nhập...")
        page.goto("http://127.0.0.1:8050/login")
        page.wait_for_selector("#login-username")
        page.fill("#login-username", "admin")
        page.fill("#login-password", "admin123")
        page.click("#login-submit-btn")
        page.wait_for_timeout(1000)

        log("2. Mở /report-admin danh sách...")
        page.goto("http://127.0.0.1:8050/report-admin")
        page.wait_for_selector("#admin-list-container")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "01_app_report_admin_list.png"))

        log("3. Bấm + Báo cáo mới -> Bước 1...")
        page.goto("http://127.0.0.1:8050/report-admin?new=1")
        page.wait_for_selector("#admin-s1-report-code", timeout=10000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "02_wizard_step1_empty.png"))

        # Điền thông tin Bước 1
        t_suffix = str(int(time.time()))[-4:]
        rep_code = f"FIN_REV_{t_suffix}"
        tpl_code = f"TPL_DET_{t_suffix}"

        log(f"Điền thông tin: {rep_code} / {tpl_code}...")
        page.fill("#admin-s1-report-code", rep_code)
        page.fill("#admin-s1-report-name", "Báo cáo doanh thu tổng hợp")
        page.fill("#admin-s1-tpl-code", tpl_code)
        page.fill("#admin-s1-tpl-name", "Chi tiết doanh thu")
        page.fill("#admin-s1-owner", "FIN")
        page.fill("#admin-s1-description", "Báo cáo doanh thu bán hàng chi tiết theo đơn vị và khách hàng.")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "03_wizard_step1_filled.png"))

        log("4. Bấm Tiếp theo -> chuyển sang Bước 2...")
        page.click("#admin-s1-save-btn")
        page.wait_for_selector("#admin-s2-ds", timeout=10000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT_DIR / "04_wizard_step2_initial.png"))

        log("5. Kiểm tra Bước 2: chọn bảng để tự sinh SQL...")
        page.wait_for_selector("#admin-s2-object-select", timeout=10000)
        page.wait_for_timeout(800)
        page.click("#admin-s2-object-select")
        page.wait_for_timeout(600)
        # Gõ tìm kiếm recon_user và click option RECON_USER
        page.fill("#admin-s2-object-select", "recon_user")
        page.wait_for_timeout(600)
        page.locator("[data-combobox-option]:has-text('RECON_USER')").first.click()
        page.wait_for_timeout(1500)
        sql_val = page.locator("#admin-s2-sql").input_value()
        log("SQL tự sinh ra:\n" + sql_val)
        page.screenshot(path=str(OUT_DIR / "05_wizard_step2_table_selected_sql_generated.png"))

        log("6. Bấm Phân tích SQL...")
        page.click("#admin-s2-analyze-btn")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT_DIR / "06_wizard_step2_analyzed.png"))

        log("7. Bấm Tiếp theo -> chuyển sang Bước 3 (Tham số & LOV)...")
        page.click("#admin-next-btn")
        page.wait_for_selector("#admin-p-code", timeout=10000)
        page.wait_for_timeout(800)
        # Thêm 1 tham số mẫu p_status
        page.fill("#admin-p-code", "p_status")
        page.fill("#admin-p-label", "Trạng thái người dùng")
        page.click("#admin-p-save-btn")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT_DIR / "07_wizard_step3_params.png"))

        log("8. Bấm Tiếp theo -> chuyển sang Bước 4 (Cấu hình cột)...")
        page.click("#admin-next-btn")
        page.wait_for_selector("#admin-col-save-btn", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "08_wizard_step4_columns.png"))

        log("9. Bấm Tiếp theo -> chuyển sang Bước 5 (Xem trước)...")
        page.click("#admin-next-btn")
        page.wait_for_selector("#admin-dryrun-btn", timeout=10000)
        page.wait_for_timeout(800)
        log("Chạy dry-run ở Bước 5...")
        page.click("#admin-dryrun-btn")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "09_wizard_step5_dryrun.png"))

        log("10. Bấm Tiếp theo -> chuyển sang Bước 6 (Hoàn tất & Kích hoạt)...")
        page.click("#admin-next-btn")
        page.wait_for_selector("#admin-activate-btn", timeout=10000)
        page.wait_for_timeout(800)
        log("Bấm Kích hoạt template...")
        page.click("#admin-activate-btn")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT_DIR / "10_wizard_step6_activated.png"))

        browser.close()
        log("Hoàn tất chụp và kiểm thử toàn bộ wizard!")

if __name__ == "__main__":
    run()
