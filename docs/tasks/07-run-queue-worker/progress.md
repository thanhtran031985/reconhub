# Tiến độ — 07-run-queue-worker

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Precheck + create | ✅ | 2026-11-01 | 09ba5b4 |
| 2 | Worker + executor | ✅ | 2026-11-01 | 71d298a |
| 3 | Đọc kết quả | ✅ | 2026-11-01 | 2ea1b9e |
| 4 | Dry-run + activate + grain | ✅ | 2026-11-01 | 77ce617 |
| 5 | Xóa dữ liệu tạm | ✅ | 2026-11-01 | c3c2911 |
| 6 | Demo | ⬜ |  |  |

## Nhật ký
### Bước 5 — 2026-11-01 01:40
- Đã làm: Cài đặt dịch vụ `app/services/temp_data.py` (`mark_checked`, `usage`, `preview`, `purge_runs`, `purge_filter`, `purge_results`) tuân thủ nghiêm ngặt nguyên tắc chỉ xóa dữ liệu tạm khi người dùng yêu cầu (ADR-012, Spec 04 mục 12). Cài đặt cơ chế an toàn dữ liệu dùng chung (chỉ xóa file gốc và `RECON_EXCEL_ROW` khi tất cả các run tham chiếu đã được xóa), giữ trọn vẹn kết quả `RECON_RESULT_*` và export Excel, gọi `PRAGMA incremental_vacuum` thu hồi dung lượng SQLite và ghi `RECON_PURGE_LOG` + audit log. Tích hợp lệnh CLI `purge-temp` (`--run`, `--checked-before`, `--dry-run`). Viết bài test `tests/unit/test_temp_data_purge.py` (7 tests) kiểm chứng quyền hạn, chặn xóa run RUNNING, xác nhận từ khóa `XOA` và kiểm tra file dùng chung.
- Kiểm tra: `uv run pytest tests/unit/test_temp_data_purge.py` (7 passed); `uv run poe test` (225 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Quản lý dữ liệu dùng chung theo mức tham chiếu ngăn chặn việc xóa nhầm file khi một file Excel được dùng cho nhiều profile run khác nhau.
- Việc cần người làm thủ công: Không có.

### Bước 4 — 2026-11-01 01:34
- Đã làm: Cài đặt dịch vụ `dry_run` trong `app/services/run_service.py` với cờ `persist=False`, dọn dẹp hàng đợi tạm, cập nhật `DRY_RUN_OK='Y'`, `SAMPLE_FILE_ID` và lưu tóm tắt vào `DRY_RUN_JSON`. Bổ sung kiểm tra và phân tích Grain cảnh báo trùng khóa hoặc grain quá thô. Đồng bộ kiểu `JsonText` với encoder `default=str` để an toàn tuần tự hóa Decimal/datetime. Viết bài test `tests/unit/test_dry_run_activate.py` kiểm chứng vòng đời Dry-run: sửa cấu hình bản nháp tự động reset `DRY_RUN_OK='N'`, chặn kích hoạt với `DRY_RUN_REQUIRED` và kích hoạt thành công sau khi Dry-run lại.
- Kiểm tra: `uv run pytest tests/unit/test_dry_run_activate.py` (1 passed); `uv run poe test` (218 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Dry-run dọn sạch run tạm giúp bảo vệ schema không bị rác và giữ cho bản nháp tiếp tục chỉnh sửa trên cùng version mà không bị ép nhảy version.
- Việc cần người làm thủ công: Không có.

### Bước 3 — 2026-11-01 01:30
- Đã làm: Cài đặt trọn vẹn nhóm hàm đọc kết quả trong `app/services/run_service.py` (`get_run`, `list_runs`, `get_run_columns`, `get_run_rows`, `get_row_detail`, `get_invalid_rows`, `export_run`). Hỗ trợ phân trang, tìm kiếm trên khóa, sắp xếp theo độ lệch tuyệt đối `ABS_DIFF_SORT`. Trích xuất các dòng thô Excel từ `RECON_EXCEL_ROW` kèm cơ chế thông báo rõ khi dữ liệu tạm đã bị xóa (`purged_at`). Tích hợp route Flask `/download/export/<run_id>` cho phép tải file export Excel. Viết bài test `tests/unit/test_run_query.py` xác minh đếm khớp chính xác trên G01 (184 MATCHED, 4 MISMATCH, 2 MISSING_IN_DB, 2 MISSING_IN_EXCEL) và kiểm tra file Excel sinh ra hợp lệ qua openpyxl.
- Kiểm tra: `uv run pytest tests/unit/test_run_query.py` (7 passed); `uv run poe test` (217 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Export Excel từ các bảng kết quả lưu trong RECON_APP vẫn hoạt động độc lập và toàn vẹn ngay cả sau khi xóa các dòng dữ liệu tạm.
- Việc cần người làm thủ công: Không có.

### Bước 2 — 2026-11-01 01:26
- Đã làm: Cài đặt `app/services/run_executor.py` (`execute_run`, `SourceFetcherWrapper`) điều phối 5 giai đoạn READ (10%) -> FILTER (25%) -> FETCH_DB (55%) -> COMPARE (80%) -> SAVE (100%). Ghi nhận kết quả lô 5.000 dòng vào `RECON_RESULT_ROW`, `RECON_RESULT_DIFF`, `RECON_INVALID_ROW`, `RECON_RUN_SUMMARY`, an toàn rollback khi gặp sự cố không để kết quả dở. Nâng cấp `worker/runner.py` với thread heartbeat định kỳ và cơ chế tự động dọn dẹp job treo `reset_stale_jobs`. Viết bài test `tests/unit/test_worker_executor.py` kiểm chứng không tranh chấp claim job trên SQLite, thực thi đúng số liệu G01 (184 MATCHED, 4 MISMATCH, 2 MISSING_IN_DB, 2 MISSING_IN_EXCEL) và reset stale job.
- Kiểm tra: `uv run pytest tests/unit/test_worker_executor.py` (4 passed); `uv run poe test` (209 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Hỗ trợ đa dạng fetcher (callable, DataFrame, Oracle thin connection) giúp pipeline chạy linh hoạt cả trong test lẫn môi trường thật.
- Việc cần người làm thủ công: Không có.

### Bước 1 — 2026-11-01 01:19
- Đã làm: Định nghĩa schema `app/schemas/run.py` (`PrecheckParams`, `CreateRunParams`, `RunResponse`, `RunListFilter`, `RunRowsFilter`, `PurgeFilter`). Cài đặt `app/services/run_service.py` với 2 hàm cốt lõi `precheck` và `create_run`. Kiểm tra chặt chẽ `INVALID_RANGE`, `RANGE_TOO_LARGE`, `PROD_CONFIRM_REQUIRED`, chế độ bảo trì `MAINTENANCE_MODE` trên `RECON_APP_SETTING`, xác thực quyền hạn RBAC và đẩy job vào `RECON_RUN_QUEUE` với trạng thái `READY` kèm audit log.
- Kiểm tra: `uv run pytest tests/unit/test_run_create.py` (6 passed); `uv run poe test` (205 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): `max_range_days` được lấy linh hoạt từ `time_filter` trong cấu hình template hoặc mặc định 93 ngày.
- Việc cần người làm thủ công: Không có.
