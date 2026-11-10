# Plan — Task 41

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_page_padding41.py`: root của 5 trang có
  `style["padding"] == "8px 12px"` (khớp `#admin-list-container` của
  /report-admin, test khóa giá trị tham chiếu); `/account` root cùng
  padding + `dmc.Stack(maw=640)` có `mx == "auto"`.
- Chạy test đỏ trước khi sửa.

## Bước 2 — Sửa layout

- `data_sources.py`, `lookups.py`, `users.py`, `roles.py`, `menus.py`:
  thêm `"padding": "8px 12px"` vào style của root `html.Div` (cả nhánh
  lỗi của menus). Không thêm `gap` (các trang đã có `mb="xs"` ở header/
  filter bar, thêm gap sẽ nhân đôi khoảng cách).
- `account.py`: root thêm `"padding": "8px 12px"`; `dmc.Stack(maw=640)`
  thêm `mx="auto"` để canh giữa. Giữ nguyên padding trong `16px 20px`
  của vùng cuộn (khoảng đệm quanh cột nội dung).

## Bước 3 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-41.py`: đo computed padding-left/top của
  header từng trang (12px/8px), đo cột /account canh giữa (lệch trái ≈
  lệch phải, dung sai 2px); screenshot 1 trang.
- Commit, xuất patch từ `fa25b0f` (tip task 40), verify `git am` sạch.
