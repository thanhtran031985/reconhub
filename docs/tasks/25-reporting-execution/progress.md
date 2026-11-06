# Tiến độ – 25-reporting-execution

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | REPORT_RUN, bind/whitelist execution | ✅ | 6d206bb |
| 2 | Server-side count/page/filter/sort | ✅ | |
| 3 | Cancel/timeout/metrics | ⬜ | |
| 4 | History, preset, favorite, owner scope | ⬜ | |

## Bước 2 — Server-side count/page/filter/sort (06/11/2026)
- `get_report_page` (report_center): chạy lại count + page từ PARAMS_JSON + VERSION_ID đã snapshot của run (không dùng version hiện tại); trả {run_id, total, rows, columns, page, page_size}. Sorts validate whitelist theo cột của version (field lạ → SQL_NOT_ALLOWED, direction lạ → VALIDATION_ERROR); stable sort = sorts người dùng + cột đầu tiên làm tiebreaker (Q6). page < 1 hoặc page_size ngoài 1..200 → VALIDATION_ERROR.
- Helper thuần `build_count_query` / `build_paged_query` (OFFSET/FETCH, Oracle 12c+).
- Test: `tests/unit/test_report_run_page.py` (8 test, T25-04/05 — mock Oracle trả lát cắt theo OFFSET trong SQL, 3 trang liên tiếp không trùng/mất row). 8 pass.

## Bước 1 — REPORT_RUN, bind/whitelist execution (06/11/2026)
- Service mới `app/services/report_run.py`: `create_report_run` (snapshot ACTIVE version + PARAMS_JSON đã resolve qua task 23; template_id bỏ trống → template đầu tiên có ACTIVE version), `execute_report_run` đồng bộ (QUEUED→RUNNING→DONE/FAILED, count + trang đầu, lưu ROW_COUNT/QUERY_MS, lỗi truy vấn → FAILED kèm ERROR_CODE/MESSAGE chứ không raise), `dry_run_version` (DRAFT-only, tối đa preview_max_rows, thành công → DRY_RUN_OK — đóng vòng T21-04).
- Hàm lõi `_execute_count_page`: CUSTOM_SQL dùng SQL snapshot + binds (key = param CODE); VIEW/TABLE dùng `build_report_query` (filter từ FILTER_COLUMN/FILTER_OPERATOR, selected = cột WEB_VISIBLE); count `SELECT COUNT(*) FROM (...)` timeout riêng min(TIMEOUT_SEC, 30s); data `ORDER BY + OFFSET/FETCH` timeout min(TIMEOUT_SEC, DS). Map lỗi Oracle theo mẫu `fetch.py` (ORA-01013 → SOURCE_TIMEOUT, mất kết nối → SOURCE_CONNECTION_LOST, còn lại → SOURCE_QUERY_FAILED).
- Test: `tests/unit/test_report_run_execute.py` (12 test, T25-01/02/03 + dry-run). 12 pass.
