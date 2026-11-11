# Task 55 — decisions

- D1: AG Grid rowModel clientSide + getRowId theo run id (pattern task
  37: `getRowId="params.data.id.toString()"`). Phân trang vẫn server-side
  (20/50/100 qua list_report_runs) — grid chỉ nhận 1 trang dữ liệu;
  rowData mới mỗi tick, grid tự diff theo id.
- D2: Nút bấm trong cell dùng custom component JS
  (`window.dashAgGridComponentFunctions`) + `props.setData` ghi marker
  action vào row data → callback Dash `cellValueChanged` dispatch sang
  `_do_export_action` (task 52). Marker được xóa khi refresh trả rowData
  mới. Spike chứng minh đường này trước khi code thật.
- D3: Bỏ dcc.Loading quanh bảng: với AG Grid, tick chỉ cập nhật dòng
  đổi nên không cần spinner; loading lúc tải trang đầu/đổi lọc thể hiện
  bằng empty state (bảng trống) như cũ.
- D4: Giữ nguyên fingerprint task 53: tick chỉ đưa rowData mới vào grid
  khi fingerprint đổi (tránh ghi rowData giống nhau mỗi 10s — dù AG Grid
  diff rẻ, vẫn tránh nhịp cập nhật thừa). Nút "Làm mới" vẫn ép tải lại.
