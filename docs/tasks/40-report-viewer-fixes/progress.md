# Progress — 40-report-viewer-fixes

| Bước | Nội dung | Trạng thái | Ngày | Commit |
| --- | --- | --- | --- | --- |
| 0 | Task + nhánh `feat/40-report-viewer-fixes` từ `8e2ee1d` + plan | Xong | 2026-11-10 |  |
| 1 | Test đỏ cho 5 mục (20 test mới, 19 đỏ + 1 xanh rỗng) | Xong | 2026-11-10 |  |
| 2 | Sửa viewer + service export + migration | Xong | 2026-11-10 |  |
| 3 | Kiểm chứng cuối + xuất patch | Xong | 2026-11-10 |  |

## Số liệu kiểm chứng (10/11/2026)

- Test mới 20 (`test_report_viewer_fixes40.py`): xanh sau sửa. Test cũ cập
  nhật theo arity mới của `handle_run_click` (4 giá trị, thêm loading) và
  `handle_export_click` (7 giá trị, thêm download + loading).
- Migration 0007 (`PROGRESS_PCT`/`PROGRESS_STEP`): manifest regenerate
  (60 events, COLUMN_ADDED 13, version `0007_export_progress`); 3 test
  schema cập nhật số đếm theo.
- Typecheck 0 lỗi, lint sạch (đã hoàn tác `ruff format` toàn repo vô tình
  chạy — chỉ giữ diff các file thuộc task).
- Full suite: **1434 pass / 6 skipped** (1414 + 20 test mới).
- Playwright `~/workspace/check-40.py`: **19/19 PASS** — seed 200.000 dòng:
  nút Xem disabled + `data-loading` trong lúc chạy, bấm 2 lần chỉ 1 run,
  font grid 13px, tab SQL admin hiện SQL + bind `p_org = None` (báo cáo có
  guard, không cảnh báo), báo cáo SQL không guard Org trống ra 0 dòng +
  cảnh báo thiếu IS NULL/NVL, operator không thấy tab SQL, export hiện %
  trung gian (0, 36, 71%) rồi 100% + tự tải `part-001.xlsx`, không còn link
  "Tải file Excel", console không lỗi mới.
