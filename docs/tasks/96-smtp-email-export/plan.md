# Implementation Plan — Task 96: `96-smtp-email-export`
**Tiêu đề**: Trang cấu hình máy chủ SMTP và gửi email đính kèm file xuất  
**Nhánh git**: `feat/96-smtp-email-export`

---

### Bước 1 — Xây dựng Engine gửi mail thuần `app/engine/mailer.py`
- **File tạo mới**:
  - `app/engine/mailer.py`
  - `tests/unit/test_mailer.py`
- **Nội dung làm**:
  - Định nghĩa cấu trúc `AttachmentSpec` (`filename: str`, `content: bytes`, `mimetype: str`).
  - Hàm `build_email_message(from_addr, to_addrs, subject, body_html, body_text, attachments)`: Dùng thư viện chuẩn `email.message.EmailMessage` (UTF-8 tiếng Việt, multipart/alternative, đính kèm file bytes trực tiếp từ bộ nhớ).
  - Hàm `send_smtp_email(host, port, security, username, password, from_addr, to_addrs, subject, body_html, attachments, timeout=10)`:
    - Hỗ trợ các chế độ bảo mật: `STARTTLS` (port 587), `SSL/TLS` (port 465), `NONE` (port 25 nội bộ).
    - Đăng nhập SMTP nếu có tài khoản / mật khẩu.
    - Timeout 10s. Bắt các ngoại lệ `socket.timeout`, `smtplib.SMTPAuthenticationError`, `smtplib.SMTPConnectError` và trả kết quả rõ ràng.
- **Test viết trước (`tests/unit/test_mailer.py`)**:
  - `test_build_email_message`: Kiểm tra message có đủ headers, body HTML và đính kèm đúng file/MIME type.
  - `test_send_smtp_email_mocked`: Mock `smtplib.SMTP` và `smtplib.SMTP_SSL` để kiểm tra STARTTLS, SSL, login và gửi thành công.
  - `test_send_smtp_email_auth_error`: Mock lỗi xác thực và kiểm tra thông báo lỗi.
- **Kiểm tra**: `uv run pytest tests/unit/test_mailer.py`

---

### Bước 2 — Service quản lý cấu hình SMTP `app/services/smtp_settings.py`
- **File tạo mới**:
  - `app/services/smtp_settings.py`
  - `tests/unit/test_smtp_settings.py`
