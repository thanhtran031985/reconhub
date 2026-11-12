# Task 78 — Thêm tính năng notification (trung tâm thông báo trong app)

## Bối cảnh

- User yêu cầu 20:18 12/11/2026: tạo task mới, thêm tính năng
  notification.
- Hiện trạng (đã rà code): app chỉ có toast thoáng qua
  (`app/ui/components/notification.py`: `notify_success/error/
  warning/info`, dùng ở 178 chỗ) — toast biến mất khi chuyển trang,
  không lưu lại, không có chuông, không có danh sách, không gửi
  email. Không có bảng notification, không có cấu hình SMTP.
- Ràng buộc từ task 52 (user đã chốt 11/11/2026): xuất báo cáo chạy
  ngầm thì "tự vào lịch xem (không thông báo)" — kiểu EBS. Nên thông
  báo "xuất xong" KHÔNG được bật mặc định; user tự bật nếu muốn.
- Nguồn sự kiện đã có sẵn: run/batch/export chuyển trạng thái
  DONE/FAILED/CANCELLED (run_executor, export worker, sync_batch_
  status), worker heartbeat + danh sách kẹt (worker_health, task 62),
  migration DONE (task 63). User có cột EMAIL (RECON_USER) nhưng chưa
  có gì gửi mail.

## Phạm vi đề xuất (chờ user chọn)

- A — Trung tâm thông báo đầy đủ: bảng RECON_NOTIFICATION mới
  (migration), service tạo/liệt kê/đánh dấu đã đọc, chuông + badge
  chưa đọc ở header, panel/danh sách thông báo (bấm vào đi tới
  run/báo cáo liên quan), cài đặt từng loại sự kiện theo user
  (mặc định: lỗi BẬT, xuất-xong TẮT theo task 52).
- B — Chỉ báo khi lỗi: chỉ các sự kiện FAILED + worker chết/kẹt
  (ADMIN), không có xuất-xong, không có cài đặt từng loại.
- Email KHÔNG nằm trong task này (chưa có SMTP; làm sau nếu user
  muốn).
