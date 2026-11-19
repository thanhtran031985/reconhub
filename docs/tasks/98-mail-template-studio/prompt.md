# TASK PROMPT: MAIL TEMPLATE STUDIO – TRÌNH THIẾT KẾ EMAIL KÉO THẢ CHO RECONHUB

## 1. Vai trò của AI trong task này

Bạn là Senior Full-stack Engineer chịu trách nhiệm triển khai chức năng **Mail Template Studio** cho ReconHub.

Chức năng cho phép người dùng quản trị tạo và chỉnh sửa email template bằng cách kéo thả các component, không yêu cầu người dùng nhập HTML.

Bạn phải:

1. Đọc toàn bộ code hiện tại trước khi sửa.
2. Đọc các tài liệu thiết kế, spec, task, database convention và UI convention hiện có.
3. Kiểm kê các chức năng notification, event, email, user, role, menu, audit và worker đã có trong dự án.
4. Lập Implementation Plan chi tiết.
5. Chưa code khi kế hoạch chưa được duyệt.
6. Chỉ sửa những phần thuộc phạm vi task này.
7. Viết test trước cho các phần logic quan trọng.
8. Không phá vỡ Notification Center, Dynamic Reporting, Batch Run, phân quyền, audit hoặc các chức năng đang chạy.

Prototype UI/UX được duyệt là:

`designs/components/Screen-MailTemplateStudio/preview.html`

Nếu prototype chưa nằm đúng thư mục, sử dụng file:

`ReconHub_Mail_Template_Studio.html`

Prototype là nguồn tham chiếu chính về bố cục, hành vi và tương tác người dùng. Không tự ý thay đổi thiết kế sang một kiểu hoàn toàn khác.

---

## 2. Mục tiêu nghiệp vụ

Mail Template Studio cho phép người dùng có quyền quản trị:

- Tạo email template mới.
- Chọn menu và loại sự kiện mà template hỗ trợ.
- Nhập subject email có placeholder.
- Thiết kế email bằng component kéo thả.
- Chèn biến dữ liệu theo schema của sự kiện.
- Cấu hình điều kiện hiển thị cho từng component.
- Preview bằng dữ liệu mẫu.
- Preview Desktop và Mobile.
- Kiểm tra lỗi template.
- Gửi thử email tới chính người thiết kế.
- Lưu phiên bản Draft.
- Kích hoạt một version để Notification Worker sử dụng.
- Nhân bản version hoặc template hiện có.
- Gắn template vào Notification Rule.
- Xem lịch sử version.
- Archive template hoặc version cũ.
- Lưu Design JSON để mở lại trong editor.
- Render Design JSON thành HTML email và plain text khi gửi.

Người dùng không được nhập JavaScript và không được nhập HTML tùy ý.

---

## 3. Ranh giới chức năng

### 3.1. Mail Template Studio chịu trách nhiệm

- Thiết kế nội dung email.
- Quản lý component.
- Quản lý variable binding.
- Preview.
- Validation.
- Versioning.
- Render Design JSON thành HTML và plain text.
- Test send.
- Gắn template với event hoặc Notification Rule.
- Audit thay đổi template.

### 3.2. Mail Template Studio không chịu trách nhiệm

- Quản lý SMTP password.
- Quản lý Microsoft Graph secret.
- Quản lý Teams webhook secret.
- Quản lý worker Notification tổng thể.
- Tự truy vấn Oracle để lấy dữ liệu.
- Tự xác định người nhận bằng SQL.
- Tự cấp quyền xem dữ liệu cho người nhận.
- Tự tạo mã sự kiện không tồn tại trong backend.
- Cho phép gửi một email tùy ý ngoài Notification Rule.

SMTP, Microsoft Graph, Teams connector và credential phải nằm trong phần cấu hình hệ thống, được mã hóa hoặc lấy từ environment/secret store.

---

## 4. Mô hình tổng thể

Quan hệ nghiệp vụ:

**Menu → Business Event → Notification Rule → Mail Template → Mail Template Version**

Ví dụ:

