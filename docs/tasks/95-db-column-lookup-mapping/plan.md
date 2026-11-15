# Kế hoạch thực hiện — 95-db-column-lookup-mapping

## Bước 1: Migration 112 field chưa tồn tại của `fact_bill` vào `DB_COLUMN_MAPPING`
1. Lấy danh sách 119 cột của `DATARAW.FACT_BILL`.
2. Truy vấn các mã hiện có trong `RECON_LOOKUP_CODE` với `LOOKUP_TYPE = 'DB_COLUMN_MAPPING'`.
3. Bỏ qua các mã đã có (7 mã hiện hữu: `CONFIRM_DATE`, `CONT_NO`, `CONT_SIZE`, `CONT_TYPE`, `INVOICE_DATE`, `INVOICE_NO`, `INV_CURRENCY`).
4. Thêm 112 mã còn lại vào `RECON_LOOKUP_CODE` với:
   - `LOOKUP_TYPE`: `'DB_COLUMN_MAPPING'`
   - `LOOKUP_CODE`: Tên cột viết hoa.
   - `MEANING`: Nhãn nghiệp vụ tiếng Việt (nếu có trong hệ thống) hoặc Title Case (`prettify_column_label`).
   - `DISPLAY_ORDER`: Tiếp nối các mã hiện có.
   - `IS_ACTIVE = 'Y'`, `COLOR_BADGE = 'blue'`, `ICON_NAME = 'lucide:circle'`, `IS_SYSTEM = 'N'`.
5. Tạo migration revision / seed idempotent để chạy tự động và an toàn.

## Bước 2: Tra cứu mapping nhãn cột khi tạo template mới
1. Thêm hàm helper `get_db_column_mappings(conn)` trong `app/services/lookup.py`.
2. Cập nhật `apply_source_diff` trong `app/services/report_source.py`:
   - Khi phát hiện cột mới từ nguồn (`col in diff["added"]`):
   - Tra cứu `name.upper()` trong `DB_COLUMN_MAPPING`.
   - Nếu tìm thấy: gán `LABEL = lookup_meaning`.
   - Nếu không tìm thấy: gán `LABEL = prettify_column_label(name)`.

## Bước 3: Bảo vệ giá trị user đã nhập khi mở lại / edit template
1. Trong `app/services/report_column.py` (`_column_dict` / `list_columns`):
   - Đảm bảo khi mở lại version đã có nhãn được lưu, hệ thống trả về đúng `row["LABEL"]` người dùng đã nhập.
   - Tuyệt đối không tự động lấy đè từ `DB_COLUMN_MAPPING` khi edit.

## Bước 4: Kiểm thử và hoàn tất
1. Viết unit test cho:
   - Migration dữ liệu không trùng lặp, giữ nguyên 7 mã cũ, đủ 119 mã.
   - Khi tạo template mới / discover cột mới: mapping đúng nhãn từ lookup code.
   - Khi mở lại template đã có nhãn lưu bởi user: giữ nguyên nhãn của user, không bị đè bởi lookup code.
2. Kiểm tra trên giao diện `/lookups` và `/report-admin`.
3. Chạy `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` và `uv run poe tasks-dashboard`.
