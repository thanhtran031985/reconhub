# 04-excel-reader — Đọc Excel, chuẩn hóa, control total, nạp dữ liệu tạm

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ1
- Phụ thuộc: 00
- Nhánh git: feat/04-excel-reader

## Mục tiêu
Engine đọc Excel/CSV mọi cột chuỗi, map theo template, chuẩn hóa, tách dòng lỗi, kiểm control total, lọc thời gian; dữ liệu đã chuẩn hóa nạp vào RECON_EXCEL_LOAD/ROW; service upload, inspect, detect.

## Phạm vi
- engine/reader.py, mapping.py, normalize.py, control_total.py, filters.py, inspect.py (spec 04 mục 1–4, 11)
- services/file_service.py (lưu theo sha256, magic bytes, kích thước, zip bomb), services/excel_load.py (nạp theo lô, ước BYTES_EST, bỏ qua nếu đã nạp và chưa xóa)
- Route /download/file/<id> kiểm quyền; file đã xóa → thông báo
- Golden runner khung + G03, G04, G05, G09, G12 phần đọc

## Ngoài phạm vi
- Gộp, so sánh (task 06)

## Thiết kế
- designs/components/Screen03-TemplateWizard (bước 1–2)

## Spec liên quan
- docs/specs/04 mục 1–4, 11
- docs/specs/02 mục 4
- docs/specs/06 mục 4

## Quyết định kiến trúc
- Polars + calamine; openpyxl chỉ trong test

## Các bước
### Bước 1 — Reader
- Làm: read_sheet, list_sheets, __row_no, CSV
- Test viết trước: sample: 201 dòng thô, Mã giao dịch giữ chuỗi; số 0 ở đầu
- Kiểm tra: `uv run poe test-engine`

### Bước 2 — Mapping + detect
- Làm: Mapping + detect
- Test viết trước: thiếu cột, alias, khác hoa thường
- Kiểm tra: `uv run poe test-engine`

### Bước 3 — Normalize + derive + invalid
- Làm: Normalize + derive + invalid
- Test viết trước: G04, G09
- Kiểm tra: `uv run poe test-engine`

### Bước 4 — Control total + filters
- Làm: Control total + filters
- Test viết trước: G05 sample 366.732.000; file thật trong samples/private nếu có; G06 phần Excel
- Kiểm tra: `uv run poe test-engine`

### Bước 5 — Inspect
- Làm: Inspect
- Test viết trước: sample: phát hiện 'Tổng tiền', 190/200 hóa đơn, Mã giao dịch lẫn kiểu
- Kiểm tra: `uv run poe test-engine`

### Bước 6 — Service file + nạp dữ liệu tạm
- Làm: upload, inspect, detect, excel_load, route
- Test viết trước: nạp sample 200 dòng, nạp lại không trùng; .exe đổi đuôi → FILE_TYPE_NOT_ALLOWED
- Kiểm tra: `uv run poe test`

## Chấp nhận khi
- [ ] Sample đọc đúng 200 dòng, dòng tổng loại, control total khớp
- [ ] Dữ liệu tạm lưu và đọc lại được
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
