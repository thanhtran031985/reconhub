# 18-batch-run — Bộ đối soát và chạy nhiều template một lần

- Ngày tạo: 2026-11-04
- Giai đoạn: GĐ3 (có thể làm ngay sau task 12)
- Phụ thuộc: 07-run-queue-worker, 12-export-history; 13-metadata-migration cho bước 10
- Nhánh git: feat/18-batch-run

## Mục tiêu
Khai báo một lần nhóm template (Bộ đối soát) cùng mẫu tên file, gộp file, bắt buộc, tham số ghi đè có công thức theo kỳ. Mỗi kỳ, người dùng tải tất cả file một lần, hệ thống ghép file vào template, soát tham số, kiểm tra trước và chạy song song có giới hạn; xem kết quả tổng hợp, chạy lại run lỗi, tải .zip gồm file riêng từng template.

## Đọc trước
- docs/specs/10_batch_run.md (nghiệp vụ, quy trình, service, UI, test)
- docs/specs/10_batch_run_tables.md (bảng dữ liệu, migration, claim_job)
- designs/components/Screen13-BatchRun/README.md và preview.html
- Spec v4 liên quan: 02, 03, 04 (mục 1–4, 9, 10, 12), 05, 06, 08

## Phạm vi
- 5 bảng mới, cột mới ở RECON_RUN, RECON_EXCEL_LOAD, RECON_EXCEL_ROW
- Service batch_def, batch_run, batch_formula, batch_matcher
- Gộp nhiều file cho một template trong engine/executor
- Giới hạn song song theo Data Source trong worker
- 3 màn: Bộ đối soát (kèm hộp thoại Thêm template), Chạy bộ đối soát (5 bước), Kết quả lần chạy bộ
- Export .zip; audit; chuyển Oracle

## Ngoài phạm vi
Lịch chạy tự động; lấy file từ thư mục/SFTP/SharePoint; phụ thuộc thứ tự giữa template; kỳ khác nhau trong một lần chạy bộ; gộp chi tiết nhiều template vào một file; thay đổi thuật toán so sánh.

## Quyết định đã chốt
- Bộ tham chiếu template, dùng version Active mới nhất lúc chạy; run con ghi version.
- Cùng một kỳ cho cả bộ; template khác kỳ chạy riêng. Lệch vài ngày dùng công thức `{ky.tu±Nd}`.
- Template không phụ thuộc nhau. Song song tối đa `MAX_PARALLEL_PER_DS` (mặc định 2) mỗi Data Source.
- Một hệ thống nhiều file/tháng: cờ MULTI_FILE, gộp trước khi đọc, control total kiểm từng file.
- Xuất file riêng trong .zip + 1 file tổng hợp.
- Lỗi một mục không chặn mục khác.

## Các bước
### Bước 1 — Schema, migration và FILE_SET_HASH
- Làm: 5 bảng + cột mới (spec 10a), revision Alembic mới; migration tính FILE_SET_HASH, SOURCE_FILE_ID cho dữ liệu cũ
- Test viết trước: test_batch_migration.py: upgrade 2 lần, downgrade/upgrade, dữ liệu run cũ vẫn đọc được, UQ, CK
- Kiểm tra: `uv run poe test`

### Bước 2 — Công thức và ghép file (hàm thuần)
- Làm: app/services/batch_formula.py, batch_matcher.py
- Test viết trước: test_batch_formula.py, test_batch_matcher.py (ca ở spec 10 mục 13)
- Kiểm tra: `uv run poe test`

### Bước 3 — Service bộ đối soát
- Làm: batch_def: CRUD, add/remove item, addable_templates, preview_params, quyền, audit, ROW_VERSION
- Test viết trước: test_batch_def_service.py
- Kiểm tra: `uv run poe test`

### Bước 4 — Lần chạy bộ: tạo, tải file, ghép, tham số
- Làm: batch_run: create, add_files (.zip an toàn), assign/ignore/skip, set_param_override
- Test viết trước: test_batch_run_draft.py, test_batch_zip_security.py
- Kiểm tra: `uv run poe test`

