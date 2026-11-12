# Task 78 — Decisions

- D1: notification trong app (chuông + danh sách lưu DB), không gửi
  email trong task này (chưa có SMTP).
- D2: tôn trọng quyết định task 52 — thông báo "xuất/run xong" mặc
  định TẮT (tự vào lịch xem); lỗi mặc định BẬT.
- D3: thông báo chỉ thấy của mình; thông báo hệ thống (worker,
  migration) chỉ ADMIN.
- D4: user chọn phương án A (trung tâm thông báo đầy đủ) 20:20
  12/11/2026.
- D5: cài đặt theo user lưu ở bảng riêng `RECON_NOTIFICATION_PREF`
  (USER_ID, EVENT_TYPE, ENABLED, UPDATED_AT; PK cặp) — thiếu dòng
  nghĩa là dùng mặc định. RECON_APP_SETTING là global (KEY là PK)
  nên không dùng được cho từng user.
- D6: trang `/notifications` có menu riêng `notifications`
  ("Thông báo", nhóm DOI_SOAT, order 95, icon lucide:bell), cấp cho
  cả 3 vai trò (như queue_health) qua migration 0010 phần dữ liệu
  (idempotent, mẫu 0009) + ROLE_MENUS_SEED.
- D7: badge chưa đọc tính lúc render header (render_app_shell dựng
  lại header mỗi lần đổi trang) + Interval 60s riêng
  (`app-notif-poll`) cập nhật badge; không poll 5s, không thêm
  Interval nặng.
- D8: worker chết/kẹt không thể do worker tự báo (worker chết thì
  không chạy được) — phát hiện ở tiến trình app, trong callback
  Interval đếm badge (`app-notif-poll`, 60s) gọi
  `maybe_notify_worker_health`: WORKER_DOWN khi status "down",
  QUEUE_STUCK khi có mục kẹt; chống spam bằng dedup tối đa 1 lần/60
  phút mỗi loại (kiểm tra RECON_NOTIFICATION gần nhất). Chỉ chạy ở
  callback Interval — đường render header (create_header) giữ thuần
  đọc (chỉ đếm chưa đọc), không ghi DB. Bọc try/except — lỗi không
  được làm hỏng badge/header.
- D9: 12 loại sự kiện — RUN_FAILED/RUN_DONE, REPORT_RUN_FAILED/
  REPORT_RUN_DONE, EXPORT_FAILED/EXPORT_DONE, BATCH_FAILED/
  BATCH_DONE, WORKER_DOWN, QUEUE_STUCK, MIGRATION_DONE/
  MIGRATION_FAILED. Mặc định BẬT: mọi loại *_FAILED + WORKER_DOWN +
  QUEUE_STUCK + MIGRATION_*; mặc định TẮT: RUN_DONE/REPORT_RUN_DONE/
  EXPORT_DONE/BATCH_DONE (theo task 52). Link: run đối soát
  /runs/<id>; run báo cáo /reports/<id>?run=<id>; export /report-runs;
  batch /batch-runs/<id>/result; worker/kẹt /queue-health; migration
  /data-sources.

## Quyết định chốt lúc làm (12/11/2026)

- D10: PARTIAL của batch (= có mục lỗi) báo bằng sự kiện BATCH_FAILED
  (không tạo loại riêng): hook ở `sync_batch_status` khi chuyển
  RUNNING -> PARTIAL/DONE; chuyển trạng thái chỉ xảy ra 1 lần nên
  mỗi bộ báo tối đa 1 lần.
- D11: export bị worker reset vì treo (reset_stale_exports) và run bị
  reset vì treo (reset_stale_jobs) cũng báo FAILED cho chủ (mỗi run/
  export chỉ reset 1 lần nên không spam). Export bị user Hủy thì
  không báo (CANCELLED không phải FAILED; `_fail_export` return sớm
  khi rowcount == 0).
- D12: migration fake mode không báo (mô phỏng ở client, không qua
  `start_migration`); chỉ migration thật mới báo ADMIN (DONE/FAILED).
- D13: `notification.py` KHÔNG import `worker_health` ở top-level:
  worker_health -> export_retention -> report_export -> notification
  thành vòng tròn (lỗi ImportError cả 2 chiều import, chỉ lộ khi
  import trực tiếp — test suite vô tình qua được vì module khác đã
  nạp report_export trước). Dùng lazy import bên trong
  `maybe_notify_worker_health` (mẫu đã có ở worker/runner.py).
- D14: panel chuông bấm mục -> MenuItem có href (điều hướng) + callback
  pattern-matching đánh dấu đã đọc; badge/panel cập nhật lại sau khi
  đánh dấu. Callback panel-item dùng allow_duplicate=True cho cả 3
  Output (badge label/disabled thuộc về callback poll, panel children
  thuộc về callback vẽ panel — bài học task 74).
- D15: trang /notifications KHÔNG tự poll — danh sách tải lúc mở trang
  + nút "Làm mới" bằng tay; badge chuông vẫn poll 60s ở header.
  Phân trang: Pagination ở footer ngoài vùng vẽ lại (mẫu task 60);
  xóa mục cuối của trang cuối thì tự lùi về trang còn dữ liệu.
- D16: test schema cứng số bảng/cột/FK phải cập nhật theo schema mới:
  43 -> 45 bảng, 515 -> 530 cột (fixture; manifest thật 518 -> 530),
  53 -> 55 FK, domain Đối soát 19 -> 21, history 61 -> 63 event,
  manifest version 0009_queue_health_menu -> 0010_notifications.
- D17: migration 0010 chạy được trên DB tươi từ 0001 -> head và
  downgrade về 0009 (bảng bị drop; dòng RECON_MENU giữ lại như mẫu
  0009 — menu đồng bộ từ code bằng sync_menus). Lưu ý: alembic.ini
  có sqlalchemy.url cố định (data/recon_app.db) nên RECON_DB_URL
  không đổi được DB cho `alembic upgrade` — kiểm chứng trên DB tạm
  phải dùng bản sao alembic.ini trỏ sang file tạm.
- D18: MenuItem/Anchor có href + n_clicks thì click điều hướng ngay,
  n_clicks mất — đã chứng minh bằng debug live (callback panel-item
  chỉ chạy 1 lần với n_clicks=[None] lúc panel vẽ lại, click thật
  không tạo lần chạy thứ 2; DB vẫn IS_READ='N'). Vì vậy mục panel
  (dmc.MenuItem) và tiêu đề trên trang /notifications (html.A —
  dmc.Anchor bắt buộc có href nên không dùng được) đều KHÔNG dùng
  href; callback tự điều hướng qua Output app-location.href (dùng
  allow_duplicate=True vì handle_menu_search cũng ghi output này)
  SAU khi đánh dấu đọc — chắc chắn đã đọc trước khi chuyển trang.
  Logic panel-item tách thành hàm thuần handle_panel_item_click để
  test trực tiếp (test hồi quy TestPanelItemClick, 2 test).
