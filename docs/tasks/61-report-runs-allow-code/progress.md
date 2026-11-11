# Task 61 — progress

## Bước 1 — test đỏ → fix → xanh ✅
- Viết `tests/unit/test_history_allow_code61.py` (2 test), chạy lần đầu:
  `test_grid_has_dangerously_allow_code` FAILED (đỏ đúng chỗ),
  `test_empty_overlay_text_kept` passed.
- Fix 1 dòng: `dangerously_allow_code=True` cho `report-runs-grid`
  (`app/ui/pages/report_runs.py`).
- Chạy lại: 29 passed (file mới + test_page_report_runs +
  test_history_refresh53 + test_history_cancel_filter58); ruff sạch
  (đã bỏ import `_dump` thừa); mypy sạch.

## Bước 2 — kiểm chứng live ✅
- Chạy lại `~/workspace/debug-runs-xss.py`: mở /report-runs không còn
  lỗi console `Blocked a string` (trước fix hiện 2 lần); mở /reports/<id>
  vẫn sạch. Chỉ còn lỗi ERR_TUNNEL_CONNECTION_FAILED có sẵn (CDN icon).
- Full suite + commit + patch: parent làm chung sau khi task 60 xong.