### Bước 5 — Gộp nhiều file trong engine/executor
- Làm: reader đọc nhiều file, __source_file, control total từng file, EXCEL_LOAD theo FILE_SET_HASH, EXCEL_ROW_NOS dạng {f,r}
- Test viết trước: golden G14_merge_files; test_excel_load_fileset.py
- Kiểm tra: `uv run poe test`

### Bước 6 — Precheck, start, worker giới hạn song song
- Làm: precheck song song, start tạo run con, claim_job giới hạn theo Data Source + ưu tiên, cập nhật trạng thái batch
- Test viết trước: test_batch_precheck.py, test_claim_job_batch.py (SQLite 2 process; Oracle skip nếu thiếu biến)
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN)

### Bước 7 — Chạy lại, thay file, hủy, ma trận, .zip
- Làm: retry_failed, rerun_item, replace_files, cancel, matrix, build_zip (cache)
- Test viết trước: test_batch_rerun.py, test_batch_zip_export.py
- Kiểm tra: `uv run poe test`

### Bước 8 — UI: Bộ đối soát và hộp thoại thêm template
- Làm: pages/batch_defs.py, batch_def_edit.py theo Screen13
- Test viết trước: e2e test_batch_def.py
- Kiểm tra: `uv run poe test`; `uv run poe e2e`

### Bước 9 — UI: Wizard chạy bộ và kết quả
- Làm: pages/batch_run_wizard.py, batch_run_result.py; menu; lịch sử thêm lọc lần chạy bộ
- Test viết trước: e2e test_batch_run.py (kịch bản spec 10 mục 13)
- Kiểm tra: `uv run poe test`; `uv run poe e2e`

### Bước 10 — Chuyển Oracle, tài liệu, hồi quy
- Làm: cập nhật metadata_migration theo spec 10 mục 12; USER_GUIDE; chạy toàn bộ test
- Test viết trước: test_batch_oracle_migration.py (VPN); toàn bộ golden không đổi
- Kiểm tra: `uv run poe test`; `uv run poe test-oracle` (VPN)

## Chấp nhận khi
- [ ] Tạo bộ, thêm template đã đăng ký (Active), gỡ template; Draft/Archived/đã có trong bộ không thêm được, có lý do.
- [ ] Công thức kỳ tính đúng (kể cả qua tháng, năm nhuận); biểu thức lạ bị chặn, không thực thi mã.
- [ ] Tải nhiều file và .zip; ghép theo mẫu tên, theo header, chọn tay; trùng tên/trùng nội dung được báo; zip slip/zip bomb bị chặn.
- [ ] Mục bắt buộc thiếu file chặn chạy (trừ khi Bỏ qua tháng này); mục nhiều file chỉ chấp nhận khi MULTI_FILE.
- [ ] Gộp 3 file cho kết quả bằng chạy 1 file đã nối tay (golden G14); header lệch báo đúng file.
- [ ] Precheck báo READY/WARN/ERROR; thay file và precheck lại riêng một mục.
- [ ] Chạy 20 mục: số run RUNNING mỗi Data Source không vượt giới hạn; một run lỗi không ảnh hưởng run khác; chạy lại run lỗi tạo run mới.
- [ ] Ma trận kết quả đúng số liệu RECON_RUN_SUMMARY; .zip gồm file tổng hợp + file riêng từng mục có kết quả.
- [ ] Đánh dấu kiểm tra / xóa dữ liệu tạm theo nhóm dùng service hiện có, đúng quyền.
- [ ] Tải lại trang giữa wizard không mất công việc (DRAFT lưu DB).
- [ ] 12 golden cũ không đổi; `uv run poe typecheck`, `lint`, `test`, `e2e` xanh; test Oracle chạy qua VPN hoặc ghi rõ chưa chạy.

## Câu hỏi mở
- Có cần nhập kỳ dạng khác tháng (quý, khoảng ngày tùy ý) không? Spec hiện chỉ hỗ trợ tháng.
- Có cần gửi email/Teams khi lần chạy bộ xong không? (để task thông báo sau)
