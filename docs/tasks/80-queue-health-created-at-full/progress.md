# Task 80 — Progress

- 13/11/2026: user yêu cầu cột "Tạo lúc" ở /queue-health ghi đủ
  dd/mm/yyyy hh:mm:ss (ảnh 08:19). Parent tạo nhánh
  feat/80-queue-health-created-at-full từ 4afad8d (task 79) +
  docs task 80, triển khai trực tiếp (thay đổi nhỏ, chỉ định rõ).
- Thêm `format_full_dt` ("%d/%m/%Y %H:%M:%S") ở queue_health.py;
  ô "Tạo lúc" dùng hàm mới, "thấy lần cuối" của worker giữ dạng
  ngắn. Test mới 2 (TestCreatedAtFull): unit 22/22 pass.
- Check live (probe-queue-health-layout.py, seed 1 run QUEUED 10h):
  cả 2 bảng hiện "12/11/2026 14:27:41", không còn ô dạng ngắn;
  không lỗi JS. Đo layout: 1366x768 và 1440x900 đều không cuộn
  trang, không cuộn ngang; body card cao 220 (capped) nhưng nội
  dung 262 → bảng "Mục kẹt" cần cuộn trong card (điểm chính của
  review layout gửi kèm patch).
- Ruff + typecheck sạch (format --check còn 3 chỗ drift có sẵn
  trước task, không đụng).
- Full suite: 1879 pass, 6 skip (1877 + 2 mới).
