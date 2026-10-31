# Kế hoạch — 07-run-queue-worker

### Mục tiêu
Cài đặt hoàn chỉnh hệ thống Run, Hàng đợi, Worker nền, Dry-run & Kích hoạt Template, Đọc phân trang kết quả và Quản lý/Xóa dữ liệu tạm theo yêu cầu (Spec 04 mục 9 & 12; Spec 02 mục 4–8):
1. `app/schemas/run.py`: Schema Pydantic cho tạo run, lọc hàng đợi, phân trang kết quả, xóa dữ liệu tạm.
2. `app/services/run_service.py`: Precheck (thời gian, quyền, confirm PROD, MAINTENANCE), tạo run, hủy run, chạy lại, danh sách run, chi tiết run, cột kết quả, dòng kết quả phân trang, dòng chi tiết Excel thô, danh sách dòng lỗi validate, xuất Excel, đánh dấu đã kiểm tra (`mark_checked`).
3. `app/services/run_executor.py`: Điều phối luồng chạy 5 giai đoạn (READ 10% -> FILTER 25% -> FETCH_DB 55% -> COMPARE 80% -> SAVE 100%), ghi nhận theo lô 5.000 dòng, an toàn transaction, hỗ trợ `persist=False` cho dry-run.
4. `worker/runner.py`: Cơ chế claim job an toàn concurrency trên SQLite qua `BEGIN IMMEDIATE` / `RETURNING`, cập nhật heartbeat định kỳ, tự động xử lý reset job treo.
5. Dry-run và kích hoạt template: Chạy thử nghiệm file mẫu không lưu kết quả bảng phụ, cập nhật `DRY_RUN_OK`, chặn kích hoạt nếu sửa cấu hình mà chưa dry-run lại (`DRY_RUN_REQUIRED`).
6. `app/services/temp_data.py`: Giám sát dung lượng (`usage`), xem trước xóa (`preview`), xóa dữ liệu tạm theo run hoặc bộ lọc với từ khóa xác nhận `XOA`, xử lý dữ liệu dùng chung an toàn, gọi `incremental_vacuum`, ghi `RECON_PURGE_LOG` và audit log.
7. Lệnh CLI `purge-temp` và `uv run poe demo-run`: Kiểm thử đối soát DTP end-to-end với mẫu `dtp_sample_200.xlsx`.

---

### Bước 1 — Precheck + create (`app/schemas/run.py`, `app/services/run_service.py`)
- Định nghĩa schema `PrecheckParams`, `CreateRunParams`, `RunResponse`.
- Cài đặt `precheck`:
  - `INVALID_RANGE` khi `p_from > p_to`.
  - `RANGE_TOO_LARGE` khi số ngày vượt quá `max_range_days` của template.
  - `PROD_CONFIRM_REQUIRED` khi Data Source môi trường PROD mà thiếu cờ `confirm_prod=True`.
  - `MAINTENANCE_MODE` khi bảng `RECON_APP_SETTING` có `MAINTENANCE = 'Y'` (trừ ADMIN).
- Cài đặt `create_run`:
  - Kiểm tra quyền OPERATOR, TEMPLATE_OWNER, ADMIN.
  - Lấy template version ACTIVE (hoặc version chỉ định nếu hợp lệ).
  - Tạo bản ghi `RECON_RUN` (status `QUEUED`) và `RECON_RUN_QUEUE` (status `READY`).
  - Ghi audit log `CREATE_RUN`.
- Test viết trước: `tests/unit/test_run_create.py`.
- Kiểm tra: `uv run poe test`.

---

### Bước 2 — Worker + executor (`app/services/run_executor.py`, `worker/runner.py`)
- Cài đặt `run_executor.py`:
  - 5 giai đoạn: READ (10%), FILTER (25%), FETCH_DB (55%), COMPARE (80%), SAVE (100%).
  - Đọc từ `load_excel_to_temp` (hoặc tái sử dụng nếu đã nạp).
  - Gọi `run_pipeline` và lưu `RECON_RESULT_ROW`, `RECON_RESULT_DIFF`, `RECON_INVALID_ROW` theo batch 5.000 dòng.
  - Cập nhật `RECON_RUN_SUMMARY` và trạng thái `DONE`.
  - Bắt lỗi: FAILED với `ERROR_CODE` và `ERROR_MSG` tiếng Việt, không để kết quả dở dang.
