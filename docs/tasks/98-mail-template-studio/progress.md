# Tiến độ — 98-mail-template-studio

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Implementation Plan chi tiết & Thiết kế kiến trúc | ✅ | 2026-11-18 |  |
| 2 | Schema DB (3 bảng), Migration Alembic & Data Model Explorer | ✅ | 2026-11-18 |  |
| 3 | Event Schema Registry & Sample Payloads | ✅ | 2026-11-18 |  |
| 4 | Design JSON Schema, Validator & Table-Based HTML Renderer | ✅ | 2026-11-18 |  |
| 5 | Mail Template Service (CRUD, Clone, Versioning, Activate, Test Send) | ✅ | 2026-11-18 |  |
| 6 | Giao diện Mail Template Studio 3 vùng (`/mail-template-studio`) | ✅ | 2026-11-18 |  |
| 7 | Tương thích ngược với `/templates` & Kiểm thử E2E, Hồi quy | ✅ | 2026-11-18 |  |

## Nhật ký
- 2026-11-18: Khởi tạo task 98, sao chép prompt gốc và prototype HTML vào `designs/components/Screen-MailTemplateStudio/preview.html`. Lập Implementation Plan chi tiết 15 mục.
- 2026-11-18: Tạo 3 bảng `RECON_MAIL_TEMPLATE`, `RECON_MAIL_TPL_VERSION`, `RECON_MAIL_RULE_BINDING` và migration `0015_mail_template_studio.py`. Regenerate Data Model Explorer (`schema-manifest.json` và `schema-history.json`), kiểm tra zero drift.
- 2026-11-18: Triển khai `mail_event_registry.py` định nghĩa danh mục sự kiện và mock datasets.
- 2026-11-18: Triển khai `mail_renderer.py` biên dịch Table-based HTML lồng nhau cho Outlook/Gmail, sinh Plain Text và validator.
- 2026-11-18: Triển khai `mail_template_studio.py` service với giao dịch kích hoạt Atomic, kiểm tra lỗi và auto-clone draft khi sửa bản Active.
- 2026-11-18: Xây dựng page `/mail-template-studio` với 3 panel chuẩn Fluent Compact.
- 2026-11-18: Tích hợp ngược tính năng gửi mail danh sách template trên `/templates` với Mail Template Studio. Hoàn thành 67 bài test liên quan.
- 2026-11-18: Triển khai Dynamic Token Introspection theo Page/Table (`mail_token_inspector.py`), bổ sung sự kiện `USER_CREATED` và `USER_LIST_EXPORT`.
- 2026-11-18: Tích hợp menu Xuất danh sách Người dùng (Excel/Word/PDF/Email) trên `/users` và tự động gửi email chào mừng khi tạo mới User.
- 2026-11-18: Khắc phục lỗi kích hoạt mẫu Tạo mới user; hỗ trợ kiểm tra token theo Page và không phân biệt hoa thường; tách danh mục token thành 2 Tab cuộn độc lập (Trường bảng / Hệ thống) không bị ẩn; nâng cấp Button component hỗ trợ bo tròn/bo góc/vuông và độ rộng với viền tự động khi nền trắng. 27/27 bài test unit pass hoàn toàn.
- 2026-11-19: Tối ưu UI Panel Trái thư viện component thành lưới 3 component/hàng; khắc phục triệt để vùng hiển thị token không bị che khuất; tách biệt màu sắc của nút liên kết (Button) với khung bao ngoài canvas; loại bỏ toàn bộ cấu hình hardcode ở Alert, KPI và Table; bổ sung cấu hình Base URL hệ thống (APP_BASE_URL) trong Cài đặt SMTP để sinh URL an toàn tự động lúc gửi email (`http://127.0.0.1:8050/login`). Toàn bộ 30 bài test unit liên quan pass hoàn toàn.
- 2026-11-19: Nâng cấp Dynamic Columns cho Panel Thuộc tính của khối Bảng dữ liệu (Table) theo đúng Page đang chọn; bổ sung Mock Dataset đa bản ghi phong phú trong Live Preview; mặc định điều kiện hiển thị Table là Luôn hiển thị (always). Kiểm thử và typecheck 100% xanh.
- 2026-11-19: Bổ sung cấu hình phạm vi dữ liệu Table (`table_scope`: Tất cả danh sách user vs Chỉ đích danh user đó) trên Panel Thuộc tính và Canvas Live Preview; hỗ trợ tổng hợp tự động 1 dòng đích danh cho Welcome Email; mở rộng điều kiện hiển thị `target_only` và `all_users`. 31/31 bài test unit liên quan pass hoàn toàn.
- 2026-11-19: Tách tiến trình gửi email chào mừng người dùng mới (`_send_welcome_user_email_background`) chạy ngầm trong luồng daemon (`async_email=True`). Khi Admin bấm "Lưu" trên `/users`, modal đóng ngay tức thì và bảng người dùng làm mới lập tức mà không phải chờ SMTP gửi email. Kiểm thử đơn vị pass 100%.
