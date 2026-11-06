# Implementation Plan — 25-reporting-execution (Report execution, pagination và history)

## Bối cảnh
- Phụ thuộc task 24 — đã xong, nhánh `feat/24-reporting-columns` ở `2402c07`, đã push lên remote; task 24 không có migration.
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§5 Thực thi, §6 Export, §Bước 5 Dry-run, §Bước 6 Activate), 12a, 12b (luồng C Viewer, luồng G Permission).
- Code hiện có tái dùng được:
  - Schema task 21: RECON_REPORT_RUN (REPORT_ID, TEMPLATE_ID, VERSION_ID, PARAMS_JSON, STATUS check QUEUED/RUNNING/DONE/FAILED/CANCELLED, ROW_COUNT, QUERY_MS, ERROR_CODE/MESSAGE, CREATED_BY/AT, FINISHED_AT), RECON_RPT_PRESET (USER_ID, REPORT_ID, TEMPLATE_ID, NAME, PARAMS_JSON, IS_DEFAULT).
  - `app/services/report.py::set_report_favorite` (task 21, đã có).
  - `app/services/report_template.py::get_version` — chi tiết version kèm params (có LOV, FILTER_COLUMN/FILTER_OPERATOR) + columns; `_version_detail` có source_type, sql_text, source_owner, source_object, data_source_id, timeout_sec, preview_max_rows.
  - `app/services/report_param.py::resolve_param_values` (task 23) — điền default + validate + coerce theo DATA_TYPE; trả dict {code: value}.
  - `app/services/report_source.py::build_report_query` (task 22) — filters [{column, operator, code, value}], sorts [{column, direction}]; `open_checked_connection(data_source_id, timeout_sec)` (read-only + call_timeout = min(requested, DS CALL_TIMEOUT_S)); `describe_report_sql`.
  - `app/services/report_column.py::get_result_layout` (task 24) — layout web/excel dùng chung.
  - `app/engine/fetch.py` — mẫu map lỗi Oracle: ORA-01013/TIMEOUT → SOURCE_TIMEOUT; ORA-03113/03114/03135/DPI-1010/DPI-1080 → SOURCE_CONNECTION_LOST; còn lại → SOURCE_QUERY_FAILED. Error codes SOURCE_TIMEOUT, RUN_CANCELLED đã có trong `app/schemas/errors.py`.
- Lưu ý: task này là service + logic thực thi (test pytest). UI Dash thật (Report Center, Viewer, history) thuộc task 27. Không có worker nền trong task này — export nền thuộc task 26.
- Không thêm migration (schema đủ cho các bước 1–4 theo đề xuất Q4), không thêm package mới.

