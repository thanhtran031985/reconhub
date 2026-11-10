# Plan — Task 45

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_console_cleanup45.py`: Main height `100vh`;
  `render_param_control` không còn trả `value=None` (DATE/DATE_RANGE/
  SELECT/TEXT/NUMBER → `""`, MULTI_SELECT → `[]`); `handle_menu_search`
  còn tìm/Enter được với chữ ký mới (không pathname).
- Cập nhật test cũ `test_ui_shell.py`: các lần gọi `handle_menu_search`
  bỏ tham số pathname; bỏ test navigation-clears (hành vi xóa khi đổi
  trang nay do `render_app_shell` dựng lại header).
- Chạy test đỏ trước khi sửa.

## Bước 2 — Sửa

- `shell.py`: `AppShellMain` `height` từ `calc(100vh - 44px)` → `100vh`
  (giữ padding-top 44 của header fixed, main chạm đáy viewport).
- `shell.py`: bỏ Input pathname khỏi `handle_menu_search` + bỏ nhánh
  xóa khi đổi trang — không mất hành vi vì `render_app_shell` dựng lại
  header (ô tìm kiếm mới `value=""`, dropdown ẩn) mỗi lần đổi trang.
- `report_widgets.py`: mọi `value=None` trong `render_param_control`
  → `""` (DATE_RANGE Từ/Đến, DATE, SELECT, NUMBER, TEXT),
  MULTI_SELECT → `[]`. An toàn vì `resolve_param_values` coi `""` và
  `[]` là thiếu giá trị giống `None`.

## Bước 3 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-45.py`: tải app, đăng nhập, qua
  /report-runs + /reports/<id> — không còn 3 lỗi console (chỉ còn
  cảnh báo proxy chặn CDN iconify có sẵn); main chạm đáy viewport
  (không còn dải trắng 44px); tìm kiếm menu gõ + Enter vẫn chạy;
  form tham số DATE_RANGE trống không cảnh báo, chọn ngày + chạy được.
- Commit, xuất patch từ `f057905` (tip task 44), verify `git am` sạch.
