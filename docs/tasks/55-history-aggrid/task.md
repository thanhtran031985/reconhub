# Task 55 — history-aggrid (Lịch sử báo cáo sang AG Grid, chỉ dòng đổi mới cập nhật)

## Yêu cầu (user, 12:28 11/11/2026, đã duyệt "Làm AG Grid" 15:10)
Trang /report-runs refresh liên tục (spinner nhấp nháy mỗi tick 10s khi
có export đang chạy); muốn chỉ refresh trạng thái của dòng đang chạy
ngầm. Hỏi fix được bằng Dash table hay dùng AG Grid thay thế — đã trả
lời: Dash table không cập nhật từng dòng được, AG Grid làm được
(getRowId + rowData → grid tự diff, chỉ dòng đổi mới cập nhật).

## Phạm vi
- Bảng Lịch sử (dmc.Table, `render_runs_table`) → AG Grid qua wrapper
  `data_grid` (task 35), `getRowId` theo run id, rowModel clientSide.
- Giữ nguyên: các cột hiện có (Run, Báo cáo, Nhóm, Người chạy, Dòng,
  Tham số, Trạng thái, Bắt đầu, Kết thúc, Tổng, File, hành động), lọc
  (ngày/nhóm/tên/người chạy), phân trang server-side 20/50/100, tổng số
  run, nút "Làm mới", các nút Hủy/Thử lại/Xóa/Xuất lại + link "Chạy lại"
  + icon tải file, chỉ ADMIN mới thấy Xóa.
- Tick 10s chỉ đưa rowData mới vào grid; AG Grid tự cập nhật dòng đổi
  (trạng thái export, %) tại chỗ — không vẽ lại toàn bảng, không spinner,
  giữ vị trí cuộn. Bỏ dcc.Loading quanh bảng (chỉ giữ loading lúc tải
  trang đầu / đổi lọc nếu cần).
- Không sửa service, không migration.
