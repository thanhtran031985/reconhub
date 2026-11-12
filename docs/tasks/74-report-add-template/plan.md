# Task 74 — Plan: thêm template vào báo cáo có sẵn (tab 1 wizard)

## Thiết kế (user chốt)

1. **Mã template thành list có search**: `dmc.Select` searchable ở
   bước 1, options = template của báo cáo đang mở
   (`list_templates(report_id)`), value = template id, label
   `CODE — NAME`. Chọn mã khác → wizard load template đó
   (`handle_open_edit`), ô "Tên template" (disabled) hiện tên theo mã.
2. **Nút "Tạo mới template"**: đặt cạnh ô Mã template, mở `dmc.Modal`
   với 3 trường Mã * / Tên * / Thứ tự (mặc định 10). Lưu → gọi
   `create_template(report_id, ...)` → đóng modal, thêm template mới
   vào options của Select, chọn nó và chuyển wizard sang sửa template
   mới (version 1 DRAFT, bước 1).
3. **Đường lưu bước 1**: state thêm cờ "đang thêm template vào báo
   cáo có sẵn" (report_id có, template_id chưa có) → khi lưu thì bỏ
   qua `create_report`, gọi thẳng `create_template`. Trùng mã trong
   cùng báo cáo → service đã báo CONFLICT, hiện lỗi như các lỗi khác.

## Các bước

1. Test đỏ trước: service `create_template` dưới báo cáo có sẵn
   (trùng mã trong báo cáo → CONFLICT; cùng mã ở báo cáo khác → OK)
   — kiểm tra coverage có sẵn trước; test callback wizard (chọn mã
   đổi template; tạo mới qua modal chuyển sang template mới; ô tên
   disabled + hiện đúng tên).
2. Sửa wizard bước 1 (report_admin.py) theo thiết kế trên.
3. Check live (port 8125, DB riêng): trên 1 báo cáo có 1 template,
   tạo template thứ 2 qua modal → badge /reports lên 2; chuyển qua
   lại bằng Select → wizard hiện đúng template; trùng mã báo lỗi;
   JS sạch (quét CẢ console error VÀ pageerror).
4. Typecheck/ruff + full suite → commit → patch (áp sau patch 73,
   không db-migrate, chỉ khởi động lại app).

## Lưu ý

- Làm SAU khi task 73 (dark mode) xong để khỏi sửa cùng file
  report_admin.py song song. Nhánh `feat/74-report-add-template`
  tách từ HEAD sau task 73.