- Menu: Chạy bộ đối soát
- Event: `BATCH_RUN_COMPLETED_WITH_ERROR`
- Rule: Có ít nhất một template lỗi
- Recipient: Người chạy + Admin
- Channel: EMAIL
- Mail Template: Tóm tắt Batch Run có lỗi
- Active Version: v3

Không gắn duy nhất một template trực tiếp vào menu vì một menu có thể phát sinh nhiều sự kiện khác nhau.

Một mail template có thể tương thích với nhiều event nếu các event dùng cùng một variable schema. Việc tương thích phải được backend kiểm tra.

---

## 5. Cấu trúc màn hình

Màn Mail Template Studio có bố cục ba vùng:

1. **Component Library**, bên trái.
2. **Email Canvas**, chính giữa.
3. **Property Panel**, bên phải.

Phía trên là metadata của template và toolbar thao tác.

---

## 6. Thanh tiêu đề và metadata

### 6.1. Header

Hiển thị:

- Breadcrumb: `ReconHub / Thông báo / Mail Template Studio`
- Môi trường: UAT hoặc PROD
- Người dùng hiện tại
- Phiên bản template
- Trạng thái: DRAFT, ACTIVE hoặc ARCHIVED

### 6.2. Thông tin template

| Trường | Bắt buộc | Quy tắc |
|---|---:|---|
| Template Code | Có | Chữ hoa, số, dấu gạch dưới; không đổi sau khi tạo |
| Template Name | Có | Không trùng trong cùng phạm vi |
| Description | Không | Tối đa 500 ký tự |
| Menu Code | Có | Chọn từ `RECON_MENU`, không nhập tự do |
| Event Code | Có | Chỉ hiển thị event đã đăng ký cho menu |
| Email Subject | Có | Cho phép placeholder hợp lệ |
| Preheader | Không | Tối đa 150 ký tự |
| Default Locale | Có | Mặc định `vi-VN` |
| Status | Có | DRAFT, ACTIVE, ARCHIVED |

Nếu đổi Event Code, hệ thống phải:

1. Tải variable schema mới.
2. Kiểm tra toàn bộ placeholder trong subject và component.
3. Đánh dấu component chứa biến không tương thích.
4. Không tự xóa nội dung.
5. Chặn Activate cho đến khi sửa hết lỗi.

### 6.3. Toolbar

Các nút:

- **Kiểm tra**
- **Gửi thử**
- **Lưu nháp**
- **Kích hoạt**
- **Nhân bản**
- **Xem lịch sử version**
- **Gắn quy tắc gửi**
- **Archive**, chỉ khi được phép

Nút Kích hoạt chỉ bật khi:

- Metadata hợp lệ.
- Variable hợp lệ.
- Component hợp lệ.
- Không có URL tùy ý.
- Template có ít nhất một component.
- Test render thành công.
- Active version hiện tại không bị ghi đè trực tiếp.

---

## 7. Vùng 1 – Component Library

### 7.1. Danh sách component

| Component | Mục đích |
|---|---|
| Header | Logo, tên hệ thống, tiêu đề email |
| Text | Đoạn văn, lời chào, hướng dẫn |
| Information | Danh sách label–value |
| KPI | Hiển thị số liệu tổng hợp |
| Data Table | Danh sách template lỗi hoặc dữ liệu tổng hợp |
| Alert | Khối INFO, SUCCESS, WARNING, ERROR |
| Action Button | Mở kết quả, tải file, mở đối tượng nguồn |
| Divider | Đường phân cách |
| Spacer | Khoảng cách |
| Footer | Chữ ký, ghi chú hệ thống |
| One-column layout | Container một cột |
| Two-column layout | Container hai cột có giới hạn |

Không hỗ trợ absolute positioning.

Không cho component chồng lên nhau.

Không cho người dùng kéo component ra ngoài canvas.

### 7.2. Cách thêm component

Cho phép:

- Kéo component từ Library vào Canvas.
- Bấm component để thêm sau component đang chọn.
- Kéo component tới cuối canvas.
- Dùng bàn phím để chọn và thêm.

Khi thêm:

