# Tiến độ — 13-metadata-migration

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Precheck + bảo trì | ✅ | 2026-11-01 | feat/13-metadata-migration |
| 2 | Chép + identity | ✅ | 2026-11-01 | feat/13-metadata-migration |
| 3 | Kiểm tra + lỗi giữa chừng | ✅ | 2026-11-01 | feat/13-metadata-migration |
| 4 | Chạy trên Oracle + bản lưu cũ | ✅ | 2026-11-01 | feat/13-metadata-migration |
| 5 | UI + CLI | ✅ | 2026-11-01 | feat/13-metadata-migration |

## Nhật ký
### Bước 1 — 2026-11-01
- Triển khai `precheck`, `set_maintenance_mode`, kiểm tra tính sẵn sàng của schema đích và trạng thái các run đang chờ/chạy.
- Test unit: `test_permission_checks`, `test_precheck_target_not_found`, `test_precheck_running_run_blocks`, `test_precheck_target_not_empty`.

### Bước 2 — 2026-11-01
- Triển khai `start_migration`: sao chép dữ liệu theo thứ tự quan hệ bảng, lô 5.000 dòng, giữ nguyên ID, đồng bộ sequence identity cho Oracle (`ALTER TABLE ... MODIFY ID GENERATED AS IDENTITY (START WITH ...)`).
- Chế độ sao chép linh hoạt: `NO_TEMP` (mặc định), `FULL`, `CONFIG_ONLY`.

### Bước 3 — 2026-11-01
- Đối chiếu số dòng nguồn/đích và SHA256 checksum các bản ghi.
- Cơ chế xử lý lỗi: Khi có sự cố giữa chừng, trạng thái cập nhật `FAILED`, CSDL SQLite nguồn hoàn toàn nguyên vẹn.
- Bổ sung `clean_target_schema` để drop bảng trên schema đích khi cần thử lại sau khi chuyển lỗi.

### Bước 4 — 2026-11-01
- Triển khai `delete_old_sqlite`: chỉ cho phép thực thi khi hệ thống đang kết nối chạy trên Oracle; yêu cầu Admin nhập chính xác tên file xác nhận; ghi `RECON_PURGE_LOG` và `RECON_AUDIT_LOG`.

### Bước 5 — 2026-11-01
- Giao diện Web `app/ui/pages/data_sources.py`: Tab Lưu trữ RECON_APP tích hợp khối Chuyển dữ liệu sang Oracle, khối Bản lưu SQLite cũ, modal dọn schema đích và xóa SQLite cũ, script khởi tạo schema Oracle.
- CLI: Lệnh `uv run python -m app.cli migrate-metadata` với `--target-ds`, `--mode`, `--dry-run`, `--force`.
- Tài liệu vận hành: Tạo `docs/OPERATIONS.md` mục Đổi DB RECON_APP.
- Hoàn thành toàn bộ kiểm tra chất lượng: lint, typecheck, unit tests (299 passed), E2E (9 passed).
