# Tiến độ — 01-auth-users

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | ServiceResult và mã lỗi | ✅ | 2026-10-31 | (sẽ commit) |
| 2 | Băm mật khẩu + login + khóa | ⬜ |  |  |
| 3 | Phiên + before_request | ⬜ |  |  |
| 4 | Service user + LAST_ADMIN + audit | ⬜ |  |  |
| 5 | CLI + seed | ⬜ |  |  |
| 6 | UI login, đổi mật khẩu, tài khoản | ⬜ |  |  |

## Nhật ký
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
