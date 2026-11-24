# Kế hoạch thực hiện: 102-fastapi-sso

Kế hoạch đã được người dùng duyệt tại phiên làm việc ngày 2026-11-24.

## Mục tiêu
Xây dựng hệ thống SSO nội bộ độc lập bằng FastAPI (100% Python, không Docker, cổng 9000), tích hợp vào ReconHub (cổng 8050) với cơ chế Dual-Mode và màn hình hiển thị Flow SSO tương tác `/sso-flow`.

## Các giai đoạn
1. Xây dựng dịch vụ FastAPI SSO độc lập (`sso_server/`).
2. Tích hợp SSO Client vào ReconHub (`app/services/sso_client.py`, `app/core/config.py`).
3. Bổ sung Routes SSO phía ReconHub (`app/routes/auth_routes.py`).
4. Nâng cấp giao diện trang Đăng nhập Dual-Mode (`app/ui/pages/login.py`).
5. Xây dựng màn hình hiển thị Flow SSO (`app/ui/pages/sso_flow.py`).
6. Kiểm thử toàn diện (Unit test, integration test, typecheck, lint).
