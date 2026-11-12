# Task 75 — Tạo mã báo cáo riêng + đăng ký template chọn mã báo cáo

## Bối cảnh

- Bảng `RECON_REPORT` (Report Master) là cha, `RECON_REPORT_TEMPLATE`
  là con (`REPORT_ID`): 1 template chỉ thuộc 1 báo cáo, 1 báo cáo có
  nhiều template.
- Hiện tại app KHÔNG có chức năng tạo mã báo cáo riêng: muốn có 1 mã
  báo cáo thì phải đi qua wizard "Đăng ký Report Template", mà wizard
  này tạo luôn cả báo cáo + template đầu tiên trong 1 lần.
- Task 74 chỉ cho thêm template từ *bên trong* wizard của báo cáo có
  sẵn (mở /report-admin/10 rồi bấm "Tạo mới template"), chưa có luồng
  "đăng ký template → chọn mã báo cáo nào".

## Thiết kế (user duyệt 16:42 12/11/2026)

1. **Tạo mã báo cáo riêng**: nút "Tạo mã báo cáo" ở trang /reports →
   form (Mã *, Tên *, Nhóm, Chủ sở hữu, Mô tả) → chỉ gọi
   `create_report`, tạo xong báo cáo hiện ở hub với 0 template.
2. **Đăng ký template chọn mã báo cáo**: bước 1 wizard thêm ô
   "Báo cáo *" là list có search các mã báo cáo đã có. Chọn mã nào
   thì thông tin báo cáo khóa lại, chỉ nhập Mã/Tên template mới, lưu
   gọi thẳng `create_template`. Chọn "Báo cáo mới" trong list thì các
   ô báo cáo mở ra nhập như hiện tại (tạo báo cáo + template cùng lúc).

## Phạm vi

- Trang /reports (nút + modal tạo mã báo cáo) + wizard bước 1
  (report_admin.py: Select chọn báo cáo).
- Dùng service `create_report` / `create_template` / `list_reports`
  đã có sẵn, không đổi service. Không migration.
