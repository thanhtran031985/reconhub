# Tiến độ — 01-auth-users

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | ServiceResult và mã lỗi | ✅ | 2026-10-31 | 8968b15 |
| 2 | Băm mật khẩu + login + khóa | ✅ | 2026-10-31 | (sẽ commit) |
| 3 | Phiên + before_request | 🔄 |  |  |
| 4 | Service user + LAST_ADMIN + audit | ⬜ |  |  |
| 5 | CLI + seed | ⬜ |  |  |
| 6 | UI login, đổi mật khẩu, tài khoản | ⬜ |  |  |

## Nhật ký
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
