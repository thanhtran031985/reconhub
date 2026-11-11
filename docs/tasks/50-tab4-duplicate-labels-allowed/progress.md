# Task 50 — progress

## Bước 2 — Sửa + kiểm chứng (xong, 11/11/2026)
- Bỏ hẳn chặn trùng nhãn ở `update_column` (nhánh `final_label` /
  `other_labels` trong `_validate_column_rules`) và `update_columns`
  (khối `merged`).
- Test mới 2 (trùng có sẵn + trùng mới đều lưu được); cập nhật 3 test
  `TestLabelUnique` → `TestLabelDuplicateAllowed`.
- Typecheck 0 lỗi, lint sạch, full suite **1491 pass / 6 skipped**.
- Playwright `~/workspace/check-50.py` **4/4**: 3 cột cùng nhãn
  "Transaction Date" lưu được và giữ nguyên sau tải lại; sửa nhãn khác khi
  đang có trùng sẵn vẫn lưu được; không lỗi trang.
