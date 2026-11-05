# 20-menu-admin — Danh sách menu cho Admin

- Ngày tạo: 2026-11-05
- Giai đoạn: GĐ2 (bổ sung)
- Phụ thuộc: 19-menu-permission
- Nhánh git: feat/20-menu-admin

## Mục tiêu
Admin chỉnh cách hiển thị menu mà không cần sửa code: đổi tên hiển thị, đổi nhóm, đổi thứ tự menu và nhóm, tạm ẩn menu khỏi mọi vai trò (kèm lý do), khôi phục mặc định, đánh dấu đã xem menu mới. Không tạo menu, không sửa đường dẫn.

## Đọc trước
- docs/specs/11_menu_permission.md
- docs/specs/11_menu_permission_tables.md
- designs/components/Screen15-MenuAdmin/preview.html

## Phạm vi
- Service menu_admin: list_tree, save (một lần cho mọi thay đổi, ROW_VERSION), reset (một menu/tất cả), mark_seen, preview_sidebar
- Tạm ẩn: lý do bắt buộc ≤ 300 ký tự; chặn menu IS_HIDEABLE='N' (menu_admin, role, user); vai trò thường bị chặn ở page và service (MENU_HIDDEN); ADMIN vẫn vào được
- Trang 'Chức năng tạm ngưng' hiển thị lý do
- Tên hiển thị không rỗng, không trùng tên menu khác (không phân biệt hoa thường); tên nhóm không rỗng
- Đổi nhóm: menu xuống cuối nhóm mới; đổi thứ tự bằng nút lên/xuống (bàn phím được)
- Menu mới (IS_NEW) có nhãn Mới ở màn này, ở màn Vai trò và ở thanh bên Admin; tự bỏ nhãn khi Admin bật menu cho một vai trò, hoặc bấm Đã xem
- Menu đã gỡ khỏi code: hiện mờ, chỉ đọc, ghi chú
- Màn /menus theo Screen15; tăng PERM_REVISION khi lưu; audit từng thay đổi

## Ngoài phạm vi
- Tạo/xóa menu hoặc nhóm
- Sửa đường dẫn, icon
- Lịch ẩn tự động theo giờ
- Ẩn theo từng vai trò (dùng màn Vai trò)

## Các bước
### Bước 1 — Service và quy tắc
- Làm: menu_admin.* , kiểm hợp lệ, chặn menu bắt buộc, ROW_VERSION, audit, PERM_REVISION
- Test viết trước: test_menu_admin_service.py
- Kiểm tra: `uv run poe test`

### Bước 2 — Áp dụng ẩn menu
- Làm: Page/service trả MENU_HIDDEN, trang Chức năng tạm ngưng, ADMIN vẫn vào; trang chủ chuyển khi dashboard bị ẩn
- Test viết trước: test_menu_hidden.py
- Kiểm tra: `uv run poe test`

### Bước 3 — Hiển thị theo DISPLAY_*
- Làm: Thanh bên, màn Vai trò dùng tên/nhóm/thứ tự hiển thị; khôi phục mặc định; sync không ghi đè
- Test viết trước: test_menu_display.py
- Kiểm tra: `uv run poe test`

### Bước 4 — UI Danh sách menu
- Làm: pages/menus.py theo Screen15: bảng nhóm+menu, lọc, tìm, xem trước thanh bên, hộp thoại ẩn và lưu
- Test viết trước: e2e test_menus.py
- Kiểm tra: `uv run poe e2e`

### Bước 5 — Hồi quy
- Làm: Toàn bộ test; menu mới từ code vẫn tự xuất hiện
- Test viết trước: toàn bộ test
- Kiểm tra: `uv run poe test`

## Checklist kiểm thử
`test-checklist.md` trong thư mục này. Mọi ca ưu tiên Cao phải đạt trước khi đóng task.

## Chấp nhận khi
- [ ] Đổi tên/nhóm/thứ tự có hiệu lực ở thanh bên mọi người ≤ 5 giây
- [ ] Menu tạm ẩn biến mất với vai trò thường, chặn ở server, ADMIN vẫn vào; bỏ ẩn thì quyền cũ của vai trò có hiệu lực lại
- [ ] Không ẩn được menu_admin, role, user
- [ ] Đồng bộ code không ghi đè tên/nhóm/thứ tự Admin đã chỉnh
- [ ] Khôi phục mặc định đưa về giá trị code
- [ ] `uv run poe typecheck`, `lint`, `test`, `e2e` xanh

## Câu hỏi mở
- —
