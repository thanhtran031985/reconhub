# Task 76 — Plan: lưu nháp dùng lại mã đã có

## Thiết kế (user duyệt)

Helper chung (vd `_resolve_new_step1_codes(ctx, report_code, tpl_code)`),
dùng ở cả `handle_save_step1` và `handle_save_draft_click` (bước 1,
luồng tạo mới — khi state chưa có `report_id`/`template_id`):

1. Tìm báo cáo theo mã (qua `list_reports` lọc code, hoặc helper
   lookup theo code nếu service đã có — kiểm tra trước khi thêm mới).
   - Chưa có → `create_report` như cũ, lấy `report_id` mới.
   - Đã có → dùng lại `report_id` đó, bỏ qua `create_report`.
2. Tìm template theo (report_id, mã template) (qua `list_templates`
   lọc code).
   - Chưa có → `create_template(report_id, ...)` như cũ.
   - Đã có → resume: lấy DRAFT version của template đó
     (`_draft_version_of`, như `handle_open_edit`); có DRAFT thì state
     nhận (report_id, template_id, version_id) và tiếp tục luồng sửa;
     không có DRAFT thì báo lỗi như `handle_open_edit`.
3. Luồng sửa (editing) không đổi. Luồng "Báo cáo *" Select của task
   75 không đổi (đã chọn mã có sẵn thì đi nhánh D4, không qua helper
   này — helper chỉ chạy khi mã được gõ tay ở chế độ "Báo cáo mới").

## Các bước

1. Test đỏ trước: helper resolve (mã báo cáo mới → tạo; mã báo cáo
   có sẵn → dùng lại; mã template có sẵn → resume DRAFT; template
   không DRAFT → lỗi); test callback lưu nháp + lưu bước 1 (gõ lại mã
   đã lưu nháp → không CONFLICT, state nhận đúng ids; mã mới hoàn
   toàn → tạo như cũ).
2. Sửa report_admin.py (helper + 2 handler bước 1).
3. Check live (port 8127, DB riêng): bấm Lưu nháp với mã mới →
   tạo xong; mở wizard mới gõ lại đúng mã báo cáo + mã template →
   Lưu nháp tiếp không lỗi, wizard ở đúng template đã lưu; bỏ dở
   (template chưa có) rồi gõ lại mã báo cáo → tạo template dưới báo
   cáo có sẵn, không lỗi; template không DRAFT → báo lỗi rõ; JS sạch
   (quét CẢ console error VÀ pageerror).
4. Typecheck/ruff + full suite → commit → patch (áp sau patch 75,
   không db-migrate, chỉ khởi động lại app).

## Lưu ý

- Nhánh `feat/76-draft-reuse-code` tách từ HEAD task 75 (`bcc5b5c`).
- Task 77 (tab template ở viewer /reports/15) làm song song, file
  khác nhau (report_viewer.py) nên không đụng.
