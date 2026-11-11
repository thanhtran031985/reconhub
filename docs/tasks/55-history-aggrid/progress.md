# Task 55 — progress

## Bước 1 — Docs + nhánh + spike (xong, 11/11/2026)
- Nhánh `feat/55-history-aggrid` từ `8d42e9b` (task 54).
- Spike ở `~/workspace/spike-aggrid-button/`: nút trong cell render
  được, click về Dash qua prop `cellClicked` (colId + rowId);
  `props.setData` / `rowData` KHÔNG đồng bộ về nên không dùng.

## Bước 2 — Migrate sang AG Grid (xong)
- `render_runs_table` (dmc.Table) → `data_grid` + `_runs_row_data` +
  `_runs_grid_column_defs` (getRowId theo run id, rowModel clientSide,
  sort/filter trong grid tắt, phân trang vẫn server-side 20/50/100).
- Renderer JS trong `dashAgGridFunctions.js`: File / Trạng thái /
  nút Hủy-Thử lại-Xóa-Xuất lại / link Chạy lại.
- Nút trong cell → callback `handle_grid_cell_clicked` (cellClicked +
  rowData State) → tái dùng `_do_export_action` (task 52), guard theo
  trạng thái export; bỏ callback ALL + store action-clicks (task 52).
- Bỏ `dcc.Loading` quanh bảng. Tick 10s vẫn qua vân tay task 53:
  không đổi thì no_update, đổi thì đưa rowData mới.
- Lỗi nhánh: 2 callback cùng ghi `report-runs-alert` làm cả app không
  mount ("Duplicate callback outputs") → `allow_duplicate=True` +
  `prevent_initial_call="initial_duplicate"` ở handle_runs_refresh.

## Bước 3 — Kiểm chứng live (xong)
- Playwright check-55.py 12/12: export đổi % → chỉ dòng đó cập nhật
  tại chỗ ("Đang xuất 45%" → "Tải file"), dòng khác giữ nguyên DOM
  (còn gắn + innerHTML không đổi), vị trí cuộn giữ nguyên; bấm Hủy /
  Thử lại / Xuất lại trong cell đều chạy; không còn Loading; lọc vẫn
  chạy; không lỗi JS.
- Bài học: AG Grid chỉ vẽ lại cell khi giá trị của cột đổi — cột File /
  nút bấm ban đầu dùng field không có trong rowData nên cell không bao
  giờ đổi. Sửa: field `_export` (dict đổi theo trạng thái/%) + `colId`
  riêng để cellClicked phân biệt nút. Cột Báo cáo/Tham số dùng flex để
  tổng chiều rộng vừa khung 1440px (nút cuối vẫn thấy, khỏi cuộn ngang);
  AG Grid chỉ render cột trong khung nhìn nên test phải cuộn ngang
  trước khi bấm nút cuối.
- Unit: test mới test_history_aggrid55.py (12 test); cập nhật test
  53/43/44/52 theo rowData + columnDefs (bỏ render_runs_table).

## Bước 4 — Full suite + patch (xong)
- Full suite 1543 pass, 6 skipped (1532 + 11 test mới ròng).
- Patch ~/workspace/reconhub-task55.patch, áp sau patch 54, không cần
  db-migrate, chỉ khởi động lại app. Đang chờ user áp + kiểm chứng
  trên app thật.
