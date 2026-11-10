# Decisions — 39-report-viewer

- Sửa Org ở service (`build_run_query` CUSTOM_SQL bind đủ tham số, vắng
  → NULL) thay vì ở viewer: mọi đường chạy (viewer, dry-run, export,
  `?run=`) đều qua cùng một chỗ; VIEW/TABLE giữ nguyên (vắng = không lọc).
- Không bind NULL ở `resolve_param_values`: dict resolved là snapshot
  lưu vào PARAMS_JSON của run — thêm key None vào đó sẽ đổi ý nghĩa
  snapshot (và các chỗ đọc PARAMS_JSON khác). Bind NULL chỉ lúc dựng
  query cho CUSTOM_SQL.
- AG Grid giữ phân trang server-side (dmc.Pagination + select 50/100/200
  như hiện tại); grid chỉ hiển thị đúng trang đã fetch, không bật
  pagination nội bộ của AG Grid (tránh phải tải toàn bộ 5509 dòng về
  client).
- `render_result_table` giữ lại (không xóa) cho tới khi viewer chuyển
  hẳn sang grid và test cũ được cập nhật; xóa ở bước cuối nếu không còn
  chỗ nào dùng.
- **Grid 0px (phát hiện khi kiểm chứng live):** `dcc.Loading` nhận `style`
  vào lớp phủ spinner chứ không vào khung ngoài — khung co lại 0px, grid
  không thấy dòng nào dù DOM có đủ row (hàng Tổng cũng không thấy). Sửa
  bằng `parent_style` cho khung flex:1 (đúng bài học layout /history).
  Thêm test hồi quy `test_result_loading_frame_stretches`.
- **Sort sai sau refetch (phát hiện khi kiểm chứng live):** rowData mang
  chuỗi đã định dạng nên sort mặc định của AG Grid so chuỗi ("9.000" >
  "55.000"); server trả đúng thứ tự DESC nhưng grid sort lại sai ngay.
  Comparator phải parse ngược chuỗi về số/ngày. Dạng inline
  `{"function": "function(a, b) {...}"}` đã thử ở dash-ag-grid 35.3.0 và
  KHÔNG chạy (rơi về sort chuỗi) — chỉ dạng tham chiếu tên trong
  `window.dashAgGridFunctions` mới chạy (đã kiểm chứng bằng prototype
  `~/workspace/dag-comparator-proto.py`: inline sai, dagfuncs đúng).
  Hàm JS ở `app/ui/assets/dashAgGridFunctions.js`
  (`reconViewerNumCompare`, `reconViewerDateCompare`).
- **Đọc thứ tự hiển thị trong Playwright:** AG Grid tái dùng DOM row, chỉ
  đổi translateY khi sort — đọc `.ag-row` theo DOM order sẽ sai sau khi
  sort; phải sắp theo `getBoundingClientRect().top`. Tương tự, DOM chỉ có
  ~24 dòng đang nhìn thấy (virtualize) nên không đếm đủ 50/55 dòng trong
  DOM — chờ theo count text + số dòng tối thiểu.
- Cảnh báo console mới gặp khi nhập ngày ("changing an uncontrolled input
  to be controlled") cùng họ với cảnh báo "should not be null" đã ghi ở
  task 38 (gốc: `render_param_control` truyền `value=None` khi param chưa
  có giá trị) — không do task 39 (valueFormat chỉ đổi hiển thị, không đổi
  luồng value), để riêng làm follow-up dọn console như đã hẹn.
