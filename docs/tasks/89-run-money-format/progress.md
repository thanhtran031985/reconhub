# Progress — Task 89

## 14/11/2026
- Phân tích xong: `fmt_num` (run_result.py:111) là nguồn duy nhất của định
  dạng số tiền trang run; 18 chỗ dùng đều là số tiền; không module khác
  import. Phát hiện lỗi phụ: nhánh số lẻ cũ cho ra 2 dấu chấm.
- Nhánh `feat/89-run-money-format` từ 7772909.
- Đã sửa `fmt_num`: bỏ `.replace(",", ".")`; giữ `None`/`""` → `"—"`,
  `0` → `"0"`, số lẻ tối đa 2 chữ số. Cập nhật 21 chuỗi kỳ vọng cũ trong
  `tests/unit/test_page_run_result.py` sang dấu `,` mới.
- Test mới `tests/unit/test_run_money_format89.py`: 13 case (vd user
  1910000 → `1,910,000`; số lẻ, số âm, biên) — đỏ trước, xanh sau.
- Targeted: 49 passed (13 mới + 36 run-result). Typecheck sạch; lint chỉ
  lỗi I001 cũ ở `test_export_concurrency57.py`.
- Live check `check-89-money-format.py` PASS (port 8146): grid hiện
  `624,500,000`, drawer dòng 1 hiện `493,500,000` / `131,000,000`, không
  còn dạng cũ, không lỗi console mới.
- Full suite: **1992 passed, 6 skipped** (1979 + 13 test mới).
