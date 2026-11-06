# Tiến độ — 18-batch-run

Trạng thái: 🔄 (bắt đầu 06/11/2026, nhánh feat/18-batch-run từ ad98705; plan đã duyệt theo đề xuất Q0–Q4)

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema, migration và FILE_SET_HASH | ✅ | 06/11/2026 |  |
| 2 | Công thức và ghép file (hàm thuần) | ⬜ |  |  |
| 3 | Service bộ đối soát | ⬜ |  |  |
| 4 | Lần chạy bộ: tạo, tải file, ghép, tham số | ⬜ |  |  |
| 5 | Gộp nhiều file trong engine/executor | ⬜ |  |  |
| 6 | Precheck, start, worker giới hạn song song | ⬜ |  |  |
| 7 | Chạy lại, thay file, hủy, ma trận, .zip | ⬜ |  |  |
| 8 | UI: Bộ đối soát và hộp thoại thêm template | ⬜ |  |  |
| 9 | UI: Wizard chạy bộ và kết quả | ⬜ |  |  |
| 10 | Chuyển Oracle, tài liệu, hồi quy | ⬜ |  |  |

## Nhật ký

### Bước 1 — Schema, migration và FILE_SET_HASH (06/11/2026)
- 5 bảng mới + cột `BATCH_RUN_ID`/`BATCH_RUN_ITEM_ID` (RECON_RUN), `FILE_SET_HASH`/`SOURCE_FILES_JSON` (RECON_EXCEL_LOAD, UQ mới), `SOURCE_FILE_ID` (RECON_EXCEL_ROW, PK mới); migration `0006_batch_run`.
- Ghi chú: migration gộp 19 bản nạp trùng nội dung trên dev DB về 1 (xem decisions.md); `db-migrate` giữa chừng để lại bảng `_alembic_tmp_*` + 5 bảng batch — phải dọn tay rồi chạy lại.
- Kiểm tra: `tests/integration/test_batch_migration.py` 4 pass; `test_migrations.py` 5 pass; `test_excel_load_integration.py` 2 pass (đã sửa 1 test theo hành vi dedup mới + sửa `_reused_response`); golden + worker_executor + temp_data_purge 30 pass cùng nhóm; typecheck 21 = baseline; lint sạch.