- Nâng cấp `worker/runner.py`:
  - Worker nhận job qua `claim_next_queued_job`, thực thi `run_executor`, cập nhật heartbeat.
  - Reset job treo nếu worker chết (heartbeat timeout).
  - An toàn SQLite concurrency không bị "database is locked".
- Test viết trước: `tests/unit/test_worker_executor.py`.
- Kiểm tra: `uv run poe test`.

---

### Bước 3 — Đọc kết quả (`app/services/run_service.py`)
- Cài đặt các hàm đọc kết quả:
  - `get_run(ctx, run_id)`
  - `list_runs(ctx, filter)`
  - `get_run_columns(ctx, run_id)`
  - `get_run_rows(ctx, run_id, status, page, page_size, sort_by, sort_dir, search)`
  - `get_row_detail(ctx, run_id, row_no)`: Trả về dòng Excel thô từ `RECON_EXCEL_ROW` (nếu chưa xóa) hoặc báo `purged_at`.
  - `get_invalid_rows(ctx, run_id, page, page_size)`
  - `export_run(ctx, run_id)`: Trả về file xuất Excel từ kết quả đã lưu.
- Test viết trước: `tests/unit/test_run_query.py` (chạy trên run G01 kiểm tra đếm khớp và phân trang chính xác).
- Kiểm tra: `uv run poe test`.

---

### Bước 4 — Dry-run + activate + grain (`app/services/run_executor.py`, `app/services/template.py`)
- Tích hợp `dry_run` với `persist=False`:
  - Chạy toàn bộ pipeline trên file mẫu `SAMPLE_FILE_ID` của template version.
  - Ghi nhận `DRY_RUN_OK = 'Y'`, lưu tóm tắt vào `DRY_RUN_JSON`.
  - Cảnh báo grain: tính tỉ lệ nhóm trùng và độ phân giải khóa.
- Ràng buộc kích hoạt template (`activate_template_version`):
  - Phải có `DRY_RUN_OK == 'Y'`.
  - Nếu sửa đổi `CONFIG_JSON` sau lần dry-run cuối cùng: báo lỗi `DRY_RUN_REQUIRED`.
- Test viết trước: `tests/unit/test_dry_run_activate.py`.
- Kiểm tra: `uv run poe test`.

---

### Bước 5 — Xóa dữ liệu tạm theo yêu cầu (`app/services/temp_data.py`, `app/cli.py`)
- Cài đặt `app/services/temp_data.py`:
  - `usage(ctx)`: Kiểm tra dung lượng file, storage runs, số dòng tạm, cảnh báo `TEMP_WARN_GB` / `TEMP_WARN_DAYS`.
  - `preview(ctx, filter)`: Ước tính số run và dung lượng sẽ giải phóng.
  - `mark_checked(ctx, run_id, purge=False/True)`: Đánh dấu đã kiểm tra, xóa dữ liệu tạm nếu yêu cầu.
  - `purge_runs(ctx, run_ids)`: Xóa các file `.parquet`, xóa dòng `RECON_EXCEL_ROW` theo batch 5.000, cập nhật `TEMP_PURGED_AT`. Xử lý an toàn file/load dùng chung.
  - `purge_filter(ctx, filter, confirm_text)`: Kiểm tra gõ đúng chữ `XOA` (`PURGE_CONFIRM_MISMATCH`).
  - `purge_results(ctx, older_than_days, confirm_text)`: Xóa bảng kết quả cũ (ADMIN).
  - Thu hồi dung lượng SQLite: `PRAGMA incremental_vacuum`.
  - Ghi nhận vào `RECON_PURGE_LOG` và `RECON_AUDIT_LOG`.
- Cài đặt CLI `purge-temp` trong `app/cli.py`.
- Test viết trước: `tests/unit/test_temp_data_purge.py` (Golden G13, quyền hạn, file dùng chung, dung lượng thu hồi).
- Kiểm tra: `uv run poe test`.

---

### Bước 6 — Demo run (`uv run poe demo-run`)
- Tạo script `scripts/demo_run.py` và khai báo lệnh `poe demo-run`.
- Thực hiện toàn bộ quy trình: Nạp file `samples/dtp_sample_200.xlsx`, chạy đối soát DTP với profile `BY_INVOICE`, in ra bảng tóm tắt khớp số G01.
- Hỗ trợ cờ `--oracle` để chạy đối soát trực tiếp qua Oracle server (nếu có VPN).
- Kiểm tra: `uv run poe demo-run`.
