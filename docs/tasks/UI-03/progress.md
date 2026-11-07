# Tiến độ thực hiện TASK UI-03 — Admin Master–Detail

## Trạng thái: ✅ DONE

### Các bước đã hoàn thành:
- [x] **Bước 1 — Lookups Master–Detail (`/lookups`)**:
  - Chuyển layout sang Master-Detail 2 cột: Left (Master ~320px) danh sách Lookup Types cuộn nội bộ; Right (Detail flex: 1) quản lý Lookup Codes với sticky headers và cuộn nội bộ.
  - Tích hợp `page_header` Fluent Compact.
  - Fix lặp thuộc tính `style` trong `page_header.py`.
  - 16/16 tests passed (`tests/unit/test_page_lookups.py`).
- [x] **Bước 2 — Users Master–Detail (`/users`)**:
  - Chuyển sang bố cục Fluent Compact: Header 1 dòng gọn gàng, filter bar nhỏ gọn.
  - Sticky table headers cho bảng người dùng trong flex container cuộn nội bộ (loại bỏ page-scroll).
  - Bảo tồn 100% cấu trúc drawer và các modal/callbacks.
  - 6/6 tests passed (`tests/unit/test_page_users.py`).
- [x] **Bước 3 — Roles & Permissions Matrix (`/roles`)**:
  - Khắc phục triệt để lỗi tràn ngang 1410px và cuộn 1496px: Master (Trái 320px) danh sách vai trò cuộn nội bộ; Detail (Phải flex: 1) cấu hình quyền menu & xem trước với sticky dirty bar.
  - Chuyển `dmc.Grid` sang flex row không tràn ngang.
  - 29/29 tests passed (`tests/unit/test_page_roles.py`).
- [x] **Bước 4 — Menus Administration (`/menus`)**:
  - Khắc phục triệt để lỗi tràn ngang 1460px và cuộn 3017px: Master (Trái flex: 1) bảng phân cấp menu kèm toolbar lọc, cuộn nội bộ với sticky header; Detail (Phải 340px) xem trước thanh bên & trang tạm ngưng cuộn riêng.
  - Giữ nguyên các modal thao tác và cơ chế diff/save nháp.
  - 24/24 tests passed (`tests/unit/test_menus_page.py`).
- [x] **Bước 5 — Verification & Lint**:
  - Toàn bộ 75/75 unit tests của 4 trang đều PASSED.
  - `uv run ruff check` passed cleanly.
