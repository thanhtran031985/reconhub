# Implementation Plan — 26-reporting-export (Background export XLSX/CSV/ZIP)

## Bối cảnh
- Phụ thuộc task 25 — đã xong, nhánh `feat/25-reporting-execution` ở `1c4bc71`, đã push lên remote; task 25 không có migration.
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§5 Thực thi, §6 Export, §giới hạn), 12a, 12b (luồng E Export, luồng G Permission).
- Code hiện có tái dùng được:
  - Schema task 21: RECON_RPT_EXPORT (RUN_ID, FORMAT check XLSX/CSV/ZIP, STATUS check QUEUED/RUNNING/DONE/FAILED/CANCELLED, FILE_PATH, FILE_SIZE, FILE_HASH, PART_COUNT default 1, ROW_COUNT, CREATED_BY/AT, FINISHED_AT, ERROR_MESSAGE).
  - Task 25 `app/services/report_run.py`: `create/execute/get_report_page` + `_build_run_query` (CUSTOM_SQL snapshot / VIEW-TABLE whitelist builder), `_stable_order_by`, `_map_oracle_error`, `open_checked_connection` (task 22, read-only + call_timeout), `resolve_param_values` (task 23), `get_result_layout` (task 24).
  - Worker hiện có `worker/runner.py` (`ReconWorker`: poll RECON_RUN_QUEUE, claim nguyên tử qua `app/db/dialect.py::claim_next_queued_job` — SQLite UPDATE ... RETURNING / Oracle FOR UPDATE SKIP LOCKED, heartbeat thread 3s, `reset_stale_jobs` 300s, `poll_once` → `execute_run`); entry `python -m worker` (`worker/__main__.py`, `uv run poe worker`).
  - Xuất file hiện có `app/engine/export.py` + `export_styles.py` (XlsxWriter, formats `#,##0` / `#,##0.00`); `RECON_STORAGE_DIR` mặc định `./storage`, file recon lưu ở `storage/files/` theo sha (file_service).
  - XlsxWriter đã có trong dependencies (cùng openpyxl); XlsxWriter stream ra đĩa theo từng dòng (`constant_memory`) — tương đương openpyxl write-only.
- Lưu ý: task này là service + worker (test pytest, mock Oracle). UI Dash thật (nút export, danh sách export, download) thuộc task 27. Không có worker nền cho run trong task này — worker export chạy cùng tiến trình worker hiện có (Q3).
- Không thêm package mới. Có migration 0005 (Q2).

