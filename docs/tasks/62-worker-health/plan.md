# Task 62 — plan (đã duyệt 11/11/2026, user nói "duyệt")

## Bước 1 — Nhịp tim worker
- Service mới `app/services/worker_health.py`: `write_worker_heartbeat`
  (ghi worker_id + timestamp vào RECON_APP_SETTING, không migration) và
  `get_worker_health` (trả trạng thái alive/stale + last seen + worker_id;
  alive = nhịp tim mới hơn 30 giây).
- Cả 2 vòng lặp worker (`worker/runner.py` ReconWorker.run,
  `worker/export_runner.py` ReportExportWorker.run) ghi nhịp tim mỗi vòng
  poll (hoặc mỗi N vòng — ghi rõ lựa chọn vào decisions.md).

## Bước 2 — Thống kê hàng đợi + danh sách kẹt
- Cùng service (hoặc mở rộng service có sẵn): đếm export/run theo trạng
  thái + giới hạn song song hiện tại (EXPORT_MAX_CONCURRENT); danh sách
  kẹt = export/run QUEUED quá 30 phút chưa được nhận (CREATED_AT), và
  RUNNING quá hạn heartbeat (đã có reset_stale tự FAILED sau 300s nên
  chỉ liệt kê, không đổi trạng thái ở đây).

## Bước 3 — Thẻ dashboard
- Thẻ mới "Sức khỏe hàng đợi & worker" trên dashboard: badge trạng thái
  worker (Đang chạy/Không phản hồi + thời gian thấy lần cuối), 4 con số
  hàng đợi, danh sách kẹt + nút Hủy (quyền như nút Hủy ở Lịch sử: chủ
  run hoặc ADMIN). Thẻ ai cũng xem được.
- Theo pattern task 60: header/footer tĩnh, callback chỉ cập nhật body
  (không vẽ lại cả card); cập nhật theo trigger refresh của dashboard.

## Bước 4 — Kiểm chứng
- Test unit cho nhịp tim (ghi/đọc, ngưỡng 30s), ngưỡng kẹt 30 phút,
  thống kê đếm; test viết trước (đỏ) rồi code cho xanh.
- Check live `~/workspace/check-62-worker-health.py`: dừng worker → thẻ
  báo "Không phản hồi"; chạy lại → "Đang chạy"; hủy run kẹt → mất khỏi
  danh sách; quét cả console error + pageerror (bài học task 61).
- Full suite (parent chạy). Patch riêng, áp sau patch 61, không
  db-migrate, khởi động lại app + worker.
