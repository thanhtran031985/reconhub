# 07-run-queue-worker — Run, hàng đợi, worker, dry-run, xóa dữ liệu tạm theo yêu cầu

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ1
- Phụ thuộc: 03, 06
- Nhánh git: feat/07-run-queue-worker

## Mục tiêu
Tạo run qua service, worker xử lý qua hàng đợi trên SQLite, ghi kết quả, đọc phân trang; dry-run, kích hoạt template; đánh dấu đã kiểm tra và xóa dữ liệu tạm theo yêu cầu (từng run, nhiều run, theo điều kiện) với cảnh báo dung lượng. Hết GĐ1: `poe demo-run` chạy được DTP end-to-end.

## Phạm vi
- services/run_service.py (precheck, create, cancel, rerun, list, get, columns, rows, row_detail, invalid, export, mark_checked)
- services/run_executor.py (spec 04 mục 9); worker claim_job, heartbeat, reset job treo
- Dry-run (persist=False), activate, grain
- services/temp_data.py (spec 04 mục 12): usage, preview, purge_runs, purge_filter (gõ XOA), purge_results (mặc định tắt), purge_log; dữ liệu dùng chung; incremental_vacuum; RECON_PURGE_LOG + audit
- Cảnh báo: usage so với TEMP_WARN_GB/TEMP_WARN_DAYS (không xóa)
- CLI purge-temp (--run, --checked-before, --dry-run); route /download/export/<run_id>
- `poe demo-run`: run DTP với fetcher giả (hoặc ORACLE_TEST nếu có `--oracle`), in summary

## Ngoài phạm vi
- Giao diện
- Tự động xóa

## Thiết kế
- designs/components/Screen05-NewRun, Screen06-RunResult, Screen07-History, Screen08-DataSources (khối Dữ liệu tạm)

## Spec liên quan
- docs/specs/04 mục 9, 12
- docs/specs/05 mục 2
- docs/specs/02 mục 4–8

## Quyết định kiến trúc
- Hàng đợi bằng bảng
- Run DONE bất biến (trừ trạng thái kiểm tra và dữ liệu tạm)
- Không tự xóa (ADR-012)

## Các bước
### Bước 1 — Precheck + create
- Làm: Precheck + create
- Test viết trước: INVALID_RANGE, RANGE_TOO_LARGE, PROD_CONFIRM_REQUIRED, MAINTENANCE_MODE
- Kiểm tra: `uv run poe test`

### Bước 2 — Worker + executor
- Làm: Worker + executor
- Test viết trước: SQLite 2 process không trùng job; ghi nháp trong lúc worker ghi 200.000 dòng không 'database is locked'; ngắt nguồn giữa chừng → FAILED không kết quả dở
- Kiểm tra: `uv run poe test`

### Bước 3 — Đọc kết quả
- Làm: get, columns, rows, row_detail, invalid, export
- Test viết trước: trên run G01 đếm khớp expected
- Kiểm tra: `uv run poe test`

### Bước 4 — Dry-run + activate + grain
- Làm: Dry-run + activate + grain
- Test viết trước: sửa config sau dry-run → DRY_RUN_REQUIRED
- Kiểm tra: `uv run poe test`

### Bước 5 — Xóa dữ liệu tạm
- Làm: mark_checked, purge_runs, preview, purge_filter, purge_results, usage, log, CLI
- Test viết trước: G13; run RUNNING không xóa; PURGE_CONFIRM_MISMATCH; quyền (OP chỉ xóa run qua mark_checked); file SQLite nhỏ lại sau xóa; không có job tự xóa nào
- Kiểm tra: `uv run poe test`

### Bước 6 — Demo
- Làm: demo-run
- Test viết trước: —
- Kiểm tra: `uv run poe demo-run` in đúng số G01; có VPN: `uv run poe demo-run --oracle`

## Chấp nhận khi
- [ ] demo-run đúng G01 qua worker trên SQLite
- [ ] Xóa dữ liệu tạm chỉ khi được yêu cầu, giữ kết quả và export
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
