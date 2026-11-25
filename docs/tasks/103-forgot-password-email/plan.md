# Kế hoạch triển khai: Task 103 — Chức năng quên mật khẩu & đặt lại mật khẩu qua email

- **Nhánh git**: `feat/103-forgot-password-email`
- **Mục tiêu**: Cho phép người dùng tự đặt lại mật khẩu qua email cá nhân một cách an toàn, chống lộ danh tính người dùng (Anti-Enumeration), vô hiệu hóa mọi phiên đăng nhập cũ sau khi đổi mật khẩu, và ghi nhật ký kiểm toán đầy đủ.
- **Thư viện bên ngoài**: Không cần cài thêm bất kỳ package nào (đã có đủ `argon2-cffi`, `secrets`, `hashlib`, SMTP sẵn có).

---

### Chi tiết 5 bước thực hiện:

#### Bước 1 — Schema & Database Migration
- **Công việc**:
  - Thêm bảng `recon_password_reset_token` vào `app/db/metadata.py`:
    - `ID`: BigInteger PK
    - `USER_ID`: BigInteger FK -> `RECON_USER.ID`
    - `TOKEN_HASH`: String(64) (Lưu băm SHA-256 của token, không lưu token thô)
    - `EXPIRES_AT`: DateTime (Thời hạn 20 phút)
    - `IS_USED`: String(1) default `'N'` (dùng 1 lần duy nhất)
    - `CREATED_AT`, `CREATED_IP`: Lưu vết thời gian và IP yêu cầu
  - Tạo file Alembic revision tương thích cả SQLite (batch mode) và Oracle.
  - Chạy `uv run poe schema-introspect` cập nhật `schema-manifest.json` và `schema-history.json` theo đúng quy tắc Data Model Explorer.
- **Test viết trước**: `tests/unit/test_password_reset_schema.py`
- **Lệnh kiểm tra**: `uv run poe db-migrate && uv run poe schema-introspect --check`

#### Bước 2 — Service Quên & Đặt lại mật khẩu (Backend Logic)
- **Công việc**:
  - Tạo `app/services/password_reset.py`:
    - `request_password_reset(engine, identifier, ip)`: Tìm user theo username/email; nếu hợp lệ và có email thì sinh `raw_token = secrets.token_urlsafe(32)`, lưu SHA-256 hash vào DB, gửi mail; luôn trả về `ServiceResult.success()` để chống User Enumeration.
    - `validate_reset_token(engine, raw_token)`: So khớp hash, kiểm tra thời hạn và trạng thái chưa sử dụng.
    - `perform_password_reset(engine, raw_token, new_password, ip)`: Kiểm tra độ an toàn của mật khẩu, băm bằng Argon2id, cập nhật `PASSWORD_HASH`, tăng `SESSION_VERSION` (thu hồi toàn bộ phiên đăng nhập cũ), reset `FAILED_COUNT = 0` và `LOCKED_UNTIL = None`, đánh dấu token `IS_USED = 'Y'`, ghi `RECON_AUDIT_LOG`.
  - Tích hợp hàm gửi email đặt lại mật khẩu với giao diện đẹp qua `app/services/email_sender.py`.
- **Test viết trước**: `tests/unit/test_password_reset_service.py`
- **Lệnh kiểm tra**: `uv run pytest tests/unit/test_password_reset_service.py -v`

#### Bước 3 — Giao diện Yêu cầu đặt lại mật khẩu (`/forgot-password`)
- **Công việc**:
  - Tạo trang `app/ui/pages/forgot_password.py` đăng ký route `/forgot-password`:
    - Card chuẩn Fluent Compact gồm ô nhập Tên đăng nhập hoặc Email.
    - Nút *"Gửi liên kết đặt lại mật khẩu"* (kèm trạng thái loading).
    - Thông báo xác nhận gửi thành công an toàn.
    - Nút liên kết *"Quay lại Đăng nhập"*.
  - Cập nhật trang `app/ui/pages/login.py`: Đổi dòng văn bản *"Quên mật khẩu..."* thành liên kết bấm được trỏ sang `/forgot-password`.
- **Test viết trước**: `tests/unit/test_page_forgot_password.py`
- **Lệnh kiểm tra**: `uv run pytest tests/unit/test_page_forgot_password.py -v`

#### Bước 4 — Giao diện Đặt lại mật khẩu (`/reset-password`)
- **Công việc**:
  - Tạo trang `app/ui/pages/reset_password.py` đăng ký route `/reset-password`:
    - Đọc tham số `token` từ URL.
    - Nếu token không hợp lệ hoặc đã hết hạn: Hiển thị Alert cảnh báo lỗi rõ ràng + nút quay lại trang Đăng nhập.
    - Nếu token hợp lệ: Hiển thị form nhập **Mật khẩu mới** và **Xác nhận mật khẩu mới**, nút Submit *"Xác nhận đặt lại mật khẩu"*.
    - Khi đổi thành công: Chuyển hướng người dùng về `/login?msg=reset_success` kèm thông báo thành công màu xanh.
- **Test viết trước**: `tests/unit/test_page_reset_password.py`
- **Lệnh kiểm tra**: `uv run pytest tests/unit/test_page_reset_password.py -v`

#### Bước 5 — E2E Playwright, Kiểm thử hồi quy & Hoàn tất task
- **Công việc**:
  - Viết bài test E2E `tests/e2e/test_forgot_password_flow.py` mô phỏng hành vi người dùng thật trên trình duyệt: yêu cầu -> nhận token -> mở trang đặt lại -> nhập mật khẩu mới -> đăng nhập thành công.
  - Kiểm tra các tiêu chuẩn: `poe lint`, `poe typecheck`, `poe test`, `schema-introspect --check`.
  - Cập nhật tiến độ `progress.md`, `checklist.md` và dashboard.