1. Sinh Component ID duy nhất trong version.
2. Gán property mặc định.
3. Chọn component vừa thêm.
4. Đánh dấu template có thay đổi chưa lưu.
5. Cập nhật Property Panel.
6. Cập nhật preview.

### 7.3. Danh sách biến sự kiện

Bên dưới Component Library hiển thị variable schema của Event Code hiện tại.

Ví dụ:

- `actor.name`
- `batch.name`
- `batch.period`
- `summary.total`
- `summary.failed`
- `batch.items`
- `links.result`

Phân nhóm biến:

- Actor
- Source object
- Summary
- Collection
- Link
- System

Mỗi biến cần có:

- Tên.
- Kiểu dữ liệu.
- Mô tả.
- Ví dụ.
- Có thể rỗng hay không.
- Format hỗ trợ.

Người dùng bấm biến để chèn vào:

1. Field nội dung đang focus ở Property Panel.
2. Subject nếu không có field nội dung nào đang focus.

Không bắt người dùng nhớ hoặc tự gõ placeholder.

---

## 8. Vùng 2 – Email Canvas

### 8.1. Canvas

Canvas mô phỏng email rộng tối đa khoảng 600px trên Desktop.

Các chế độ:

- Desktop preview.
- Mobile preview khoảng 360px.
- Edit mode.
- Preview mode.

Ở Edit mode:

- Component được viền khi hover.
- Component được viền màu primary khi được chọn.
- Component có toolbar nhỏ:
  - Đưa lên.
  - Đưa xuống.
  - Nhân bản.
  - Xóa.

Ở Preview mode:

- Ẩn viền editor.
- Ẩn toolbar component.
- Ẩn drop zone.
- Áp dụng điều kiện hiển thị.
- Render placeholder bằng dữ liệu mẫu.

### 8.2. Sắp xếp component

Cho phép:

- Kéo thả component.
- Đưa lên hoặc xuống bằng nút.
- Dùng bàn phím.

Sau khi đổi vị trí:

- Cập nhật `DISPLAY_ORDER`.
- Không thay đổi Component ID.
- Không mất property.
- Không mất variable binding.
- Không tạo component trùng.

### 8.3. Nhân bản

Khi nhân bản:

- Copy toàn bộ property.
- Sinh Component ID mới.
- Đặt bản sao ngay sau component gốc.
- Không chia sẻ reference object với component cũ.
- Sửa bản sao không làm thay đổi bản gốc.

### 8.4. Xóa

Khi xóa:

- Nếu là component bình thường: xóa ngay, cho Undo trong toast hoặc command history.
- Nếu component đang chứa dữ liệu quan trọng như bảng hoặc nút hành động: hỏi xác nhận.
- Sau khi xóa, chọn component gần nhất.
- Không được để state `selected_component_id` trỏ tới component đã xóa.

### 8.5. Dữ liệu thử

Có ít nhất ba scenario:

- Thành công.
- Có lỗi.
- Không có dữ liệu.

Scenario lấy từ sample payload đã đăng ký cho event.

Admin có thể tạo thêm sample payload nhưng phải:

- Tuân thủ event schema.
- Không chứa dữ liệu thật nhạy cảm.
- Không truy vấn Oracle trong preview.

---

## 9. Vùng 3 – Property Panel

Property Panel thay đổi theo component đang chọn.

### 9.1. Thuộc tính chung

Mọi component có:

- Background color.
- Text color.
- Font size.
- Font weight.
- Alignment.
- Padding.
- Margin hoặc spacing giới hạn.
- Border color.
- Border radius.
- Condition.
- Visibility.
- Component label nội bộ.

Giá trị phải có min/max:

- Font size: 10–32px.
- Padding: 0–40px.
- Radius: 0–20px.
- Table row limit: 1–20.
- Email content width: không vượt giới hạn được cấu hình.

Không cho nhập CSS tự do.

### 9.2. Header

Thuộc tính:

- Logo mặc định từ hệ thống.
- Tiêu đề.
- Subtitle.
- Màu nền.
- Chiều cao.
- Căn trái hoặc giữa.

Không cho tải logo từ URL tùy ý. Logo lấy từ asset đã đăng ký hoặc upload nội bộ đã quét.

### 9.3. Text

