# Task 62 — progress

## Bước 1 — Nhịp tim worker ✅
- Service mới `app/services/worker_health.py`: `write_worker_heartbeat`
  (ghi worker_id + timestamp ISO vào RECON_APP_SETTING, key
  WORKER_HEARTBEAT_RECON / WORKER_HEARTBEAT_EXPORT, UPDATED_BY =
  worker_id; không migration) + `get_worker_health` (alive = nhịp tim
  mới hơn 30 giây; status running/partial/down theo 2 luồng).
- Cả 2 vòng lặp worker ghi nhịp tim mỗi vòng poll
  (`worker/runner.py` ReconWorker.run, `worker/export_runner.py`
  ReportExportWorker.run), bọc try/except để lỗi ghi không làm chết
  worker.
- Test `tests/unit/test_worker_health62.py`: TestHeartbeat (5 test:
  ghi/đọc, chưa từng chạy → down, quá 30s → down, 1 luồng stale →
  partial, kind sai → ValueError) + TestWorkerLoopHeartbeat (2 test:
  chạy thật 2 vòng lặp ~0,4s rồi kiểm tra key trong DB). Viết trước,
  đỏ đúng chỗ (module chưa có / worker chưa ghi), code xong xanh.

## Bước 2 — Thống kê hàng đợi + danh sách kẹt ✅
- Cùng service: `get_queue_health(ctx, now=None)` (@service,
  @requires_menu("dashboard")) trả worker health + max_concurrent
  (dùng lại get_export_max_concurrent) + đếm export/run theo trạng
  thái + danh sách kẹt (tối đa 20, cũ nhất trước). Owner scope như
  list_exports/list_report_runs (không phải ADMIN chỉ thấy của mình).
- Danh sách kẹt: export/run QUEUED quá 30 phút (CREATED_AT); export
  RUNNING quá hạn heartbeat 300s (cùng điều kiện reset_stale). Run
  RUNNING không liệt kê (RECON_REPORT_RUN không có cột heartbeat).
  can_cancel theo đúng luật service hủy (xem decisions.md D4).
- Test TestQueueHealth (8 test): đếm theo trạng thái (ADMIN + owner
  scope), kẹt QUEUED run/export, RUNNING export quá hạn heartbeat,
  run RUNNING không liệt kê, giới hạn 20 + cũ nhất trước, luật
  can_cancel. Tổng file: 15 passed, ruff + mypy sạch.

## Bước 3 — Thẻ dashboard ✅
- `app/ui/pages/dashboard.py`: `fetch_queue_health` (bọc get_queue_health,
  lỗi → {}), `_format_age` (phút → "45 phút"/"2 giờ 10 phút"),
  `_health_card_body(health, note, note_tone)` (badge tổng qua
  status_chip: Đang chạy/Chạy một phần/Không phản hồi; từng dòng
  Worker Đối soát/Export + thời gian thấy lần cuối qua
  format_short_dt hoặc "Chưa từng chạy"; 4 con số Export/Run đang
  chờ/đang chạy + Song song tối đa; bảng mục kẹt: Loại, Mục #id · tên
  báo cáo (link /runs/<id> hoặc /report-runs), Người tạo, Tạo lúc,
  Kẹt bao lâu, Trạng thái (+ "quá hạn heartbeat" khi stale), nút Hủy
  button_subtle icon lucide:x chỉ khi can_cancel), `render_health_card`
  (header tĩnh: tiêu đề + nút "Làm mới" id dashboard-health-refresh-btn
  + link "Xem lịch sử" → /report-runs; body div id
  dashboard-health-card-body, maxHeight 220, cuộn trong), đặt thẻ
  full-width dưới Group 2 card trong render_dashboard (chỉ nhánh bình
  thường, không nhánh trống), callback duy nhất
  `handle_health_actions` (Input nút Làm mới + Input ALL nút Hủy,
  prevent_initial_call=True, dispatch theo triggered_id, guard chặn
  re-fire khi body vẽ lại / trigger không phải nút bấm; hủy gọi
  cancel_export/cancel_report_run, note "Đã hủy …" hoặc message lỗi).
- Test: TestHealthCardBody (3) + TestHealthCardPage (1) +
  TestHealthCancelCallback (6) — viết trước đỏ đúng chỗ (thiếu hàm),
  2 lỗi do dmc.TableScrollContainer bắt buộc minWidth (đã sửa
  minWidth=520) rồi xanh. Tổng: 24 test task 62 + 17 test trang
  dashboard = 41 passed; ruff check + format sạch trên file sửa
  (ruff format chỉ chạy trên 2 file mới worker_health.py +
  test_worker_health62.py; dashboard.py sửa tay 2 dòng def cho đúng
  format, không chạm drift có sẵn); mypy sạch.

## Bước 4 — Kiểm chứng live ✅
- `~/workspace/check-62-worker-health.py` (DB/storage riêng
  /run/pytest-tmp/check62.*, cổng 8108): **10/10 passed**.
  - 62-1 worker chưa chạy → "Không phản hồi" / "Chưa từng chạy".
  - 62-2 run QUEUED 40 phút hiện trong danh sách kẹt sau "Làm mới"
    ("#2 · BC RM Updated", "40 phút", nút Hủy visible).
  - 62-3 bấm Hủy → note "Đã hủy run #2", "Không có mục kẹt", DB
    CANCELLED.
  - 62-4 chạy worker → nhịp tim ghi vào RECON_APP_SETTING, thẻ báo
    "Đang chạy" cả 2 luồng + thời gian thấy lần cuối.
  - 62-5 dừng worker → sau ~30s (ngưỡng stale) thẻ về "Không phản
    hồi" (dòng worker hiện "thấy lần cuối" cũ).
  - 62-6 không lỗi JS (quét cả console error + pageerror, bỏ qua
    ERR_TUNNEL_CONNECTION_FAILED).
- 2 vấn đề phát hiện và đã sửa trong lúc check:
  1. D7 (decisions.md): thẻ không hiện ở nhánh trống total == 0 vì
     `get_dashboard_summary` chỉ đếm run đối soát, không đếm run báo
     cáo — đã thêm thẻ vào nhánh trống + test
     `test_health_card_in_empty_branch`.
  2. Check script (không phải app): Mantine Badge viết hoa bằng CSS
     nên innerText trả "KHÔNG PHẢN HỒI" — assert so sánh không phân
     biệt hoa/thường.
- Unit tổng: 25 test task 62 + 17 test trang dashboard + 29 test
  worker/export/run liên quan = 71 passed; ruff check + format sạch
  trên file sửa; mypy sạch.
