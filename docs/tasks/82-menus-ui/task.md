# Task 82 — /menus UI theo chuẩn ui-dash + thu nhỏ preview + icon thao tác + ẩn/hiện preview

## Yêu cầu (user 13/11/2026, kèm ảnh /menus)
- Chỉnh lại UI trang Danh sách menu (`/menus`, Screen15) cho đúng thiết kế chuẩn (ui-dash).
- Card "Xem trước thanh bên" giảm còn 2/3 so với hiện tại.
- Các button ở cột Thao tác chuyển thành icon + hint thay vì button + text (chiếm nhiều diện tích).
- Card "Xem trước thanh bên" thêm button để bấm ẩn/hiện card.

## Hiện trạng (đã đọc code `app/ui/pages/menus.py`, 1355 dòng)
- Layout: page_header | alert mới/bị gỡ | Master–Detail 2 cột (bảng trái + cột phải 340px với 2 Paper xem trước) | thanh Lưu dính ở chân. Trang không cuộn (root `height: calc(100vh - 48px)`, overflow hidden).
- Lệch chuẩn: (1) hàng tìm kiếm/lọc/nút nằm TRONG Paper của bảng, không phải command bar riêng; (2) style px viết thẳng khắp trang (cột phải 340px, input 220/200/140px, padding 8px 12px, gap 12px); (3) cột Thao tác mỗi dòng tới 3 nút chữ (Tạm ẩn/Bỏ ẩn, Đã xem, Mặc định) + dòng nhóm có nút "Mặc định"; (4) bảng không đặt độ rộng cột.
- Callback các nút thao tác bám theo id dict (`menus-hide-btn`, `menus-unhide-btn`, `menus-seen-btn`, `menus-reset-btn`, `menus-group-reset-btn`), không bám theo text → đổi cách render nút không ảnh hưởng callback.
- Test `tests/unit/test_menus_page.py` chỉ assert text "Mặc định: Dashboard" (nhãn mờ dưới ô tên, không phải text nút) → đổi nút thành icon không phá test đó.
- Tiền lệ `dmc.Tooltip` + `dmc.ActionIcon`: `app/ui/pages/data_sources.py:184` (label + ActionIcon, variant subtle).
