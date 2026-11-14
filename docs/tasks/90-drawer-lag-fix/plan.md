# Plan — Task 90

## Bước
1. Đọc `handle_save_issue_from_drawer` + xác nhận 5 chỗ trả `0` cho trigger
   Store ở nhánh chặn/lỗi; xác nhận không callback nào khác ghi trigger
   Store. (Xong — xem task.md.)
2. Test đỏ: sửa `test_handle_save_issue_from_drawer` (`trig == 0` →
   `trig is dash.no_update`) + thêm test mới cho 4 nhánh lỗi còn lại.
3. Sửa code: 5 chỗ `..., 0` → `..., dash.no_update` trong
   `handle_save_issue_from_drawer`. Nhánh thành công giữ nguyên.
4. Chạy targeted tests + typecheck + ruff (chỉ dòng đổi).
5. Live check Playwright (port 8146, DB seed check-88f): S0 mở drawer → không
   còn response vẽ grid (`run-res-grid-container`), không còn longtask >1s;
   S1 bấm Lưu → grid vẫn refresh (trigger bump còn nguyên); không lỗi console
   mới.
6. Full suite → commit → patch → verify `git am` trên worktree sạch tại
   3871579 → cập nhật MEMORY.md → giao patch (áp SAU patch 89).

## Rủi ro
- Thấp: đổi giá trị trả về ở nhánh chặn/lỗi thành `no_update`; nhánh thành
  công không đổi. Test + live check bao phủ cả hai chiều (không refresh thừa,
  vẫn refresh khi lưu thật).
