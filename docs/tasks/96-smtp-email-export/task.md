# 96-smtp-email-export — Trang cấu hình máy chủ SMTP và gửi email đính kèm file xuất

- Ngày tạo: 2026-11-18
- Giai đoạn: GĐ3
- Phụ thuộc: 01, 08, 19
- Nhánh git: feat/96-smtp-email-export

## Mục tiêu
1. Cung cấp trang/khối cấu hình máy chủ SMTP dành cho Admin trên giao diện để quản lý kết nối gửi email mà không cần cấu hình trong file `.env`. Mật khẩu được mã hóa an toàn bằng Fernet trong `RECON_APP_SETTING`.
2. Hỗ trợ nút kiểm tra kết nối (Test connection / Gửi mail thử) ngay trên trang cấu hình SMTP để kiểm tra thông số máy chủ.
3. Bổ sung chức năng gửi email kèm file đính kèm (Excel `.xlsx`, Word `.docx`, PDF `.pdf`) trên trang danh sách Template (`/templates`) qua Modal chọn người nhận, tiêu đề, nội dung và định dạng file đính kèm.

## Phạm vi
- `app/engine/mailer.py`: Hàm thuần kết nối SMTP, dựng email MIME multipart UTF-8, đính kèm file in-memory (bytes), xử lý timeout 10s và ngoại lệ an toàn.
- `app/services/smtp_settings.py`: Service lấy cấu hình, lưu cấu hình SMTP (mã hóa Fernet mật khẩu), kiểm tra kết nối gửi email thử nghiệm.
- `app/services/template_export_import.py`: Service nghiệp vụ `send_templates_email` sinh file đính kèm (Excel, Word, PDF), gửi email qua cấu hình SMTP và ghi nhật ký `RECON_AUDIT_LOG`.
- `app/ui/pages/settings.py`: Khối cấu hình SMTP Server trên giao diện Cài đặt hệ thống (Host, Port, Bảo mật TLS/SSL, Username, Password, From Name/Email, nút Lưu và nút Gửi thử).
- `app/ui/pages/templates.py`: Mục "Gửi qua Email" trong dropdown Xuất danh sách, mở Modal nhập người nhận, tiêu đề, chọn định dạng đính kèm (Excel, Word, PDF) và gửi.
- Unit tests kiểm thử toàn diện: `tests/unit/test_smtp_settings.py`, `tests/unit/test_mailer.py`, `tests/unit/test_template_email.py`.

## Ngoài phạm vi
- Không cài thêm thư viện ngoài (sử dụng thư viện chuẩn `smtplib` và `email` của Python).
- Không tự động gửi email định kỳ (chỉ gửi theo thao tác người dùng hoặc khi có yêu cầu).

## Thiết kế
- Phong cách Fluent Compact (DMC 2.x), thẻ `dmc.Paper` hoặc `dmc.Card` withBorder đồng nhất với cấu hình Telegram trong `app/ui/pages/settings.py`.
- Modal `dmc.Modal` gọn gàng, tự động điền email người dùng hiện tại, có trạng thái loading khi gửi.

## Quyết định kiến trúc
- Mật khẩu SMTP luôn mã hóa Fernet (`encrypt_secret` / `decrypt_secret`), không bao giờ log ra console hay hiển thị dạng rõ trên giao diện.
- Gửi mail đính kèm file bytes trực tiếp từ bộ nhớ, không sinh file rác trên ổ cứng.
- Giao dịch gửi mail ghi `RECON_AUDIT_LOG` rõ ràng: ai gửi, gửi đến đâu, file đính kèm gì.

## Các bước
### Bước 1 — Xây dựng Engine gửi mail thuần `app/engine/mailer.py`
- Làm: Tạo hàm `send_smtp_email(host, port, security, username, password, from_addr, to_addrs, subject, body_html, attachments)` sử dụng `smtplib` và `email.message.EmailMessage`.
- Test viết trước: Kiểm tra tạo MIME message có đủ headers, đính kèm bytes với đúng MIME type và tên file.
- Kiểm tra: `uv run pytest tests/unit/test_mailer.py`

### Bước 2 — Service quản lý cấu hình SMTP `app/services/smtp_settings.py`
- Làm: `get_smtp_settings(ctx)`, `set_smtp_settings(ctx, ...)`, `test_smtp_connection(ctx, to_email)`. Lưu cấu hình mã hóa vào `RECON_APP_SETTING`.
- Test viết trước: Kiểm tra lưu cấu hình, giải mã mật khẩu, chặn user không phải ADMIN.
- Kiểm tra: `uv run pytest tests/unit/test_smtp_settings.py`

### Bước 3 — Giao diện cấu hình SMTP trong `app/ui/pages/settings.py`
- Làm: Thêm thẻ Cấu hình máy chủ SMTP (Host, Port, STARTTLS/SSL/None, Tài khoản, Mật khẩu, Tên hiển thị, Nút Lưu cấu hình, Nút Gửi thử nghiệm) kèm callbacks.
- Kiểm tra: `uv run poe test`

### Bước 4 — Service gửi email đính kèm danh sách Template
- Làm: Bổ sung `send_templates_list_email(ctx, to_emails, format_types, search_term, status_filter, custom_subject, notes)` trong `app/services/template_export_import.py`, ghi audit log.
- Test viết trước: Kiểm tra gọi gửi mail với file đính kèm Excel, Word, PDF.
- Kiểm tra: `uv run pytest tests/unit/test_template_email.py`

### Bước 5 — Modal gửi email trên giao diện `/templates`
- Làm: Thêm menu item "Gửi qua Email" trong dropdown Xuất danh sách của `app/ui/pages/templates.py`, modal nhập email, tiêu đề, chọn định dạng và callback gửi.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh
- [ ] Trang Cài đặt có form cấu hình máy chủ SMTP và nút Test kết nối hoạt động
- [ ] Trang `/templates` có Modal gửi mail đính kèm file xuất (Excel, Word, PDF) và gửi thành công
- [ ] Mật khẩu SMTP được bảo mật mã hóa Fernet

### Data Model Impact
- [ ] Task không thay đổi database schema (sử dụng bảng `RECON_APP_SETTING` đã có để lưu cấu hình).

## Câu hỏi mở
- Không.
