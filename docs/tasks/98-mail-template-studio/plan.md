# Implementation Plan: Mail Template Studio (Task 98)

> **Mục tiêu**: Triển khai phân hệ **Mail Template Studio** cho ReconHub theo tài liệu đặc tả `docs/tasks/98-mail-template-studio/prompt.md` và prototype đã duyệt `designs/components/Screen-MailTemplateStudio/preview.html`.

---

## 1. Kiểm kê chức năng notification/email hiện có trong hệ thống

- **SMTP Mailer Engine (`app/engine/mailer.py`)**: Đã triển khai ở Task 96, hỗ trợ kết nối SMTP (STARTTLS, SSL, NONE), đính kèm tệp tin (`AttachmentSpec`), gửi HTML body và multipart MIME. Độc lập, chạy tốt, tái sử dụng 100%.
- **SMTP Settings Service (`app/services/smtp_settings.py`)**: Lưu cấu hình máy chủ SMTP trong `RECON_APP_SETTING`, mật khẩu mã hóa Fernet. Tái sử dụng 100%.
- **Notification Center & Preferences (Task 78)**: Đã có bảng `RECON_NOTIFICATION`, `RECON_NOTIFICATION_PREF` quản lý thông báo in-app và sở thích nhận tin.
- **Telegram Notify (Task 94)**: Đã có dịch vụ gửi thông báo kết quả qua bot Telegram.
- **Email Template cơ bản (Task 97)**: Đã có bảng `RECON_EMAIL_TEMPLATE` và service sơ khởi. Sẽ nâng cấp thành mô hình Studio đa phiên bản.
- **Menu Permission System (Task 19)**: Phân quyền qua `RECON_MENU`, `RECON_ROLE_MENU`, hàm `@requires_menu`.

---

## 2. Danh sách bảng mới và bảng dùng lại

### A. Bảng dùng lại:
- `RECON_MENU`: Bổ sung menu code `mail_template_studio`.
- `RECON_APP_SETTING`: Đọc cấu hình máy chủ SMTP.
- `RECON_AUDIT_LOG`: Ghi nhật ký các thao tác tạo/sửa/kích hoạt template.
- `RECON_NOTIFICATION` & `RECON_NOTIFICATION_PREF`: Phân hệ quản lý thông báo.

### B. Bảng mới (Theo mục 18 của Prompt):
1. **`RECON_MAIL_TEMPLATE`**:
   - `ID` (PK, Integer)
   - `CODE` (Varchar(64), Unique, Not Null) — Mã định danh chữ hoa, vd `TMPL_BATCH_RUN_ERROR`
   - `NAME` (Varchar(255), Not Null) — Tên hiển thị
   - `DESCRIPTION` (Varchar(500)) — Mô tả
   - `MENU_CODE` (Varchar(64), Not Null) — FK logic tới `RECON_MENU`
   - `EVENT_CODE` (Varchar(64), Not Null) — Mã sự kiện nghiệp vụ
   - `CURRENT_ACTIVE_VERSION_ID` (Integer, Nullable) — ID của version đang Active
   - `IS_ACTIVE` (String(1), Default 'Y')
   - `CREATED_BY`, `CREATED_AT`, `UPDATED_BY`, `UPDATED_AT`, `ROW_VERSION`

