# Plan — Task 46

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_console_cleanup46.py`:
  - `page_header(title="Chuỗi")` → đúng 1 thẻ h4 chứa chuỗi.
  - `page_header(title=dmc.Title(..., id="history-title"))` → đúng 1 thẻ
    h4, giữ nguyên id (không bọc thêm).
  - `handle_drag_drop_reorder` với kéo tham số hợp lệ → trả 2 giá trị
    (không còn Output thứ 3); kéo rỗng/không phải param → PreventUpdate.
- Chạy test đỏ trước khi sửa.

## Bước 2 — Sửa

- `page_header.py`: `title: str | Any` — chuỗi thì bọc `Title(order=4)`
  như cũ; component thì dùng thẳng.
- `report_admin.py`: `handle_drag_drop_reorder` bỏ Output
  `admin-col-preview-container` + bỏ giá trị trả thứ 3 ở cả 2 nhánh.

## Bước 3 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-46.py`: tải /report-admin (danh sách)
  không còn ReferenceError Output; mở /history không còn cảnh báo
  h4 lồng h4, tiêu đề có id history-title; mở wizard template, kéo
  tham số ở bước 3 (mô phỏng qua set_props) vẫn đổi vị trí + hiện
  alert thành công, không lỗi console.
- Commit, xuất patch từ `4604709` (tip task 45), verify `git am` sạch.
