# Tiến độ — 96-smtp-email-export

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Xây dựng Engine gửi mail thuần `app/engine/mailer.py` | ✅ | 2026-11-18 |  |
| 2 | Service quản lý cấu hình SMTP `app/services/smtp_settings.py` | ✅ | 2026-11-18 |  |
| 3 | Giao diện cấu hình SMTP trong `app/ui/pages/settings.py` (Tabs) | ✅ | 2026-11-18 |  |
| 4 | Service gửi email đính kèm danh sách Template | ✅ | 2026-11-18 |  |
| 5 | Modal gửi email trên giao diện `/templates` | ✅ | 2026-11-18 |  |

## Nhật ký
- 2026-11-18: Khởi tạo task và kế hoạch đã được người dùng phê duyệt. Tạo nhánh `feat/96-smtp-email-export`.
- 2026-11-18: Hoàn thành Bước 1 (Engine mailer) và Bước 2 (Service SMTP settings).
- 2026-11-18: Hoàn thành Bước 3 (Giao diện cấu hình SMTP trong `/settings` dạng Tabs theo yêu cầu người dùng + test gửi thử + unit test `test_page_settings.py` đạt 3/3).
- 2026-11-18: Hoàn thành Bước 4 (`send_templates_list_email` trong `template_export_import.py`, hỗ trợ XLSX, DOCX, PDF, audit log `SEND_TEMPLATE_EMAIL` + unit test `test_template_email.py` đạt 4/4).
- 2026-11-18: Hoàn thành Bước 5 (Menu Xuất email + Modal cấu hình tệp đính kèm/người nhận/lời nhắn trên trang `/templates` + callbacks + unit test `test_page_templates.py` đạt 17/17).