2. **`RECON_MAIL_TPL_VERSION`**:
   - `ID` (PK, Integer)
   - `TEMPLATE_ID` (Integer, FK tới `RECON_MAIL_TEMPLATE.ID`, Index)
   - `VERSION_NO` (Integer, Not Null) — Số phiên bản: 1, 2, 3...
   - `STATUS` (Varchar(20), Not Null) — `DRAFT`, `ACTIVE`, `ARCHIVED`, `INVALID`
   - `EVENT_SCHEMA_VERSION` (Integer, Default 1)
   - `SUBJECT_TEMPLATE` (Varchar(255), Not Null)
   - `PREHEADER_TEMPLATE` (Varchar(150))
   - `DESIGN_JSON` (Text/Json, Not Null) — Nguồn sự thật (Single Source of Truth)
   - `RENDERED_HTML` (Text) — Snapshot HTML table-based được biên dịch
   - `PLAIN_TEXT` (Text) — Snapshot text thuần
   - `DESIGN_HASH` (Varchar(64)) — SHA256 kiểm tra trùng lặp
   - `RENDERER_VERSION` (Varchar(20))
   - `VALIDATION_JSON` (Text/Json) — Kết quả kiểm tra lỗi
   - `CREATED_BY`, `CREATED_AT`, `ACTIVATED_BY`, `ACTIVATED_AT`, `ARCHIVED_AT`

3. **`RECON_MAIL_RULE_BINDING`**:
   - `RULE_ID` (Varchar(64), PK)
   - `TEMPLATE_ID` (Integer, FK tới `RECON_MAIL_TEMPLATE.ID`, Not Null)
   - `CREATED_BY`, `CREATED_AT`

---

## 3. Event Schema Registry

Module `app/engine/mail_event_registry.py` quản lý danh mục sự kiện nghiệp vụ cứng & payload schema:
- **`GENERAL_EXPORT`** (Menu `common`): Dùng làm fallback cho mọi tính năng xuất dữ liệu (`actor.name`, `module_name`, `summary.count`, `files_list`, `notes`, `links.download`).
- **`BATCH_RUN_COMPLETED`** / **`BATCH_RUN_COMPLETED_WITH_ERROR`** (Menu `batch_run`): Dành cho phiên chạy bộ đối soát (`actor.name`, `batch.name`, `batch.period`, `batch.run_code`, `summary.total`, `summary.failed`, `batch.items`, `links.result`).
- **`REPORT_EXPORT_COMPLETED`** (Menu `report`): Dành cho kết xuất báo cáo (`actor.name`, `report.name`, `export.filename`, `export.rows`, `links.download`).
- **`TEMPLATE_LIST_EXPORT`** (Menu `template`): Dành cho xuất danh sách mẫu đối soát (`actor.name`, `items_count`, `files_list`, `notes`).
- Mỗi Event định nghĩa danh mục biến phân loại (`actor`, `source`, `summary`, `collection`, `links`, `system`), kiểu dữ liệu (`string`, `integer`, `array`, `link_token`) và các bộ dữ liệu mẫu (Scenario: `success`, `error`, `empty`).

---

## 4. Design JSON Schema

Schema chuẩn JSON của một bản thiết kế email:
```json
{
  "schemaVersion": 1,
  "canvasSettings": {
    "maxWidth": 600,
    "bgColor": "#f3f5f9",
    "fontFamily": "Segoe UI, Arial, sans-serif"
  },
  "blocks": [
    {
      "id": 1,
      "type": "header | text | info | kpi | table | alert | button | divider | spacer | footer",
      "displayOrder": 1,
      "properties": {
        "text": "Nội dung hoặc nhãn có chứa {{variable}}",
        "color": "#192b43",
        "bg": "#ffffff",
        "size": 14,
        "pad": 16,
        "align": "left | center | right",
        "limit": 5,
        "url": "links.result",
        "columns": ["name", "status", "detail"]
      },
      "condition": {
        "type": "always | errors | noerrors",
        "field": "summary.failed",
        "operator": ">",
        "value": 0
      }
    }
  ]
}
```

---

## 5. Renderer Architecture (Biên dịch Table-based cho Email)