## Nhánh và tài liệu
- Nhánh mới `feat/25-reporting-execution` từ `2402c07` (đầu nhánh task 24 đã push).
- Chép `docs/tasks/25-reporting-execution/` từ nhánh docs vào nhánh mới (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 25.

## Các bước (theo progress.md)

### Bước 1 — REPORT_RUN, bind/whitelist execution
- Service mới `app/services/report_run.py` (`@service`; đọc `@requires_menu("report_center")`, ghi/chạy `@requires_menu("report_center")`, dry-run/admin `@requires_menu("report_admin")`).
- `create_report_run(ctx, report_id, template_id=None, values=None)` (T25-01): template_id bỏ trống → template đầu tiên (theo display order) có ACTIVE version; không có version ACTIVE → VALIDATION_ERROR. Resolve params qua `resolve_param_values` (task 23) trên ACTIVE version; tạo RECON_REPORT_RUN QUEUED với snapshot VERSION_ID + PARAMS_JSON (giá trị đã resolve), trả run dict. Run giữ VERSION_ID cũ mãi (task 21 T21-05 — activate sau này không đụng run cũ).
- `execute_report_run(ctx, run_id, page=1, page_size=50)` — đồng bộ trong request (Q2): QUEUED/RUNNING → chạy count + trang dữ liệu đầu tiên → DONE + ROW_COUNT + QUERY_MS; lỗi → FAILED + ERROR_CODE/ERROR_MESSAGE + FINISHED_AT. Chỉ chạy run QUEUED (chạy lại run DONE/FAILED → VALIDATION_ERROR, dùng create mới).
- `_run_query(version_detail, resolved, page, page_size, sorts)` (hàm lõi): CUSTOM_SQL dùng SQL snapshot + binds là resolved values (key = param CODE); VIEW/TABLE dùng `build_report_query` với filters từ param [{column: FILTER_COLUMN, operator: FILTER_OPERATOR, code, value}] và selected = cột WEB_VISIBLE. Count: `SELECT COUNT(*) FROM (<sql>)` với cùng binds. Data: bọc `SELECT * FROM (<sql>) ORDER BY ... OFFSET ... FETCH ...` (Oracle 12c+).
- `dry_run_version(ctx, version_id, values)` (report_admin, DRAFT-only): thực thi tối đa preview_max_rows của version; thành công → DRAFT→DRY_RUN_OK trong cùng transaction (đóng vòng T21-04 — hiện activate yêu cầu DRY_RUN_OK nhưng chưa có đường nào tới đó); trả {columns, rows, row_count, query_ms, warnings}. Lỗi → version giữ DRAFT + báo lỗi (không cho activate khi lỗi — spec §Bước 5).
- Test trước: `tests/unit/test_report_run_execute.py` — T25-01 (snapshot params/version đúng ACTIVE version), T25-02 (CUSTOM_SQL bind execute, mock Oracle), T25-03 (VIEW/TABLE builder whitelist execute), dry-run đổi DRAFT→DRY_RUN_OK và giữ DRAFT khi lỗi. Mock Oracle theo mẫu task 22/23: patch `app.services.report_source.open_source_connection`, cursor.execute/fetchone/fetchmany + description.
- Kiểm tra: `uv run poe test` (phạm vi unit), `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Server-side count/page/filter/sort
- `get_report_page(ctx, run_id, page, page_size, sorts=None)` (T25-04/05): đọc run (owner scope) → chạy lại count + page từ PARAMS_JSON + VERSION_ID đã snapshot (không dùng version hiện tại); trả {run_id, rows, total, page, page_size, columns (layout web)}. Sorts [{field, direction}] validate whitelist theo cột của version (field lạ → SQL_NOT_ALLOWED); stable sort bắt buộc (Q6): ORDER BY theo sorts người dùng + cột đầu tiên của kết quả làm tiebreaker. page < 1 → VALIDATION_ERROR; page_size vượt max (Q5) → chặn.
- Helper thuần `build_paged_query(sql, page, page_size, order_by)` và `build_count_query(sql)` trong report_run.py (dễ test không cần Oracle).
- Filter: filter của trang = param đã resolve trong run (VIEW/TABLE qua build_report_query; CUSTOM_SQL đã bind trong SQL snapshot) — không có filter ad-hoc ngoài param ở task này.
- Test trước: `tests/unit/test_report_run_page.py` — T25-04 (2 trang liên tiếp không trùng/mất row — mock trả rows theo OFFSET), T25-05 (sort whitelist: field hợp lệ ok, field lạ bị chặn; filter param qua builder đúng cột/operator), count/page SQL chứa OFFSET/FETCH + ORDER BY.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Cancel/timeout/metrics
- `cancel_report_run(ctx, run_id)` (T25-07): QUEUED/RUNNING → CANCELLED + FINISHED_AT (Q4: đặt CANCELLED trực tiếp, không thêm cột CANCEL_REQUESTED — mô hình cancel-request của spec §5 cần worker checkpoint, worker nền thuộc task 26; task 25 thực thi đồng bộ nên cancel chỉ có nghĩa với run QUEUED/RUNNING). DONE/FAILED/CANCELLED → VALIDATION_ERROR.
- Timeout (T25-06, Q3): count query timeout riêng = min(version TIMEOUT_SEC, 30 giây); data query timeout = min(version TIMEOUT_SEC, DS CALL_TIMEOUT_S) (qua `open_checked_connection`). Map lỗi theo mẫu `fetch.py`: ORA-01013/TIMEOUT → SOURCE_TIMEOUT (run FAILED, lưu ERROR_CODE), mất kết nối → SOURCE_CONNECTION_LOST, còn lại → SOURCE_QUERY_FAILED.
- `report_run_metrics(ctx)` (T25-11): {total_runs, by_status: {QUEUED, RUNNING, DONE, FAILED, CANCELLED}, avg_query_ms (chỉ run DONE có QUERY_MS), total_rows} — owner scope (người thường chỉ số của mình, ADMIN toàn bộ).
- Test trước: `tests/unit/test_report_run_cancel.py` — T25-06 (count timeout riêng: mock assert call_timeout của count ≤ 30s; data timeout theo version/DS), T25-07 (cancel QUEUED ok, cancel DONE bị chặn, cancel run người khác → NOT_FOUND), T25-11 (metrics đúng theo owner, ADMIN thấy tất cả).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — History, preset, favorite, owner scope
- `list_report_runs(ctx, report_id=None, status=None, page=1, page_size=50)` + `get_report_run(ctx, run_id)` (T25-09/10): owner scope theo luồng G — lọc CREATED_BY=username, ADMIN bypass; mở run của người khác → NOT_FOUND (không phân biệt "không tồn tại" hay "không phải của mình"). Trả run kèm report/template/version (không trả PARAMS_JSON của người khác — đã NOT_FOUND từ trước).
- Preset (T25-08): `create_preset(ctx, report_id, template_id, name, values)` (resolve + validate qua `resolve_param_values` rồi lưu PARAMS_JSON đã resolve; NAME không rỗng, tối đa 200; IS_DEFAULT: đặt preset mặc định thì bỏ mặc định của preset khác cùng user+template trong cùng transaction), `list_presets(ctx, report_id, template_id)`, `delete_preset(ctx, preset_id)` (chỉ chủ sở hữu, ADMIN cũng chỉ xóa của mình? — preset là cá nhân: chỉ USER_ID = mình mới xóa/sửa, kể cả ADMIN), `apply_preset(ctx, preset_id, values_override=None)` (trả values đã resolve để tạo run).
- Favorite: tái dùng `set_report_favorite` (task 21) — không viết lại; test T25-08 kiểm tra favorite + preset cùng nhau.
- T25-09 ghi loại E2E trong checklist nhưng chưa có UI (trang /report-runs thuộc task 27): kiểm tra ở mức service trong task 25 (pytest: user B get/list run của A → NOT_FOUND/trống), và kiểm tra lại bằng Playwright ở task 27 khi trang history có thật (ghi vào decisions.md).
- Test trước: `tests/unit/test_report_run_history.py` — T25-08 (favorite/preset CRUD + default duy nhất), T25-09 (user B mở run A → NOT_FOUND; list của B không có run A), T25-10 (ADMIN thấy tất cả), T25-11 (metrics đã test ở bước 3, ở đây kiểm tra history filter theo status/report).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path.

## Câu hỏi chốt (Q0–Q8)
- Q0: Nhánh `feat/25-reporting-execution` từ `2402c07` (đầu nhánh task 24 đã push). Đồng ý?
- Q1: Làm xong cả task rồi gửi xem như các task trước, hay dừng sau mỗi bước chờ "continue"?
- Q2: `execute_report_run` chạy đồng bộ trong request (chặn tới DONE/FAILED); thực thi nền thuộc task 26 (background export). Đồng ý?
- Q3: Count timeout riêng = min(version TIMEOUT_SEC, 30 giây); data timeout = min(version TIMEOUT_SEC, DS CALL_TIMEOUT_S). Đồng ý?
- Q4: Cancel = đặt CANCELLED trực tiếp (không thêm cột CANCEL_REQUESTED, không migration); mô hình cancel-request cần worker, thuộc task 26. Đồng ý?
- Q5: page_size mặc định 50, tối đa 200 (web); dry-run tối đa preview_max_rows của version. Đồng ý?
- Q6: Stable sort = sorts người dùng + cột đầu tiên của kết quả làm tiebreaker (ghi rõ: không có PK nên chỉ bảo đảm tuyệt đối khi sort chứa cột duy nhất). Đồng ý?
- Q7: `dry_run_version` thành công thì DRAFT→DRY_RUN_OK (đóng vòng T21-04, nếu không activate không bao giờ chạy được). Đồng ý?
- Q8: T25-09 (E2E) kiểm tra ở mức service trong task 25, kiểm tra lại bằng Playwright ở task 27 khi trang /report-runs có thật. Đồng ý?
