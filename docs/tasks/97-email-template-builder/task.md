# 97-email-template-builder — Hệ thống Mẫu Email động, kéo thả và Live Preview theo chức năng

- Ngày tạo: 2026-11-18
- Giai đoạn: GĐ4
- Phụ thuộc: 96
- Nhánh git: feat/97-email-template-builder

## Mục tiêu
Xây dựng phân hệ Quản lý Mẫu Email (Email Template Builder) cho phép người dùng tùy chỉnh tiêu đề và nội dung email bằng cách chèn/kéo thả các thẻ dữ liệu động (tokens), xem trước diện mạo thư trong thời gian thực (Live Preview), hỗ trợ mẫu riêng cho từng chức năng của hệ thống (Xuất danh sách template, Báo cáo, Cảnh báo...) và tự động fallback về mẫu mặc định khi chưa có cấu hình riêng.

## Phạm vi
1. **Schema & Migration**:
   - Bảng `RECON_EMAIL_TEMPLATE`: `template_code` (PK), `name`, `function_code`, `subject_pattern`, `body_html`, `available_tokens` (JSON), `is_default`, `created_by`, `created_at`, `updated_by`, `updated_at`.
   - Migration Alembic hỗ trợ cả SQLite (batch mode) và Oracle.
   - Seed các template mặc định cho hệ thống (ví dụ: `TMPL_LIST_EXPORT`).
2. **Engine & Services**:
   - `app/engine/email_template.py`: Hàm render template an toàn, thay thế placeholder `{{token}}` bằng dữ liệu thực tế, kiểm tra cú pháp token.
   - `app/services/email_template.py`: CRUD cấu hình email template, khôi phục mẫu mặc định (reset to default), lấy template theo `function_code` (với logic fallback nếu chưa đăng ký).
3. **Giao diện Builder trên `/settings` (Tab "Mẫu Email")**:
   - Cột trái: Lựa chọn Chức năng / Phân hệ áp dụng; danh sách Thẻ dữ liệu (Chips/Badges) có thể click/kéo thả chèn vào nội dung.
   - Cột giữa: Trình soạn thảo Tiêu đề & Nội dung email; các nút thao tác "Khôi phục mặc định", "Lưu mẫu email".
   - Cột phải: Cửa sổ Live Preview thời gian thực mô phỏng giao diện hộp thư (Gmail/Outlook) với dữ liệu mẫu (mock data).
4. **Tích hợp vào chức năng gửi mail hiện tại**:
   - Cập nhật service `send_templates_list_email` trong `app/services/template_export_import.py` để nạp template từ `email_template_service` thay vì hardcode HTML.

## Ngoài phạm vi
- Xây dựng trình soạn thảo WYSIWYG HTML phức tạp của bên thứ ba (giữ phong cách chuẩn gọn của Dash & DMC, Markdown / Token Blocks trực quan).

## Spec liên quan
- `docs/specs/00-architecture.md`
- `docs/PRD.md`
- Task 31: Data Model Explorer

## Quyết định kiến trúc
- Mẫu mặc định (Default Template) được lưu trong DB đồng thời có fallback an toàn trong mã Python để đảm bảo không bao giờ lỗi gửi mail nếu DB bị xóa template.
- Live preview được cập nhật bằng Clientside / Server callback với dữ liệu giả lập chuẩn theo từng chức năng.

## Các bước
### Bước 1 — Schema `RECON_EMAIL_TEMPLATE` và Migration
- Tạo bảng trong `app/db/metadata.py`, tạo migration Alembic.
- Chạy `uv run poe schema-introspect` và cập nhật Data Model Explorer.
- Test migration và schema.

### Bước 2 — Engine render template & Fallback logic
- `app/engine/email_template.py`: parser token, replace placeholder, HTML template fallback.
- Test unit `tests/unit/test_email_template_engine.py`.

### Bước 3 — Service quản lý Email Template
- `app/services/email_template.py`: `get_email_template(function_code)`, `save_email_template(...)`, `reset_email_template(...)`.
- Test unit `tests/unit/test_email_template_service.py`.

### Bước 4 — Giao diện Tab "Mẫu Email" trên `/settings`
- Cột chức năng & token, cột soạn thảo, cột Live Preview.
- Callbacks live preview, đổi chức năng, lưu template, khôi phục mặc định.
- Test unit `tests/unit/test_page_settings_email_template.py`.

### Bước 5 — Tích hợp vào `/templates` và Kiểm thử hồi quy
- Nạp template động vào `send_templates_list_email`.
- Kiểm thử toàn diện: `lint`, `typecheck`, `test`, `security-check`.

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh
- [ ] Migration cập nhật, `uv run poe schema-introspect` đã chạy, drift = 0
- [ ] Tab Mẫu Email trên `/settings` soạn thảo và Live Preview mượt mà
- [ ] Gửi mail từ `/templates` hiển thị đúng theo mẫu template đã tùy biến hoặc mẫu mặc định