Thuộc tính:

- Nội dung rich text giới hạn.
- Placeholder.
- Căn lề.
- Typography.
- Link nội bộ đã đăng ký.

Rich text chỉ hỗ trợ:

- Bold.
- Italic.
- Underline.
- Danh sách.
- Link an toàn.
- Xuống dòng.

Không cho script, iframe, object, form hoặc inline event handler.

### 9.4. Information

Cấu hình danh sách label–value.

Ví dụ:

- Kỳ: `{{batch.period}}`
- Người chạy: `{{actor.name}}`
- Mã run: `{{batch.run_code}}`

Cho phép:

- Thêm hoặc xóa dòng.
- Đổi label.
- Chọn variable.
- Chọn format.
- Ẩn dòng khi value rỗng.

### 9.5. KPI

Cấu hình nhiều KPI item:

- Label.
- Value variable.
- Format số.
- Màu.
- Điều kiện cảnh báo.
- Số KPI mỗi hàng.

Ví dụ:

- Tổng template.
- Hoàn tất.
- Có lỗi.

Giới hạn số KPI hợp lý, mặc định tối đa 4 hoặc 6.

### 9.6. Data Table

Cấu hình:

- Collection variable.
- Các cột của object.
- Header cột.
- Display order.
- Width tương đối.
- Format.
- Alignment.
- Row limit từ 1 đến 20.
- Điều kiện lọc bằng builder.
- Hành vi khi không có dữ liệu.
- Dòng “Xem thêm trong ứng dụng” khi vượt giới hạn.

Không cho template tự nhập SQL.

Không render hàng nghìn dòng vào email.

Nếu dữ liệu vượt row limit:

- Chỉ render số dòng cho phép.
- Hiển thị ghi chú còn bao nhiêu dòng.
- Hiển thị Action Button tới màn chi tiết.

### 9.7. Alert

Loại:

- INFO.
- SUCCESS.
- WARNING.
- ERROR.

Thuộc tính:

- Icon.
- Nội dung.
- Màu từ design token.
- Điều kiện hiển thị.

Không cho người dùng tạo màu cảnh báo không tương phản.

### 9.8. Action Button

Thuộc tính:

- Button label.
- Action link variable.
- Primary hoặc Secondary style.
- Alignment.
- Điều kiện hiển thị.

Action link chỉ được chọn từ danh sách link variable do Event Schema cung cấp, ví dụ:

- `links.result`
- `links.report_history`
- `links.download`

Không cho nhập URL tùy ý.

Backend phải kiểm quyền lại khi người dùng mở liên kết. Email link không được dùng để bypass owner filter.

### 9.9. Divider, Spacer và Footer

Divider:

- Màu.
- Độ dày 1–3px.
- Khoảng cách.

Spacer:

- Chiều cao giới hạn 4–48px.

Footer:

- Nội dung.
- Chữ ký hệ thống.
- Link hỗ trợ.
- Unsubscribe nếu loại email yêu cầu.
- Môi trường UAT/PROD.

---

## 10. Điều kiện hiển thị

Không cho người dùng viết JavaScript hoặc Python.

Condition Builder dạng:

- Field.
- Operator.
- Value.

Hỗ trợ:

- Equal.
- Not equal.
- Greater than.
- Less than.
- Is empty.
- Is not empty.
- Collection has items.
- Collection is empty.

Ví dụ:

- `summary.failed > 0`
- `export.is_ready = true`
- `batch.items has items`

Mỗi component có thể:

- Luôn hiển thị.
- Hiển thị khi điều kiện đúng.
- Ẩn khi value rỗng.

Condition phải được validate theo Event Schema.

---

## 11. Subject và Preheader

Subject hỗ trợ placeholder nhưng không hỗ trợ HTML.

Ví dụ:

`[ReconHub] {{batch.name}} · {{batch.period}}`

Yêu cầu:

- Validate placeholder.
- Giới hạn độ dài hợp lý, khuyến nghị 150–200 ký tự.
- Render sample trong preview.
- Cảnh báo nếu subject rỗng.
- Cảnh báo nếu subject chứa variable không tồn tại.
- Không cho line break.

