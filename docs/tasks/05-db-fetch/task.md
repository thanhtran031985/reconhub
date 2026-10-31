# 05-db-fetch — SQL sinh từ bảng/cột, SQL guard, fetch Oracle qua VPN

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ1
- Phụ thuộc: 02, 03
- Nhánh git: feat/05-db-fetch

## Mục tiêu
Từ khai báo Bảng/View + cột lọc, sinh SELECT an toàn cho Oracle, sinh SQL gộp theo profile, kéo dữ liệu về Polars với timeout, giới hạn dòng, xử lý mất kết nối VPN. SQL tự viết qua SQL guard.

## Phạm vi
- engine/sql_dialect.py, sql_builder.py, sql_guard.py, fetch.py (spec 04 mục 8)
- Service template.describe_source, preview_sql
- Fetcher giả đọc db.parquet cho golden và e2e

## Ngoài phạm vi
- So sánh (task 06)
- Tạo dữ liệu nguồn trên Oracle (người dùng chạy scripts/oracle)

## Thiết kế
- designs/components/Screen03-TemplateWizard (bước 3: Câu SELECT sinh ra; bước 4: SQL gộp)

## Spec liên quan
- docs/specs/03 mục 5
- docs/specs/04 mục 8
- docs/specs/06 mục 3

## Quyết định kiến trúc
- Định danh từ whitelist, quote; giá trị luôn bind

## Các bước
### Bước 1 — Builder kind=table
- Làm: SELECT từ table/filters/static_where
- Test viết trước: snapshot SQL DTP; cột ngoài whitelist → COLUMN_NOT_FOUND; skip_if_empty
- Kiểm tra: `uv run poe test-engine`

### Bước 2 — SQL gộp theo profile
- Làm: GROUP BY, derived, norm, value_map, first_distinct
- Test viết trước: snapshot 3 profile
- Kiểm tra: `uv run poe test-engine`

### Bước 3 — SQL guard
- Làm: check_sql
- Test viết trước: ≥25 case
- Kiểm tra: `uv run poe test-engine`

### Bước 4 — Fetch + describe
- Làm: fetch_df theo lô, Decimal, max_rows, timeout, mất kết nối
- Test viết trước: unit với connection giả (timeout, ngắt giữa chừng → SOURCE_CONNECTION_LOST); oracle: SQL gộp BY_INVOICE trên bảng test ra 190 nhóm (190 − 2 + 2)
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN; người dùng chạy và dán kết quả)

## Chấp nhận khi
- [ ] SQL sinh từ bảng/cột chạy đúng trên Oracle test
- [ ] SQL độc hại bị chặn
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- Tên bảng/view nguồn DTP thật và cột ngày/đơn vị (để dựng template UAT, không chặn task)
