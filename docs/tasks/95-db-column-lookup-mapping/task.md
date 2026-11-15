# 95-db-column-lookup-mapping — Đồng bộ nhãn cột từ lookup DB_COLUMN_MAPPING khi tạo template và migrate fact_bill

- Ngày tạo: 2026-11-15
- Giai đoạn: GĐ2
- Phụ thuộc: 17, 24, 27
- Nhánh git: feat/95-db-column-lookup-mapping

## Mục tiêu
1. Migrate tất cả các field của bảng `DATARAW.FACT_BILL` (Oracle GMD_DEV) vào loại danh mục `DB_COLUMN_MAPPING` trên trang `/lookups` đối với các field chưa tồn tại (112 cột còn thiếu, giữ nguyên 7 cột đã có).
2. Tại Tab 4 (Cấu hình cột) của trang `/report-admin`:
   - Khi tạo template mới hoặc discover cột lần đầu (hoặc làm mới cột từ nguồn khi xuất hiện cột mới): tự động mapping nhãn cột (`label`) theo `meaning` trong danh mục `DB_COLUMN_MAPPING` (so sánh không phân biệt hoa thường: `field_name.upper() == lookup_code.upper()`).
   - Trường hợp không matching được lookup code thì lấy theo rule hiện tại (chuyển `UPPER_SNAKE_CASE` sang `Title Case` qua `prettify_column_label`).
3. **Bảo toàn dữ liệu người dùng:** Khi mở lại hoặc chỉnh sửa (edit) template, hệ thống **không được tự động ghi đè** từ lookup mà **phải lấy đúng giá trị người dùng đã nhập / đã lưu** trong database (`RECON_RPT_COLUMN.LABEL`).
4. Nhãn cột hiển thị nhất quán trên Tab 4, sub-tab Xem trước layout, Trình xem báo cáo (`/report-viewer`) và file xuất Excel.

## Phạm vi
- Bổ sung dữ liệu seed / migration cho loại danh mục `DB_COLUMN_MAPPING` trong `RECON_LOOKUP_CODE`.
- Cập nhật service `app/services/lookup.py` để cung cấp hàm helper tra cứu `DB_COLUMN_MAPPING` nhanh và cache trong bộ nhớ.
- Cập nhật cơ chế phân giải nhãn cột trong `app/services/report_source.py` và `app/services/report_column.py`:
  - `apply_source_diff`: khi thêm cột mới từ nguồn, lấy nhãn mặc định từ `DB_COLUMN_MAPPING` nếu khớp mã; nếu không khớp thì dùng `prettify_column_label`.
  - `_column_dict` / `list_columns`: ưu tiên nhãn đã lưu nếu người dùng đã lưu nhãn khác rỗng; nếu nhãn lưu trùng tên cột (chưa từng lưu/default cũ) thì thử match `DB_COLUMN_MAPPING` trước khi fallback về `prettify_column_label`.
- Đảm bảo tính nhất quán giữa wizard cấu hình, viewer kết quả và export XLSX.

## Ngoài phạm vi
- Không thay đổi cấu trúc bảng `RECON_LOOKUP_CODE` hay `RECON_RPT_COLUMN` (không đổi schema DDL).
- Không tự động sửa nhãn các template đã tồn tại mà người dùng đã tùy biến trước đó.

## Thiết kế
- `designs/components/Screen16-Reporting/preview.html`
- Trang `/lookups` và `/report-admin`

## Spec liên quan
- `docs/specs/12-reporting-columns.md`
- `docs/tasks/49-column-label-format`

## Quyết định kiến trúc
- **D1 (Migration idempotent):** Migration nạp 112 cột từ `FACT_BILL` vào `RECON_LOOKUP_CODE` với `LOOKUP_TYPE = 'DB_COLUMN_MAPPING'`. Kiểm tra tồn tại trước khi insert (chỉ insert các field chưa có).
- **D2 (Ưu tiên nhãn đã lưu khi edit):** Khi template đã được lưu, nhãn do người dùng nhập/chỉnh sửa trong `RECON_RPT_COLUMN.LABEL` là giá trị ưu tiên cao nhất khi mở lại / edit. Lookup `DB_COLUMN_MAPPING` chỉ đóng vai trò gán nhãn khởi tạo lần đầu (initial mapping).
- **D3 (So sánh upper):** So sánh `field_name.strip().upper() == lookup_code.strip().upper()` để đảm bảo khớp chính xác bất kể định dạng chữ hoa/chữ thường.

## Các bước
### Bước 1 — Migration các field của `fact_bill` vào `DB_COLUMN_MAPPING`
- Làm: Tạo migration / seed script nạp 112 cột chưa tồn tại của `DATARAW.FACT_BILL` vào `RECON_LOOKUP_CODE` loại `DB_COLUMN_MAPPING`.
- Test viết trước: Kiểm tra số lượng mã trong `DB_COLUMN_MAPPING` đủ 119 cột, không duplicate, 7 mã ban đầu không bị ghi đè.
- Kiểm tra: `uv run poe test` → xanh.

### Bước 2 — Service tra cứu mapping nhãn cột và khởi tạo nhãn khi tạo template
- Làm: Thêm hàm helper `get_column_mappings()` trong `lookup.py`. Cập nhật `apply_source_diff` trong `report_source.py` để gán nhãn ban đầu từ `DB_COLUMN_MAPPING`.
- Test viết trước: Test discover nguồn gán đúng nhãn từ lookup khi mã khớp, và sinh Title Case khi không khớp.
- Kiểm tra: `uv run poe test` → xanh.

### Bước 3 — Bảo vệ giá trị user đã nhập khi mở lại / edit template
- Làm: Cập nhật `_column_dict` và `resolve_column_label` trong `report_column.py`: nếu cột đã có nhãn được lưu bởi user (hoặc đã lưu tùy biến), giữ nguyên nhãn đó; không tự động lấy đè từ lookup khi edit.
- Test viết trước: Test mở lại version đã có nhãn lưu thủ công thì nhãn không bị đè bởi lookup.
- Kiểm tra: `uv run poe test` → xanh.

### Bước 4 — Kiểm thử hồi quy, tích hợp UI và hoàn tất task
- Làm: Rà soát trang `/report-admin` Tab 4 và trang `/lookups`, chạy toàn bộ test suite.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` → xanh.

## Chấp nhận khi
- [ ] 112 field mới của `fact_bill` xuất hiện đầy đủ trong danh mục `DB_COLUMN_MAPPING` trên `/lookups` (tổng cộng 119 mã).
- [ ] 7 field đã có từ trước trong `DB_COLUMN_MAPPING` không bị thay đổi hay ghi đè.
- [ ] Khi tạo template mới với nguồn `FACT_BILL`: các cột tự động nhận nhãn từ `DB_COLUMN_MAPPING` (ví dụ `CONT_TYPE` nhận `LOẠI CONT`, `CONFIRM_DATE` nhận `NGÀY XÁC NHẬN`...).
- [ ] Cột không có trong `DB_COLUMN_MAPPING` tự động nhận nhãn theo rule hiện tại (Title Case).
- [ ] Khi mở lại / edit template đã lưu nhãn riêng: hệ thống giữ đúng giá trị user đã nhập, không tự động ghi đè từ lookup.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

### Data Model Impact
- [x] Task không thay đổi database schema (chỉ thêm dữ liệu bảng `RECON_LOOKUP_CODE`).
