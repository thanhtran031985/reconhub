# Task 79 — Trung tâm thông báo theo thiết kế (NOTIFICATION-01)

## Bối cảnh

- Task 78 đã xây trung tâm thông báo (chuông + trang danh sách +
  cài đặt từng loại). User gửi ảnh thiết kế (file
  `~/workspace/user/media_library/image/Designer__1.png`) kèm
  prompt NOTIFICATION-01 và yêu cầu làm theo ảnh, cập nhật vào task.
- 3 file trong prompt KHÔNG có trong repo
  (`tasks/NOTIFICATION-01/task.md`, `test-checklist.md`,
  `designs/reference/notification-center.html`) — task này ghi lại
  theo quy ước repo (`docs/tasks/79-notification-center-design/`,
  checklist ở `test-checklist.md` trong thư mục này); tên
  NOTIFICATION-01 là tên gọi của prompt thiết kế.
- Đối chiếu 21:51 12/11/2026 (ảnh thiết kế vs task 78): task 78 đã
  có chuông + badge, panel 5 mục, trang danh sách + phân trang +
  đánh dấu đã đọc/xóa/đánh dấu tất cả, cài đặt từng loại, sự kiện
  run/export/batch/worker/migration, menu Thông báo.

## Còn thiếu so với thiết kế (phạm vi task này)

1. **Bố cục Master–Detail + không cuộn trang** (≥1366×768): list
   trái + panel chi tiết phải rộng 320 (token `size-detail-panel`);
   chỉ list/panel cuộn trong. Task 78 hiện là 1 cột cuộn cả trang.
2. **Thanh lọc**: tìm kiếm + lọc loại sự kiện + lọc đã/chưa đọc +
   lọc thời gian (7 ngày qua) + Làm mới. Service hiện chỉ có
   `unread_only`.
3. **Danh sách nhóm theo ngày** (HÔM NAY/HÔM QUA), giờ tương đối
   ("2 phút", "1 giờ"), icon trạng thái, chấm xanh chưa đọc, dòng
   đang chọn highlight.
4. **Panel chi tiết bên phải**: badge loại + mã loại, ngày giờ, Mã
   lần chạy (copy), Bộ đối soát, Template, Thời gian chạy, hộp đỏ
   "Nguyên nhân", nút "Mở kết quả Run" + "Sao chép mã run".
   Task 78 KHÔNG lưu đủ dữ liệu: notification chỉ có
   TITLE/MESSAGE/LINK → cần tham chiếu entity gốc + service đọc chi
   tiết run.
5. **Footer**: "N thông báo · M chưa đọc · Cập nhật HH:MM:SS".
6. **Popover chuông**: tab Tất cả / Chưa đọc + "Đánh dấu tất cả đã
   đọc" trong popover.
7. **Cài đặt**: công tắc tổng "Nhận thông báo trong ứng dụng" (tắt
   thì không tạo thông báo nào) + Hủy/Lưu; dạng Modal theo thiết kế.
8. **Menu**: chuyển "Thông báo" từ nhóm ĐỐI SOÁT (order 95) sang
   nhóm QUẢN TRỊ (order 30) theo thiết kế.
9. **Nhỏ**: bỏ style inline px (`padding: "12px 16px"`) trong
   `notifications.py` → dùng token (quy tắc ui-dash).

## Deferred (không làm trong task này)

- 2 loại sự kiện trong ảnh chưa có nguồn sinh: "Cập nhật dữ liệu
  thành công" (đồng bộ danh mục), "Bảo trì hệ thống".
- Email (đã chốt ngoài scope từ task 78 — app chưa có SMTP).
