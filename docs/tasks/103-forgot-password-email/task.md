# 103-forgot-password-email — Chức năng quên mật khẩu và đặt lại mật khẩu tự phục vụ qua email

- Ngày tạo: 2026-11-24
- Giai đoạn: GĐ1 (Mở rộng Xác thực & Bảo mật)
- Phụ thuộc: 01, 96
- Nhánh git: feat/103-forgot-password-email

## Mục tiêu
Cho phép người dùng tài khoản nội bộ tự đặt lại mật khẩu khi quên thông qua liên kết xác thực an toàn gửi tới email cá nhân đã đăng ký, giảm tải can thiệp thủ công của Quản trị viên, đảm bảo tuân thủ tiêu chuẩn an toàn thông tin (chống User Enumeration, token một lần, thời hạn ngắn, thu hồi mọi phiên đăng nhập cũ).

## Phạm vi
- Database: Bảng `RECON_PASSWORD_RESET_TOKEN` lưu token hash (SHA-256), thời hạn 15–30 phút, dùng 1 lần (`IS_USED`).
- Service: `app/services/password_reset.py` (tạo yêu cầu đặt lại mật khẩu, gửi email kèm token ngẫu nhiên `secrets.token_urlsafe`, xác thực token và cập nhật mật khẩu mới qua Argon2id).
- Email: Tích hợp với dịch vụ SMTP sẵn có (`app/services/email_sender.py`) và định dạng mẫu mail đặt lại mật khẩu.
- UI:
  - Cập nhật trang `/login`: Liên kết "Quên mật khẩu?" dẫn tới màn hình yêu cầu.
  - Trang `/forgot-password`: Nhập Tên đăng nhập / Email để nhận liên kết xác thực.
  - Trang `/reset-password`: Xác thực token từ query parameter, nhập mật khẩu mới và xác nhận mật khẩu.
- Bảo mật:
  - Chống User Enumeration (thông báo đồng nhất dù tài khoản tồn tại hay không).
  - Tăng `SESSION_VERSION` trong `RECON_USER` để vô hiệu hóa ngay lập tức mọi phiên đăng nhập đang mở trên các trình duyệt khác sau khi đổi mật khẩu thành công.
  - Ghi vết hành động vào `RECON_AUDIT_LOG` (`ACTION = 'PASSWORD_RESET_SELF'`).
  - Cập nhật Data Model Explorer và schema manifest (Alembic migration cho SQLite batch mode và Oracle).

## Ngoài phạm vi
- Không áp dụng đặt lại mật khẩu cho tài khoản SSO Doanh nghiệp (tài khoản SSO đổi mật khẩu tại IdP tập trung).
- Không gửi mật khẩu dưới dạng văn bản thô (plain-text) qua email.

## Thiết kế
- Trang `/forgot-password` và `/reset-password` tuân thủ chuẩn Fluent Compact, kích thước tương tự Card đăng nhập (`w=380`, `p="lg"`, `shadow="xs"`, `radius="md"`).
- Component Mantine: `dmc.TextInput`, `dmc.PasswordInput`, `dmc.Button`, `dmc.Alert`, `dmc.Anchor`, `dmc.Paper`.

## Spec liên quan
- `docs/specs/01_auth_users.md`
- `docs/specs/06_security_ops.md`

## Quyết định kiến trúc
- **Lưu trữ Token an toàn**: Không lưu chuỗi token gốc vào database. Chỉ lưu giá trị băm `SHA-256` của token. Khi người dùng click link, hệ thống tính hash của token nhận được để so khớp với DB.
- **Thời hạn Token**: 20 phút kể từ lúc sinh token. Token bị hủy ngay sau lần sử dụng đầu tiên (`IS_USED = 'Y'`).
- **Thu hồi phiên đăng nhập**: Khi đổi mật khẩu thành công, cập nhật `SESSION_VERSION = SESSION_VERSION + 1`, reset `FAILED_COUNT = 0` và `LOCKED_UNTIL = None`.

## Các bước
### Bước 1 — Schema & Database Migration
- Làm: Tạo bảng `RECON_PASSWORD_RESET_TOKEN` trong `app/db/metadata.py`, tạo Alembic migration chạy trên SQLite batch mode và Oracle. Chạy `uv run poe schema-introspect`.
- Test viết trước: `tests/unit/test_password_reset_schema.py`
- Kiểm tra: `uv run poe db-migrate && uv run poe test` → xanh

### Bước 2 — Service Quên & Đặt lại mật khẩu (Backend)
- Làm: Xây dựng `app/services/password_reset.py` gồm các hàm `request_password_reset`, `validate_reset_token`, `perform_password_reset`. Gửi mail qua `email_sender`.
- Test viết trước: `tests/unit/test_password_reset_service.py`
- Kiểm tra: `uv run pytest tests/unit/test_password_reset_service.py -v` → passed

### Bước 3 — Giao diện Yêu cầu đặt lại mật khẩu (`/forgot-password`)
- Làm: Xây dựng page `app/ui/pages/forgot_password.py` và cập nhật link trên `app/ui/pages/login.py`.
- Test viết trước: `tests/unit/test_page_forgot_password.py`
- Kiểm tra: `uv run pytest tests/unit/test_page_forgot_password.py -v` → passed

### Bước 4 — Giao diện Đặt lại mật khẩu (`/reset-password`) & Hoàn tất
- Làm: Xây dựng page `app/ui/pages/reset_password.py` nhận token, validate mật khẩu mới và submit đổi mật khẩu.
- Test viết trước: `tests/unit/test_page_reset_password.py`
- Kiểm tra: `uv run pytest tests/unit/test_page_reset_password.py -v` → passed

### Bước 5 — E2E Testing, Data Model Validation & Đóng task
- Làm: Viết Playwright E2E test cho toàn bộ luồng quên mật khẩu, kiểm tra Data Model Explorer, rà soát lint/typecheck.
- Test: `tests/e2e/test_forgot_password_flow.py`
- Kiểm tra: `uv run poe lint; uv run poe typecheck; uv run poe test` → toàn bộ đạt chuẩn

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh
- [ ] Bảng `RECON_PASSWORD_RESET_TOKEN` được tạo với migration chuẩn SQLite và Oracle
- [ ] Chống User Enumeration thành công trên giao diện và API
- [ ] Token dùng 1 lần, hết hạn sau 20 phút, lưu dạng băm SHA-256
- [ ] Đổi mật khẩu thành công hủy toàn bộ phiên cũ của người dùng (`SESSION_VERSION`)
- [ ] Ghi đầy đủ `RECON_AUDIT_LOG`

### Data Model Impact
- [ ] Migration cập nhật.
- [ ] DB model cập nhật.
- [ ] `uv run poe schema-introspect` đã chạy.
- [ ] `docs/data-model/schema-manifest.json` đã regenerate.
- [ ] `docs/data-model/schema-history.json` đã cập nhật.
- [ ] Schema drift = 0 hoặc đã ghi rõ lý do.
- [ ] Page `/data-model` hiển thị thay đổi.
- [ ] Regression tests pass.

## Câu hỏi mở
- Không.