Module `app/engine/mail_renderer.py`:
- Không dùng HTML canvas thô.
- Đọc `DESIGN_JSON`, resolve biến an toàn, đánh giá điều kiện hiển thị `evaluate_condition`.
- **Cấu trúc Table-based lồng nhau (Nested Tables)**:
  - Container chính: `<table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#f3f5f9">...</table>`
  - Khung nội dung tối đa 600px: `<table width="600" align="center" border="0" cellpadding="0" cellspacing="0" bgcolor="#ffffff" style="max-width:600px; width:100%;">`
  - Từng block được bọc trong `<tr><td style="padding:...; color:...; font-size:...;">...</td></tr>`
  - Button dùng `<td>` bo góc hoặc padding inline có `background-color`, tương thích hoàn toàn Outlook 2016/2019/365 Desktop, Gmail App, Apple Mail.
- **Plain Text Generator**: Tự động duyệt qua các component Text, KPI, Info để sinh bản plain-text ngắn gọn, mạch lạc.

---

## 6. Sanitization Policy (Chính sách Bảo mật)

- **Cấm hoàn toàn**: `<script>`, `<iframe>`, `<object>`, `<embed>`, `<form>`, `<input>`, `style` tùy ý ngoài whitelist.
- **Whitelist thuộc tính**: Chỉ cho phép `size` (10-32px), `pad` (0-40px), `limit` (1-20 dòng), `align` (`left`, `center`, `right`), bảng mã màu hex tiêu chuẩn.
- **Liên kết**: Thuộc tính URL của nút chỉ được map vào các token `links.*` hợp lệ do Event Schema đăng ký. Cấm `javascript:`, `data:` hoặc URL bên ngoài tự do.
- **Escape biến dữ liệu**: Mọi giá trị dữ liệu từ payload đều qua hàm `html.escape()` trước khi điền vào template.

---

## 7. Notification Rule & Worker Integration

- Phân tách ranh giới rõ ràng: Mail Template Studio chỉ chịu trách nhiệm thiết kế nội dung và kích hoạt phiên bản.
- Việc xác định danh sách người nhận (`recipients`), kiểm tra quyền dữ liệu của người nhận (`data access policy`) và gửi theo hàng đợi được đảm nhiệm bởi Notification Rule / Event Outbox.
- Idempotency key: `EVENT_ID + RECIPIENT_ID + CHANNEL + RULE_ID` tránh gửi trùng lặp.

---

## 8. Provider Abstraction

- Tầng gửi mail trừu tượng: Kết nối với SMTP Mailer hiện có (`app.engine.mailer.send_smtp_email`).
- Sẵn sàng mở rộng cho Microsoft Graph API hoặc Teams Webhook mà không phải sửa lại Design JSON hay Studio UI.

---

## 9. Versioning Transaction

- Luồng chuyển trạng thái:
  - Tạo mới: Tạo `RECON_MAIL_TEMPLATE` và `RECON_MAIL_TPL_VERSION` v1 (`DRAFT`).
  - Sửa bản `ACTIVE`: Tự động nhân bản (clone) thành `v(N+1)` ở trạng thái `DRAFT`. Bản Active cũ vẫn phục vụ bình thường cho worker.
  - Khi bấm **Kích hoạt (Activate)**: Chạy trong 1 Transaction SQLAlchemy:
    1. Kiểm tra validation toàn diện.
    2. Cập nhật version cũ đang Active thành `ARCHIVED` (ghi `ARCHIVED_AT`).
    3. Cập nhật version mới thành `ACTIVE` (ghi `ACTIVATED_AT`, `ACTIVATED_BY`).
    4. Cập nhật `CURRENT_ACTIVE_VERSION_ID` trên bảng master `RECON_MAIL_TEMPLATE`.
    5. Ghi `RECON_AUDIT_LOG`.

---

## 10. Permission Mapping

- Mã menu: `mail_template_studio`.
- Cấp quyền cho vai trò `ADMIN` (mặc định) và có thể gán cho `TEMPLATE_OWNER` qua màn hình Phân quyền (Task 19, Task 20).
- Tất cả API/Service đều bảo vệ bằng decorator `@requires_menu("mail_template_studio")`.

---

## 11. Audit Events

