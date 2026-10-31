# Tiến độ — 01-auth-users

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | ServiceResult và mã lỗi | ✅ | 2026-10-31 | 8968b15 |
| 2 | Băm mật khẩu + login + khóa | ✅ | 2026-10-31 | c5c695e |
| 3 | Phiên + before_request | ✅ | 2026-10-31 | (sẽ commit) |
| 4 | Service user + LAST_ADMIN + audit | 🔄 |  |  |
| 5 | CLI + seed | ⬜ |  |  |
| 6 | UI login, đổi mật khẩu, tài khoản | ⬜ |  |  |

## Nhật ký
### Bước 3 — 2026-10-31 23:04
- Đã làm:
  - Viết test `tests/integration/test_session_middleware.py` kiểm tra: chưa đăng nhập redirect về `/login`, đường dẫn công khai (`/health`, `/login`, assets, dash layout) mở tự do, người dùng đã đăng nhập truy cập thành công, đổi `SESSION_VERSION` trong DB làm phiên cũ bị đăng xuất, cờ `MUST_CHANGE_PW` tự động bắt buộc chuyển sang `/login?step=change`, kiểm tra header `Origin` trên `/_dash-update-component` chống CSRF.
  - Cài đặt `app/core/session.py` với bộ đệm trạng thái phiên 60s trên process, `get_current_ctx`, `login_session`, `logout_session`.
  - Cài đặt blueprint `app/routes/auth_routes.py` với route `/logout`.
  - Tích hợp hook `before_request` và cấu hình session cookie an toàn (HttpOnly, SameSite=Lax) trong `app/ui/app.py`.
- Kiểm tra:
  - `uv run pytest tests/integration/test_session_middleware.py -v`: 6/6 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 26 source files.
  - `uv run poe test`: 30 passed, 1 skipped (Oracle).
- Suy ra (nếu có): Invalidate cache phiên khi unit test cập nhật `SESSION_VERSION` trực tiếp trong DB.

### Bước 2 — 2026-10-31 23:00
- Đã làm:
  - Viết test `tests/unit/test_auth_core.py` bao quát: băm Argon2id và kiểm tra mật khẩu, mật khẩu rỗng ném PASSWORD_EMPTY, xác thực thành công, khóa tài khoản sau 5 lần sai liên tiếp, tự động mở khóa khi hết hạn `LOCKED_UNTIL`, tài khoản vô hiệu hóa `ACCOUNT_INACTIVE`, thông báo bảo mật chung giống nhau giữa sai mật khẩu và không tồn tại người dùng, ghi `RECON_LOGIN_LOG`.
  - Cài đặt `app/core/auth.py` gồm `hash_password`, `verify_password`, `needs_rehash`, `LoginData`, `authenticate_user`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_auth_core.py -v`: 7/7 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success: no issues found in 24 source files.
- Suy ra (nếu có): Lưu và so sánh datetime UTC naive trên SQLite để tránh lỗi mismatch timezone giữa aware và naive.

### Bước 1 — 2026-10-31 22:58
- Đã làm:
  - Viết test `tests/unit/test_service_result.py` kiểm tra `ServiceResult`, `ErrorCode`, `require_role`, decorator `@service` (xử lý `ValidationError` tiếng Việt và ẩn stack trace của lỗi nội bộ).
  - Cài đặt `app/schemas/errors.py` chứa đầy đủ mã lỗi enum `ErrorCode`, `ServiceError`, và `ServiceResult[T]`.
  - Cài đặt `app/core/context.py` chứa `Ctx`, enum `Role`, từ điển `ROLE_ALIASES` (hỗ trợ viết tắt AD, TO, OP, VI) và hàm `require_role(ctx, *roles)`.
  - Cài đặt decorator `@service` tại `app/services/__init__.py`.
  - Bổ sung `get_logger` vào `app/core/logging.py`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_service_result.py -v`: 9/9 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 23 source files.
  - `uv run poe test`: 17 passed, 1 skipped (Oracle do chưa có VPN/biến môi trường).
- Suy ra (nếu có): Hỗ trợ thêm `ROLE_ALIASES` để ánh xạ mượt mà giữa các ký hiệu ngắn gọn trong spec (`AD`, `TO`, `OP`, `VI`) và tên role đầy đủ trong cơ sở dữ liệu (`ADMIN`, `TEMPLATE_OWNER`, `OPERATOR`, `VIEWER`).
