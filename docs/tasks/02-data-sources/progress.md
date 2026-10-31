# Tiến độ — 02-data-sources

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Mã hóa + repo + service | ✅ | 2026-10-31 | d514653 |
| 2 | Kiểm tra kết nối | ✅ | 2026-10-31 | (sẽ commit) |
| 3 | open_source + catalog | 🔄 |  |  |
| 4 | METADATA đang dùng + seed | ⬜ |  |  |

## Nhật ký
### Bước 2 — 2026-10-31 23:31
- Đã làm:
  - Cài đặt hàm `test_data_source(ctx, ds_id)` trong `app/services/data_source.py`: đo thời gian phản hồi ms; kiểm tra kết nối SQLite đọc file và dung lượng MB; kiểm tra kết nối Oracle thin mode kèm cấu hình `call_timeout`.
  - Phân nhánh kiểm tra theo vai trò: `PURPOSE='SOURCE'` kiểm tra và cảnh báo nếu tài khoản có quyền ghi (`DS_NOT_READ_ONLY`); `PURPOSE='METADATA'` kiểm tra schema đích trống hay đã có các bảng `RECON_*`. Cập nhật `LAST_TEST_*` vào cơ sở dữ liệu.
  - Viết test `tests/unit/test_data_source_connection.py` cho cả SQLite và Oracle (mock oracledb kiểm tra quyền ghi và schema trống).
  - Bổ sung test integration `test_service_test_data_source_oracle` trong `tests/integration/test_oracle_smoke.py` (tự động skip khi thiếu biến môi trường/VPN).
- Kiểm tra:
  - `uv run pytest tests/unit/test_data_source_connection.py -v`: 3/3 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 36 source files.
  - `uv run poe test`: 50 passed, 2 skipped (Oracle integration tests).
- Suy ra (nếu có): Import alias hàm test của service trong module test để tránh bị pytest tự động nhận diện thành test case.

### Bước 1 — 2026-10-31 23:28
- Đã làm:
  - Cài đặt `app/core/crypto.py` mã hóa và giải mã chuỗi bí mật bằng Fernet với key derivation SHA-256 an toàn từ `RECON_SECRET_KEY`.
  - Cài đặt `app/schemas/data_source.py` chứa DTOs: `DataSourceCreateDTO`, `DataSourceUpdateDTO`, `DataSourceResponse` (không lộ mật khẩu/chuỗi mã hóa), `DataSourceOption`.
  - Cài đặt `app/services/data_source.py`: `list_data_sources` (Admin), `options_data_sources` (mọi role), `create_data_source`, `update_data_source` (giữ nguyên mật khẩu cũ khi để rỗng), `deactivate_data_source` (bảo vệ nguồn `IS_CURRENT_METADATA`).
  - Viết test `tests/unit/test_data_source_service.py` bao quát mã hóa, phân quyền, bảo vệ mật khẩu, và bảo vệ `DS_CURRENT_METADATA_LOCKED`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_data_source_service.py -v`: 5/5 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 36 source files.
  - `uv run poe test`: 47 passed, 1 skipped.
- Suy ra (nếu có): Base64-urlsafe hóa SHA256 digest của `RECON_SECRET_KEY` giúp mã hóa Fernet chấp nhận bất kỳ độ dài key nào từ cấu hình môi trường mà không bị lỗi padding hay invalid key.
