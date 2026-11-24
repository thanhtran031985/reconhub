# 102-fastapi-sso — Hệ thống SSO nội bộ độc lập bằng FastAPI, tích hợp Dual-Mode và màn hình Flow SSO

- Ngày tạo: 2026-11-24
- Giai đoạn: GĐ3
- Phụ thuộc: 01-auth-users
- Nhánh git: feat/102-fastapi-sso

## Mục tiêu
1. Xây dựng dịch vụ SSO nội bộ độc lập bằng FastAPI (`sso_server/`), 100% Python, không Docker, quản lý danh tính tập trung, hỗ trợ Single Sign-On dựa trên JWT Cookie và Authorization Code flow (TTL 60s).
2. Tích hợp SSO Client vào ReconHub: cấu hình `SSO_ENABLED`, JIT User Provisioning vào `RECON_USER`, tái sử dụng phiên Flask hiện tại (`login_session`).
3. Giao diện đăng nhập kép (Dual-Mode): nút "Đăng nhập SSO Doanh nghiệp" + form tài khoản nội bộ dự phòng cho Admin khẩn cấp.
4. Màn hình hiển thị Flow SSO tương tác (`/sso-flow`) trực quan bằng sơ đồ Mermaid (theo thiết kế minh họa người dùng cung cấp), có nút sao chép mã và thông số cấu hình.

## Phạm vi
- Dịch vụ FastAPI SSO: `sso_server/` (config, main, users).
- ReconHub Backend: `app/core/config.py`, `app/services/sso_client.py`, `app/routes/auth_routes.py`.
- ReconHub UI: `app/ui/pages/login.py`, `app/ui/pages/sso_flow.py`.
- Tests: `tests/unit/test_sso_server.py`, `tests/unit/test_sso_client.py`.
- Task poe: `uv run poe sso` để chạy dev server SSO trên cổng 9000.

## Ngoài phạm vi
- Không can thiệp schema `RECON_USER` bắt buộc migration (dùng hash unguessable `!sso_<uuid>` thỏa mãn `NOT NULL` và ngăn chặn login password).
- Không can thiệp LDAP/Active Directory bên ngoài (dùng local store của SSO Server).

## Quyết định kiến trúc
- Ghi nhận trong `docs/tasks/102-fastapi-sso/decisions.md`.

## Các bước
### Bước 1 — Xây dựng FastAPI SSO Server độc lập (`sso_server/`)
- Làm: Tạo `sso_server/` với `config.py`, `users.py` (Argon2 hash), `main.py` (Login UI, JWT cookie, one-time code, verify API, whitelist redirect_uri). Thêm task `poe sso`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_server.py` xanh.

### Bước 2 — Tích hợp SSO Client vào ReconHub
- Làm: Cập nhật `app/core/config.py`, `.env.example`. Tạo `app/services/sso_client.py` để verify code và JIT provisioning user vào `RECON_USER`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_client.py` xanh.

### Bước 3 — Bổ sung Routes SSO phía ReconHub
- Làm: Thêm `/auth/sso/login` và `/auth/sso/callback` vào `app/routes/auth_routes.py`.
- Kiểm tra: Request callback gọi thành công JIT provisioning và tạo phiên Flask.

### Bước 4 — Nâng cấp giao diện đăng nhập Dual-Mode
- Làm: Chỉnh sửa `app/ui/pages/login.py` hiển thị nút SSO khi `SSO_ENABLED=True` và form fallback.
- Kiểm tra: Giao diện hiển thị đúng 2 chế độ, fallback hoạt động bình thường.

### Bước 5 — Xây dựng màn hình hiển thị Flow SSO (`/sso-flow`)
- Làm: Tạo `app/ui/pages/sso_flow.py` hiển thị sơ đồ Mermaid theo đúng minh họa người dùng cung cấp, kèm nút sao chép, chi tiết từng bước, và bảng cấu hình.
- Kiểm tra: Mở trang `/sso-flow`, Mermaid diagram render chính xác và responsive.

### Bước 6 — Kiểm thử và tài liệu hóa
- Làm: Chạy lint, typecheck, test toàn bộ. Bổ sung hướng dẫn vận hành Windows Service NSSM.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh
- [ ] Task không thay đổi database schema (không phát sinh schema drift).
- [ ] Flow SSO hoạt động trơn tru: Login SSO -> Cấp Code -> Callback ReconHub -> Vào trang chủ.
- [ ] Trang `/sso-flow` hiển thị chuẩn đẹp sơ đồ Mermaid theo ảnh người dùng cung cấp.
