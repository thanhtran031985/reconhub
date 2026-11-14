# Decisions — Task 94

- **D1 — Phạm vi: chỉ run đối soát DONE/FAILED.** Báo cáo, export,
  batch để task sau. Chỉ gửi cho chủ run (`RECON_RUN.CREATED_BY`),
  không gửi cho ADMIN khác.
- **D2 — Bot API, không dùng MTProto/user API.** Gọi
  `api.telegram.org` bằng `urllib` chuẩn của Python, không thêm
  package ngoài Stack. Worker cần ra được internet tới
  `api.telegram.org` (ghi chú kiểm chứng cho user).
- **D3 — Cổng Telegram độc lập với pref trong app.** `notify_for_run`
  và pref trong app giữ nguyên. Telegram có cổng riêng
  `is_telegram_enabled`: đã liên kết chat_id + pref `TELEGRAM` trong
  `RECON_NOTIFICATION_PREF` (thiếu dòng = BẬT) + default riêng
  `RUN_DONE=True, RUN_FAILED=True` (user chốt: DONE trên Telegram
  mặc định BẬT, khác trong app đang TẮT).
- **D4 — Token mã hóa, username + offset để rõ.**
  `RECON_APP_SETTING`: `TELEGRAM_BOT_TOKEN` = `encrypt_secret(token)`
  (Fernet; VALUE String(400) đủ chứa), `TELEGRAM_BOT_USERNAME`
  (bỏ `@` đầu), `TELEGRAM_UPDATE_OFFSET` (update_id cuối đã xử lý).
  Không ghi token vào log/audit; UI không hiện lại token đã lưu.
- **D5 — Migration 0012 thêm 3 cột vào RECON_USER:**
  `TELEGRAM_CHAT_ID` String(64), `TELEGRAM_LINK_CODE` String(32),
  `TELEGRAM_LINK_EXPIRES_AT` DateTime, đều nullable. Chạy được
  SQLite (batch mode) + Oracle; regenerate schema manifest + drift 0
  (quy tắc task 31).
- **D6 — Liên kết bằng mã qua /start (không dùng webhook).** App
  không có URL công khai nên bot không gọi webhook được; worker
  poll `getUpdates` (short-poll, 30s/lần). Mã 8 ký tự
  (`secrets.token_urlsafe(6)`), hạn 15 phút, hiện trên /account kèm
  link `https://t.me/<bot>?start=<mã>`. `/start` không mã hoặc mã
  sai/hết hạn → bot nhắn hướng dẫn lấy mã ở /account.
- **D7 — Gửi không bao giờ raise.** Mọi hàm gửi/poll đều bọc
  try/except, lỗi chỉ log warn + trả False/0; timeout HTTP 10s để
  không treo worker. Không chặn luồng chạy.
- **D8 — Tin nhắn chỉ mang số liệu, không kèm link.** App chạy
  localhost nên link /runs/<id> trên điện thoại không mở được.
  DONE: `Run #<id> đã xong — <tên template>, kỳ <từ>–<đến>:
  Khớp <n> · Lệch <n> · Thiếu trong DB <n> · Thiếu trong Excel <n>.`
  (kỳ lấy từ `P_FROM`/`P_TO` của run, dạng ngày; số thiếu
  `CNT_MISSING_IN_DB`/`CNT_MISSING_IN_EXCEL`; run không có summary
  thì bỏ phần số đếm). FAILED: `Run #<id> lỗi — <lý do, cắt 500 ký tự>.`
  Tin nhắn text thuần, không dùng Markdown (tránh lỗi escape).
- **D9 — Số task 94.** Task sửa /templates đã hoãn trước đó (user
  chọn /data-sources trước) sẽ lấy số 95 khi bắt đầu, tránh nhầm.
- **D10 — Thêm vào hạn chế tối đa chạm code cũ.** Chỉ thêm 1 dòng gọi
  `notify_telegram_for_run` sau mỗi `notify_for_run` hiện có ở
  run_executor (DONE/FAILED) và worker `reset_stale_jobs`; không sửa
  `notify_for_run`, không sửa pref trong app, không sửa service khác.
- **D11 — Thêm helper đọc trạng thái liên kết (lệch nhỏ so với plan).**
  Plan bước 6 mô tả section Telegram trên /account nhưng không đặt tên
  hàm đọc. Thêm `@service get_telegram_link_status(ctx)` trả
  `{linked, chat_id, enabled}` để `layout()` vẽ trạng thái mà không
  cần đọc DB trực tiếp từ page. Chỉ đọc user_id của chính ctx, không
  gắn menu (miễn trừ như `change_password`, ghi ở
  `test_perm_registry.py`).
