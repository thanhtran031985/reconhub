# 02-data-sources — Data Source: nguồn Oracle và đích lưu RECON_APP

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ0
- Phụ thuộc: 01
- Nhánh git: feat/02-data-sources

## Mục tiêu
Admin khai báo kết nối Oracle cho nguồn đối soát (user chỉ đọc) và đích lưu RECON_APP (user/password schema); DB đang dùng (SQLite) hiện tự động; mật khẩu mã hóa; kiểm tra kết nối báo quyền phù hợp; liệt kê bảng/cột nguồn qua VPN.

## Phạm vi
- Repo, service data_source theo spec 05 (PURPOSE, HOST, PORT, SERVICE_NAME, DEFAULT_SCHEMA, CALL_TIMEOUT_S mặc định 600)
- app/core/crypto.py Fernet
- services/source_conn.py: `open_source(ds_id)` (oracledb Thin, call_timeout); mất kết nối → SOURCE_CONNECTION_LOST
- Kiểm tra SOURCE: ms, phiên bản, cảnh báo quyền ghi. Kiểm tra METADATA: quyền tạo bảng, quota, schema trống/đã có RECON_*
- Khởi động: đồng bộ bản ghi METADATA cho RECON_DB_URL (RECON_APP_SQLITE, FILE_PATH, dung lượng)
- engine/catalog.py: list_tables, list_columns, cache 10 phút
- Seed Data Source ORACLE_TEST từ biến ORACLE_TEST_* (nếu có)

## Ngoài phạm vi
- Giao diện (task 08)
- Chuyển metadata (task 13)

## Thiết kế
- designs/components/Screen08-DataSources (trường dữ liệu)

## Spec liên quan
- docs/specs/02 mục 2
- docs/specs/05 mục 2
- docs/specs/06 mục 2–3
- docs/specs/08 mục 2

## Quyết định kiến trúc
- Mật khẩu không nằm trong ServiceResult, log, audit, dcc.Store

## Các bước
### Bước 1 — Mã hóa + repo + service
- Làm: crypto, CRUD, options, deactivate, giữ mật khẩu khi rỗng, quyền
- Test viết trước: unit + integration SQLite
- Kiểm tra: `uv run poe test`

### Bước 2 — Kiểm tra kết nối
- Làm: test(id) theo purpose; lỗi tiếng Việt
- Test viết trước: unit với connection giả; oracle: RECON_SRC_RO read_only=true; RECON_APP_TEST đủ quyền, schema trống
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 3 — open_source + catalog
- Làm: pool, timeout, list_tables, list_columns
- Test viết trước: oracle: thấy SRC_FACT_INVOICE_DTP và 10 cột đúng kiểu
- Kiểm tra: `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

### Bước 4 — METADATA đang dùng + seed
- Làm: startup hook, seed
- Test viết trước: khởi động 2 lần chỉ một bản ghi Đang dùng
- Kiểm tra: `uv run poe db-seed`; `uv run poe test`

## Chấp nhận khi
- [ ] CRUD + kiểm tra kết nối chạy qua service đúng quyền
- [ ] Liệt kê bảng/cột nguồn qua VPN
- [ ] Không lộ mật khẩu
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- Host/service UAT/PROD và user chỉ đọc cho nguồn thật?
