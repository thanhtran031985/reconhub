# Task 71 — Xem báo cáo lỗi giới hạn 30s (câu COUNT)

## Yêu cầu (user 12/11/2026, kèm ảnh /reports/5)

Báo cáo "BC RM Updated", tham số Từ ngày 2026-01-01, Đến ngày 2026-11-12,
App "Catos", Org trống. Bấm "Xem báo cáo" thì báo:

> Lỗi — Chạy báo cáo lỗi: Truy vấn Oracle bị quá thời gian cho phép
> (30 giây).

Kết quả hiện "Chưa chạy", không có dữ liệu. User hỏi: sao lại lỗi giới
hạn 30s?

## Phạm vi

- Chỉ đường xem báo cáo ở Trung tâm báo cáo (`app/services/report_run.py`,
  `_execute_count_page`). Không đổi SQL báo cáo, không migration.
