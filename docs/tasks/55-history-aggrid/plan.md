# Task 55 — plan

## Các bước
1. Docs + nhánh `feat/55-history-aggrid` từ `8d42e9b` (task 54).
2. Spike (bước 0, làm trước khi code thật): app Dash tối thiểu ở
   `~/workspace/spike-aggrid-button/` — grid 2 dòng, 1 cột có 2 nút
   (Hủy / Thử lại) render bằng custom component trong
   `dashAgGridFunctions.js` (`window.dashAgGridComponentFunctions`),
   bấm nút → `props.setData` ghi marker action vào row data → callback
   Dash `cellValueChanged` nhận được. Kiểm chứng bằng Playwright: bấm
   nút dòng 1 → status div đổi, dòng 2 không đổi. Nếu spike thất bại
   thì dừng và báo lại user (fallback: bỏ Loading quanh bảng dmc.Table
   hiện tại, chấp nhận vẽ lại toàn bảng nhưng không còn spinner).
3. Migrate `app/ui/pages/report_runs.py`:
   - Helper `_runs_row_data(runs, exports_by_run, can_delete)` → list
     dict cho rowData: mỗi run một dòng gồm các trường hiển thị + trường
     `_export` (dict export mới nhất: id/status/progress_pct) để cell
     renderer File quyết định nội dung.
   - `columnDefs` cho grid Lịch sử (đặt trong report_runs.py): cột text
     thường + cột Trạng thái (badge — render bằng valueFormatter hay
     custom renderer text màu) + cột File (custom renderer: trạng thái
     export + nút Hủy/Thử lại/Xóa/icon tải theo trạng thái) + cột hành
     động (link "Chạy lại" + nút "Xuất lại").
   - Layout: thay Paper/TableScrollContainer bằng `data_grid` (id
     `report-runs-grid`); `handle_runs_refresh` trả rowData thay vì
     children của container (output đổi thành `rowData` của grid +
     pagination/total/filter như cũ + fingerprint như cũ).
   - Nút bấm trong cell → `cellValueChanged` (marker action) → dispatch
     sang `_do_export_action` hiện có (task 52) rồi bump refresh-store
     để tải lại rowData. Marker phải được xóa sau khi xử lý (trả rowData
     mới không có marker) để bấm lại được.
   - Bỏ `dcc.Loading` quanh bảng (hết spinner mỗi tick); giữ loading
     lúc tải trang đầu bằng skeleton/empty state như cũ.
4. Test unit `tests/unit/test_history_aggrid55.py`: `_runs_row_data`
   (đủ trường, export mới nhất, can_delete), `_rows_fingerprint`
   dùng lại được cho rowData (đổi khi export đổi trạng thái/%),
   dispatch action từ cellValueChanged (cancel/retry/delete/rerun gọi
   đúng service + bump refresh).
5. Kiểm chứng: typecheck + ruff; Playwright check-55.py — mở Lịch sử,
   cuộn xuống, đợi qua 1 tick 10s với export đang chạy: assert dòng
   đang chạy cập nhật % tại chỗ, các dòng khác giữ nguyên DOM (tham
   chiếu phần tử còn gắn), vị trí cuộn không đổi, không có spinner;
   bấm Hủy trong cell → export bị hủy (audit), bấm Thử lại → QUEUED
   lại; phân trang/lọc vẫn chạy. Full suite.
6. Commit + xuất patch `~/workspace/reconhub-task55.patch` (áp sau
   patch 54, không db-migrate), verify `git am` sạch trên worktree ở
   `8d42e9b`.
