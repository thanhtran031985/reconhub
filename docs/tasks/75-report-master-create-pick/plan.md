# Task 75 — Plan: tạo mã báo cáo riêng + đăng ký template chọn mã báo cáo

## Thiết kế (user duyệt)

1. **Modal "Tạo mã báo cáo" trên /reports** (mẫu modal task 74):
   nút "Tạo mã báo cáo" cạnh nút "+ Đăng ký báo cáo" (reports.py:313)
   → `dmc.Modal` với Mã * / Tên * / Nhóm / Chủ sở hữu / Mô tả.
   Lưu → `create_report` (service đã có) → đóng modal, toast thành
   công, hub làm mới (báo cáo mới hiện badge 0 template). Trùng mã
   báo cáo → service báo CONFLICT, modal ở lại mở + lỗi (mẫu task 74).
   Nhóm: dùng cùng nguồn options như Select nhóm ở wizard bước 1 nếu
   có sẵn, không thì TextInput/Select với các nhóm đã dùng.
2. **Wizard bước 1: ô "Báo cáo *"** (chỉ luồng tạo mới, không sửa):
   `dmc.Select` searchable ở đầu bước 1, options = `list_reports`
   (value = report id, label `CODE — NAME`) + 1 option "Báo cáo mới"
   (mặc định). Chọn báo cáo có sẵn → state nhận `report_id` (chưa có
   `template_id`), bước 1 vẽ lại với các ô báo cáo hiện đúng giá trị
   của báo cáo đó và disabled; chỉ ô template nhập được; lưu đi theo
   nhánh D4 của task 74 (có `report_id`, chưa có `template_id` → bỏ
   qua `create_report`, gọi thẳng `create_template`). Chọn lại
   "Báo cáo mới" → state `report_id` None, các ô báo cáo mở ra nhập
   như hiện tại. Callback chuyển báo cáo có guard kiểu switch task 74
   (chỉ chạy khi giá trị đổi, giá trị rỗng/không đổi → PreventUpdate).
   Thông tin báo cáo đã chọn lấy qua `get_report` (hoặc từ dữ liệu
   `list_reports` nếu đủ trường).

## Các bước

1. Test đỏ trước: service đã có (create_report trùng mã → CONFLICT
   đã có test? kiểm tra coverage trước); test callback/modal wizard
   (tạo mã báo cáo qua modal; chọn báo cáo khóa ô; chọn "Báo cáo mới"
   mở lại ô; lưu khi chọn báo cáo chỉ tạo template, không tạo thêm
   báo cáo; render bước 1 luồng mới có Select báo cáo).
2. Sửa /reports (nút + modal + callback) và wizard bước 1
   (report_admin.py: Select + callback chuyển báo cáo).
3. Check live (port 8126, DB riêng): tạo mã báo cáo qua modal → hub
   badge 0; mở wizard mới → chọn mã đó ở Select → ô báo cáo khóa,
   lưu template → badge lên 1; trùng mã báo cáo → lỗi, modal ở lại
   mở; trùng mã template trong cùng báo cáo → lỗi; chọn "Báo cáo mới"
   → tạo báo cáo + template như cũ; JS sạch (quét CẢ console error VÀ
   pageerror).
4. Typecheck/ruff + full suite → commit → patch (áp sau patch 74,
   không db-migrate, chỉ khởi động lại app).

## Lưu ý

- Nhánh `feat/75-report-master-create-pick` tách từ HEAD task 74
  (`6c97076`). Patch 75 áp sau patch 74.
- Không động vào luồng sửa (editing) của task 74; Select báo cáo chỉ
  ở luồng tạo mới.
