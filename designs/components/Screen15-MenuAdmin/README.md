# Screen15-MenuAdmin – Danh sách menu (`/menus`, menu `menu_admin`)

Prototype: `preview.html`. Spec 11 mục 7.2, task 20.

- Đầu trang: mô tả quy tắc (menu do code, Admin chỉnh hiển thị và tạm ẩn). Cảnh báo menu mới từ code và menu đã gỡ khỏi code.
- Bảng nhóm + menu: Thứ tự (nút ↑↓, có aria-label), Tên hiển thị (ô sửa + "Mặc định: …"), Mã · đường dẫn (chỉ đọc, mono), Nhóm (select + mặc định), Vai trò bật, Trạng thái (Hiển thị / Đang ẩn + lý do / Mới / Đã gỡ khỏi code / Bắt buộc), thao tác (Tạm ẩn / Bỏ ẩn / Đã xem / Mặc định).
- Dòng nhóm: đổi tên, đổi thứ tự nhóm, khôi phục mặc định.
- Tìm, lọc (Tất cả, Đang ẩn, Mới, Đã đổi so với mặc định, Đã gỡ khỏi code); Khôi phục mặc định tất cả.
- Cột phải: Xem trước thanh bên (theo thay đổi chưa lưu) và Trang "Chức năng tạm ngưng".
- Hộp thoại Tạm ẩn: lý do bắt buộc, số vai trò bị ảnh hưởng. Hộp thoại Lưu: liệt kê từng thay đổi.
- Thanh dưới: số thay đổi chưa lưu, Hủy thay đổi, Lưu. Dòng đã đổi có vạch tím.
- Nút "Mô phỏng đồng bộ từ code" chỉ có trong prototype.

Dash: bảng dùng `dag.AgGrid` hoặc `dmc.Table` (≤ 50 dòng); hộp thoại `dmc.Modal`; nút lên/xuống thay kéo thả (truy cập bằng bàn phím).
