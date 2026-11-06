# Tiến độ – 25-reporting-execution

Trạng thái: ✅

## Hồi quy cuối (06/11/2026)
- Test đầy đủ: **884 pass, 5 skip, 0 fail** (850 cuối task 24 + 34 test task 25 mới).
- E2E: **12 pass**.
- Typecheck: **21 lỗi = baseline, 0 mới**. Lint: sạch (ruff auto-fix 15 lỗi import thừa/sắp xếp/biến thừa trong code + test task 25).
- `tasks-dashboard`: 29 task, 23 xong.
- T25-01..T25-11 đều ☑. Không thêm migration, không thêm package.

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | REPORT_RUN, bind/whitelist execution | ✅ | 6d206bb |
| 2 | Server-side count/page/filter/sort | ✅ | bb93eec |
| 3 | Cancel/timeout/metrics | ✅ | 0628200 |
| 4 | History, preset, favorite, owner scope | ✅ | |

## Bước 4 — History, preset, favorite, owner scope (06/11/2026)
- `list_report_runs` (filter report_id/status, phân trang SQL) + `get_report_run` — owner scope luồng G: lọc CREATED_BY, ADMIN bypass, run người khác → NOT_FOUND (T25-09/10).
- Preset (T25-08): `create_preset` (resolve qua ACTIVE version rồi lưu PARAMS_JSON đã resolve; IS_DEFAULT duy nhất theo user+template trong cùng transaction), `list_presets` (của mình, mặc định lên trước), `delete_preset` (chỉ của mình, kể cả ADMIN), `apply_preset` (merge override rồi resolve lại theo ACTIVE version hiện tại). Favorite tái dùng `set_report_favorite` (task 21).
- T25-09 (ghi loại E2E): kiểm tra ở mức service trong task 25; kiểm tra lại bằng Playwright ở task 27 khi trang /report-runs có thật (Q8).
- Test: `tests/unit/test_report_run_history.py` (7 test, T25-08/09/10). 34 test task 25 pass (execute 12 + page 8 + cancel 7 + history 7).

## Bước 3 — Cancel/timeout/metrics (06/11/2026)
- `cancel_report_run` (T25-07, Q4): QUEUED/RUNNING → CANCELLED + FINISHED_AT; DONE/FAILED/CANCELLED → VALIDATION_ERROR; run người khác → NOT_FOUND.
- Timeout (T25-06, Q3): count = min(TIMEOUT_SEC, 30s), data = min(TIMEOUT_SEC, DS CALL_TIMEOUT_S) — test chứng minh bằng call_timeout ghi trên mock conn (30_000 vs 300_000 ms khi DS = 600s).
- `report_run_metrics` (T25-11): {total_runs, by_status, avg_query_ms (chỉ run có QUERY_MS), total_rows} theo owner scope (người thường chỉ số của mình, ADMIN toàn bộ).
- Test: `tests/unit/test_report_run_cancel.py` (7 test, T25-06/07/11). 7 pass.

## Bước 2 — Server-side count/page/filter/sort (06/11/2026)
- `get_report_page` (report_center): chạy lại count + page từ PARAMS_JSON + VERSION_ID đã snapshot của run (không dùng version hiện tại); trả {run_id, total, rows, columns, page, page_size}. Sorts validate whitelist theo cột của version (field lạ → SQL_NOT_ALLOWED, direction lạ → VALIDATION_ERROR); stable sort = sorts người dùng + cột đầu tiên làm tiebreaker (Q6). page < 1 hoặc page_size ngoài 1..200 → VALIDATION_ERROR.
- Helper thuần `build_count_query` / `build_paged_query` (OFFSET/FETCH, Oracle 12c+).
- Test: `tests/unit/test_report_run_page.py` (8 test, T25-04/05 — mock Oracle trả lát cắt theo OFFSET trong SQL, 3 trang liên tiếp không trùng/mất row). 8 pass.

## Bước 1 — REPORT_RUN, bind/whitelist execution (06/11/2026)
- Service mới `app/services/report_run.py`: `create_report_run` (snapshot ACTIVE version + PARAMS_JSON đã resolve qua task 23; template_id bỏ trống → template đầu tiên có ACTIVE version), `execute_report_run` đồng bộ (QUEUED→RUNNING→DONE/FAILED, count + trang đầu, lưu ROW_COUNT/QUERY_MS, lỗi truy vấn → FAILED kèm ERROR_CODE/MESSAGE chứ không raise), `dry_run_version` (DRAFT-only, tối đa preview_max_rows, thành công → DRY_RUN_OK — đóng vòng T21-04).
- Hàm lõi `_execute_count_page`: CUSTOM_SQL dùng SQL snapshot + binds (key = param CODE); VIEW/TABLE dùng `build_report_query` (filter từ FILTER_COLUMN/FILTER_OPERATOR, selected = cột WEB_VISIBLE); count `SELECT COUNT(*) FROM (...)` timeout riêng min(TIMEOUT_SEC, 30s); data `ORDER BY + OFFSET/FETCH` timeout min(TIMEOUT_SEC, DS). Map lỗi Oracle theo mẫu `fetch.py` (ORA-01013 → SOURCE_TIMEOUT, mất kết nối → SOURCE_CONNECTION_LOST, còn lại → SOURCE_QUERY_FAILED).
- Test: `tests/unit/test_report_run_execute.py` (12 test, T25-01/02/03 + dry-run). 12 pass.
