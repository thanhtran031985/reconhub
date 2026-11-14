# Plan — Task 94

1. Đọc kỹ trước khi code: `app/services/notification.py`
   (`notify_user` 184+, `is_enabled` 156+, `notify_for_run` 306+,
   `EVENT_TYPES` 49+), `app/services/run_executor.py` (DONE ~608,
   FAILED ~673), `worker/runner.py` (`reset_stale_jobs`,
   `notify_for_run` ở đó), `worker/__main__.py` (cách start 2 thread
   worker), `app/services/report_timeouts.py` (mẫu setting
   RECON_APP_SETTING + `@service`), `app/core/crypto.py`
   (`encrypt_secret`/`decrypt_secret`), `app/ui/pages/settings.py`
   (layout 41+, `handle_settings_save` 231+), `app/ui/pages/account.py`
   (layout 24+, đổi mật khẩu 195+), `migrations/versions/0011_notification_related.py`
   (mẫu migration), `app/db/metadata.py` (`recon_user` 96+,
   `recon_app_setting` 227+, `recon_run_summary` — các cột CNT_*).
2. Viết test đỏ trước (file mới `tests/unit/test_telegram_notify94.py`):
   - Build tin DONE từ run mẫu BILL_VTOS (seed theo
     `check-88f-followup.py`, run 1040): đúng template/kỳ/số đếm
     (Khớp/Lệch/Thiếu DB/Thiếu Excel); build tin FAILED: đúng mã run +
     lý do cắt 500 ký tự.
   - Cổng gửi: `urllib.request.urlopen` bị mock — assert đúng URL
     `https://api.telegram.org/bot<token>/sendMessage`, đúng chat_id,
     đúng text; lỗi HTTP/timeout → trả False, không raise.
   - Gate: chưa liên kết (không có chat_id) → không gửi; công tắc
     Telegram tắt → không gửi; RUN_DONE mặc định Telegram BẬT
     (khác pref trong app đang TẮT) — assert gửi khi pref trong app
     RUN_DONE đang tắt.
   - Liên kết: mã đúng + còn hạn → lưu chat_id, xóa mã; mã sai/hết hạn
     → không lưu; `/start` không mã → không lưu.
   - Token lưu mã hóa: `set_telegram_settings` xong đọc DB thấy
     `TELEGRAM_BOT_TOKEN` không chứa token dạng rõ.
   - Hồi quy: `notify_for_run` trong app vẫn như cũ (test hiện có xanh).
3. Migration 0012 (`migrations/versions/0012_telegram_link.py`):
   `RECON_USER` += `TELEGRAM_CHAT_ID` (String 64, nullable),
   `TELEGRAM_LINK_CODE` (String 32, nullable),
   `TELEGRAM_LINK_EXPIRES_AT` (DateTime, nullable). Chạy được trên
   SQLite (batch mode) và Oracle. Sau đó regenerate schema manifest
   (`uv run poe schema-introspect`, quy tắc task 31) + kiểm tra drift = 0.
