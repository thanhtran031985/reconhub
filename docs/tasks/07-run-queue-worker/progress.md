# Tiến độ — 07-run-queue-worker

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Precheck + create | ✅ | 2026-11-01 | |
| 2 | Worker + executor | ⬜ |  |  |
| 3 | Đọc kết quả | ⬜ |  |  |
| 4 | Dry-run + activate + grain | ⬜ |  |  |
| 5 | Xóa dữ liệu tạm | ⬜ |  |  |
| 6 | Demo | ⬜ |  |  |

## Nhật ký
### Bước 1 — 2026-11-01 01:19
- Đã làm: Định nghĩa schema `app/schemas/run.py` (`PrecheckParams`, `CreateRunParams`, `RunResponse`, `RunListFilter`, `RunRowsFilter`, `PurgeFilter`). Cài đặt `app/services/run_service.py` với 2 hàm cốt lõi `precheck` và `create_run`. Kiểm tra chặt chẽ `INVALID_RANGE`, `RANGE_TOO_LARGE`, `PROD_CONFIRM_REQUIRED`, chế độ bảo trì `MAINTENANCE_MODE` trên `RECON_APP_SETTING`, xác thực quyền hạn RBAC và đẩy job vào `RECON_RUN_QUEUE` với trạng thái `READY` kèm audit log.
- Kiểm tra: `uv run pytest tests/unit/test_run_create.py` (6 passed); `uv run poe test` (205 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): `max_range_days` được lấy linh hoạt từ `time_filter` trong cấu hình template hoặc mặc định 93 ngày.
- Việc cần người làm thủ công: Không có.
