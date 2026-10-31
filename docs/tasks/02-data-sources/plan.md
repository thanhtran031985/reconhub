# Kế hoạch thực hiện 02-data-sources — Data Source: nguồn Oracle và đích lưu RECON_APP

## 1. Mục tiêu
Admin quản lý kết nối Oracle cho nguồn đối soát (user chỉ đọc) và đích lưu RECON_APP (user/password schema); nhận diện tự động DB SQLite đang dùng; mật khẩu mã hóa Fernet (không bao giờ lộ ra UI, audit hay log); kiểm tra kết nối phân biệt quyền SOURCE/METADATA; dịch vụ danh mục liệt kê bảng/cột nguồn Oracle với cache 10 phút.

## 2. Kiến trúc & Quyết định kỹ thuật
- **Bảo mật bí mật**: Mật khẩu Data Source mã hóa bằng Fernet với `RECON_SECRET_KEY` trong `app/core/crypto.py`. DTO trả về không bao giờ chứa mật khẩu hoặc mật khẩu đã mã hóa.
- **Phân quyền**: Toàn bộ thao tác thêm/sửa/xóa/kiểm tra chỉ dành cho Admin (`require_role(ctx, Role.ADMIN)`). Riêng hàm `options_data_sources` mở cho mọi user đã đăng nhập để nạp dropdown chọn nguồn trong wizard và trang chạy.
- **Oracle Thin mode**: Kết nối qua `python-oracledb` Thin mode không cần Oracle Instant Client, truyền `call_timeout` theo cấu hình `CALL_TIMEOUT_S`.
- **Bảo vệ METADATA hiện tại**: Bản ghi `IS_CURRENT_METADATA='Y'` không thể xóa hoặc hủy kích hoạt (`DS_CURRENT_METADATA_LOCKED`).

## 3. Các bước thực hiện

### Bước 1 — Mã hóa Fernet, Repo/Schemas và Service CRUD
- Cài đặt `app/core/crypto.py`: hàm `encrypt_secret` và `decrypt_secret`.
- Cài đặt `app/schemas/data_source.py`: `DataSourceCreateDTO`, `DataSourceUpdateDTO`, `DataSourceResponse`, `DataSourceOption`.
- Cài đặt `app/services/data_source.py`: `list_data_sources`, `options_data_sources`, `create_data_source`, `update_data_source`, `deactivate_data_source`.
- Viết test trước: `tests/unit/test_data_source_service.py`.
- Kiểm tra: `uv run poe test`.

### Bước 2 — Kiểm tra kết nối theo vai trò (SOURCE / METADATA)
- Cài đặt hàm `test_data_source(ctx, ds_id)` trong `app/services/data_source.py`:
  - Đo thời gian ms, ghi nhận `LAST_TEST_AT`, `LAST_TEST_OK`, `LAST_TEST_MSG`, `LAST_TEST_MS`.
  - SOURCE: Kiểm tra kết nối đọc, cảnh báo nếu user có quyền ghi (`DS_NOT_READ_ONLY`).
  - METADATA: Kiểm tra quyền tạo bảng, quota, schema trống hay đã có `RECON_*`.
- Viết test: `tests/unit/test_data_source_connection.py` và integration test Oracle tự động skip khi thiếu biến.
- Kiểm tra: `uv run poe test`.

### Bước 3 — Mở kết nối nguồn và Catalog bảng/cột
- Cài đặt `app/services/source_conn.py`: `open_source_connection(ds_id)` có xử lý timeout và mất kết nối (`SOURCE_CONNECTION_LOST`, `SOURCE_TIMEOUT`).
- Cài đặt `app/engine/catalog.py`: `list_tables(ds_id, schema, q)`, `list_columns(ds_id, schema, table)` kèm bộ đệm cache in-memory TTL 10 phút.
- Viết test: `tests/unit/test_catalog.py`.
- Kiểm tra: `uv run poe test`.

### Bước 4 — Đồng bộ METADATA đang dùng lúc khởi động và Seed Data Source
- Cài đặt hàm `sync_current_metadata_source()` tự động tạo/cập nhật bản ghi `IS_CURRENT_METADATA='Y'` từ `settings.RECON_DB_URL`.
- Tích hợp hook vào startup của ứng dụng.
- Cập nhật lệnh `seed` trong `app/cli.py` để seed Data Source kiểm thử Oracle nếu có biến môi trường `ORACLE_TEST_*`.
- Viết test: `tests/unit/test_data_source_startup.py`.
- Kiểm tra: `uv run poe db-seed`; `uv run poe test`.

## 4. Chấp nhận khi
- [ ] CRUD + kiểm tra kết nối chạy qua service đúng quyền.
- [ ] Liệt kê bảng/cột nguồn qua VPN (tự skip nếu không có môi trường).
- [ ] Không lộ mật khẩu trong DB, DTO, log, audit.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh 100%.
