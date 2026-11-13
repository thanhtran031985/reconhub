# Task 80 — Cột "Tạo lúc" ở /queue-health ghi đủ dd/mm/yyyy hh:mm:ss

## Bối cảnh

User 08:19 13/11/2026 (kèm ảnh /queue-health): cột "Tạo lúc" trong
2 bảng (Đang chạy / Đang chờ, Mục kẹt) hiện chỉ ghi "12/11 14:22"
— yêu cầu ghi đủ thời gian `dd/mm/yyyy hh24:mi:ss`.

## Phạm vi

- Chỉ cột "Tạo lúc" ở `app/ui/pages/queue_health.py`: từ
  `format_short_dt` ("%d/%m %H:%M") sang định dạng đầy đủ
  "%d/%m/%Y %H:%M:%S" (vd "12/11/2026 14:22:05").
- "Thấy lần cuối" của worker giữ nguyên dạng ngắn (không nằm
  trong yêu cầu; dạng ngắn đủ dùng ở đó).
- Không đụng `format_short_dt` ở dashboard.py / history.py (bản sao
  riêng từng trang theo quy tắc không import lẫn nhau; cột của các
  trang đó không nằm trong yêu cầu).
- Không đổi layout trang (review layout /queue-health trả riêng
  cùng lúc với patch này; nếu user duyệt sửa layout thì làm
  follow-up sau).
