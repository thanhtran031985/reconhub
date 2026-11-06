# Kế hoạch — 18-batch-run

_Duyệt ngày 06/11/2026. Người dùng duyệt theo đề xuất (Q0–Q4). Chép nguyên văn Implementation Plan đã duyệt._

## Cơ sở
- Nhánh mới `feat/18-batch-run`, đi từ `feat/28` hiện tại (máy trợ lý ở `ad98705`).
- Migration mới `0006_batch_run`; áp xong chạy `uv run poe db-migrate` rồi khởi động lại app.
- Menu "Chạy bộ đối soát" (`/batch-runs`) và "Bộ đối soát" (`/batches`) đã khai báo + seed quyền từ task 19; chỉ cần làm page.
- Mỗi bước: viết test trước (thấy đỏ) rồi code cho xanh; cập nhật `progress.md`; chạy `tasks-dashboard`.
- Làm xong cả 10 bước thì xuất một patch để người dùng áp + push.

## Các bước
### Bước 1 — Schema, migration và FILE_SET_HASH
5 bảng mới (`RECON_BATCH_DEF`, `RECON_BATCH_DEF_ITEM`, `RECON_BATCH_RUN`, `RECON_BATCH_RUN_ITEM`, `RECON_BATCH_RUN_FILE`) + cột `BATCH_RUN_ID`/`BATCH_RUN_ITEM_ID` ở `RECON_RUN`, `FILE_SET_HASH`/`SOURCE_FILES_JSON` ở `RECON_EXCEL_LOAD`, `SOURCE_FILE_ID` ở `RECON_EXCEL_ROW`; migration tính `FILE_SET_HASH` cho dữ liệu cũ.

### Bước 2 — Công thức và ghép file (hàm thuần)
`app/services/batch_formula.py` (công thức kỳ `{ky.tu}`, `{ky.den±Nd}`, `{ky.thang}`, `{ky.nam}`; chặn biểu thức lạ, không `eval`) và `batch_matcher.py` (chuẩn hóa tên file có dấu, khớp mẫu glob `*`/`|`).

### Bước 3 — Service bộ đối soát
`batch_def`: CRUD bộ, thêm/gỡ template (chỉ Active, chưa có trong bộ), `addable_templates`, `preview_params`, quyền theo bảng spec §7, audit, `ROW_VERSION`.

### Bước 4 — Lần chạy bộ: tạo, tải file, ghép, tham số
`batch_run`: create, add_files (.zip an toàn), assign/ignore/skip, set_param_override.

### Bước 5 — Gộp nhiều file trong engine/executor
Reader đọc nhiều file, `__source_file`, control total từng file, `EXCEL_LOAD` theo `FILE_SET_HASH`, `EXCEL_ROW_NOS` dạng `{f,r}`; golden mới G14.

### Bước 6 — Precheck, start, worker giới hạn song song
Precheck song song, start tạo run con, `claim_next_queued_job` giới hạn theo Data Source + ưu tiên, cập nhật trạng thái batch.

### Bước 7 — Chạy lại, thay file, hủy, ma trận, .zip
`retry_failed`, `rerun_item`, `replace_files`, `cancel`, `matrix`, `build_zip` (cache).

### Bước 8 — UI: Bộ đối soát và hộp thoại thêm template
`pages/batch_defs.py`, `batch_def_edit.py` theo Screen13; e2e `test_batch_def.py`.

### Bước 9 — UI: Wizard chạy bộ và kết quả
`pages/batch_run_wizard.py`, `batch_run_result.py`; menu; lịch sử thêm lọc lần chạy bộ; e2e `test_batch_run.py`.

### Bước 10 — Chuyển Oracle, tài liệu, hồi quy
Cập nhật `metadata_migration` theo spec 10 mục 12; USER_GUIDE; chạy toàn bộ test. Kiểm chứng Oracle cần VPN phía người dùng (như các task trước).

## Quyết định đã chốt (Q0–Q4)
- **Q0 — Kỳ:** chỉ hỗ trợ tháng `YYYY-MM` đúng spec. Kỳ khác tháng (quý, khoảng ngày tùy ý) để task sau.
- **Q1 — Thông báo khi xong:** không gửi email/Teams trong task 18, để task thông báo sau.
- **Q2 — Ai thấy lần chạy bộ của ai:** theo đúng owner scope của Lịch sử run hiện tại (chỉ người tạo + ADMIN thấy tất cả; OPERATOR chỉ thấy lần chạy mình tạo).
- **Q3 — Seed mẫu:** thêm `samples/batch/batch_def_sample.json` (bộ `DOANH_THU_CUOI_THANG` với template DTP mẫu) đúng spec 10a §9.
- **Q4 — Chạy trên Data Source PROD:** xác nhận một lần cho cả lần chạy bộ, liệt kê các Data Source PROD liên quan (theo spec §7).
