# Tiến độ — 02-data-sources

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Mã hóa + repo + service | ✅ | 2026-10-31 | d514653 |
| 2 | Kiểm tra kết nối | ✅ | 2026-10-31 | cc5a68b |
| 3 | open_source + catalog | ✅ | 2026-10-31 | a1a5da8 |
| 4 | METADATA đang dùng + seed | ✅ | 2026-10-31 | 6fb6ceb |

## Nhật ký
### Bước 4 — 2026-10-31 23:43
- Đã làm:
  - Cài đặt `sync_current_metadata_source(engine)` trong `app/services/data_source.py`: tự động nhận diện kết nối SQLite hoặc Oracle hiện tại của ứng dụng và đồng bộ vào `RECON_DATA_SOURCE` với `IS_CURRENT_METADATA='Y'`, đảm bảo luôn chỉ có duy nhất 1 bản ghi metadata hiện hành (idempotent).
  - Tích hợp `sync_current_metadata_source()` vào quy trình khởi động web server tại `app/ui/app.py` và quy trình seed dữ liệu tại `app/cli.py`.
  - Bổ sung nạp data source mẫu `ORACLE_TEST` trong lệnh CLI `seed_cmd` khi phát hiện biến môi trường cấu hình `ORACLE_TEST_*`.
  - Cập nhật `Settings` trong `app/core/config.py` hỗ trợ linh hoạt cả `ORACLE_TEST_DSN` và các trường thành phần `ORACLE_TEST_HOST`, `ORACLE_TEST_PORT`, `ORACLE_TEST_SERVICE`, `ORACLE_TEST_USER`, `ORACLE_TEST_PASSWORD`.
  - Viết test `tests/unit/test_data_source_startup.py` kiểm tra đồng bộ metadata nguồn hiện tại và tính idempotent của việc nạp nguồn Oracle test.
- Kiểm tra:
  - `uv run pytest tests/unit/test_data_source_startup.py -v`: 2/2 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 38 source files.
  - `uv run poe test`: 56 passed, 2 skipped.
- Suy ra (nếu có): Dùng model_validator trên Pydantic Settings để tự động đồng bộ qua lại giữa chuỗi DSN tổng hợp và các thành phần host/port/service giúp cấu hình môi trường tương thích tối đa với cả định dạng chuỗi DSN chuẩn và biến chi tiết.
### Bước 3 — 2026-10-31 23:33
- Đã làm:
  - Cài đặt `app/services/source_conn.py`: hàm `open_source_connection(ds_id)` mở kết nối Oracle thin mode, thiết lập `call_timeout` theo `CALL_TIMEOUT_S`, bắt lỗi mất kết nối chuyển thành mã lỗi `SOURCE_CONNECTION_LOST`.
  - Cài đặt `app/engine/catalog.py`: hàm `list_tables(ds_id, schema, q)` và `list_columns(ds_id, schema, table)` truy vấn danh mục Oracle (`ALL_TABLES`, `ALL_VIEWS`, `ALL_TAB_COLUMNS`), hỗ trợ bộ đệm in-memory TTL 10 phút (600s), hàm `invalidate_catalog_cache`.
  - Viết test `tests/unit/test_catalog.py` kiểm tra kết nối nguồn, bắt lỗi timeout/mất kết nối, lấy danh sách bảng/view từ DB và từ cache, lọc từ khóa `q`, lấy chi tiết kiểu dữ liệu/độ dài/precision/scale của các cột.
- Kiểm tra:
  - `uv run pytest tests/unit/test_catalog.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 38 source files.
  - `uv run poe test`: 54 passed, 2 skipped.
- Suy ra (nếu có): Trong Python unittest.mock, patch target cần chỉ định đúng vị trí import (`app.engine.catalog.open_source_connection`) thay vì nơi định nghĩa gốc để tránh module gọi kết nối mạng thật khi chạy unit test.

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
