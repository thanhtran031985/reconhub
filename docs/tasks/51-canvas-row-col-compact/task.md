# Task 51 — canvas-row-col-compact

## Yêu cầu (user, 10:30 11/11/2026, kèm ảnh app thật)
Card span 2 ở tab 3 (Thiết kế layout tham số tìm kiếm): "Hàng" và "Cột"
rớt xuống 2 dòng; card span 3 thì không. Hỏi cách giữ trên 1 dòng
hoặc giảm chiều rộng của ô Hàng/Cột.

## Cách sửa đã duyệt (user "Làm luôn" 10:42 11/11/2026)
Đưa nhãn Hàng/Cột lên trên ô nhập (2 cột dọc mini), ô nhập 46→38px,
lề ngang card 8→6px. Cả cụm cần 80px → card span 2 vừa tới viewport
~1000px; dưới ngưỡng đó giữ `wrap="wrap"` làm lưới an toàn.
