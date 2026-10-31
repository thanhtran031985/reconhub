# Spec 06 – Bảo mật và vận hành

## 1. Người dùng, đăng nhập, phân quyền
- Người dùng lưu ở `RECON_USER`, vai trò ở `RECON_USER_ROLE` (một người nhiều vai trò). Username không phân biệt hoa thường (lưu chữ thường).
- Mật khẩu: **tự do, chỉ cần không rỗng**; băm argon2id (argon2-cffi `PasswordHasher` mặc định), `check_needs_rehash` khi đăng nhập thành công.
- Admin tạo người dùng với mật khẩu ban đầu, `MUST_CHANGE_PW='Y'` (bỏ chọn được). Đặt lại mật khẩu cũng bật cờ này. Người dùng đổi mật khẩu ở `/account`.
- Đăng nhập sai `LOGIN_MAX_FAILS` (5) lần liên tiếp → `LOCKED_UNTIL = now + LOGIN_LOCK_MINUTES` (15). Admin mở khóa được. Mọi lần đăng nhập ghi `RECON_LOGIN_LOG`. Thông báo lỗi chung "Tên đăng nhập hoặc mật khẩu không đúng"; khóa thì "Tài khoản tạm khóa đến HH:mm do đăng nhập sai nhiều lần".
- Phiên Flask: cookie `HttpOnly`, `SameSite=Lax`, ký bằng `FLASK_SECRET_KEY`, hết hạn `SESSION_HOURS` (8); lưu `user_id` + `session_version`. Mỗi request so `SESSION_VERSION` trong DB (cache 60 giây): khác → đăng xuất. Đổi/đặt lại mật khẩu, khóa, tắt user → tăng SESSION_VERSION.
- Admin đầu tiên: `uv run python -m app.cli create-admin` (hỏi username, họ tên, mật khẩu; từ chối nếu đã có Admin, trừ `--force`). `reset-password --username …` để cứu hộ khi quên mật khẩu Admin.
- Không được khóa/tắt/bỏ vai trò Admin cuối cùng đang hoạt động (`LAST_ADMIN`).
- `require_role(ctx, *roles)` trong mọi service; Flask `before_request` chặn request chưa đăng nhập (trừ /login, /health, /assets, /_dash-component-suites, /_dash-layout cho trang login); kiểm `Origin` cho `/_dash-update-component`.
- Không có SSO/Entra ID.

## 2. Bí mật
- Mật khẩu Data Source: Fernet `RECON_SECRET_KEY`; không trả về service, không vào component, Store, log, audit (`***`).
- `.env` không commit. Thư mục `data/`, `storage/`, `backup/` chỉ tài khoản chạy dịch vụ đọc/ghi được (Windows: ACL thư mục; Linux: chmod 700).

## 3. Truy vấn nguồn
User chỉ đọc; kiểm tra kết nối cảnh báo nếu có quyền ghi (`DS_NOT_READ_ONLY`); SQL guard; bind; whitelist; `call_timeout`; `max_rows`; chạy PROD cần xác nhận.

## 4. Upload
50MB; kiểm phần mở rộng + magic bytes (xlsx `PK`, xls OLE); không mở macro; chống zip bomb (tổng giải nén ≤ 500MB).

## 5. Audit
Ghi trong cùng transaction: tạo/sửa/khóa/mở khóa/đặt lại mật khẩu/gán vai trò người dùng; Data Source; template; run (tạo, hủy, đánh dấu đã kiểm tra); mọi lần xóa dữ liệu tạm, kết quả, file SQLite cũ; chuyển metadata; issue.

## 6. Log và giám sát
Log JSON (structlog) ra `logs/` (xoay vòng hằng ngày, giữ 30 ngày): request_id, user, route, ms; worker: run_id, stage, ms. Không log giá trị dữ liệu, SQL kèm bind values, mật khẩu. `/health`, `/health/worker` (heartbeat < 60s).

## 7. Dữ liệu tạm
Chỉ xóa theo yêu cầu (spec 04 mục 12). Cảnh báo khi vượt `TEMP_WARN_GB`/`TEMP_WARN_DAYS`.

## 8. Triển khai (task 16, không Docker)

| | Windows Server | Linux |
|---|---|---|
| Python | Python 3.12 + uv, `uv sync --frozen` | như Windows |
| Web | `waitress-serve --listen=0.0.0.0:8050 app.wsgi:server` (4–8 thread) | `gunicorn -w 3 -b 0.0.0.0:8050 app.wsgi:server` |
| Worker | `uv run python -m worker` | như Windows |
| Tự khởi động | 2 Windows Service (`ReconHub-Web`, `ReconHub-Worker`) bằng NSSM, chạy dưới tài khoản dịch vụ riêng | 2 unit systemd `reconhub-web.service`, `reconhub-worker.service`, user `reconhub` |
| Reverse proxy (tùy chọn) | IIS + ARR hoặc chạy thẳng cổng nội bộ | Nginx |
| Sao lưu SQLite | Task Scheduler chạy `app.cli backup` hằng đêm | cron/systemd timer |
- Web và worker chạy trên **cùng máy**, `data/` trên ổ local.
- Nâng cấp: dừng 2 dịch vụ → `git pull`/copy bản mới → `uv sync --frozen` → `uv run poe db-migrate` → khởi động lại.
- Sao lưu SQLite: `VACUUM INTO` hằng đêm vào `backup/`, giữ 14 bản; Oracle theo DBA. `storage/` là dữ liệu tạm, không bắt buộc sao lưu.