## Nhánh và tài liệu
- Nhánh mới `feat/26-reporting-export` từ `1c4bc71` (đầu nhánh task 25 đã push).
- Chép `docs/tasks/26-reporting-export/` từ nhánh docs vào nhánh mới (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 26.

## Các bước (theo progress.md)

### Bước 1 — Queue/worker export
- Migration `migrations/versions/0005_export_claim.py` (down_revision `0004_reporting_core`, Q2): thêm LOCKED_BY (String 60), LOCKED_AT, HEARTBEAT_AT (DateTime, nullable) vào RECON_RPT_EXPORT — để claim nguyên tử + reset stale, theo mẫu RECON_RUN_QUEUE. Downgrade bỏ 3 cột.
- Service mới `app/services/report_export.py` (`@service`):
  - `request_export(ctx, run_id, format, force=False)` (report_center; T26-01): run phải DONE (export từ run đã chạy xong); format XLSX/CSV (ZIP chỉ là kết quả khi split, không request trực tiếp); cache (Q7): đã có DONE export cùng run+format và force=False → trả lại export đó; ngược lại tạo RECON_RPT_EXPORT QUEUED (FORMAT=requested, PART_COUNT=1), trả export dict.
  - `execute_export(export_id, max_rows_per_file=1_000_000)` (hàm thuần, không decorator — worker gọi): claim đã xong ở worker; tải run + version detail (đổi `_load_version_detail` trong report_run.py thành public `load_version_detail` để dùng chung); chạy count + stream data; ghi file; cập nhật DONE/FAILED cùng transaction.
- Worker `worker/export_runner.py`: `ReportExportWorker` theo mẫu ReconWorker — `claim_next_export()` (QUEUED cũ nhất, bỏ qua user đã có ≥2 RUNNING — Q4; claim nguyên tử qua method mới `claim_next_queued_export` trong `app/db/dialect.py`, cùng cấu trúc SQLite RETURNING / Oracle SKIP LOCKED), `_start_heartbeat` (3s), `reset_stale_exports` (RUNNING + heartbeat > 300s → FAILED + ERROR_MESSAGE), `poll_once()` → claim → `execute_export` → dừng heartbeat, `run(stop_event)`.
- `worker/__main__.py`: chạy cả hai worker trong cùng tiến trình (2 thread, Q3).
- Test trước: `tests/unit/test_report_export_queue.py` — T26-01 (3 QUEUED của user A + 1 của user B: claim lấy của B trước khi A đủ 2 RUNNING; export thứ 3 của A chờ), claim nguyên tử (claim 2 lần liên tiếp → lần 2 None), stale reset (RUNNING heartbeat cũ → FAILED), request_export (run chưa DONE → VALIDATION_ERROR; format lạ → VALIDATION_ERROR; run người khác → NOT_FOUND; cache hit trả lại DONE cũ).
- Kiểm tra: `uv run poe test` (phạm vi unit), `uv run poe lint`, `uv run poe typecheck`, `uv run poe db-migrate` trên DB test (migration 0005 lên/xuống).

### Bước 2 — Streaming fetchmany và write-only XLSX
- Executor stream: mở connection (data timeout = min(TIMEOUT_SEC, DS)), execute data query (ORDER BY stable sort, không OFFSET — stream toàn bộ), lặp `fetchmany(5000)` (Q5) — không `fetchall`, không load toàn bộ RAM (T26-02).
- XLSX qua XlsxWriter `Workbook(path, {'constant_memory': True})` (T26-03): header = LABEL từ layout web; mỗi dòng ghi theo DATA_TYPE — STRING luôn `write_string` (giữ leading zero, T26-04), NUMBER `write_number` kèm num_format từ FORMAT_MASK, DATE/DATETIME `write_datetime` hoặc `write_string` theo mask; cột nào cũng có format Text cho mã/invoice/container (spec §6).
- CSV qua module `csv`: BOM UTF-8 đầu file + utf-8, quoting minimal, cùng vòng stream (T26-05).
- Test trước: `tests/unit/test_report_export_write.py` — T26-02 (tracemalloc: 10x rows → peak < 3x; assert fetchmany gọi với 5000, không gọi fetchall), T26-03 (XLSX đọc lại bằng openpyxl đủ dòng/cột), T26-04 ("00123", "000456" đọc lại vẫn là text "00123"/"000456"), T26-05 (CSV bắt đầu bằng BOM, parse đúng, chứa ký tự Việt).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Split file/zip/hash/storage
- Split (T26-06, Q6): sau mỗi 1.000.000 data rows thì đóng file hiện tại, mở part tiếp theo (`part-001.xlsx`, `part-002.xlsx`, ...). Đúng 1.000.000 → 1 part.
- ZIP (T26-07): PART_COUNT > 1 → zip toàn bộ part + `_summary.txt` (report code, run id, tổng rows, số part, format, thời gian) → FILE_PATH trỏ tới file zip, FORMAT='ZIP', PART_COUNT=n. 1 part → FILE_PATH trỏ thẳng file đó, FORMAT giữ nguyên request.
- Storage + hash (T26-08): file lưu ở `storage/report_exports/<export_id>/` (theo RECON_STORAGE_DIR); FILE_SIZE + FILE_HASH (sha256 của file cuối, đọc theo chunk) tính lúc đóng file; cập nhật DONE + FILE_PATH/SIZE/HASH/PART_COUNT/ROW_COUNT/FINISHED_AT trong một transaction; lỗi giữa chừng → FAILED + ERROR_MESSAGE, file dở xóa.
- `execute_export` nhận `max_rows_per_file` (mặc định 1.000.000) để test split với ngưỡng nhỏ mà không cần 2M dòng thật.
- Test trước: `tests/unit/test_report_export_split.py` — T26-06 (ngưỡng 100: 250 dòng → 3 part; đúng 100 → 1 part), T26-07 (zip chứa đủ part + `_summary.txt` đúng nội dung), T26-08 (hash == sha256 file, size == kích thước thật, status DONE + ROW_COUNT đúng).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Download/history/cache/security
- `list_exports(ctx, run_id=None)` + `get_export(ctx, export_id)` (report_center): owner scope (CREATED_BY, ADMIN bypass, người khác → NOT_FOUND).
- `download_export(ctx, export_id)` (T26-10/11): trả {file_path, file_name, file_size, file_hash}; file không còn trên đĩa → NOT_FOUND "File xuất đã không còn (đã xóa/hết hạn)" — lịch sử giữ nguyên record. T26-10 ghi loại E2E: kiểm tra mức service trong task 26, kiểm tra lại bằng Playwright ở task 27 khi UI download có thật (Q8).
- `retry_export(ctx, export_id)` (T26-09): chỉ FAILED → QUEUED (reset FILE_PATH/SIZE/HASH/ROW_COUNT/ERROR_MESSAGE về NULL); DONE/QUEUED/RUNNING → VALIDATION_ERROR; chỉ chủ sở hữu (ADMIN cũng chỉ retry của mình? — export là cá nhân: chỉ CREATED_BY = mình, kể cả ADMIN, theo mẫu preset task 25).
- `cancel_export(ctx, export_id)`: QUEUED/RUNNING → CANCELLED; executor kiểm tra STATUS giữa các batch (mỗi 10 batch đọc lại DB) và dừng, xóa file dở — đây là nửa còn lại của mô hình cancel ở task 25 Q4 (worker hủy ở checkpoint).
- Test trước: `tests/unit/test_report_export_download.py` — T26-09 (retry FAILED → QUEUED + reset field; retry DONE → lỗi), T26-10 (user B download/list export của A → NOT_FOUND/trống; ADMIN thấy tất cả), T26-11 (xóa file trên đĩa → download NOT_FOUND), cancel (QUEUED → CANCELLED; worker bỏ qua CANCELLED; executor dừng giữa chừng khi bị cancel).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Migration 0005 lên/xuống trên DB test; Oracle leg của T26-12 để phía có VPN kiểm tra sau.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path.

## Câu hỏi chốt (Q0–Q8)
- Q0: Nhánh `feat/26-reporting-export` từ `1c4bc71` (đầu nhánh task 25 đã push). Đồng ý?
- Q1: Làm xong cả task rồi gửi xem như các task trước, hay dừng sau mỗi bước chờ "continue"?
- Q2: Migration 0005 thêm LOCKED_BY/LOCKED_AT/HEARTBEAT_AT vào RECON_RPT_EXPORT (claim nguyên tử + reset stale, theo mẫu RECON_RUN_QUEUE). Đồng ý?
- Q3: Export worker chạy cùng tiến trình worker hiện có (2 thread trong `python -m worker`) thay vì tiến trình riêng. Đồng ý?
- Q4: Tối đa 2 export RUNNING cùng lúc cho mỗi user (vượt thì QUEUED chờ). Đồng ý?
- Q5: fetchmany batch 5000; XLSX qua XlsxWriter constant_memory; STRING luôn write_string (giữ leading zero), NUMBER write_number, DATE/DATETIME theo format mask. Đồng ý?
- Q6: Split 1.000.000 data rows/file; >1 part → ZIP (parts + `_summary.txt`), FORMAT='ZIP', PART_COUNT=n. Đồng ý?
- Q7: request_export cache — DONE export cùng run+format được trả lại (không chạy lại), force=True để chạy mới. Đồng ý?
- Q8: T26-10 (E2E) kiểm tra mức service trong task 26, Playwright ở task 27; T26-12 (Oracle benchmark) để phía có VPN kiểm tra sau (như T21-01/T22-07). Đồng ý?
