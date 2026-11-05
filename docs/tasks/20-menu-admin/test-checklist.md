# Checklist kiểm thử — 20-menu-admin

Loại: **A** tự động (pytest) · **E** E2E (Playwright) · **O** Oracle qua VPN · **M** kiểm tay. Ca ưu tiên **Cao** phải đạt trước khi đóng task.

Tổng: **26 ca** · Cao 16

## 1. Đổi hiển thị

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-00-01 | Đổi tên hiển thị, lưu | — | Thanh bên mọi người đổi ≤ 5 giây; màn Vai trò dùng tên mới | E | Cao |
| ☐ | T20-00-02 | Tên rỗng / trùng menu khác (khác hoa thường) | — | Lỗi dưới ô, không lưu | E | Cao |
| ☐ | T20-00-03 | Đổi nhóm | — | Menu xuống cuối nhóm mới; nhóm cũ rỗng thì ẩn khỏi thanh bên | E | Cao |
| ☐ | T20-00-04 | Đổi thứ tự menu, thứ tự nhóm bằng nút lên/xuống và bàn phím | — | Thứ tự đúng; nút đầu/cuối bị khóa | E | Trung bình |
| ☐ | T20-00-05 | Đổi tên nhóm | — | Thanh bên dùng tên mới | E | Trung bình |
| ☐ | T20-00-06 | Khôi phục mặc định một menu / tất cả | — | Về giá trị code; không đổi trạng thái ẩn, không đổi quyền | A | Cao |
| ☐ | T20-00-07 | Đồng bộ code sau khi Admin chỉnh | Code đổi label | DISPLAY_* giữ, dòng 'Mặc định' cập nhật | A | Cao |

## 2. Tạm ẩn

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-01-01 | Ẩn không nhập lý do | — | Chặn, lỗi dưới ô | E | Cao |
| ☐ | T20-01-02 | Ẩn menu, lưu | Vai trò thường có menu | Mất khỏi thanh bên; URL → trang Chức năng tạm ngưng có lý do; service MENU_HIDDEN | E | Cao |
| ☐ | T20-01-03 | ADMIN với menu đang ẩn | — | Vẫn thấy (nhãn Đang ẩn) và vào được | E | Cao |
| ☐ | T20-01-04 | Bỏ ẩn | — | Vai trò đã bật trước đó có lại menu | A | Cao |
| ☐ | T20-01-05 | Ẩn menu_admin, role, user | UI và gọi service | Không có nút; service MENU_NOT_HIDEABLE | A | Cao |
| ☐ | T20-01-06 | Ẩn dashboard | — | Trang chủ chuyển tới menu đầu tiên người dùng có | E | Trung bình |
| ☐ | T20-01-07 | Màn Vai trò khi menu đang ẩn | — | Vẫn bật/tắt được, có nhãn Đang ẩn | E | Trung bình |

## 3. Menu mới, menu gỡ khỏi code

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-02-01 | Menu mới | menu_sync thêm | Nhãn Mới ở màn này, màn Vai trò, thanh bên Admin; cảnh báo đầu trang | E | Cao |
| ☐ | T20-02-02 | Bấm Đã xem / bật cho một vai trò | — | Mất nhãn Mới | A | Trung bình |
| ☐ | T20-02-03 | Menu đã gỡ | — | Mờ, chỉ đọc, ghi chú; lọc 'Đã gỡ khỏi code' ra đúng | E | Trung bình |

## 4. Lưu, quyền, audit

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-03-01 | Lưu nhiều thay đổi | — | Hộp thoại liệt kê đúng; một transaction; PERM_REVISION tăng | A | Cao |
| ☐ | T20-03-02 | Hai Admin cùng sửa | ROW_VERSION cũ | STALE_DATA, không ghi đè | A | Cao |
| ☐ | T20-03-03 | Rời trang khi chưa lưu | — | Cảnh báo | E | Thấp |
| ☐ | T20-03-04 | Vai trò không có menu menu_admin | Mở /menus, gọi service | /forbidden; FORBIDDEN | A | Cao |
| ☐ | T20-03-05 | Audit | đổi tên, nhóm, thứ tự, ẩn (lý do), bỏ ẩn, khôi phục | Có bản ghi trước/sau | A | Cao |

## 5. Giao diện

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-04-01 | Tìm, lọc (Đang ẩn, Mới, Đã đổi, Đã gỡ), không kết quả có Xóa bộ lọc | — | Đúng | E | Trung bình |
| ☐ | T20-04-02 | Xem trước thanh bên theo thay đổi chưa lưu | — | Đúng, ẩn menu đang ẩn | E | Trung bình |
| ☐ | T20-04-03 | 4 trạng thái, 1366/375/320px, chế độ tối | — | Không tràn trang; bảng cuộn trong khung | E | Trung bình |

## 6. Hồi quy

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T20-05-01 | Task 19 checklist nhóm 3–5 | — | Vẫn đạt | A | Cao |

## Ghi nhận

| Ngày | Người | ID | Kết quả | Ghi chú |
|---|---|---|---|---|
|  |  |  |  |  |
