# Task 45 — Dọn khoảng trắng dưới trang + 3 lỗi console

## Yêu cầu (10/11/2026, người dùng)

- Dưới phân trang /report-runs có 1 khoảng trắng — có phải footer?
- 3 lỗi console: (1) `ReferenceError: app-menu-search-input` không tồn
  tại trong callback; (2) `value` prop on `input` should not be null;
  (3) uncontrolled input → controlled.

## Nguyên nhân (đã đọc code)

1. **Khoảng trắng: không phải footer** (app không có footer).
   `AppShellMain` đặt `height: calc(100vh - 44px)` nhưng main bắt đầu từ
   `y=0` (header fixed đè lên trên), nên main kết thúc sớm hơn đáy màn
   hình đúng 44px, lộ nền trắng của body. Đo được ở môi trường kiểm
   chứng: viewport 900 → main hết ở 856. Lỗi khung app, mọi trang đều bị.
2. **Menu-search race:** layout gốc (`create_shell_layout`) chỉ có
   `app-shell-container` rỗng; `render_app_shell` (theo pathname) mới
   chèn AppShell + ô tìm kiếm. `handle_menu_search` có Input pathname
   nên chạy ngay lúc tải trang, trước khi header kịp render → Dash báo
   input không tồn tại. Sau khi header render xong thì tìm kiếm chạy
   bình thường.
3. **value=null:** `render_param_control` truyền `value=None` cho ô nhập
   khi tham số chưa có giá trị (DATE_RANGE Từ/Đến, DATE, SELECT,
   MULTI_SELECT, NUMBER, TEXT). React coi null là uncontrolled, lúc có
   giá trị thì thành controlled → cả 2 cảnh báo.

## Phạm vi

- `shell.py` (Main height + menu-search), `report_widgets.py`
  (value=None → "" / []), test.
- Không sửa `issues.py`: drawer ở đó truyền `value=None` nhưng service
  `update_issue_by_id` chỉ ghi REASON_CODE `if reason_code is not None`
  — đổi sang "" sẽ ghi đè "" xuống DB, đổi hành vi lưu. Ghi chú lại,
  sửa riêng nếu cần.
- Không migration.
