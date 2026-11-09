# Tiến độ — 30-menu-search

Trạng thái: ⬜

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Bỏ hẳn badge "Mới" ở menu thanh bên | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |
| 2 | Ô tìm kiếm menu ở header (sau breadcrumb, trước badge môi trường) | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |

## Nhật ký
- 2026-11-09: Khởi tạo task 30 từ yêu cầu của người dùng (bỏ badge "Mới" + thêm ô tìm kiếm menu ở header, bo tròn kiểu Google Search, tìm có dấu/không dấu). Tạo nhánh `feat/30-menu-search` từ `4cf90bf`. Lên plan và được duyệt (Q0–Q3 theo đề xuất: Enter tới kết quả đầu, giới hạn 8 kết quả, chỉ khớp tên menu, rộng 320px).
- 2026-11-09: Hoàn thành bước 1 + 2 trong một commit chung (thay vì mỗi bước một commit như plan, vì cả hai bước cùng sửa `shell.py` và dùng chung file test `test_ui_shell.py`, tách ra sẽ làm commit giữa bị vỡ test): bỏ khối `dmc.Badge("Mới")` trong `create_navbar`; thêm `dmc.TextInput` bo tròn + `dcc.Store` + `dmc.Paper` kết quả trong `create_header`, helper `_strip_accents`/`filter_menu_items`, callback `handle_menu_search`. Test shell 17 pass, ruff + mypy sạch.
- 2026-11-09: Đang kiểm chứng Playwright (gõ "doi soat" → thấy "Chạy đối soát", bấm → chuyển trang) và chụp màn hình 1440×900 / 1366×768 cho người dùng xem trước.