4. Code — service mới `app/services/telegram_notify.py` (không sửa
   `notification.py` ngoài việc import nếu cần; không đổi hành vi
   trong app):
   - Hằng: `TELEGRAM_BOT_TOKEN_KEY`, `TELEGRAM_BOT_USERNAME_KEY`,
     `TELEGRAM_UPDATE_OFFSET_KEY`, `TELEGRAM_PREF_EVENT = "TELEGRAM"`,
     `TELEGRAM_EVENT_DEFAULTS = {"RUN_DONE": True, "RUN_FAILED": True}`,
     timeout gửi/getUpdates 10s.
   - `get_telegram_settings(ctx)` / `set_telegram_settings(ctx, token,
     username)` (`@service`, ADMIN, theo mẫu `report_timeouts.py`):
     token mã hóa Fernet trước khi lưu, username strip + bỏ `@` đầu.
   - `send_telegram_message(chat_id, text) -> bool`: POST
     `sendMessage` bằng `urllib`, không raise, lỗi → log warn + False.
   - `is_telegram_enabled(engine, user_id, event_type) -> bool`:
     đã liên kết (có `TELEGRAM_CHAT_ID`) + pref `TELEGRAM` (thiếu
     dòng = BẬT) + default riêng theo `TELEGRAM_EVENT_DEFAULTS`.
   - `notify_telegram_for_run(engine, run_id, event_type) -> bool`:
     đọc chủ run (`CREATED_BY`), chat_id, summary (CNT_*), template
     (CODE/NAME), kỳ (`P_FROM`/`P_TO`); build tin theo task.md; gửi;
     không raise. FAILED thì không cần summary.
   - `generate_link_code(ctx) -> dict`: tạo mã ngẫu nhiên 8 ký tự
     (`secrets.token_urlsafe(6)`), hạn 15 phút, lưu vào user; trả mã +
     link `https://t.me/<bot_username>?start=<mã>` (bot chưa cấu hình
     username → lỗi rõ).
   - `unlink_telegram(ctx) -> dict`: xóa chat_id (+ mã), tắt nhận.
   - `set_telegram_enabled(ctx, enabled) -> dict`: ghi pref
     `TELEGRAM` ('Y'/'N') cho chính user.
   - `send_telegram_test(ctx) -> dict`: gửi tin thử
     `"Tin thử từ ReconHub — bot Telegram đã nối."` tới chat đã liên
     kết của chính ADMIN; chưa liên kết → lỗi rõ.
   - `poll_telegram_updates_once(engine) -> int`: đọc token + offset,
     gọi `getUpdates` (short-poll, timeout 10s); với mỗi update có
     `message.text` bắt đầu `/start`: tách mã, tìm user theo
     `TELEGRAM_LINK_CODE` còn hạn → lưu `TELEGRAM_CHAT_ID`, xóa mã,
     nhắn xác nhận `"Đã liên kết Telegram với tài khoản <username>.
     Run đối soát xong/lỗi sẽ báo về đây."`; `/start` không mã hoặc mã
     sai/hết hạn → nhắn hướng dẫn lấy mã ở trang /account. Cập nhật
     offset sau mỗi batch. Không raise (lỗi → log warn + trả 0).
5. Code — gọi gửi (mỗi chỗ 1 dòng, sau `notify_for_run` hiện có):
   - `app/services/run_executor.py`: DONE (~608) và FAILED (~673).
   - `worker/runner.py`: `reset_stale_jobs` (sau `notify_for_run`
     của run bị treo).
6. Code — UI:
   - `/settings`: thêm Paper Telegram vào SimpleGrid hiện có (theo mẫu
     3 Paper task 71-followup): `PasswordInput#settings-telegram-token`
     (không hiện lại token đã lưu — chỉ placeholder "Đã lưu" khi có),
     `TextInput#settings-telegram-username`, nút
     `#settings-telegram-test-btn` ("Gửi thử"); lưu chung trong
     `handle_settings_save` (gọi `set_telegram_settings`, lỗi thì báo
     như timeout).
   - `/account`: thêm section Telegram: trạng thái liên kết (đã liên
     kết chat … / chưa liên kết), nút `#account-telegram-link-btn`
     ("Lấy mã liên kết") → hiện mã + link `t.me/...` (mở tab mới) +
     hạn 15 phút, nút `#account-telegram-unlink-btn` ("Hủy liên kết"),
     `Switch#account-telegram-enabled` ("Nhận thông báo Telegram").
     Dùng design token + component DMC, không hex/px trong page.
7. Code — worker: `worker/__main__.py` thêm thread Telegram poller
   (daemon): vòng lặp 30s gọi `poll_telegram_updates_once(engine)`,
   try/except quanh mỗi vòng (lỗi không giết worker).
8. Chạy test mới + test liên quan (`test_page_settings`,
   `test_page_account`, `test_notification*`, `test_run_executor*`) +
   typecheck + ruff; sửa tới khi xanh.
9. Live check `~/workspace/check-94-telegram-notify.py` (Playwright,
   port 8152, seed như check-88f, `urllib` bị stub ở tầng transport —
   KHÔNG gọi api.telegram.org thật): /settings lưu token (DB không có
   token dạng rõ) + "Gửi thử" báo lỗi khi chưa liên kết; /account lấy
   mã → poller với fixture getUpdates giả → tài khoản hiện "Đã liên
   kết"; run mẫu DONE → tin nhắn build đúng số đếm; không console
   error/pageerror.
10. Full suite (`TMPDIR=/run/pytest-tmp uv run poe test`); cập nhật
    `progress.md`; chạy `uv run poe tasks-dashboard` (sau đó REVERT
    `docs/tasks/dashboard.html` trước khi commit).
11. Parent rà soát diff, commit `94-telegram-run-notify: ...`, xuất
    patch, verify `git am` trên worktree sạch tại `8adadb3`
    (HEAD task 93), cập nhật `~/MEMORY.md`, giao patch cho user.
    User tự kiểm chứng trên app thật sau khi tạo bot: nhập token →
    liên kết → chạy 1 run thật → tin Telegram về đúng số liệu.
