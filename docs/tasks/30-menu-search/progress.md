# Tiến độ — 30-menu-search

Trạng thái: ⬜

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Bỏ hẳn badge "Mới" ở menu thanh bên | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |
| 2 | Ô tìm kiếm menu ở header (sau breadcrumb, trước badge môi trường) | ✅ | 2026-11-09 | 30-menu-search: steps 1-2 |

## Nhật ký
- 2026-11-09: Khởi tạo task 30 từ yêu cầu của người dùng (bỏ badge "Mới" + thêm ô tìm kiếm menu ở header, bo tròn kiểu Google Search, tìm có dấu/không dấu). Tạo nhánh `feat/30-menu-search` từ `4cf90bf`. Lên plan và được duyệt (Q0–Q3 theo đề xuất: Enter tới kết quả đầu, giới hạn 8 kết quả, chỉ khớp tên menu, rộng 320px).
- 2026-11-09: Hoàn thành bước 1 + 2 trong một commit chung (thay vì mỗi bước một commit như plan, vì cả hai bước cùng sửa `shell.py` và dùng chung file test `test_ui_shell.py`, tách ra sẽ làm commit giữa bị vỡ test): bỏ khối `dmc.Badge("Mới")` trong `create_navbar`; thêm `dmc.TextInput` bo tròn + `dcc.Store` + `dmc.Paper` kết quả trong `create_header`, helper `_strip_accents`/`filter_menu_items`, callback `handle_menu_search`. Test shell 17 pass, ruff + mypy sạch.
- 2026-11-09: Sửa lỗi phát hiện khi kiểm chứng Playwright: sau khi chuyển trang, ô tìm kiếm vẫn giữ từ vừa gõ (Dash giữ lại giá trị input theo id khi header dựng lại). Sửa: `TextInput` đặt sẵn `value=""` + callback `handle_menu_search` thêm Input `app-location.pathname` và Output giá trị ô tìm kiếm (đổi trang → xoá trắng + đóng dropdown). Test shell 18 pass (thêm test đổi trang xoá ô tìm kiếm), ruff + mypy sạch.
- 2026-11-09: Kiểm chứng Playwright trên server thử (DB có IS_NEW='Y' cho cả 16 menu): thanh bên không còn "Mới" (1440×900 và 1366×768); ô tìm kiếm hiện giữa breadcrumb và badge môi trường (x 518–838 ở 1440, 481–801 ở 1366), rộng 320px; gõ "doi soat" → 3 kết quả (Chạy đối soát, Chạy bộ đối soát, Bộ đối soát); Enter → /runs/new, ô tìm kiếm trống; bấm "Lịch sử" → /history; gõ "xyz" → "Không tìm thấy menu nào". Ảnh: `~/workspace/dashboard-preview/menu-search-1440.png`, `menu-search-1366.png`.
