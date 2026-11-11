# Task 49 — progress

## Bước 1 — Đọc code + chốt vị trí (xong, 11/11/2026)
- Nhãn mặc định hiện tại: `report_source.py:566` apply-diff `LABEL=name`
  (đường duy nhất tạo cột mới); clone copy nguyên nhãn.
- Các chỗ đọc nhãn: `_column_dict` (grid tab 4 + preview),
  `_result_layout` (Viewer/Export), `load_version_detail` (report_run),
  `_version_detail` (report_template).
- Nhánh `feat/49-column-label-format` từ `df35cbe` (tip task 47).
  Lưu ý: nhánh `feat/48-canvas-fill-revert` đang TẠM DỪNG theo yêu cầu
  người dùng — task 49 tách riêng, không động vào đó.

## Bước 2 — Sửa + kiểm chứng (xong, 11/11/2026)
- `prettify_column_label` + `effective_column_label` mới ở
  `report_source.py`; tạo cột lưu nhãn Title Case; 4 chỗ đọc nhãn dùng nhãn
  hiệu dụng (grid tab 4, preview, Viewer/Export, version detail).
- Test mới 16 (helper 11 case + `_column_dict` 3 + tạo cột 1 + user-label 1);
  cập nhật 6 test cũ khẳng định hành vi cũ (header export XLSX/CSV, preview,
  bulk all-or-nothing, bulk duplicate, export queue) sang nhãn Title Case.
- Typecheck 0 lỗi, lint sạch, full suite **1489 pass / 6 skipped**.
- Playwright `~/workspace/check-49.py` **11/11**: grid hiện Transaction Date
  / Invoice Date / Số tiền; sửa → Lưu cột → tải lại vẫn "Ngày giao dịch";
  preview hiện nhãn Title Case; không lỗi trang.
