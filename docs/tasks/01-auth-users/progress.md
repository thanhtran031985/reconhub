# Tiến độ — 01-auth-users

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | ServiceResult và mã lỗi | ✅ | 2026-10-31 | 8968b15 |
| 2 | Băm mật khẩu + login + khóa | ✅ | 2026-10-31 | c5c695e |
| 3 | Phiên + before_request | ✅ | 2026-10-31 | b32e630 |
| 4 | Service user + LAST_ADMIN + audit | ✅ | 2026-10-31 | b8b415f |
| 5 | CLI + seed | ✅ | 2026-10-31 | 5bf89d8 |
| 6 | UI login, đổi mật khẩu, tài khoản | ✅ | 2026-10-31 | (sẽ commit) |

## Nhật ký
### Bước 6 — 2026-10-31 23:15
- Đã làm:
  - Cài đặt trang `/login` (`app/ui/pages/login.py`) theo thiết kế Screen10-Login: thẻ 400px căn giữa, hỗ trợ view đăng nhập thông thường và view đổi mật khẩu bắt buộc (`step=change`), các callback xác thực và cập nhật phiên.
  - Cài đặt trang `/account` (`app/ui/pages/account.py`): hiển thị bảng thông tin tài khoản hiện tại, vai trò người dùng, form đổi mật khẩu cá nhân kèm ghi chú đăng xuất khỏi các phiên khác.
  - Cài đặt trang `/forbidden` (`app/ui/pages/forbidden.py`): hiển thị giao diện 403 thân thiện khi người dùng thiếu quyền, kèm nút quay lại Trang chủ.
  - Cài đặt layout tổng thể `app/ui/layout.py`: tích hợp `dmc.AppShell` với Header (Logo ReconHub, nhãn môi trường DEV/UAT/PROD, menu người dùng có Tài khoản và Đăng xuất). Ẩn AppShell ngoài khi ở trang `/login`.
  - Viết test `tests/test_ui_auth.py` kiểm tra rendering của trang Login, Đổi mật khẩu bắt buộc, Tài khoản và Forbidden.
- Kiểm tra:
  - `uv run pytest tests/test_ui_auth.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 33 source files.
  - `uv run poe test`: 42 passed, 1 skipped.
- Suy ra (nếu có): Lấy layout của page qua `dash.page_registry` trong test thay vì import trực tiếp module để tránh đăng ký trùng pathname khi Dash quét folder `pages`.

### Bước 5 — 2026-10-31 23:10
- Đã làm:
  - Viết test `tests/unit/test_cli.py` kiểm tra: lệnh `create-admin` từ chối khi đã có admin trừ khi có cờ `--force`, lệnh `reset-password` cập nhật hash mật khẩu mới và bật cờ `MUST_CHANGE_PW`, lệnh `seed` nạp 4 user mẫu idempotent (chạy nhiều lần không trùng lặp).
  - Cài đặt đầy đủ `app/cli.py` cho `create-admin`, `reset-password`, `seed` (nạp 4 user mẫu: admin, owner, operator, viewer). Xử lý an toàn stdout/stderr UTF-8 trên console Windows.
- Kiểm tra:
  - `uv run pytest tests/unit/test_cli.py -v`: 3/3 passed.
  - `uv run poe db-seed`: Đã nạp 4 user mẫu thành công; chạy lại thông báo 0 user mới (idempotent).
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 29 source files.
  - `uv run poe test`: 38 passed, 1 skipped.
- Suy ra (nếu có): Thêm reconfigure UTF-8 an toàn cho Windows cmd/powershell để không bị UnicodeEncodeError charmap cp1252 khi CLI in tiếng Việt.

### Bước 4 — 2026-10-31 23:07
- Đã làm:
  - Viết test `tests/unit/test_user_service.py` kiểm tra: Viewer gọi service Admin bị FORBIDDEN, tạo user và chặn trùng username (case-insensitive), bảo vệ bất biến `LAST_ADMIN` (chặn deactive và chặn xóa role Admin của quản trị viên cuối cùng), kiểm tra `write_audit_log` tự động mask mật khẩu thành `"***"`, người dùng tự đổi mật khẩu cá nhân.
  - Cài đặt `app/core/audit.py` ghi nhận nhật ký kiểm toán vào `RECON_AUDIT_LOG` trong cùng transaction với hàm ẩn thông tin nhạy cảm `_mask_sensitive`.
  - Cài đặt `app/schemas/user.py` chứa DTOs: `UserCreateDTO`, `UserUpdateDTO`, `UserResponse`, `ChangePasswordDTO`, `ResetPasswordDTO`.
  - Cài đặt `app/services/user.py` gồm `list_users`, `create_user`, `update_user`, `set_active`, `unlock_user`, `reset_password`, `change_password`, `get_login_log`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_user_service.py -v`: 5/5 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 29 source files.
  - `uv run poe test`: 35 passed, 1 skipped.
- Suy ra (nếu có): Invalidate session cache của người dùng ngay khi Admin cập nhật quyền, đổi mật khẩu, hoặc deactive để phiên làm việc của user bị ngắt ngay lập tức ở request kế tiếp.

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
