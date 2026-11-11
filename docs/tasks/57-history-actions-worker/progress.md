# Task 57 — progress

## Bước 1 — Docs + nhánh + spike (xong, 11/11/2026)
- Nhánh `feat/57-history-actions-worker` từ `b9b0f45` (task 56).
- Spike `~/workspace/spike-aggrid-dmc/`: nút DMC + icon render trong
  cell; bấm Hủy/Xóa → Dash nhận cellRendererData
  `{"value": "cancel"|"delete", "colId": "actions", "rowIndex",
  "rowId", "timestamp"}`. Icon trống ở máy ảo do proxy chặn CDN icon
  (đã biết), trên máy user hiện bình thường.
- User duyệt "Làm luôn cả 2 phần" 16:35.
- Skill dash_ag_grid đã sửa: setData KHÔNG đồng bộ rowData nhưng CÓ
  về Dash qua cellRendererData (kênh riêng); DMC Button + DashIconify
  dùng được làm cell renderer.

## Bước 2 — 57a: 1 cột Hành động, nút DMC có icon (xong)
- `dashAgGridFunctions.js`: `reconRunsActionsCell` mới (nút DMC subtle
  xs + icon: Hủy lucide:x, Thử lại lucide:rotate-ccw, Xóa lucide:trash-2
  đỏ, Xuất lại lucide:file-spreadsheet, Chạy lại lucide:play-circle);
  mỗi nút bấm gọi `props.setData(action)`; "Chạy lại" chuyển trang bằng
  `window.location.href`; `reconRunsFileCell` (DONE) thành nút DMC "Tải
  file" có icon file, mở tab mới bằng `window.open`. Xóa
  `reconRunsActionCell` + `reconRunsRerunLink`.
- `report_runs.py`: 5 cột nút cũ → 1 cột `actions` (width 340 khi ADMIN,
  280 khi không; `cellRendererParams: {canDelete}`); bỏ callback
  `handle_grid_cell_clicked` + `_CELL_CLICK_ACTIONS`, thêm
  `handle_renderer_action` (Input cellRendererData) → `_do_export_action`
  (guard trạng thái như cũ). Xóa class CSS `.rh-grid-btn/.rh-grid-link`
  (không còn dùng).
- Test: test_history_aggrid55 (TestColumnDefs/TestJsRenderers/TestUi56/
  TestRendererAction) + các file tham chiếu rerun_link/cancel/retry
  (page_report_runs, history43, fit44, export_background52).

## Bước 3 — 57b: worker song song + setting (xong)
- `report_export.py`: `MAX_RUNNING_PER_USER` 2 → 10 (mặc định mới).
- `export_retention.py`: key `EXPORT_MAX_CONCURRENT` (mặc định 10, kẹp
  1..50); `get_export_max_concurrent(engine)` (worker dùng, không cần
  ctx) + service `get/set_export_concurrency` (ADMIN, menu
  system_settings).
- `worker/export_runner.py`: `max_per_user=None` = đọc setting mỗi vòng
  poll; `poll_once()` claim 1 export rồi chạy trong thread riêng (trả
  False khi đủ N luồng hoặc hết hàng); `run()` claim thêm tới khi đủ N;
  thêm `wait_for_idle(timeout)` cho test. Giới hạn mỗi user trong claim
  = N (cùng 1 con số).
- `settings.py`: thêm Paper "Export chạy song song" + NumberInput
  `settings-concurrent-input`; 1 nút Lưu chung cho cả 2 phần; lưu xong
  có hiệu lực ở vòng poll tiếp theo, không cần khởi động lại worker.
- Sửa fixture `run_env` (test_report_run_execute): thêm
  `app.services.export_retention` vào danh sách patch get_recon_engine
  — trước đó service retention đọc engine thật (lỗi rò rỉ test, đã từng
  làm bẩn DB thật ở task 52); giờ test dùng đúng DB test.
- Test mới `tests/unit/test_export_concurrency57.py` (9 test): setting
  mặc định 10 / lưu / sai → 10 / vượt khoảng → 10 / ADMIN-only;
  worker max=2 chạy 2 export cùng lúc (fake execute sleep 0,4s,
  max_seen=2), setting=1 giới hạn pool, không setting → 10.
- Cập nhật 3 test cũ dùng poll_once đồng bộ (queue, queue54 ×2):
  chờ `wait_for_idle` trong khối patch mock.

## Bước 4 — Kiểm chứng live (xong, 11/11/2026)
- check-57.py **13/13**: 1 cột Hành động duy nhất (không cột trống);
  nút DMC trong cell (Hủy/Xuất lại/Chạy lại, không Xóa ở dòng QUEUED);
  worker max=2 chạy 2 export cùng lúc (max RUNNING = 2, quan sát được
  nhờ nhân dữ liệu lên ~7000 dòng), cả 3 export DONE; bấm Xóa → export
  bị xóa; Xuất lại → run mới; Hủy → CANCELLED; Chạy lại → viewer
  ?rerun_from=1; Tải file là nút DMC; tick vẫn cập nhật dòng; /settings
  hiện giá trị 2, lưu qua UI thành 3; không lỗi JS.
- Bài học check: worker phải dừng sau phần 57b1 (không thì nhận export
  mới làm lệch check Hủy); notify_success render qua portal nên check
  phải đọc body.innerText, không đọc #settings-alert.

## Bước 5 — Full suite + commit + patch (xong, 11/11/2026)
- `uv run poe typecheck`: no issues (143 file).
- `ruff check` (file đổi): All checks passed.
- Full suite: **1557 passed, 6 skipped** (tăng 9 test mới task 57).
- Patch `~/workspace/reconhub-task57.patch`, áp sau patch 56, không
  cần db-migrate, khởi động lại app + worker.
- Nhắc user: icon trên nút chỉ hiện trên máy bạn (máy ảo chặn CDN icon
  nên nút hiện chữ, không icon — đã kiểm chứng cấu trúc nút Mantine).
