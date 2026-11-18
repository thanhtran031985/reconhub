# Implementation Plan — 97-email-template-builder

## Mục tiêu
Triển khai hệ thống Email Template động với giao diện kéo thả token và Live Preview tại `/settings`, cho phép tùy biến mẫu gửi thư theo từng chức năng và tự động fallback về mẫu mặc định.

## Kế hoạch từng bước

### Bước 1: Schema `RECON_EMAIL_TEMPLATE` & Migration
- Khai báo bảng `recon_email_template` trong `app/db/metadata.py`.
- Tạo migration revision Alembic (chạy trên SQLite batch mode và Oracle).
- Viết seed các mẫu email mặc định cho chức năng `TEMPLATE_LIST_EXPORT`.
- Chạy `uv run poe db-migrate` và `uv run poe schema-introspect` (cập nhật Data Model Explorer).
- Viết test migration trong `tests/integration/test_migrations.py` hoặc test unit metadata.

### Bước 2: Engine render email template (`app/engine/email_template.py`)
- Định nghĩa hàm `render_email_body(template_html: str, context: dict[str, Any]) -> str`.
- Định nghĩa hàm `render_email_subject(subject_pattern: str, context: dict[str, Any]) -> str`.
- Cung cấp hàm `get_builtin_default_template(function_code: str) -> dict[str, Any]` (fallback an toàn).
- Viết unit test trong `tests/unit/test_email_template_engine.py`.

### Bước 3: Service quản lý Email Template (`app/services/email_template.py`)
- `get_email_template_for_function(ctx: Ctx, function_code: str) -> dict[str, Any]`: Lấy template tùy biến từ DB, nếu chưa có thì lấy template mặc định.
- `list_supported_email_functions(ctx: Ctx) -> list[dict[str, Any]]`: Trả về danh sách chức năng (Mã, Tên, Danh sách token hỗ trợ, Mock context cho preview).
- `save_email_template(ctx: Ctx, function_code: str, subject_pattern: str, body_html: str) -> dict[str, Any]`: Lưu mẫu tùy biến, ghi audit log `UPDATE_EMAIL_TEMPLATE`.
- `reset_email_template_to_default(ctx: Ctx, function_code: str) -> dict[str, Any]`: Khôi phục mẫu gốc của hệ thống.
- Viết unit test trong `tests/unit/test_email_template_service.py`.

### Bước 4: Giao diện Tab "Mẫu Email" trên `/settings` (`app/ui/pages/settings.py`)
- Bổ sung tab `dmc.TabsTab("Mẫu Email", value="email_templates", leftSection=DashIconify(icon="lucide:file-code", width=16))`.
- Bố cục 3 cột (Grid 12 cột):
  - Cột 1 (3 cột): Chọn chức năng (`dmc.Select`) và Danh sách thẻ dữ liệu khả dụng (Badge tokens). Click vào token sẽ chèn ngay vào vị trí con trỏ trong khung soạn thảo.
  - Cột 2 (5 cột): Khung soạn thảo Tiêu đề mẫu (`dmc.TextInput`) và Nội dung mẫu (`dmc.Textarea`). Nút "Khôi phục mặc định" và nút "Lưu mẫu".
  - Cột 3 (4 cột): Khung Live Preview mô phỏng Email Client với tiêu đề và nội dung HTML hiển thị thời gian thực theo dữ liệu giả lập.
- Callbacks đồng bộ:
  - Khi đổi chức năng -> Tải template tương ứng và cập nhật Live Preview.
  - Khi gõ nội dung hoặc chèn token -> Live Preview cập nhật tức thì.
  - Khi bấm "Khôi phục mặc định" -> Reset về mẫu chuẩn của hệ thống.
  - Khi bấm "Lưu mẫu" -> Lưu vào DB và hiển thị thông báo.
- Viết unit test `tests/unit/test_page_settings_email_template.py`.

### Bước 5: Tích hợp vào `/templates` và Kiểm thử toàn diện
- Sửa `send_templates_list_email` trong `app/services/template_export_import.py` để lấy template từ `get_email_template_for_function(ctx, "TEMPLATE_LIST_EXPORT")` và render qua engine.
- Chạy toàn bộ bộ kiểm tra:
  - `uv run poe lint`
  - `uv run poe typecheck`
  - `uv run poe test`
  - `uv run poe security-check`
  - `uv run poe tasks-dashboard`
