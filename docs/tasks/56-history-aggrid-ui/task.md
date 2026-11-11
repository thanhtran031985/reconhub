# Task 56 — history-aggrid-ui-fixes (chỉnh UI bảng Lịch sử sau khi test thật)

## Yêu cầu (user, 16:09 11/11/2026, đã test task 55 trên app thật)
- "mình test thấy ok, không refresh lại trang" — cơ chế per-row update OK.
- Nhưng: "phần AG Grid giảm size xuống 12, đẩy column tham số về sau
  cùng, xem lại độ rộng của column báo cáo, nhóm, trạng thái, bắt đầu
  vào kết thúc, các button hủy, xóa, chạy lại, xuất lại để giống như
  dash table lần trước, hiện tại không css gì".

## Phạm vi
- Font grid 12px (theo pattern task 40: class CSS + biến
  `--ag-font-size`, viewer dùng 13px).
- Cột Tham số chuyển về cuối cùng (sau Chạy lại).
- Rà lại độ rộng: Báo cáo (flex, tối thiểu 130), Nhóm 90, Trạng thái
  100, Bắt đầu/Kết thúc 150 (đủ hiện "11/11/2026 13:09:56" ở font 12).
- Nút Hủy/Xóa/Chạy lại/Xuất lại + link Tải file/Chạy lại style lại
  giống nút Mantine subtle xs của bảng cũ (nền trong suốt, không viền,
  chữ xanh, hover nền xanh nhạt; Xóa chữ đỏ) — hiện tại là button mặc
  định của trình duyệt (hộp xám, có viền).
- Không đổi cơ chế cập nhật (task 55), không migration.