Preheader:

- Plain text.
- Placeholder hợp lệ.
- Không chứa HTML.
- Giới hạn 150 ký tự.

---

## 12. Event Schema

Backend phải có registry của event.

Mỗi event gồm:

- Event Code.
- Menu Code.
- Display Name.
- Description.
- Payload JSON Schema.
- Sample payloads.
- Link variables.
- Collection definitions.
- Version của schema.
- Trạng thái Active.

Ví dụ `BATCH_RUN_COMPLETED_WITH_ERROR`:

- `actor.name`: string.
- `batch.name`: string.
- `batch.period`: string.
- `summary.total`: integer.
- `summary.failed`: integer.
- `batch.items`: array.
- `batch.items[].name`: string.
- `batch.items[].status`: string.
- `batch.items[].detail`: string.
- `links.result`: internal URL token.

Template không được tự thêm event field.

Nếu event schema nâng version:

- Không sửa âm thầm template Active.
- Chạy compatibility check.
- Active template không tương thích phải được đánh dấu Warning hoặc Invalid.
- Yêu cầu tạo version template mới.

---

## 13. Lưu dữ liệu thiết kế

Không chỉ lưu HTML.

Mỗi version lưu:

- Design JSON.
- Event Code.
- Event Schema Version.
- Subject template.
- Preheader template.
- Rendered HTML snapshot nếu cần cache.
- Plain text snapshot.
- Validation result.
- Version number.
- Status.
- Created By/At.
- Activated By/At.
- Design hash.
- Renderer version.

Design JSON phải chứa:

- Schema version.
- Canvas settings.
- Component list.
- Component ID.
- Component type.
- Display order.
- Properties.
- Data binding.
- Condition.
- Style tokens.

Renderer phải đọc Design JSON và sinh HTML. Không dùng HTML từ người dùng làm nguồn chính.

---

## 14. Versioning

Trạng thái:

- DRAFT.
- ACTIVE.
- ARCHIVED.
- INVALID, nếu schema đã không còn tương thích.

Luồng:

1. Tạo template Draft v1.
2. Chỉnh sửa và validate.
3. Gửi thử.
4. Activate v1.
5. Khi sửa Active: clone thành v2 Draft.
6. v1 vẫn Active trong khi v2 đang sửa.
7. Activate v2 trong transaction.
8. v1 chuyển Archived.
9. Notification đã gửi giữ tham chiếu version chính xác.

Chỉ được có một Active version trên một template.

Không cho sửa trực tiếp Active version.

---

## 15. Gửi thử

Gửi thử chỉ tới:

- Chính email của người thiết kế.
- Hoặc danh sách email test được Admin cấu hình.

Không cho nhập người nhận tùy ý trong màn Studio.

Gửi thử phải:

- Dùng sample payload.
- Có prefix `[TEST]`.
- Có banner “Đây là email thử”.
- Không dùng dữ liệu Oracle thật.
- Ghi audit.
- Ghi delivery log riêng với trạng thái TEST.

Nếu chưa cấu hình SMTP hoặc Microsoft Graph:

- Hiển thị lỗi cấu hình rõ.
- Không giả vờ gửi thành công.

Prototype hiện tại chỉ mô phỏng, production phải dùng service thật.

---

## 16. Gắn quy tắc gửi

Màn Studio chỉ chọn hoặc liên kết Notification Rule.

Rule chứa:

- Event Code.
- Condition.
- Recipient resolver.
- Channel.
- Mail Template ID.
- Active template version tại thời điểm gửi.
- Priority.
- Quiet hours.
- Retry policy.
- Active flag.

Không nhúng recipients vào Design JSON.

Recipient resolver hỗ trợ:

- Actor.
- Object owner.
- Report owner.
- Data Source owner.
- Assignee.
- Manager.
- Role.
- User đã cấu hình.

Mọi người nhận phải qua authorization và data access policy.

---

## 17. Data flow

### 17.1. Thiết kế

Admin mở Studio
→ chọn menu và event
→ tải Event Schema
→ tạo hoặc clone Draft Version
→ kéo thả component
→ binding placeholder
→ cấu hình style và condition
→ preview với sample payload
→ validate Design JSON
→ render HTML + plain text
→ gửi thử
→ activate version.

