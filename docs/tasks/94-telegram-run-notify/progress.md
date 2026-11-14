# Progress — Task 94

- 14/11/2026 — Task tạo theo yêu cầu user ("Tạo task và làm luôn
  bạn", 17:42): run đối soát DONE/FAILED → Telegram của người chạy.
  Đã đọc: `notification.py` (`notify_user`/`is_enabled`/
  `notify_for_run`), `run_executor.py` (DONE ~608, FAILED ~673),
  `worker/runner.py` + `worker/__main__.py` (2 thread worker),
  `report_timeouts.py` (mẫu setting), `crypto.py` (Fernet),
  `settings.py` + `account.py` (UI). Viết xong `task.md`, `plan.md`,
  `decisions.md`. Chờ subagent triển khai theo plan (tests-first,
  không commit).
- 14/11/2026 17:55 — Bước 2 xong (tests-first): file mới
  `tests/unit/test_telegram_notify94.py`, 21 test. Đỏ xác nhận bằng
  ModuleNotFoundError `app.services.telegram_notify` trước khi code.
- 14/11/2026 18:00 — Bước 3 xong: migration 0012
  (`migrations/versions/0012_telegram_link.py`, head mới) + 3 cột
  `TELEGRAM_*` vào `recon_user` trong `metadata.py`; regenerate
  manifest (`schema-introspect`, 45 tables, 68 events) + drift 0
  (test_schema_drift pass). Cập nhật 3 assertion đếm hardcode theo
  lệ các task trước: manifest version → 0012 (test_schema_inspector),
  history 65 → 68, COLUMN_ADDED 16 → 19 (test_page_data_model).
- 14/11/2026 18:10 — Bước 4 xong: service mới
  `app/services/telegram_notify.py` (token Fernet, urllib, gate
  riêng, build tin D8, link code 8 ký tự/15 phút, poll getUpdates).
  31 test mới xanh ngay lần đầu (nhiều hơn 21 dự kiến vì tách nhỏ
  gate/poll).
- 14/11/2026 18:15 — Bước 5 xong: 1 dòng `notify_telegram_for_run`
  sau mỗi `notify_for_run` ở run_executor (DONE/FAILED) và
  worker/runner.py `reset_stale_jobs`. Không sửa notify_for_run hay
  pref trong app.
- 14/11/2026 18:20 — Bước 6 xong: /settings thêm Paper Telegram
  (token PasswordInput placeholder 'Đã lưu', username, nút 'Gửi thử',
  lưu chung handle_settings_save); /account thêm section Telegram
  (trạng thái, nút lấy mã + link t.me, nút hủy liên kết, Switch nhận
  tin) với 1 callback chung dispatch theo triggered_id.
- 14/11/2026 18:25 — Bước 7 xong: worker/__main__.py thêm thread
  poller daemon 30s gọi `poll_telegram_updates_once`, try/except
  quanh mỗi vòng.
- 14/11/2026 18:30 — Bước 8 xong: test mới 31 + liên quan
  (notifications78, design79, timeouts71, worker_executor) 110 pass;
  typecheck sạch (150 files); ruff check sạch trên file đổi (còn 1
  I001 có sẵn ở test_export_concurrency57); `ruff format` chỉ chạy
  trên 2 file mới (telegram_notify.py, test mới). Format drift có sẵn
  ở run_executor.py (dòng 542, 610) và worker/__main__.py (thread
  recon/export) không chạm.
- 14/11/2026 18:50 — Bước 9 xong: live check
  `~/workspace/check-94-telegram-notify.py` (port 8152, urllib stub ở
  tầng transport qua sitecustomize — KHÔNG gọi api.telegram.org thật)
  PASS — S1 /settings lưu token mã hóa (DB không có token dạng rõ,
  placeholder 'Đã lưu' sau tải lại) + 'Gửi thử' khi chưa liên kết
  không gọi sendMessage; S2 /account lấy mã → poller fixture liên
  kết chat 555000 + tin xác nhận, tải lại hiện 'Đã liên kết'; S3 run
  #1040 DONE → tin đúng số đếm (Khớp 0 · Thiếu DB 55 · Thiếu Excel
  0, theo seed check-88f); S3b 'Gửi thử' sau liên kết gửi đúng tin
  thử; không console error/pageerror. Ảnh `~/workspace/check94-settings.png`
  (Paper Telegram + toast lỗi 'Bạn chưa liên kết Telegram…' hiện góc
  phải — toast render qua portal, `#settings-telegram-alert`
  innerText rỗng là bình thường) và `~/workspace/check94-account.png`.
  2 lỗi script tự sửa khi chạy: fixture getUpdates thiếu `"ok": true`;
  tin DONE kỳ vọng sai số đếm (seed check-88f là 0/55/0, không phải
  604/6114/469 của test unit).
- 14/11/2026 19:05 — Bước 10: full suite lần 1 có 2 lỗi do code mới:
  (1) test_save_callback (task 52) gọi `handle_settings_save` thiếu 2
  tham số mới → cập nhật test truyền thêm `None, None`; (2) registry
  menu yêu cầu mọi @service có ctx phải gắn menu — 4 hàm tự phục vụ
  trên /account (generate_link_code, get_telegram_link_status,
  set_telegram_enabled, unlink_telegram) được thêm vào EXEMPT_SERVICES
  theo đúng lệ `change_password` (chỉ chạm user_id của ctx). Chạy lại
  full suite: **2040 passed, 6 skipped** (2009 + 31 test mới).
  Chạy `uv run poe tasks-dashboard`, đã REVERT docs/tasks/dashboard.html.
