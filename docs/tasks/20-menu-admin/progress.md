# Tiến độ — 20-menu-admin

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Service và quy tắc | ✅ | 06/11/2026 |  |
| 2 | Áp dụng ẩn menu | ✅ | 06/11/2026 |  |
| 3 | Hiển thị theo DISPLAY_* | 🔄 |  |  |
| 4 | UI Danh sách menu | ⬜ |  |  |
| 5 | Hồi quy | ⬜ |  |  |

## Nhật ký

- 06/11/2026: plan 5 bước + Q0–Q8 duyệt ("làm theo đề xuất"). Nhánh `feat/20-menu-admin` tạo từ `18c8472` (đầu nhánh 19 sau patch bố cục `/roles`). Plan chép nguyên văn vào `plan.md`.
- 06/11/2026 bước 1 ✅: service mới `app/services/menu_admin.py` — `list_menu_tree_admin` (cây nhóm+menu kèm menu đã gỡ, số vai trò đang dùng), `save_menu_changes` (kiểm hết rồi ghi một transaction, khóa lạc quan ROW_VERSION từng dòng, nhãn trùng không phân biệt hoa thường, đổi nhóm xuống cuối nhóm mới, ẩn cần lý do ≤300 ký tự, chặn menu bắt buộc, audit từng thay đổi, tăng PERM_REVISION một lần), `reset_menus` (một menu/nhóm/tất cả, không đổi trạng thái ẩn), `mark_seen` (một menu/tất cả — Q1), `preview_sidebar` (áp thay đổi chưa lưu trong bộ nhớ theo prototype Screen15). Test viết trước `tests/unit/test_menu_admin_service.py` (29 test, đỏ trước khi code). Kiểm tra: `uv run poe test` 530 pass, 5 skip (tăng 29 so với 501); ruff check + format xanh. Test Oracle skip (không VPN trên máy ảo).
- 06/11/2026 bước 2 ✅: áp dụng ẩn menu — sidebar ADMIN hiện menu ẩn kèm nhãn "(Đang ẩn)" (`get_nav_items_for_menus(..., is_admin)`, `create_navbar` truyền `is_admin(ctx)`), menu đã gỡ không hiện với ai; trang chủ bị ẩn thì chuyển tới menu đầu tiên người dùng có (Q2, helper `first_nav_href` trong shell + `dashboard.layout()`); page_gate/service MENU_HIDDEN và `/suspended` đã có từ task 19, chỉ rà soát lại. Test viết trước `tests/unit/test_menu_hidden.py` (14 test). Trong lúc làm phát hiện: test dùng service thật phải patch cả namespace của module chứa hàm (`app.services.dashboard.get_recon_engine`) vì `_engine_for` lấy engine từ đó, không phải từ `app.db.engine` — test chạy lẻ thì xanh (import muộn bind đúng hàm đã patch) nhưng chạy cả bộ thì đỏ do module import trước. Kiểm tra: `uv run poe test` 544 pass, 5 skip (528 unit + 16 integration, tăng 14); ruff check + format xanh.
