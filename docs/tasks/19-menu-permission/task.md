# 19-menu-permission — Phân quyền theo menu và phạm vi dữ liệu theo người chạy

- Ngày tạo: 2026-11-05
- Giai đoạn: GĐ0 (bổ sung)
- Phụ thuộc: 01-auth-users (làm ngay sau task 01)
- Nhánh git: feat/19-menu-permission

## Mục tiêu
Thay 4 vai trò cố định bằng vai trò do Admin tạo, cấu hình bật/tắt từng menu; ADMIN là vai trò đặc biệt duy nhất. Danh sách menu khai báo trong code và tự đồng bộ vào DB. Vai trò thường chỉ thấy run do mình chạy; thao tác nhạy cảm chỉ ADMIN. Thay đổi quyền có hiệu lực ≤ 5 giây không cần đăng xuất.

## Đọc trước
- docs/specs/11_menu_permission.md
- docs/specs/11_menu_permission_tables.md
- designs/components/Screen14-Permission/preview.html (đã duyệt, xem điều chỉnh spec 11 mục 7.1)

## Phạm vi
- 4 bảng mới + đổi RECON_USER_ROLE sang ROLE_ID (spec 11a), seed vai trò tương đương v4
- app/ui/menus.py (MENUS, GROUPS) và services/menu_sync.py (đồng bộ khi khởi động, khóa chống chạy chồng)
- services/perm.py: effective_menus, is_admin, @requires_menu, require_admin, owner_filter; cache theo PERM_REVISION
- Gắn menu_code cho mọi page và service hiện có; test quét registry phát hiện chỗ thiếu
- owner_filter cho mọi đường truy cập run, lần chạy bộ, lịch sử, dashboard, tải file (NOT_FOUND khi không thuộc phạm vi)
- Màn Vai trò và phân quyền (/roles) theo Screen14 với điều chỉnh ở spec 11 mục 7.1
- Thanh bên đọc effective_menus, tự làm mới khi PERM_REVISION đổi; màn Người dùng chọn vai trò từ RECON_ROLE
- Audit; chuyển Oracle (spec 08) chép đúng thứ tự

## Ngoài phạm vi
- Đổi tên/nhóm/thứ tự/ẩn menu (task 20)
- Phân quyền mức thao tác
- Quyền riêng từng người
- Phạm vi dữ liệu khác ngoài 'của mình'/'tất cả (ADMIN)'

## Các bước
### Bước 1 — Schema và migration
- Làm: 4 bảng, RECON_USER_ROLE → ROLE_ID, seed vai trò + menu, PERM_REVISION
- Test viết trước: test_perm_migration.py: upgrade/downgrade, user cũ giữ đúng menu như v4
- Kiểm tra: `uv run poe test`

### Bước 2 — Khai báo menu và đồng bộ
- Làm: menus.py, menu_sync: thêm/cập nhật SOURCE_*/gỡ khỏi code/xuất hiện lại; không ghi đè DISPLAY_*
- Test viết trước: test_menu_sync.py (gồm 2 process khởi động cùng lúc)
- Kiểm tra: `uv run poe test`

### Bước 3 — Tính quyền và kiểm tra
- Làm: effective_menus, requires_menu, require_admin, cache revision
- Test viết trước: test_perm_effective.py, test_perm_registry.py (mọi page/service có menu_code)
- Kiểm tra: `uv run poe test`

### Bước 4 — Phạm vi dữ liệu
- Làm: owner_filter ở repo run, batch, issue, dashboard, route tải file
- Test viết trước: test_owner_scope.py: B dùng ID của A ở mọi đường → NOT_FOUND; ADMIN thấy hết
- Kiểm tra: `uv run poe test`

### Bước 5 — Service vai trò
- Làm: create/clone/update/delete/users_of/effective_of_user, rào chắn ADMIN, LAST_ADMIN, ROLE_IN_USE, audit
- Test viết trước: test_role_service.py
- Kiểm tra: `uv run poe test`

### Bước 6 — UI vai trò và thanh bên
- Làm: pages/roles.py 3 tab; thanh bên theo quyền, làm mới ≤ 5 giây; trang /forbidden
- Test viết trước: e2e test_roles.py
- Kiểm tra: `uv run poe e2e`

### Bước 7 — Cập nhật task cũ và hồi quy
- Làm: Thay require_role trong code đã có; cập nhật USER_GUIDE; chuyển Oracle
- Test viết trước: toàn bộ test + test-oracle (VPN)
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle`

## Checklist kiểm thử
`test-checklist.md` trong thư mục này. Mọi ca ưu tiên Cao phải đạt trước khi đóng task.

## Chấp nhận khi
- [ ] Admin tạo vai trò, bật/tắt menu; người dùng thấy đúng thanh bên và bị chặn ở server khi gọi màn không có quyền
- [ ] ADMIN không sửa/xóa được, luôn có mọi menu kể cả menu mới; không xóa được ADMIN cuối cùng
- [ ] Menu mới thêm trong code tự xuất hiện, chỉ ADMIN có cho tới khi bật cho vai trò
- [ ] Vai trò thường không thấy run/lần chạy bộ của người khác ở mọi đường truy cập (NOT_FOUND)
- [ ] 3 thao tác nhạy cảm chỉ ADMIN dù có menu
- [ ] Đổi quyền có hiệu lực ≤ 5 giây với phiên đang mở
- [ ] `uv run poe typecheck`, `lint`, `test`, `e2e` xanh

## Câu hỏi mở
- Có cần màn xem nhật ký thay đổi phân quyền riêng, hay dùng màn audit chung?
