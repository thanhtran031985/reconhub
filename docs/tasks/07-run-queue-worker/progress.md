# Tiến độ — 07-run-queue-worker

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Precheck + create | ✅ | 2026-11-01 | 09ba5b4 |
| 2 | Worker + executor | ✅ | 2026-11-01 | |
| 3 | Đọc kết quả | ⬜ |  |  |
| 4 | Dry-run + activate + grain | ⬜ |  |  |
| 5 | Xóa dữ liệu tạm | ⬜ |  |  |
| 6 | Demo | ⬜ |  |  |

## Nhật ký
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
