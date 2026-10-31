# StatusChip

Chip trạng thái luôn có icon + chữ.

## Props và quy tắc

Kết quả: theo `tokens.json` khóa `status`. Run: QUEUED off "Chờ chạy", RUNNING info, DONE có lệch warn, DONE khớp ok, FAILED crit, CANCELLED off. Kiểm tra: "Chưa kiểm tra" off, "Đã kiểm tra" ok. Dữ liệu tạm: "Còn · 3,2 MB" warn, "Đã xóa" off. Người dùng: Hoạt động ok, Tạm khóa đến HH:mm warn, Đã tắt off. Vai trò: plain. Template: DRAFT off, ACTIVE ok, ARCHIVED off.

## Kiểu dáng
Lớp `rh-…` trong `../bundle.css`; xem `../Gallery/preview.html`.

## Chuyển sang Dash
Hàm trong `app/ui/components/` theo bảng "Ánh xạ sang Dash Mantine" ở `designs/README.md`. Không dùng hex/px.
