# Quyết định — Task 43

- Dòng format dấu phẩy (`14,585`) theo yêu cầu người dùng — cố tình khác
  `format_number` của app (dấu chấm). Chỉ áp dụng ở cột Dòng trang này.
- Tổng thời gian = `FINISHED_AT − CREATED_AT` (cả chờ + chạy), 1 chữ số
  thập phân, dấu phẩy thập phân kiểu Việt Nam (`12,4 giây`); chưa xong → `—`.
  Không dùng `QUERY_MS` (chỉ thời gian chạy câu SQL).
- Cột Tham số hiển thị `mã=giá trị` (không tra nhãn từ version để tránh
  N query), ngày `YYYY-MM-DD` → `DD/MM/YYYY`, `None` → `—`, `title`
  chứa chuỗi đầy đủ.
- Nhóm: nhãn theo `CATEGORY_LABELS` của /report-admin; mã không có trong
  map (vd `FIN`) hiện nguyên mã.
- Chạy lại qua `?rerun_from=<run_id>`, điền tham số lúc dựng layout
  (Dash truyền query string vào `layout(**kwargs)` — mẫu có sẵn ở
  /report-admin `?new=1`); khớp theo mã tham số ở version ACTIVE hiện
  tại, mã lạ bỏ qua; không tự chạy.
- Không migration; không đổi logic tải file (chỉ đổi hiển thị nút).
