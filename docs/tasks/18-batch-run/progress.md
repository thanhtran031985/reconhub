# Tiến độ — 18-batch-run

Trạng thái: 🔄 (bắt đầu 06/11/2026, nhánh feat/18-batch-run từ ad98705; plan đã duyệt theo đề xuất Q0–Q4)

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema, migration và FILE_SET_HASH | ✅ | 06/11/2026 |  |
| 2 | Công thức và ghép file (hàm thuần) | ✅ | 06/11/2026 |  |
| 3 | Service bộ đối soát | ✅ | 06/11/2026 |  |
| 4 | Lần chạy bộ: tạo, tải file, ghép, tham số | ✅ | 06/11/2026 |  |
| 5 | Gộp nhiều file trong engine/executor | ✅ | 06/11/2026 |  |
| 6 | Precheck, start, worker giới hạn song song | ✅ | 06/11/2026 |  |
| 7 | Chạy lại, thay file, hủy, ma trận, .zip | ✅ | 06/11/2026 |  |
| 8 | UI: Bộ đối soát và hộp thoại thêm template | ✅ | 06/11/2026 |  |
| 9 | UI: Wizard chạy bộ và kết quả | ✅ | 07/11/2026 |  |
| 10 | Chuyển Oracle, tài liệu, hồi quy | ⬜ |  |  |

## Nhật ký

### Bước 9 — UI Wizard chạy bộ và kết quả (07/11/2026)
- `app/ui/pages/batch_run_wizard.py` (`/batch-runs`, `/batch-runs/<id>`, `/batch-runs/new?def=<id>`): form tạo lần chạy (chọn bộ ACTIVE qua `list_active_defs`, kỳ mặc định tháng hiện tại, tên tùy chọn, khối lần chạy gần đây) + wizard 5 bước (Tải file → Ghép file → Tham số → Kiểm tra → Chạy): dcc.Upload giải base64 (`decode_uploads`), ghép theo mẫu tên/header/tay, sửa tham số ghi đè (set None = về mặc định), precheck, xác nhận PROD một lần (modal liệt kê DS PROD từ `res.details`), chạy `n` template, interval 2s khi RUNNING, hủy lần chạy.
- `app/ui/pages/batch_run_result.py` (`/batch-runs/<id>/result`): KPI + ma trận (tổng Excel/DB, chênh lệch, khớp/lệch/thiếu, tỷ lệ khớp, so tháng trước), chạy lại run lỗi (chung + từng mục), tải file riêng từng mục (export của run con), tải .zip tổng, đánh dấu đã kiểm tra + xóa dữ liệu tạm hàng loạt (modal xác nhận XOA, chỉ ADMIN).
- `app/ui/pages/history.py`: thêm lọc "Lần chạy bộ" (Tất cả/Chỉ run bộ/Chỉ run đơn lẻ) + chip "Bộ <mã>" trong ô Template của run con; `app/services/run_service.py list_runs` thêm `batch_only` (outerjoin RECON_BATCH_RUN + RECON_BATCH_DEF) và `RunListFilter.batch_only`.
- Kiểm tra: `tests/unit/test_batch_run_pages.py` 26 pass + `tests/e2e/test_batch_run.py` 6 pass; cụm hồi quy liên quan (history, run_query, owner_scope, e2e batch) 65 pass; cụm batch (def/run/precheck/rerun/zip/claim/e2e def) 93 pass + 1 skip Oracle; full suite 1187 pass, 6 skipped — 6 fail ban đầu toàn ở bước 9, đã sửa xong (xem decisions.md); typecheck 21 = baseline; lint sạch; kiểm chứng đăng ký page: `create_app()` thấy `/batch-runs` và `/batch-runs/1/result`, tổng 26 pages.
- Ghi chú: xem decisions.md (Stepper chỉ hiển thị, bước lưu ở store; `list_active_defs` vì OPERATOR không có menu batch_def; menu `/batch-runs` mở thẳng form tạo; seed mẫu Q3 đã có sẵn và khớp spec 10a §9).
- Sự cố môi trường: full suite lần 1 INTERNALERROR + hết dung lượng `/tmp` (tmpfs 512M); lần chạy lại với TMPDIR trên ổ home btrfs chỉ đạt 17% sau 13 phút (pytest kẹt disk sleep chờ btrfs writeback); chạy lại với `TMPDIR=/run/pytest-tmp` (tmpfs 1.6G) xong trong 215s. Ghi vào `~/TOOLS.md`: không đặt TMPDIR trên ổ home, dùng `/run/pytest-tmp` (tạo lại sau mỗi lần VM thay thế).

