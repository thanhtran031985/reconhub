# Task 57 — history-actions-worker (gom nút + worker song song)

## Yêu cầu (user, 16:27 11/11/2026, kèm tài liệu DMC Dash AG Grid v3)
- "mình thấy button có lên được icon" (theo tài liệu DMC: cell renderer
  dùng `window.dash_mantine_components.Button` + `DashIconify`) — "xem
  vào chỉnh lại".
- "từ tải file đến chạy lại, thấy có 2 column trống không có header, bỏ
  2 column trống này? hãy group các button vào 1 group action cho dễ
  nhìn" — 2 cột trống là cột Hủy/Thử lại (trống ở hầu hết các dòng vì
  chỉ hiện khi export đang chạy/lỗi); gom tất cả nút vào 1 cột.
- "chỉnh lại có thể cho nhiều worker tải file chạy song song, cấu hình
  trong cài đặt hệ thống, để mặt định là 10" — hiện worker chỉ có 1
  luồng làm tuần tự từng export, giới hạn mỗi user 2 export cùng chạy.

## Phạm vi
- 57a (UI): 1 cột "Hành động" duy nhất, renderer là nút DMC thật có
  icon (Hủy lucide:x, Thử lại lucide:rotate-ccw, Xóa lucide:trash-2 đỏ,
  Xuất lại lucide:file-spreadsheet, Chạy lại lucide:play-circle); bấm
  gọi `setData(action)` → Dash đọc qua `cellRendererData`; cột File giữ
  riêng (hiện tiến trình "Đang xuất 45%") nhưng "Tải file" thành nút
  DMC có icon file. Bỏ 5 cột nút cũ + callback cellClicked.
- 57b (worker): cài đặt `EXPORT_MAX_CONCURRENT` (mặc định 10) trên
  trang Cài đặt hệ thống (cạnh phần dọn file task 52); worker chạy
  nhóm luồng song song tối đa N export, giới hạn mỗi user cũng N.
- Không đổi cơ chế tick/vân tay (task 53/55), không migration.
