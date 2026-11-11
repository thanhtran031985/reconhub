# Task 57 — decisions

- D1: Gom nút vào 1 cột "Hành động" bằng renderer DMC Button
  (`window.dash_mantine_components.Button` + `DashIconify` làm
  leftSection) thay vì nút HTML + class CSS (task 56). Lý do: user
  gửi tài liệu DMC và muốn nút có icon như bảng cũ (Chạy lại từng có
  icon play-circle, Tải file từng có icon file-spreadsheet).
- D2: Phân biệt nút trong 1 cột bằng `props.setData(action)` →
  `cellRendererData` (spike 11/11/2026: payload có value/colId/rowId/
  timestamp). `cellClicked` chỉ báo colId nên không phân biệt được nút
  trong cùng 1 cột; `setData` KHÔNG đồng bộ rowData/cellValueChanged
  (bài học task 55) nhưng kênh `cellRendererData` là riêng và hoạt
  động. Callback cellClicked cũ bị xóa; class CSS `.rh-grid-btn` /
  `.rh-grid-link` (task 56) không còn dùng cho nút nữa nhưng giữ lại
  trong custom.css (không hại, tránh patch xóa CSS gây lệch) — xem lại
  khi rà soát cuối.
- D3: Nút "Chạy lại" chuyển trang trực tiếp trong JS
  (`window.location.href = '/reports/...?rerun_from=...'`) thay vì
  qua Dash, vì đó là điều hướng thuần túy, không cần service. Tương
  tự "Tải file" chuyển tới `/download/report-export/{id}`.
- D4: Cột File giữ riêng (không gộp vào Hành động) vì nó hiện trạng
  thái/tiến trình export ("Đang xuất 45%", "Đã hủy"), không chỉ là
  nút bấm.
- D5: Song song = nhóm luồng trong 1 tiến trình worker (không phải
  chạy nhiều tiến trình `python -m worker`): `ReportExportWorker`
  giữ tối đa N thread chạy `execute_export`, N đọc từ setting
  `EXPORT_MAX_CONCURRENT` (mặc định 10, kẹp 1..50) mỗi vòng poll để
  đổi setting không cần sửa code; giới hạn mỗi user trong claim cũng
  = N (cùng 1 con số, tránh 2 cài đặt lệch nhau). Đổi setting cần
  khởi động lại worker (worker đọc N mỗi vòng poll nên thực ra đổi
  là có hiệu lực ở vòng sau — ghi chú rõ trên trang Cài đặt).
- D6: `poll_once()` đổi từ đồng bộ sang claim + chạy trong thread
  (trả True/False); test cũ dùng poll_once đồng bộ phải chờ bằng
  `wait_for_idle(timeout)` mới assert DONE.
