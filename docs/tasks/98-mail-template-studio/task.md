# Task 98: Mail Template Studio — Trình thiết kế email kéo thả cho ReconHub

## Mục tiêu
Triển khai phân hệ **Mail Template Studio** cho ReconHub theo tài liệu đặc tả `docs/tasks/98-mail-template-studio/prompt.md` và thiết kế mẫu đã duyệt `designs/components/Screen-MailTemplateStudio/preview.html`.
Chức năng cho phép người dùng quản trị tạo và chỉnh sửa email template bằng cách kéo thả component trực quan, không yêu cầu người dùng viết HTML/CSS thô, hỗ trợ quản lý đa phiên bản (Draft, Active, Archived), kiểm tra lỗi (Validate), xem trước đa kịch bản (Preview), gửi thử nghiệm an toàn, và biên dịch ra mã HTML chuẩn Table-based tương thích 100% với Outlook/Gmail.

## Tài liệu tham chiếu
- Prototype đã duyệt: `designs/components/Screen-MailTemplateStudio/preview.html`
- Prompt đặc tả chi tiết: `docs/tasks/98-mail-template-studio/prompt.md`
- Quy tắc hệ thống: `AGENTS.md` (Quy tắc Task 31 Data Model Explorer, quy tắc service, quy tắc bảo mật).
- Phân hệ liên quan: `app/engine/mailer.py` (Task 96 SMTP), `app/services/template_export_import.py` (Task 96 & 97).

## Yêu cầu cốt lõi
1. **Menu mới**: `mail_template_studio` (`/mail-template-studio`), bảo vệ bằng phân quyền menu (Task 19).
2. **Database 3 bảng**: `RECON_MAIL_TEMPLATE`, `RECON_MAIL_TPL_VERSION`, `RECON_MAIL_RULE_BINDING`.
3. **Data Model Explorer**: Sinh migration Alembic SQLite/Oracle, cập nhật manifest, kiểm tra Zero Drift.
4. **No-Code Component Builder**: 10 loại component chuẩn (Header, Text, Info, KPI, Table, Alert, Button, Divider, Spacer, Footer) với giới hạn style whitelist, cấm chèn raw HTML/JS tùy ý.
5. **Event Schema Registry**: Đăng ký biến dữ liệu theo sự kiện nghiệp vụ (`BATCH_RUN_COMPLETED`, `REPORT_EXPORT_COMPLETED`, `TEMPLATE_LIST_EXPORT`, `GENERAL_EXPORT`...).
6. **Condition Builder**: Đánh giá điều kiện hiển thị component (`summary.failed > 0`, `is_empty`...).
7. **Table-Based HTML Compiler & Sanitizer**: Biên dịch `DESIGN_JSON` thành HTML lồng thẻ `<table>` tương thích sâu với Microsoft Outlook và Gmail, kèm plain-text alternative.
8. **Versioning & Active Switch**: Đa phiên bản Draft / Active / Archived trong một transaction; Active version là read-only.
9. **Test Send & Validation**: Kiểm tra lỗi trước khi Active, gửi thử email có tiền tố `[TEST]` tới chính người thiết kế.
10. **Tương thích ngược**: Tích hợp thông suốt với tính năng gửi email danh sách template trên `/templates` và các phân hệ hiện có.
