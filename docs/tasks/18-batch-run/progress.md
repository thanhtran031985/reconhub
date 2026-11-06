# Tiến độ — 18-batch-run

Trạng thái: 🔄 (bắt đầu 06/11/2026, nhánh feat/18-batch-run từ ad98705; plan đã duyệt theo đề xuất Q0–Q4)

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema, migration và FILE_SET_HASH | ✅ | 06/11/2026 |  |
| 2 | Công thức và ghép file (hàm thuần) | ✅ | 06/11/2026 |  |
| 3 | Service bộ đối soát | ✅ | 06/11/2026 |  |
| 4 | Lần chạy bộ: tạo, tải file, ghép, tham số | ✅ | 06/11/2026 |  |
| 5 | Gộp nhiều file trong engine/executor | ✅ | 06/11/2026 |  |
| 6 | Precheck, start, worker giới hạn song song | ⬜ |  |  |
| 7 | Chạy lại, thay file, hủy, ma trận, .zip | ⬜ |  |  |
| 8 | UI: Bộ đối soát và hộp thoại thêm template | ⬜ |  |  |
| 9 | UI: Wizard chạy bộ và kết quả | ⬜ |  |  |
| 10 | Chuyển Oracle, tài liệu, hồi quy | ⬜ |  |  |

## Nhật ký

### Bước 5 — Gộp nhiều file trong engine/executor (06/11/2026)
- `app/engine/merge_files.py` mới: `merge_excel_files` (đọc từng file theo cùng FileSpec, thêm `__source_file`, header đã map phải khớp — lệch → BATCH_MERGE_HEADER_MISMATCH chỉ rõ file, control total kiểm từng file) + `sum_control_totals`; `reader.read_sheets` đọc nhiều file.
- `run_pipeline(excel_files=[(path, tên hiển thị)])`; `aggregate` ghi `__row_nos` dạng `[{"f": tên file, "r": dòng}]` khi có `__source_file`, 1 file giữ `[r, …]`.
- `load_excel_files_to_temp` (excel_load): FILE_SET_HASH dedup/dùng lại/ghi lại bản nạp đã purge, SOURCE_FILES_JSON từng file, dòng RECON_EXCEL_ROW mang SOURCE_FILE_ID + EXCEL_ROW_NO theo từng file.
- Executor SAVE ghi EXCEL_ROW_NOS dạng JSON `[{"f": file_id, "r": dòng}]` khi gộp (map tên → id qua SOURCE_FILES_JSON); run_service đọc lại chi tiết/xuất theo cả 2 dạng; export hiện "file · dòng r".
- Kiểm tra: golden G14 (3 file = 1 file nối tay, trùng khóa giữa 2 file, header lệch) + `tests/integration/test_excel_load_fileset.py` 5 pass; typecheck 21 = baseline; lint sạch.
- Ghi chú: xem decisions.md (EXCEL_ROWS_READ gộp = 204 vs 202 vì mỗi file có 1 dòng tổng riêng; FILE_ID của bản nạp gộp = file đầu tiên theo comment sẵn trong metadata).

### Bước 4 — Service lần chạy bộ (06/11/2026)
- `app/services/batch_run.py`: create/get/list (owner scope Q2), add_files (tải + ghép mẫu tên/header, .zip an toàn, trùng tên/nội dung), assign_file/ignore_file, skip_item (USER_SKIP), set_param_override (giải lại tham số với kỳ).
- Kiểm tra: `tests/unit/test_batch_run_service.py` 24 pass; batch_def + formula/matcher + migration + excel_load 73 pass; golden + worker_executor + temp_data_purge 24 pass; typecheck 21 = baseline; lint sạch.
- Ghi chú: xem decisions.md (tên cột thật CNT_ITEMS/NORMALIZED_NAME/SEQ_NO; không có IS_INCLUDED/FILE_PATTERN trên bảng run; tải 2 giai đoạn vì SQLite khóa DB khi lồng transaction; mục template lưu trữ vẫn snapshot version/DS nhưng SKIPPED).

### Bước 3 — Service bộ đối soát (06/11/2026)
- `app/services/batch_def.py`: list/get/create/update/archive/activate/add_items/update_item/remove_item/addable_templates/preview_params; quyền AD+TO sửa, mọi role có menu đọc; audit đầy đủ.
- Kiểm tra: `tests/unit/test_batch_def_service.py` 26 pass; typecheck 21 = baseline; lint sạch.
- Ghi chú: thêm `activate_batch_def` (spec 10 mục 8 không liệt kê nhưng spec 10a mục 1 yêu cầu điều kiện kích hoạt); không sửa bộ đã ARCHIVED; thêm/sửa mục chỉ kiểm tham số lạ + cú pháp công thức, lỗi kiểu lộ ở preview/chạy.

### Bước 2 — Công thức và ghép file (06/11/2026)
- `batch_formula.py` (parse_period, resolve, resolve_params, compute_file_set_hash) + `batch_matcher.py` (normalize_name, match); mã lỗi BATCH_* mới trong errors.py.
- Kiểm tra: `tests/unit/test_batch_formula.py` + `test_batch_matcher.py` 36 pass cùng excel_load integration; typecheck 21 = baseline; lint sạch.
- Ghi chú: `compute_file_set_hash` gom về một chỗ (excel_load bỏ helper riêng); `normalize_name` lấy basename trước khi chuẩn hóa (file trong .zip có đường dẫn).

### Bước 1 — Schema, migration và FILE_SET_HASH (06/11/2026)
- 5 bảng mới + cột `BATCH_RUN_ID`/`BATCH_RUN_ITEM_ID` (RECON_RUN), `FILE_SET_HASH`/`SOURCE_FILES_JSON` (RECON_EXCEL_LOAD, UQ mới), `SOURCE_FILE_ID` (RECON_EXCEL_ROW, PK mới); migration `0006_batch_run`.
- Ghi chú: migration gộp 19 bản nạp trùng nội dung trên dev DB về 1 (xem decisions.md); `db-migrate` giữa chừng để lại bảng `_alembic_tmp_*` + 5 bảng batch — phải dọn tay rồi chạy lại.
- Kiểm tra: `tests/integration/test_batch_migration.py` 4 pass; `test_migrations.py` 5 pass; `test_excel_load_integration.py` 2 pass (đã sửa 1 test theo hành vi dedup mới + sửa `_reused_response`); golden + worker_executor + temp_data_purge 30 pass cùng nhóm; typecheck 21 = baseline; lint sạch.