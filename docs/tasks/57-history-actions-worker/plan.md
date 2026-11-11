# Task 57 — plan (user duyệt "Làm luôn cả 2 phần" 16:35 11/11/2026)

## Các bước
1. Spike (xong trước khi duyệt): app thử `~/workspace/spike-aggrid-dmc/`
   — nút DMC + icon render trong cell; bấm Hủy/Xóa thì Dash nhận
   `cellRendererData = {"value": "cancel"|"delete", "colId", "rowIndex",
   "rowId", "timestamp"}`. Icon hiện ô trống ở máy ảo do proxy chặn CDN
   icon (đã biết từ trước), trên máy user hiện bình thường.
2. 57a — UI (`app/ui/pages/report_runs.py`, `dashAgGridFunctions.js`):
   - `_runs_grid_column_defs`: bỏ 5 cột cancel/retry/delete/rerun/
     rerun_link; thêm 1 cột `{"field": "_export", "colId": "actions",
     "headerName": "Hành động", "width": 300, "cellRenderer":
     "reconRunsActionsCell"}` (đặt trước cột Tham số).
   - JS: `reconRunsActionsCell` render các nút DMC (subtle, xs) theo
     trạng thái export + nút Chạy lại (onClick chuyển trang bằng
     `window.location.href`); mỗi nút bấm gọi `props.setData(action)`.
     `reconRunsFileCell` (DONE) render nút DMC "Tải file" có icon file,
     onClick chuyển tới `/download/report-export/{id}`.
   - Xóa callback `handle_grid_cell_clicked`; thêm callback
     `handle_renderer_action` (Input cellRendererData, State rowData +
     refresh-store, Output alert allow_duplicate) → `_do_export_action`
     (tái dùng, guard theo trạng thái như cũ). Bỏ `_CELL_CLICK_ACTIONS`.
   - Giữ class CSS `.rh-grid-btn/.rh-grid-link` (task 56) cho fallback
     nếu DMC chưa kịp tải? Không — renderer mới chỉ dùng DMC Button,
     CSS cũ còn dùng cho link "Tải file" thì bỏ theo (xem D2).
3. 57b — worker (`app/services/export_retention.py`,
   `worker/export_runner.py`, `app/ui/pages/settings.py`):
   - Thêm key `EXPORT_MAX_CONCURRENT` (mặc định 10, kẹp 1..50) vào
     RECON_APP_SETTING; helper `get_export_max_concurrent(engine)` +
     mở rộng `get/set_export_retention_settings` (đổi tên? không — thêm
     hàm riêng `get/set_export_concurrency` cho gọn).
   - `ReportExportWorker`: giữ danh sách thread đang chạy; mỗi vòng
     poll: đọc lại setting, claim + chạy thread mới tới khi đủ N (mỗi
     thread: heartbeat + `execute_export`); `poll_once()` đổi thành
     claim 1 export rồi chạy trong thread (trả True/False); thêm
     `wait_for_idle(timeout)` cho test. `claim_next_queued_export`
     nhận `max_per_user=N` (giới hạn mỗi user = N).
   - Trang /settings: thêm NumberInput "Số export chạy song song tối đa"
     (mặc định 10), lưu cùng nút Lưu cài đặt; cần khởi động lại worker
     mới có hiệu lực (ghi chú trên trang).
4. Test unit: test mới `tests/unit/test_history_actions57.py` (cột
   actions duy nhất, renderer JS có DMC Button + icon + setData,
   cellRendererData dispatch qua `_do_export_action`, File cell là nút
   DMC); `tests/unit/test_export_concurrency57.py` (setting mặc định
   10 / giá trị lưu / giá trị sai → 10; worker chạy 3 export song song
   với max 2... xem plan chi tiết khi code); cập nhật test cũ dùng
   `poll_once` đồng bộ và `handle_grid_cell_clicked`.
5. Kiểm chứng: typecheck + ruff; Playwright check-57.py — 1 cột Hành
   động duy nhất (không còn cột trống), nút DMC có icon (trên máy ảo
   icon trống do CDN — assert theo cấu trúc nút Mantine, không assert
   svg), bấm Hủy/Thử lại/Xuất lại/Chạy lại chạy đúng, tick vẫn cập
   nhật dòng; worker: seed 3 export QUEUED, chạy worker với max=2 →
   2 export RUNNING cùng lúc, xong thì cái thứ 3 chạy. Full suite.
6. Commit + xuất patch `~/workspace/reconhub-task57.patch` (áp sau
   patch 56, không db-migrate), verify `git am` sạch trên worktree ở
   `b9b0f45`.
