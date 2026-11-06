# Tiến độ — 20-menu-admin

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Service và quy tắc | ✅ | 06/11/2026 |  |
| 2 | Áp dụng ẩn menu | ✅ | 06/11/2026 |  |
| 3 | Hiển thị theo DISPLAY_* | ✅ | 06/11/2026 |  |
| 4 | UI Danh sách menu | 🔄 |  |  |
| 5 | Hồi quy | ⬜ |  |  |

## Nhật ký

- 06/11/2026: plan 5 bước + Q0–Q8 duyệt ("làm theo đề xuất"). Nhánh `feat/20-menu-admin` tạo từ `18c8472` (đầu nhánh 19 sau patch bố cục `/roles`). Plan chép nguyên văn vào `plan.md`.
- 06/11/2026 bước 1 ✅: service mới `app/services/menu_admin.py` — `list_menu_tree_admin` (cây nhóm+menu kèm menu đã gỡ, số vai trò đang dùng), `save_menu_changes` (kiểm hết rồi ghi một transaction, khóa lạc quan ROW_VERSION từng dòng, nhãn trùng không phân biệt hoa thường, đổi nhóm xuống cuối nhóm mới, ẩn cần lý do ≤300 ký tự, chặn menu bắt buộc, audit từng thay đổi, tăng PERM_REVISION một lần), `reset_menus` (một menu/nhóm/tất cả, không đổi trạng thái ẩn), `mark_seen` (một menu/tất cả — Q1), `preview_sidebar` (áp thay đổi chưa lưu trong bộ nhớ theo prototype Screen15). Test viết trước `tests/unit/test_menu_admin_service.py` (29 test, đỏ trước khi code). Kiểm tra: `uv run poe test` 530 pass, 5 skip (tăng 29 so với 501); ruff check + format xanh. Test Oracle skip (không VPN trên máy ảo).
- 06/11/2026 bước 2 ✅: áp dụng ẩn menu — sidebar ADMIN hiện menu ẩn kèm nhãn "(Đang ẩn)" (`get_nav_items_for_menus(..., is_admin)`, `create_navbar` truyền `is_admin(ctx)`), menu đã gỡ không hiện với ai; trang chủ bị ẩn thì chuyển tới menu đầu tiên người dùng có (Q2, helper `first_nav_href` trong shell + `dashboard.layout()`); page_gate/service MENU_HIDDEN và `/suspended` đã có từ task 19, chỉ rà soát lại. Test viết trước `tests/unit/test_menu_hidden.py` (14 test). Trong lúc làm phát hiện: test dùng service thật phải patch cả namespace của module chứa hàm (`app.services.dashboard.get_recon_engine`) vì `_engine_for` lấy engine từ đó, không phải từ `app.db.engine` — test chạy lẻ thì xanh (import muộn bind đúng hàm đã patch) nhưng chạy cả bộ thì đỏ do module import trước. Kiểm tra: `uv run poe test` 544 pass, 5 skip (528 unit + 16 integration, tăng 14); ruff check + format xanh.
- 06/11/2026 bước 3 ✅: hiển thị theo DISPLAY_* — `menu_sync.read_display_tree` (dùng chung cho thanh bên và /roles, `list_menu_tree` refactor theo nó); `get_nav_items_for_menus` đọc tên/nhóm/thứ tự từ DB, chưa migration thì dùng lại hằng số code; nhãn "Mới" khôi phục ở checkbox /roles (xanh lá như trước) và thanh bên ADMIN (Badge cạnh tên mục, mini mode chỉ hiện trong tooltip); xem trước thanh bên ở /roles nhận thêm `is_admin` (vai trò hệ thống / user admin thì menu ẩn vẫn hiện kèm "Đang ẩn"); Q7: `role.update`/`create_role` tự đặt IS_NEW='N' cho menu vừa bật (cùng transaction). Test viết trước `tests/unit/test_menu_display.py` (15 test); test cũ `test_menu_checkboxes_no_new_badge_but_hidden_badge` đổi thành `..._new_badge_and_hidden_badge` theo hành vi mới. Trong lúc làm phát hiện 2 việc: (1) `render_sidebar_preview` có 2 docstring liên tiếp từ trước, đã gộp thành một; (2) rò settings cache: fixture `test_page_dashboard` đổi RECON_DB_URL + cache_clear ở setup nhưng không clear ở teardown, `get_settings` lru_cache giữ DB tạm (ở đó user_id=1 là operator) khiến thanh bên của `test_ui_shell` rỗng vì giờ đọc cây menu từ DB — sửa bằng fixture autouse `_clear_settings_cache` trong `tests/conftest.py` (theo mẫu `_clear_perm_cache`). Kiểm tra: `uv run poe test` 559 pass, 5 skip (tăng 15); ruff check + format xanh.
