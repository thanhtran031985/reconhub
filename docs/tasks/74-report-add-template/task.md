# Task 74 — Thêm template vào báo cáo có sẵn (tab 1 wizard)

## Bối cảnh

- 1 báo cáo (Report Master) có thể chứa nhiều template (gắn theo
  `REPORT_ID`), nhưng UI chưa có luồng nào thêm template vào báo cáo
  có sẵn (chẩn đoán 12/11/2026 từ ảnh /reports + /report-admin).
- Mỗi lần wizard "Báo cáo mới" tạo 1 báo cáo mới + template đầu tiên;
  mã template chỉ duy nhất trong 1 báo cáo nên cùng mã RM_REPORT ở
  2 báo cáo khác nhau không gộp lại.

## Thiết kế (user chốt 15:48–15:50 12/11/2026)

Trong wizard đăng ký template, tab 1 "Thông tin chung":

1. Nút "Tạo mới template" cạnh ô Mã template → mở form tạo template
   mới cho đúng báo cáo đang mở (chỉ Mã + Tên + Thứ tự, mặc định 10),
   lưu xong wizard tự chuyển sang sửa template vừa tạo (DRAFT v1).
2. Ô "Mã template *" đổi từ textbox sang list có search, liệt kê các
   template của báo cáo này → chọn mã nào thì wizard chuyển sang sửa
   template đó; ô "Tên template *" chuyển disable và tự hiện tên theo
   mã đã chọn.

## Phạm vi

- Chỉ wizard tab 1 + modal tạo mới (report_admin.py); service
  `create_template` / `list_templates` đã có sẵn, không đổi.
- Không migration, không thêm cột, không đổi model.