### 17.2. Gửi email thật

Business transaction
→ ghi Event Outbox trong cùng transaction
→ Notification Worker claim event
→ tìm Notification Rule phù hợp
→ resolve recipients
→ kiểm quyền dữ liệu
→ kiểm preference và quiet hours
→ lấy Active Mail Template Version
→ validate payload theo schema version
→ render Design JSON
→ sanitize HTML
→ sinh plain text
→ tạo Delivery Record
→ gửi qua provider
→ cập nhật delivery status
→ retry hoặc dead-letter khi lỗi.

### 17.3. Idempotency

Delivery key:

`EVENT_ID + RECIPIENT_ID + CHANNEL + RULE_ID`

Nếu worker retry, không tạo delivery trùng.

Cần phân biệt:

- Provider chưa nhận request.
- Provider nhận nhưng response timeout.
- Provider xác nhận Message ID.
- Provider reject.
- Provider temporarily unavailable.

Không mặc định retry mù sau response timeout.

---

## 18. Database đề xuất

### `RECON_MAIL_TEMPLATE`

- ID
- CODE
- NAME
- DESCRIPTION
- MENU_CODE
- EVENT_CODE
- CURRENT_ACTIVE_VERSION_ID
- IS_ACTIVE
- CREATED_BY/AT
- UPDATED_BY/AT
- ROW_VERSION

### `RECON_MAIL_TPL_VERSION`

- ID
- TEMPLATE_ID
- VERSION_NO
- STATUS
- EVENT_SCHEMA_VERSION
- SUBJECT_TEMPLATE
- PREHEADER_TEMPLATE
- DESIGN_JSON
- RENDERED_HTML
- PLAIN_TEXT
- DESIGN_HASH
- RENDERER_VERSION
- VALIDATION_JSON
- CREATED_BY/AT
- ACTIVATED_BY/AT
- ARCHIVED_AT

### `RECON_MAIL_RULE_BINDING`

- RULE_ID
- TEMPLATE_ID
- CREATED_BY/AT

Notification Event, Notification Rule, Delivery Log, Dead Letter và Outbox sử dụng module Notification Center, không tạo cơ chế trùng lặp.

---

## 19. Service interface

### Mail Template Service

- `list_templates`
- `get_template`
- `create_template`
- `update_template_metadata`
- `clone_version`
- `save_draft`
- `validate_version`
- `preview_version`
- `send_test`
- `activate_version`
- `archive_template`
- `list_versions`
- `get_version`
- `bind_rule`
- `unbind_rule`

### Event Schema Service

- `list_events_by_menu`
- `get_schema`
- `get_sample_payloads`
- `validate_payload`
- `check_template_compatibility`

### Renderer Service

- `validate_design`
- `render_html`
- `render_plain_text`
- `sanitize_html`
- `collect_variables`
- `evaluate_condition`

Tất cả service trả cấu trúc `ServiceResult` theo convention hiện có.

---

## 20. Quyền

Menu mới:

`mail_template_studio`

Theo cơ chế task 19:

- Có menu thì mở được Studio và quản lý template.
- ADMIN có mọi menu.
- Các thao tác quản trị provider/credential chỉ ADMIN.
- Nếu tổ chức yêu cầu, Activate có thể giới hạn ADMIN dù role khác có menu. Nếu chưa có quyết định mới, tuân thủ đúng quy tắc phân quyền menu đã chốt, không tự tạo quyền granular ngoài scope.

Mọi service vẫn phải kiểm menu ở server.

Không chỉ ẩn UI.

---

## 21. Validation

Trước khi Activate, kiểm tra:

- Tên và mã template hợp lệ.
- Event đang Active.
- Event Schema tồn tại.
- Subject không rỗng.
- Placeholder hợp lệ.
- Component type được hỗ trợ.
- Component ID duy nhất.
- Display order hợp lệ.
- Condition hợp lệ.
- Table collection hợp lệ.
- Table có ít nhất một cột.
- Row limit 1–20.
- Button dùng internal link variable hợp lệ.
- Không có raw HTML/script.
- Style nằm trong whitelist.
- HTML render không vượt giới hạn kích thước.
- Plain text render thành công.
- Có ít nhất một sample preview thành công.
- Nếu có component conditional, phải thử đủ sample thành công/lỗi/rỗng hoặc cảnh báo rõ.

