# Task 76 — Lưu nháp / lưu bước 1 dùng lại mã đã có (resume thay vì báo lỗi)

## Bối cảnh

- `handle_save_draft_click` (report_admin.py:5279), bước 1 luồng tạo
  mới, gọi `create_report` rồi `create_template` ngay — "Lưu nháp"
  lưu thẳng xuống DB, không giữ nháp local. Bấm Lưu nháp là mã báo
  cáo bị "chiếm" ngay.
- Hậu quả: phần template lỗi hoặc bỏ dở wizard thì master nằm lại
  0 template (RM_REPORT, RM_REPORT_REV); vào lại wizard mới gõ cùng
  mã thì dính CONFLICT "Mã báo cáo ... đã tồn tại" (user gặp 17:10
  12/11/2026 với RM_REPORT_REV ở /report-admin/new).
- Nút "Tiếp theo" ở bước 1 (`handle_save_step1`) cũng tạo luôn như
  vậy ở luồng mới — cùng một lỗi khi vào lại wizard với mã đã có.

## Thiết kế (user duyệt 17:21 12/11/2026)

Lưu nháp / lưu bước 1 ở luồng tạo mới gặp mã đã tồn tại thì **dùng
lại (resume)** thay vì báo lỗi:

1. Mã báo cáo đã có → dùng lại report đó (bỏ qua `create_report`),
   tạo template mới dưới nó (trường hợp RM_REPORT_REV: báo cáo có
   sẵn 0 template, chỉ tạo template).
2. Mã template cũng đã có dưới báo cáo đó → mở lại đúng template đó
   để sửa tiếp (load version DRAFT của nó vào state wizard, như
   `handle_open_edit`); template không có DRAFT thì báo lỗi như
   `handle_open_edit` ("không có version DRAFT, hãy Clone").
3. Mã chưa có → tạo mới như hiện tại.

## Phạm vi

- `handle_save_step1` + `handle_save_draft_click` (bước 1, luồng tạo
  mới) ở report_admin.py, qua 1 helper chung resolve mã → ids.
- Dùng service đã có (`list_reports` / `get_report` / `list_templates`
  / `get_template` / `_draft_version_of`); chỉ thêm helper nhỏ trong
  service nếu thật sự cần. Không migration, không đổi model.
