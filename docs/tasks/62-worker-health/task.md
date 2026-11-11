# Task 62 — Sức khỏe hàng đợi & worker (dashboard)

## Yêu cầu
Dashboard không có cách nào biết worker còn sống hay đã dừng, hàng đợi
có kẹt hay không. Hai lần phải mò mới ra: task 57 worker chưa khởi động
lại nên export #31 chờ trong khi #30 đang chạy; 2 run #32/#33 kẹt QUEUED
không có export (ảnh 17:34 11/11/2026, chưa rõ tạo bằng cách nào).

## Hiện trạng
- Worker là 1 tiến trình chạy 2 luồng (`worker/__main__.py`):
  `ReconWorker` (chạy run đối soát) + `ReportExportWorker` (chạy export),
  poll mỗi 2 giây (`WORKER_POLL_SECONDS`).
- Worker KHÔNG ghi lại dấu vết nào là nó còn sống — chỉ có heartbeat
  của từng job/export riêng lẻ (HEARTBEAT_AT trên RECON_RUN_QUEUE /
  RECON_RPT_EXPORT). Luồng recon chỉ log "Heartbeat worker hoạt động"
  mỗi 5 vòng poll, không ghi DB.
- Đã có xử lý stale: `reset_stale_exports` (export RUNNING quá hạn
  heartbeat 300s → FAILED), `reset_stale_jobs` tương tự cho run. Nhưng
  item QUEUED không có heartbeat nên không bao giờ bị đánh dấu kẹt.

## Cách fix (plan đã duyệt 11/11/2026)
1. Nhịp tim worker: mỗi vòng poll, cả 2 luồng ghi `worker_id` + thời
   gian vào `RECON_APP_SETTING` (không cần migration, đúng pattern
   setting song song task 57). Dashboard coi worker "Đang chạy" nếu nhịp
   tim mới hơn 30 giây, ngược lại "Không phản hồi" kèm thời gian thấy
   lần cuối.
2. Thống kê hàng đợi: service mới đọc số lượng export/run theo trạng
   thái (đang chờ/đang chạy/hoàn tất/lỗi/đã hủy) + giới hạn song song
   hiện tại; dùng lại hàm list đã có khi được.
3. Thẻ mới trên dashboard "Sức khỏe hàng đợi & worker": badge trạng thái
   worker, 4 con số hàng đợi, danh sách run/export kẹt + nút Hủy theo
   đúng quyền như nút Hủy ở Lịch sử (chủ run hoặc ADMIN). Thẻ ai cũng
   xem được.
4. Kiểm chứng: test unit + check live + full suite; patch riêng, áp sau
   patch 61, không db-migrate, khởi động lại app + worker.

## Quyết định đã chốt khi duyệt
- Ngưỡng kẹt QUEUED: 30 phút chưa được nhận.
- Thẻ ai cũng xem được; nút Hủy theo quyền chủ run/ADMIN.