---

## 22. Bảo mật

- Không render raw user HTML.
- Escape mọi text và payload value.
- Sanitize output HTML bằng whitelist.
- Không cho `javascript:`, `data:` hoặc external URL tùy ý.
- Không cho CSS expression.
- Không cho iframe, object, embed, form, input hoặc script.
- Không cho template tự truy vấn database.
- Không cho gửi dữ liệu vượt quyền người nhận.
- Không đưa secret vào Design JSON.
- Không lưu provider credential trong database dạng rõ.
- Link tải file phải hết hạn hoặc kiểm quyền lại.
- Audit mọi create/update/clone/activate/archive/test-send/rule-binding.
- Log không chứa toàn bộ dữ liệu email nhạy cảm.
- Sample payload không chứa dữ liệu thật nhạy cảm.

---

## 23. Hiệu năng và giới hạn

- Tối đa 100 component/version.
- Tối đa 20 dòng trong Data Table.
- Design JSON tối đa khoảng 1 MB.
- Render HTML mục tiêu dưới 500ms với payload bình thường.
- HTML email sau render nên dưới 500 KB; cảnh báo từ 300 KB.
- Sample payload tối đa khoảng 500 KB.
- Autosave debounce 1–2 giây nếu triển khai autosave.
- Không render lại toàn bộ canvas khi chỉ đổi một property nếu framework cho phép cập nhật cục bộ.
- Không giữ nhiều bản HTML lớn trong client state nếu không cần.

---

## 24. UI states

Mỗi vùng phải có:

- Loading.
- Empty.
- Error.
- Normal.
- Dirty.
- Disabled.
- Read-only Active Version.
- Invalid version.

Ví dụ:

- Không có event: Empty với hướng dẫn đăng ký event.
- Không tải được schema: giữ design cũ và báo lỗi.
- Save conflict: thông báo `STALE_DATA`, không ghi đè.
- Active version: read-only; nút “Tạo version mới”.
- Component không tương thích: viền đỏ và lỗi cụ thể.

---

## 25. Undo/Redo

Nên hỗ trợ command history:

- Thêm component.
- Xóa.
- Nhân bản.
- Di chuyển.
- Sửa property.
- Đổi condition.

Giới hạn khoảng 30–50 thao tác.

Undo/Redo chỉ áp dụng trong phiên editor, không thay thế versioning.

Nếu chưa triển khai trong phase đầu, kiến trúc state không được cản trở việc thêm sau.

---

## 26. Responsive và accessibility

- Desktop: ba vùng.
- Tablet: Library + Canvas; Property Panel xuống dưới.
- Mobile: xếp lần lượt Library → Canvas → Property.
- Không có scroll toàn trang ngang.
- Bảng trong email và Data Table editor cuộn trong vùng riêng.
- Drag phải có thao tác bàn phím tương đương.
- Nút icon có `aria-label` và tooltip.
- Modal giữ focus và trả focus về nút mở khi đóng.
- Dynamic notification dùng `aria-live`.
- Không phân biệt trạng thái chỉ bằng màu.
- Tương phản đạt mức WCAG AA phù hợp.
- Hỗ trợ reduced motion.

---

## 27. Email client compatibility

HTML production phải dùng cấu trúc email tương thích rộng:

- Table-based layout cho phần render gửi thật.
- Inline style đã sanitize.
- Không phụ thuộc CSS Grid hoặc Flex trong email gửi thật.
- Canvas editor có thể dùng CSS hiện đại, nhưng Renderer phải output HTML riêng phù hợp Outlook.
- Test ít nhất:
  - Outlook Desktop.
  - Outlook Web.
  - Gmail Web.
  - Gmail Mobile.
  - Apple Mail nếu môi trường cho phép.

Phải có plain-text alternative.

