# Plan — Task 89

## Bước
1. Đọc `fmt_num` + xác nhận 18 chỗ dùng đều là số tiền, không module khác
   import nó. (Xong — xem task.md.)
2. Sửa `fmt_num`: bỏ `.replace(",", ".")`, giữ hành vi `None`/`""` → `"—"`,
   `0` → `"0"`, số lẻ tối đa 2 chữ số, cắt 0 thừa.
3. Test mới `tests/unit/test_run_money_format89.py`: 1910000 → `1,910,000`;
   624500000 → `624,500,000`; 1234567.89 → `1,234,567.89`; 1234.5 →
   `1,234.5`; 0 → `0`; None/`""` → `—`; -1910000 → `-1,910,000`;
   `"abc"` → `"abc"`; 1000.0 → `1,000`.
4. Chạy targeted tests + typecheck + ruff (chỉ dòng đổi).
5. Live check Playwright (port 8146, DB seed check-88f): grid dòng 1 hiện
   `624,500,000`; mở drawer dòng 1 hiện `493,500,000` / `131,000,000`,
   không còn `493.500.000` trong vùng số tiền; không lỗi console mới.
6. Full suite → commit → patch → verify `git am` trên worktree sạch tại
   7772909 → cập nhật MEMORY.md → giao patch.

## Rủi ro
- Thấp: thay đổi 2 dòng trong 1 hàm cục bộ của 1 trang; test + live check
  bao phủ.