### Bước 8 — UI Bộ đối soát và hộp thoại thêm template (06/11/2026)
- `app/ui/pages/batch_defs.py` (`/batches`): bảng Mã/Tên/Trạng thái/Số mục/Song song/DS/Thao tác, lọc tìm kiếm + trạng thái phía client, modal Tạo bộ (mã/tên/mô tả/max_parallel 1–4) rồi redirect sang trang chi tiết, modal xác nhận lưu trữ, quyền ghi ADMIN/TEMPLATE_OWNER.
- `app/ui/pages/batch_def_edit.py` (`/batches/<id>`): form thông tin bộ (mã disabled), bảng mục sửa inline (mẫu tên file, Gộp/Bắt buộc, Ưu tiên, DS, tham số ghi đè JSON) + store theo dõi số mục thay đổi chưa lưu, nút Lưu gọi `update_batch_def`/`update_batch_def_item` kèm row_version; khối Kỳ thử + xem trước tham số (`preview_params`); modal Thêm template (tìm kiếm, lọc chỉ template thêm được, cấu hình từng template đã chọn với mẫu gợi ý `*<MÃ>*`); modal gỡ template + lưu trữ bộ; nút Kích hoạt.
- Kiểm tra: `tests/e2e/test_batch_def.py` 4 pass + `tests/unit/test_batch_def_pages.py` 5 pass; mypy 2 file sạch; ruff check + format sạch.
- Ghi chú: xem decisions.md (bảng dùng dmc.Table thay vì AgGrid; kiểm chứng đăng ký page: `create_app()` thấy `/batches` và `/batches/1`, tổng 24 pages).

### Bước 7 — Chạy lại, thay file, hủy, ma trận, .zip (06/11/2026)
- `retry_failed` (mục FAILED → run con mới, ATTEMPT_NO+1, batch lại RUNNING), `rerun_item` (DONE/FAILED/NOT_RUN, kể cả DONE sau khi sửa file), `replace_files` (file cũ REPLACED, file mới ghép riêng mục + precheck lại mục đó), `cancel` (DRAFT/RUNNING; run con QUEUED bị hủy ngay, run đang chạy dừng ở bước kiểm tra tiếp theo của executor).
- `matrix`: số liệu từ RECON_RUN_SUMMARY của CURRENT_RUN_ID + tỷ lệ khớp so với lần chạy DONE gần nhất kỳ trước; `build_zip`: 00_TONG_HOP (ma trận + Tham số + File) + file riêng từng mục DONE (giống hệt export của run), cache theo danh sách CURRENT_RUN_ID.
- Executor: kiểm tra batch CANCELLED khi nhận job + sau READ + sau COMPARE (run con → CANCELLED, xóa hàng đợi); `sync_batch_status` map run con CANCELLED → mục NOT_RUN; worker `reset_stale_jobs` đã đồng bộ từ bước 6.
- Kiểm tra: `tests/unit/test_batch_rerun.py` 12 pass + `tests/unit/test_batch_zip_export.py` 6 pass; typecheck 21 = baseline; lint sạch.
- Ghi chú: xem decisions.md (retry_failed không yêu cầu xác nhận PROD lại; replace_files không đổi trạng thái batch; VIEWER không có menu batch_run theo spec 11 nên không xem/tải .zip dù spec 10 §7 ghi có).

### Bước 6 — Precheck, start, worker giới hạn song song (06/11/2026)
- `batch_run.precheck` (song song tối đa 4 luồng): template, tham số, đọc/gộp file, control total từng file, dòng ngoài kỳ, dòng không hợp lệ, kết nối DS (cache theo DS); ghi PRECHECK_JSON + READY/WARN/ERROR.
- `batch_run.start`: PROD xác nhận một lần (PROD_CONFIRM_REQUIRED + PROD_CONFIRMED_BY), tạo run con QUEUED (version Active lúc chạy, tham số từ PARAMS_RESOLVED_JSON, ATTEMPT_NO+1) + enqueue; WARN chạy theo include_warn, ERROR/PENDING → NOT_RUN, mục không file: bắt buộc NOT_RUN / không bắt buộc SKIPPED/NO_FILE; đồng bộ DONE/PARTIAL ngay sau start.
- `sync_batch_status`: mục theo run con, batch DONE khi mọi mục DONE/SKIPPED, PARTIAL khi có FAILED hoặc NOT_RUN bắt buộc.
- `dialect.claim_next_queued_job`: giới hạn song song theo DS (đếm queue PROCESSING cùng batch+DS, so với MAX_PARALLEL_PER_DS) + thứ tự PRIORITY/SEQ_NO/ENQUEUED_AT; Oracle chọn ứng viên rồi khóa dòng queue (FOR UPDATE SKIP LOCKED).
- Executor: run con batch nạp tập file (`load_excel_files_to_temp`) + `run_pipeline(excel_files=...)`, mục → RUNNING khi bắt đầu, đồng bộ batch khi xong (cả DONE lẫn FAILED); worker `reset_stale_jobs` cũng đồng bộ batch của run treo.
- Kiểm tra: `tests/unit/test_batch_precheck.py` 16 pass (gồm thực thi run con: DONE → batch DONE 184 khớp; FAILED → PARTIAL); `tests/unit/test_claim_job_batch.py` 4 pass + 1 skip Oracle; typecheck 21 = baseline; lint sạch.
- Ghi chú: xem decisions.md (mục PENDING không precheck thì NOT_RUN khi start; đếm PROCESSING thay vì RUNNING để tránh đua claim).

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