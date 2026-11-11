# Task 61 — plan (đã duyệt, làm luôn)

## Bước 1 — test đỏ rồi fix (1 dòng)
- Test mới `tests/unit/test_history_allow_code61.py` (2 test): grid
  `report-runs-grid` có `dangerously_allow_code=True`; chuỗi
  `overlayNoRowsTemplate` vẫn giữ nguyên.
- Fix: thêm `dangerously_allow_code=True` vào `data_grid(...)` của
  grid Lịch sử báo cáo trong `app/ui/pages/report_runs.py`.

## Bước 2 — kiểm chứng
- Test đích danh (file mới + test_page_report_runs + test_history_refresh53
  + test_history_cancel_filter58) xanh; ruff + mypy sạch.
- Check live lại bằng script repro `~/workspace/debug-runs-xss.py` (mở
  /report-runs rồi /reports/<id>, quét cả console error lẫn pageerror):
  không còn lỗi `Blocked a string`, viewer vẫn sạch.
- Full suite (parent chạy chung với task 60). Patch riêng, áp sau patch
  59, không db-migrate, chỉ khởi động lại app.