Ghi nhận các hành động vào `RECON_AUDIT_LOG`:
- `CREATE_MAIL_TEMPLATE`: Tạo template mới.
- `SAVE_MAIL_TEMPLATE_DRAFT`: Lưu bản nháp version.
- `ACTIVATE_MAIL_TEMPLATE_VERSION`: Kích hoạt phiên bản mới làm Active.
- `CLONE_MAIL_TEMPLATE_VERSION`: Nhân bản version.
- `ARCHIVE_MAIL_TEMPLATE`: Lưu trữ template/version cũ.
- `TEST_SEND_MAIL_TEMPLATE`: Gửi thử nghiệm.

---

## 12. Migration Strategy (Tuân thủ Quy tắc Task 31)

- Viết file migration Alembic `0015_mail_template_studio.py` tạo 3 bảng mới với foreign keys và indices phù hợp, hỗ trợ cả SQLite (batch mode) và Oracle.
- Tự động di chuyển dữ liệu mặc định từ Task 97 sang phiên bản v1 `ACTIVE` trong bảng mới để đảm bảo tính liên tục của hệ thống.
- Chạy `uv run poe schema-introspect` để cập nhật `schema-manifest.json` và `schema-history.json`. Đảm bảo drift = 0.

---

## 13. Test Strategy

1. **Unit tests (`tests/unit/test_mail_template_engine.py`)**:
   - Parse token, validate event schema, evaluate condition, table limit clamp.
   - Render table-based HTML, sanitize XSS, plain-text generation.
2. **Service tests (`tests/unit/test_mail_template_service.py`)**:
   - Chạy trên isolated SQLite in-memory DB (`tmp_path`).
   - Kiểm tra CRUD, Clone Draft, Activate Transaction (chỉ 1 bản Active), Audit rollback.
3. **UI / Page tests (`tests/unit/test_page_mail_template_studio.py`)**:
   - Render 3 vùng giao diện (Library, Canvas, Property).
   - Kiểm tra các callbacks Validate, Test Send, Save Draft, Switch Desktop/Mobile, Switch Scenario.
4. **Integration & Regression tests**:
   - Trang `/templates` gọi gửi mail vẫn hoạt động trơn tru với template mới.

---

## 14. Rollback Strategy

- Database: Hạ revision Alembic về `0014_email_template` (`alembic downgrade -1`).
- Fallback code: Nếu Studio gặp lỗi, các service gửi email tự động dùng `get_builtin_default_template` gốc để đảm bảo không làm gián đoạn nghiệp vụ gửi mail của người dùng.

---

## 15. Danh sách file sẽ tạo hoặc sửa đổi

### Files mới:
- `app/engine/mail_event_registry.py`: Registry sự kiện nghiệp vụ và variable schemas.
- `app/engine/mail_renderer.py`: Engine biên dịch Design JSON -> Table-based HTML + Plain text.
- `app/services/mail_template_studio.py`: Service nghiệp vụ Master Template & Versioning.
- `app/ui/pages/mail_template_studio.py`: Giao diện 3 panel studio (`/mail-template-studio`).
- `migrations/versions/0015_mail_template_studio.py`: Migration tạo 3 bảng.
- `tests/unit/test_mail_template_engine.py`: Unit test engine & renderer.
- `tests/unit/test_mail_template_service.py`: Unit test service & versioning.
- `tests/unit/test_page_mail_template_studio.py`: Unit test UI Studio.

### Files sửa đổi:
- `app/db/metadata.py`: Khai báo 3 bảng SQLAlchemy Core (`recon_mail_template`, `recon_mail_tpl_version`, `recon_mail_rule_binding`).
- `app/services/schema_inspector.py`: Khai báo mô tả bảng và domain `admin` cho Data Model Explorer.
- `app/ui/menus.py`: Đăng ký menu `mail_template_studio`.
- `app/services/template_export_import.py`: Cập nhật hàm gọi lấy template từ `mail_template_studio` service.
- `docs/tasks/README.md` & `dashboard.html`: Đăng ký Task 98.
