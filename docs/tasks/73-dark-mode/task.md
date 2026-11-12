# Task 73 — Dark mode: chữ chìm, nền lẫn lộn

## Yêu cầu (user 12/11/2026, kèm ảnh dashboard dark mode)

Bật dark mode (nút mặt trăng trên header) thì giao diện lẫn lộn, khó đọc:

- Tiêu đề trang "Tháng 11/2026: 420 run, 207 chưa kiểm tra" chữ xám
  nhạt trên nền trắng — gần như không đọc được.
- 4 thẻ KPI nền tối nhưng số liệu chữ tối trên nền tối ("420",
  "32,5%", "417" chìm; chỉ "207" màu cam còn thấy).
- Nền trang vẫn sáng trong khi sidebar + một số thẻ đã tối; bảng
  "Run gần đây" thì nền sáng chữ tối (đọc được), thẻ "Tỉ lệ lệch theo
  template" nền tối chữ sáng (đọc được). Lỗi chỉ xuất hiện ở một số
  chỗ, không phải toàn trang.

## Phạm vi

- Sửa cơ chế dark mode + các chỗ chữ/nền bị chìm (ưu tiên dashboard
  và component dùng chung). Không đổi bố cục, không thêm tính năng.
