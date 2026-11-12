# Task 74 — Decisions

- D1: list "Mã template" chỉ liệt kê template của báo cáo ĐANG MỞ
  (đơn vị gom nhiều template là báo cáo, theo `REPORT_ID`).
- D2: form tạo mới chỉ có Mã + Tên (+ Thứ tự, mặc định 10) — user
  chốt "không migration" (15:50 12/11/2026). Bảng template không có
  cột diễn giải và không có cờ active riêng: "đang dùng" được tính từ
  version ACTIVE; template mới luôn bắt đầu ở version 1 DRAFT, cấu
  hình SQL xong mới kích hoạt được (luồng hiện tại, không đổi).
- D3: làm SAU task 73 (dark mode) để khỏi sửa cùng file
  report_admin.py song song; nhánh `feat/74-report-add-template`
  tách từ HEAD sau task 73.
- D4 (làm rõ khi triển khai, không đổi thiết kế): plan bước 3 nói
  "state thêm cờ đang thêm template" — triển khai bằng nhánh trong
  `handle_save_step1` key theo hình dạng state (report_id có,
  template_id chưa có) thì chỉ gọi `create_template`, bỏ qua
  `create_report`; không cần thêm field cờ riêng vì hình dạng state
  đã phân biệt đủ. Modal Lưu tạo trực tiếp qua `create_template`
  (plan bước 2), rồi chuyển wizard sang template mới bằng
  `_state_from_version` + gán report_id.
- D5: lỗi trong modal hiện dạng toast `notify_error` như mọi lỗi khác
  trong app (`dmc.Notification action="show"` render qua portal,
  không nằm trong `.mantine-Modal-content`) — modal ở lại mở để sửa
  lại mã. Check live assert lỗi trên body text, không assert trong
  modal.