- **Nội dung làm**:
  - Các key cấu hình trong `RECON_APP_SETTING`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD_ENC` (mã hóa Fernet), `SMTP_FROM_NAME`, `SMTP_FROM_EMAIL`.
  - `get_smtp_settings(ctx)`: Lấy thông tin cấu hình cho UI (chỉ ADMIN). Trả về `has_password: bool` để không lộ mật khẩu ra giao diện.
  - `get_smtp_config_internal()`: Hàm nội bộ giải mã mật khẩu bằng `decrypt_secret` cho service gửi mail sử dụng.
  - `set_smtp_settings(ctx, data)`: Chỉ ADMIN (`require_role(ctx, Role.ADMIN)`). Mã hóa mật khẩu bằng `encrypt_secret` trước khi lưu vào `RECON_APP_SETTING`. Ghi `RECON_AUDIT_LOG`.
  - `test_smtp_connection(ctx, to_email)`: Gửi 1 email kiểm tra kết nối để xác thực thông số.
- **Test viết trước (`tests/unit/test_smtp_settings.py`)**:
  - `test_smtp_settings_rbac_admin_only`: Người dùng thường bị chặn truy cập.
  - `test_smtp_settings_save_and_retrieve`: Lưu cấu hình và mật khẩu được mã hóa an toàn.
  - `test_smtp_test_connection_service`: Mock gửi mail test thành công và trường hợp thiếu cấu hình.
- **Kiểm tra**: `uv run pytest tests/unit/test_smtp_settings.py`

---

### Bước 3 — Giao diện cấu hình SMTP trong `app/ui/pages/settings.py`
- **File sửa**:
  - `app/ui/pages/settings.py`
  - `tests/unit/test_page_settings.py`
- **Nội dung làm**:
  - Thêm thẻ Card **Cấu hình máy chủ gửi email (SMTP)** trên trang `/settings` (đồng nhất với phong cách khối cấu hình Telegram):
    - Các ô nhập: Máy chủ SMTP (Host), Cổng (Port), Phương thức bảo mật (Select: STARTTLS, SSL/TLS, Không bảo mật), Tài khoản, Mật khẩu (PasswordInput kèm placeholder khi đã có pass), Email người gửi (From Email), Tên người gửi hiển thị (From Name).
    - Ô "Email nhận thử nghiệm" và Nút **"Gửi email thử"** (có loading).
    - Nút **"Lưu cấu hình SMTP"**.
  - Callbacks: Tải cấu hình khi vào trang, lưu cấu hình và gửi email thử nghiệm kèm thông báo Toast.
- **Kiểm tra**: `uv run pytest tests/unit/test_page_settings.py`

---

### Bước 4 — Service gửi email đính kèm danh sách Template
- **File sửa**:
  - `app/services/template_export_import.py`
  - `tests/unit/test_template_email.py` (tạo mới)
- **Nội dung làm**:
  - Bổ sung service `send_templates_list_email(ctx, to_emails, format_types, search_term="", status_filter="", custom_subject="", notes="")`:
    - Kiểm tra quyền menu `template`.
    - Validate danh sách email người nhận hợp lệ.
    - Lấy cấu hình SMTP qua `get_smtp_config_internal()`. Nếu chưa cấu hình -> trả lỗi hướng dẫn vào Cài đặt để cấu hình.
    - Lấy danh sách template phù hợp bộ lọc hiện tại.
    - Sinh các file đính kèm bytes tương ứng (`build_templates_list_excel`, `docx`, `pdf`).
    - Dựng email HTML chuẩn (thông tin xuất, số lượng template, người xuất, ghi chú).
    - Gửi qua `send_smtp_email(...)`.
    - Ghi nhận hành động `SEND_TEMPLATE_EMAIL` vào `RECON_AUDIT_LOG`.
- **Test viết trước (`tests/unit/test_template_email.py`)**:
  - `test_send_templates_email_validation`: Báo lỗi khi thiếu email người nhận hoặc chưa cấu hình SMTP.
  - `test_send_templates_email_success`: Mock mailer, kiểm tra tạo file đính kèm và ghi audit log.
- **Kiểm tra**: `uv run pytest tests/unit/test_template_email.py`

---

### Bước 5 — Modal gửi email trên giao diện `/templates`
- **File sửa**:
  - `app/ui/pages/templates.py`
  - `tests/unit/test_page_templates.py`
- **Nội dung làm**:
  - Thêm mục `Gửi qua Email...` (icon `lucide:mail`) trong dropdown **Xuất danh sách**.
  - Bổ sung `dmc.Modal` (id `tmpl-email-modal`):
    - Chọn định dạng file đính kèm: `[x] Excel (.xlsx)` `[ ] Word (.docx)` `[ ] PDF (.pdf)`.
    - Nhập người nhận (tự động điền email của người dùng hiện tại nếu có).
    - Nhập tiêu đề email (gợi ý mặc định `[ReconHub] Danh sách Template đối soát — <Ngày>`).
    - Lời nhắn / Ghi chú (tùy chọn).
    - Nút "Hủy" và nút `button_primary("Gửi email", id="tmpl-email-submit-btn", icon="lucide:send")`.
  - Callbacks mở/đóng modal và callback gọi service gửi email (hiển thị trạng thái loading và thông báo Toast thành công/thất bại).
- **Kiểm tra**: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`

---

### Tiêu chí chấp nhận & An toàn
- [x] Không cài thêm bất kỳ thư viện ngoài nào (sử dụng `smtplib` và `email` chuẩn Python).
- [x] Mật khẩu SMTP luôn mã hóa Fernet, không leak ra log / UI.
- [x] Bảng `RECON_APP_SETTING` tái sử dụng, không làm thay đổi database schema.
- [x] Toàn bộ test suite, lint và typecheck xanh.
