# Tiến độ: 102-fastapi-sso

- Nhánh git: `feat/102-fastapi-sso`
- Trạng thái tổng: ✅ Hoàn thành 100% và đã được duyệt commit

## Nhật ký bước
- [x] Khởi tạo task 102, tài liệu task và nhánh git.
- [x] Bước 1: Xây dựng FastAPI SSO Server độc lập (`sso_server/`).
  - `sso_server/config.py`: Host, port, JWT secret, session duration, redirect whitelist.
  - `sso_server/users.py`: Quản lý tài khoản mẫu băm bằng Argon2id.
  - `sso_server/main.py`: HTML Login UI, cấp JWT cookie, cấp mã code dùng 1 lần (TTL 60s), endpoint `/api/verify-code`, `/health`, `/logout`.
  - Task poe: `uv run poe sso`.
- [x] Bước 2: Tích hợp SSO Client vào ReconHub.
  - `app/core/config.py`: Bổ sung `SSO_ENABLED`, `SSO_SERVER_URL`, `SSO_CLIENT_SECRET`.
  - `app/services/sso_client.py`: `verify_sso_code`, `sync_sso_user` (JIT Provisioning tự tạo tài khoản nếu chưa có).
- [x] Bước 3: Bổ sung Routes SSO phía ReconHub.
  - `app/routes/auth_routes.py`: Thêm `/auth/sso/login` và `/auth/sso/callback`.
  - `app/ui/app.py`: Mở public prefix cho `/auth/sso`.
- [x] Bước 4: Tinh chỉnh giao diện đăng nhập Dual-Mode theo feedback.
  - `app/ui/pages/login.py`:
    - Nút "Đăng nhập" mật khẩu nội bộ giữ màu xanh primary như cũ ở trên.
    - Chuyển nút "Đăng nhập qua SSO Doanh nghiệp" xuống dưới form sau divider.
    - Xóa bỏ hoàn toàn liên kết xem sơ đồ SSO trên trang login (tránh lộ thông tin khi chưa đăng nhập).
- [x] Bước 5: Chuyển màn hình Flow SSO thành Menu nội bộ & Nâng cấp Archify Diagram.
  - `app/ui/menus.py`: Đăng ký menu `sso_flow` ("Kiến trúc SSO") trong nhóm `QUAN_TRI` với icon `lucide:shield-check`.
  - Khắc phục triệt để lỗi 401 màn hình trắng do chưa xác thực.
  - Ứng dụng skill `archify` tạo sơ đồ kiến trúc 2 phân hệ tương tác chuyên nghiệp (`app/ui/assets/sso_flow_archify.html`).
  - `app/ui/pages/sso_flow.py`:
    - Bỏ các subtitle và comment thừa trên trang.
    - Nhúng sơ đồ Archify tương tác qua Iframe.
    - Bổ sung Switch bật/tắt SSO trên giao diện (lưu runtime và bền vững vào `.env`).
- [x] Bước 6: Kiểm thử tự động & Playwright E2E.
  - `tests/unit/test_sso_server.py`: 5/5 passed.
  - `tests/unit/test_sso_client.py`: 3/3 passed.
  - `tests/unit/test_sso_flow_page.py`: 2/2 passed.
  - `tests/unit/test_sso_routes.py`: 4/4 passed.
  - `scripts/verify_sso_ui_playwright.py`: 100% kịch bản UI Playwright đạt chuẩn.
  - `ruff check`, `mypy` đạt 100% không lỗi.