Không lấy HTML canvas trực tiếp làm nội dung gửi.

---

## 28. Test bắt buộc

### Unit test

- Parse placeholder.
- Validate variable.
- Evaluate condition.
- Render text.
- Escape payload.
- Sanitize HTML.
- Clamp style values.
- Component ID unique.
- Display order.
- Table row limit.
- Internal link validation.
- Design hash.
- Plain text generation.

### Service test

- Tạo template.
- Save Draft.
- Clone Active.
- Activate transaction.
- Chỉ một Active version.
- Stale row version.
- Archive.
- Test send.
- Bind rule.
- Permission.
- Audit rollback.
- Event schema incompatibility.

### Security test

- Script injection trong text.
- HTML injection trong payload.
- `javascript:` URL.
- External URL không được phép.
- CSS injection.
- Event variable không tồn tại.
- Payload sai type.
- Collection chứa dữ liệu bất thường.
- Người không quyền mở link.
- User B truy cập version không được chia sẻ nếu chính sách hạn chế.

### E2E test

1. Admin mở Studio.
2. Chọn menu và event.
3. Tạo template.
4. Thêm component.
5. Kéo thả component.
6. Chỉnh thuộc tính.
7. Chèn variable.
8. Thêm KPI.
9. Thêm Data Table.
10. Đặt condition lỗi > 0.
11. Preview scenario Có lỗi.
12. Preview scenario Thành công.
13. Preview Mobile.
14. Validate.
15. Save Draft.
16. Test Send.
17. Activate.
18. Gắn Notification Rule.
19. Phát event mẫu.
20. Notification Worker render đúng version.
21. Delivery Log ghi đúng.
22. Retry không gửi trùng.

### Regression

- Notification Center vẫn hoạt động.
- Rule hiện tại không mất dữ liệu.
- User preference và quiet hours không đổi.
- Batch Run không bị rollback khi gửi email lỗi.
- Dynamic Reporting export không bị rollback khi gửi thông báo lỗi.
- Task 19 menu permission vẫn chặn đúng.
- Audit và worker queue hiện có không lỗi.

---

## 29. Tiêu chí hoàn tất

Task chỉ được đóng khi:

- UI ba vùng khớp prototype đã duyệt.
- Tất cả component phase đầu hoạt động.
- Kéo thả và bàn phím đều dùng được.
- Design JSON mở lại không mất cấu hình.
- Render HTML và plain text đúng.
- Event variables được validate.
- Condition hoạt động.
- Test send hoạt động với provider test hoặc mock chuẩn.
- Versioning hoạt động.
- Active version không bị sửa trực tiếp.
- Notification Rule sử dụng đúng Active Version.
- Retry không gửi trùng trong các trường hợp có confirmation rõ từ provider.
- Permission và audit đạt test.
- Không có lỗi JavaScript.
- Không tràn ngang ở 1440, 1366, 768, 375 và 320px.
- Typecheck, lint, unit test, integration test và E2E đều xanh.
- Kết quả test được cập nhật vào `progress.md`.

---

## 30. Trình tự triển khai bắt buộc

Trước khi code, hãy tạo Implementation Plan gồm:

1. Kiểm kê chức năng notification/email hiện có.
2. Danh sách bảng mới và bảng dùng lại.
3. Event Schema registry.
4. Design JSON schema.
5. Renderer architecture.
6. Sanitization policy.
7. Notification Rule integration.
8. Provider abstraction.
9. Versioning transaction.
10. Permission mapping.
11. Audit events.
12. Migration strategy.
13. Test strategy.
14. Rollback strategy.
15. Danh sách file sẽ tạo hoặc sửa.

Trong plan phải nêu rõ:

- Phần nào dùng lại từ Notification Center.
- Phần nào là mới.
- Cách tránh gửi trùng.
- Cách kiểm quyền dữ liệu người nhận.
- Cách render tương thích Outlook.
- Cách xử lý template Active khi Event Schema thay đổi.
- Cách xử lý save conflict.
- Cách rollback migration.

Sau khi lập Implementation Plan, dừng lại để tôi duyệt. Không code trước khi nhận lệnh tiếp tục.
