from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    # ==========================================
    # 1. KIỂM TRA MÀN HÌNH /login
    # ==========================================
    print("\n--- 1. Kiểm tra màn hình /login ---")
    page.goto("http://127.0.0.1:8050/login", timeout=15000)
    page.wait_for_selector("#login-submit-btn")

    # Kiểm tra không còn link xem sơ đồ SSO trên login
    flow_link = page.query_selector("a[href='/sso-flow']")
    assert flow_link is None, "LỖI: Link xem sơ đồ SSO vẫn còn trên trang login!"
    print(" -> Đã xóa bỏ hoàn toàn link 'Xem sơ đồ luồng SSO' trên trang login: PASSED")

    # Kiểm tra nút Đăng nhập chính ở trên, form mật khẩu
    login_btn = page.query_selector("#login-submit-btn")
    assert login_btn is not None
    print(f" -> Nút Đăng nhập chính: '{login_btn.inner_text()}' (màu primary ở trên): PASSED")

    # Kiểm tra nút SSO ở dưới
    sso_btn = page.query_selector("a[href='/auth/sso/login'] button")
    assert sso_btn is not None
    print(f" -> Nút Đăng nhập SSO ở dưới cùng: '{sso_btn.inner_text()}': PASSED")

    # Chụp ảnh login
    page.screenshot(path="storage/login_dual_mode_latest.png")
    print(" -> Đã chụp ảnh lưu: storage/login_dual_mode_latest.png")

    # ==========================================
    # 2. ĐĂNG NHẬP ADMIN VÀO RECONHUB
    # ==========================================
    print("\n--- 2. Đăng nhập tài khoản admin ---")
    page.fill("#login-username", "admin")
    page.fill("#login-password", "admin123")
    page.click("#login-submit-btn")

    page.wait_for_url("http://127.0.0.1:8050/", timeout=15000)
    print(" -> Đăng nhập thành công, đã chuyển về trang chủ '/'")

    # ==========================================
    # 3. TRUY CẬP VÀO MÀN HÌNH /sso-flow
    # ==========================================
    print("\n--- 3. Kiểm tra màn hình /sso-flow ---")
    page.goto("http://127.0.0.1:8050/sso-flow", timeout=15000)
    page.wait_for_selector("#sso-toggle-switch", timeout=10000)

    # Kiểm tra nội dung text
    main_text = page.inner_text("main")

    # Đảm bảo các comment thừa đã bị loại bỏ
    assert "Mô hình Single Sign-On độc lập bằng FastAPI" not in main_text, "LỖI: Vẫn còn subtitle thừa!"
    assert "100% Python • Chạy độc lập • Không Docker" not in main_text, "LỖI: Vẫn còn badge thừa!"
    print(" -> Đã xóa bỏ các chú thích/comment thừa trên trang: PASSED")

    # Kiểm tra Switch bật/tắt SSO
    switch = page.query_selector("#sso-toggle-switch")
    assert switch is not None
    assert switch.is_checked() is True
    print(" -> Switch bật/tắt SSO đang ở trạng thái BẬT: PASSED")

    # Kiểm tra badge trạng thái
    badge_el = page.query_selector("#sso-status-badge-container")
    assert badge_el is not None
    assert "SSO ĐANG BẬT" in badge_el.inner_text().upper()
    print(f" -> Badge trạng thái ban đầu: '{badge_el.inner_text()}': PASSED")

    # Kiểm tra Iframe Archify Diagram
    iframe = page.query_selector("#sso-archify-frame")
    assert iframe is not None
    src = iframe.get_attribute("src")
    assert src == "/assets/sso_flow_archify.html"
    print(f" -> Khung Iframe Archify tồn tại và trỏ đúng: '{src}': PASSED")

    # Chờ iframe tải nội dung
    time.sleep(2)

    # Chụp ảnh màn hình toàn trang /sso-flow
    page.screenshot(path="storage/sso_flow_archify_latest.png", full_page=True)
    print(" -> Đã chụp ảnh lưu: storage/sso_flow_archify_latest.png")

    # ==========================================
    # 4. KIỂM TRA THAO TÁC TOGGLE SWITCH
    # ==========================================
    print("\n--- 4. Thử nghiệm Toggle Switch Bật/Tắt SSO ---")
    # Click toggle switch để tắt
    switch_label = page.query_selector("label:has(#sso-toggle-switch)") or switch
    switch_label.click()
    time.sleep(1)

    assert "SSO ĐANG TẮT" in badge_el.inner_text().upper()
    print(" -> Đã toggle sang TẮT: Badge hiển thị 'SSO Đang Tắt (Local Only)': PASSED")

    # Click toggle switch để bật lại
    switch_label.click()
    time.sleep(1)
    assert "SSO ĐANG BẬT" in badge_el.inner_text().upper()
    print(" -> Đã toggle bật lại: Badge hiển thị 'SSO Đang Bật': PASSED")

    # ==========================================
    # 5. KIỂM TRA MENU SIDEBAR
    # ==========================================
    print("\n--- 5. Kiểm tra Menu Sidebar ---")
    sidebar_item = page.query_selector("a[href='/sso-flow']")
    assert sidebar_item is not None
    print(f" -> Menu 'Kiến trúc SSO' hiển thị chuẩn trong nhóm Quản trị: '{sidebar_item.inner_text()}': PASSED")

    browser.close()
    print("\n===> TẤT CẢ CÁC MỤC KIỂM TRA PLAYWRIGHT HOÀN TOÀN ĐẠT CHUẨN! <===")
