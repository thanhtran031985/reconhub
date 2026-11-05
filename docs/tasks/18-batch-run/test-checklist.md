# Checklist kiểm thử — 18-batch-run

Đối chiếu: docs/specs/10_batch_run.md, 10_batch_run_tables.md, task.md, Screen13. Loại: **A** tự động (pytest) · **E** E2E (Playwright) · **O** Oracle qua VPN · **M** kiểm tay.

Ca ưu tiên **Cao** phải đạt trước khi đóng task (skill `dong-task`). Ca **O** chưa chạy được thì ghi rõ trong progress.md, không đánh dấu đạt. Bản Excel cùng nội dung: `T18_Checklist_KiemThu.xlsx`.

Tổng: **131 ca** · Cao 87 · Trung bình 41 · Thấp 3 · A 99 · E 23 · O 7 · M 2

## 0. Chuẩn bị dữ liệu kiểm thử

_Bước task: —_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-00-01 | Bộ test gồm 5 template Active: DTP mẫu (MULTI_FILE=Y), 3 template giả 1 file, 1 template tùy chọn (IS_REQUIRED=N) | Seed SQLite tạm | Có sẵn để dùng cho mọi nhóm dưới | A | Cao |
| ☐ | T18-00-02 | Bộ file: 3 file DTP (mỗi file có dòng Tổng tiền), 1 file khớp 2 mẫu, 1 file không khớp mẫu, 1 file trùng tên, 1 file trùng nội dung khác tên, 1 file .zip hợp lệ, 1 zip slip, 1 zip bomb, 1 file thiếu cột bắt buộc | tests/fixtures/batch/ | Đủ fixture cho các ca ghép file, gộp, bảo mật zip | A | Cao |
| ☐ | T18-00-03 | Fetcher giả trả db.parquet cho từng template; 1 template giả lập mất kết nối ở lần chạy đầu | — | Chạy được toàn luồng không cần VPN | A | Cao |

## 1. Migration và schema

_Bước task: 1_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-01-01 | Upgrade head trên SQLite trống, chạy 2 lần | uv run poe db-migrate ×2 | Không lỗi; đủ 5 bảng mới và cột mới | A | Cao |
| ☐ | T18-01-02 | Downgrade về revision trước rồi upgrade lại | alembic downgrade -1; upgrade head | Không mất dữ liệu bảng cũ | A | Cao |
| ☐ | T18-01-03 | Migration trên DB đã có run cũ (1 file) | DB có 2 run G01 | FILE_SET_HASH và SOURCE_FILE_ID được điền; run cũ mở chi tiết dòng Excel vẫn đúng | A | Cao |
| ☐ | T18-01-04 | UQ_BDEF_ITEM_TPL | Thêm cùng template 2 lần vào 1 bộ bằng repo | Bị chặn bởi ràng buộc | A | Cao |
| ☐ | T18-01-05 | UQ_BRUN_FILE_NAME | Ghi 2 file cùng ORIGINAL_NAME trong 1 lần chạy | Bị chặn | A | Trung bình |
| ☐ | T18-01-06 | CK PERIOD_FROM ≤ PERIOD_TO, CK MAX_PARALLEL_PER_DS 1–4, CK PERIOD dạng YYYY-MM | Insert giá trị sai | Bị chặn | A | Trung bình |
| ☐ | T18-01-07 | Migration trên Oracle (RECON_APP_TEST) | uv run poe test-oracle | Upgrade/downgrade thành công | O | Trung bình |

## 2. Công thức tham số theo kỳ

_Bước task: 2_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-02-01 | {ky.tu}, {ky.den} kỳ 2026-10 | resolve | 01/10/2026 00:00:00 và 31/10/2026 23:59:59 | A | Cao |
| ☐ | T18-02-02 | Kỳ tháng 2 năm nhuận 2028-02 | resolve {ky.den} | 29/02/2028 23:59:59 | A | Cao |
| ☐ | T18-02-03 | {ky.tu-1d} kỳ 2026-01 (lùi qua năm) | resolve | 31/12/2025 00:00:00 | A | Cao |
| ☐ | T18-02-04 | {ky.den+3d} kỳ 2026-12 | resolve | 03/01/2027 23:59:59 | A | Trung bình |
| ☐ | T18-02-05 | {ky.thang}, {ky.nam} | resolve | 202610, 2026 | A | Cao |
| ☐ | T18-02-06 | {ky.thang+1d} | resolve | BATCH_FORMULA_INVALID | A | Trung bình |
| ☐ | T18-02-07 | Biểu thức lạ: {ky.xx}, {__import__('os')}, {ky.tu-40d}, chuỗi có { không đóng | resolve | BATCH_FORMULA_INVALID; không thực thi mã | A | Cao |
| ☐ | T18-02-08 | Thứ tự ưu tiên: ghi đè khi chạy > ghi đè trong bộ > mặc định template > {ky.tu}/{ky.den} | resolve_params với đủ 4 tầng | Lấy đúng tầng cao nhất | A | Cao |
| ☐ | T18-02-09 | Ép kiểu: p_from datetime nhận 'abc' | resolve_params | BATCH_PARAM_TYPE | A | Cao |
| ☐ | T18-02-10 | Tham số required rỗng sau khi tính | resolve_params | BATCH_PARAM_REQUIRED | A | Cao |
| ☐ | T18-02-11 | p_from > p_to sau khi tính; khoảng > max_range_days | resolve_params | Lỗi như run đơn lẻ (INVALID_RANGE / RANGE_TOO_LARGE) | A | Cao |

## 3. Ghép file theo tên

_Bước task: 2_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-03-01 | Chuẩn hóa tên có dấu, khoảng trắng, gạch ngang | 'Báo cáo DTP - T10.xlsx' | → BAOCAODTPT10 | A | Cao |
| ☐ | T18-03-02 | Mẫu nhiều nhánh *DTP*\|*HOA_DON* | Tên 'HOA_DON_T10.xlsx' | Khớp | A | Trung bình |
| ☐ | T18-03-03 | Khớp đúng 1 mục | 'DTP_BDP_T10.xlsx' | MATCHED, MATCH_BY=PATTERN | A | Cao |
| ☐ | T18-03-04 | Khớp nhiều mục | 'DEPOT_CFS_T10.xlsx' với *DEPOT* và *CFS* | AMBIGUOUS, có CANDIDATE_ITEM_IDS | A | Cao |
| ☐ | T18-03-05 | Không khớp mẫu nhưng khớp header | File tên lạ, header đủ detect_by_headers | MATCHED, MATCH_BY=HEADER | A | Cao |
| ☐ | T18-03-06 | Không khớp gì | 'BAO_CAO_TONG_HOP.xlsx' | UNMATCHED | A | Cao |
| ☐ | T18-03-07 | Không khớp mục đã gỡ (IS_ACTIVE=N) hoặc template Archived | Tên khớp mẫu của mục đó | Không ghép vào mục đó | A | Trung bình |

## 4. Tạo lần chạy, tải file, .zip

_Bước task: 4_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-04-01 | Tạo lần chạy với bộ ACTIVE, kỳ hợp lệ | batch_run.create | DRAFT; tạo đủ run item; mục template Archived → SKIPPED/TEMPLATE_ARCHIVED | A | Cao |
| ☐ | T18-04-02 | Tạo với bộ DRAFT/ARCHIVED | — | BATCH_NOT_ACTIVE | A | Cao |
| ☐ | T18-04-03 | Kỳ đã có lần chạy | Tạo lần 2 cùng bộ + kỳ | Cho tạo, trả cảnh báo; lần cũ không đổi | A | Trung bình |
| ☐ | T18-04-04 | File trùng tên trong cùng lần chạy | add_files 2 lần | Bỏ qua, BATCH_FILE_DUPLICATE | A | Cao |
| ☐ | T18-04-05 | File trùng nội dung khác tên | Cùng SHA-256 | Cảnh báo, cho giữ/bỏ | A | Trung bình |
| ☐ | T18-04-06 | Tải .zip hợp lệ có thư mục con | zip 5 file | 5 file vào lần chạy, ORIGINAL_NAME dạng ten.zip/duong/file.xlsx, FROM_ZIP_FILE_ID đúng | A | Cao |
| ☐ | T18-04-07 | Zip slip (../../x.xlsx) | — | BATCH_ZIP_INVALID; không ghi file ra ngoài thư mục tạm | A | Cao |
| ☐ | T18-04-08 | Zip bomb (giải nén > 1 GB) | — | BATCH_ZIP_INVALID trước khi giải nén hết | A | Cao |
| ☐ | T18-04-09 | Zip chứa file không phải xlsx/xls/csv, file ẩn | — | Bỏ qua các file đó, báo danh sách | A | Trung bình |
| ☐ | T18-04-10 | Vượt giới hạn: > 200 file, file > 50 MB, zip > 200 MB | — | Báo lỗi rõ, file hợp lệ khác vẫn nhận | A | Trung bình |
| ☐ | T18-04-11 | Chọn tay template cho file AMBIGUOUS/UNMATCHED | assign_file | MATCHED, MATCH_BY=MANUAL | A | Cao |
| ☐ | T18-04-12 | Bỏ file | ignore_file | IGNORED, không tính vào mục | A | Trung bình |
| ☐ | T18-04-13 | Mục bắt buộc thiếu file | — | Chặn sang bước 3 (BATCH_ITEM_MISSING_FILE) | A | Cao |
| ☐ | T18-04-14 | Bỏ qua tháng này cho mục bắt buộc | skip_item | SKIPPED/USER_SKIP, ghi SKIPPED_BY, audit | A | Cao |
| ☐ | T18-04-15 | Mục tùy chọn thiếu file | — | Tự SKIPPED/NO_FILE, không chặn | A | Cao |
| ☐ | T18-04-16 | ≥ 2 file vào mục MULTI_FILE=N | — | Chặn (BATCH_ITEM_TOO_MANY_FILES) | A | Cao |
| ☐ | T18-04-17 | Tải lại trang giữa bước 2 | Đóng/mở trình duyệt | File và ghép vẫn còn (DRAFT lưu DB) | E | Cao |

## 5. Gộp nhiều file (engine)

_Bước task: 5_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-05-01 | Golden G14: 3 file DTP gộp | Chạy mục MULTI_FILE với 3 file | Kết quả bằng chạy 1 file đã nối tay (đếm, tổng, khóa lệch) | A | Cao |
| ☐ | T18-05-02 | Header lệch giữa các file | File 2 thiếu cột Thành tiền | BATCH_MERGE_HEADER_MISMATCH chỉ đúng tên file, cột thiếu | A | Cao |
| ☐ | T18-05-03 | Control total kiểm từng file | File 2 dòng tổng sai | Cảnh báo đúng file 2; file 1, 3 vẫn khớp | A | Cao |
| ☐ | T18-05-04 | Cùng số hóa đơn ở 2 file, profile gộp | — | Cộng dồn vào 1 nhóm | A | Cao |
| ☐ | T18-05-05 | Cùng khóa ở 2 file, profile aggregate=false | — | DUPLICATE | A | Trung bình |
| ☐ | T18-05-06 | Chi tiết dòng Excel ở màn kết quả | Mở dòng lệch | Hiện 'tên file · dòng'; EXCEL_ROW_NOS dạng {f,r} | E | Cao |
| ☐ | T18-05-07 | EXCEL_LOAD dùng lại theo FILE_SET_HASH | Chạy lại cùng bộ file, cùng version | Không nạp lại; khác thứ tự upload vẫn cùng hash | A | Trung bình |
| ☐ | T18-05-08 | Run 1 file không thuộc bộ | Chạy như cũ | Không đổi hành vi, 12 golden cũ xanh | A | Cao |

## 6. Tham số khi chạy (bước 3)

_Bước task: 4_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-06-01 | Bảng hiện p_from, p_to và tham số khác cho mọi mục có file | — | Giá trị đã tính hiển thị dưới mỗi ô | E | Cao |
| ☐ | T18-06-02 | Sửa ô | set_param_override | Chỉ lưu PARAMS_RUN_OVERRIDE_JSON của run item; bộ và template không đổi; ô tô tím | A | Cao |
| ☐ | T18-06-03 | Về mặc định | Xóa ghi đè | Giá trị quay về tầng dưới | E | Trung bình |
| ☐ | T18-06-04 | Ô lỗi | Nhập {ky.xx} | Lỗi dưới ô, nút Tiếp khóa kèm lý do | E | Cao |

## 7. Kiểm tra trước (bước 4)

_Bước task: 6_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-07-01 | Mục hợp lệ | precheck | READY, PRECHECK_JSON có số dòng, control total | A | Cao |
| ☐ | T18-07-02 | Thiếu cột bắt buộc | — | ERROR | A | Cao |
| ☐ | T18-07-03 | Dòng ngoài kỳ > 0, control total lệch, dòng không hợp lệ | — | WARN kèm thông điệp | A | Cao |
| ☐ | T18-07-04 | Data Source không kết nối được | — | ERROR cho mọi mục dùng Data Source đó; chỉ thử kết nối 1 lần/Data Source | A | Trung bình |
| ☐ | T18-07-05 | Template bị Archive giữa bước 1 và bước 4 | — | ERROR | A | Trung bình |
| ☐ | T18-07-06 | Thay file cho mục ERROR | replace_files | File cũ REPLACED; precheck lại chỉ mục đó | A | Cao |
| ☐ | T18-07-07 | Bật/tắt 'Chạy cả mục có cảnh báo' | — | Nút ghi đúng số mục sẽ chạy | E | Cao |
| ☐ | T18-07-08 | Precheck không ghi dữ liệu tạm, không tạo run | Đếm RECON_EXCEL_ROW, RECON_RUN trước/sau | Không đổi | A | Cao |

## 8. Thực thi và worker

_Bước task: 6_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-08-01 | Bấm Chạy | start | Trong 1 transaction: batch RUNNING, tạo run con QUEUED có BATCH_RUN_ID/ITEM_ID, CURRENT_RUN_ID, ATTEMPT_NO=1 | A | Cao |
| ☐ | T18-08-02 | Mục ERROR, WARN bị loại | start include_warn=false | NOT_RUN với SKIP_REASON đúng | A | Cao |
| ☐ | T18-08-03 | Không có mục nào chạy được | — | BATCH_NOTHING_TO_RUN | A | Trung bình |
| ☐ | T18-08-04 | Data Source PROD | start không confirm | PROD_CONFIRM_REQUIRED; liệt kê các Data Source PROD | A | Cao |
| ☐ | T18-08-05 | Giới hạn song song | 20 run, 2 Data Source, MAX=2, 3 worker | Không lúc nào > 2 run RUNNING cùng Data Source trong 1 lần chạy bộ | A | Cao |
| ☐ | T18-08-06 | Run không thuộc bộ | Chạy cùng lúc | Không bị giới hạn bởi bộ | A | Trung bình |
| ☐ | T18-08-07 | Ưu tiên | PRIORITY khác nhau | Mục PRIORITY nhỏ được claim trước | A | Trung bình |
| ☐ | T18-08-08 | 1 run lỗi | Fetcher giả mất kết nối | Run đó FAILED; run khác DONE; batch PARTIAL | A | Cao |
| ☐ | T18-08-09 | SQLite 2 worker process + lưu nháp bộ khi worker đang ghi | — | Không 'database is locked' | A | Cao |
| ☐ | T18-08-10 | Đếm trạng thái batch | — | CNT_DONE/FAILED/SKIPPED/NOT_RUN khớp thực tế | A | Trung bình |
| ☐ | T18-08-11 | Rời trang khi đang chạy | Đóng tab, mở lại | Tiến độ vẫn cập nhật | E | Cao |
| ☐ | T18-08-12 | Hủy lần chạy bộ | cancel | QUEUED → CANCELLED; RUNNING dừng ở stage kế tiếp; không ghi kết quả dở | A | Trung bình |
| ☐ | T18-08-13 | Chạy thật trên Oracle test | Bộ 2 mục, ORACLE_TEST | Kết quả DTP như G01 | O | Trung bình |

## 9. Chạy lại và thay file

_Bước task: 7_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-09-01 | Chạy lại run lỗi | retry_failed | Tạo run mới, CURRENT_RUN_ID trỏ run mới, ATTEMPT_NO tăng; run cũ giữ trong lịch sử | A | Cao |
| ☐ | T18-09-02 | Thay file mục đã DONE | replace_files + rerun_item | Run mới với file mới; ma trận dùng run mới; cache .zip bị vô hiệu | A | Cao |
| ☐ | T18-09-03 | Thay file khi mục đang RUNNING | — | BATCH_RUN_BUSY | A | Trung bình |
| ☐ | T18-09-04 | Toàn vẹn CURRENT_RUN_ID | Sau mọi thao tác | CURRENT_RUN_ID luôn trỏ run có BATCH_RUN_ITEM_ID = chính item | A | Cao |

## 10. Kết quả lần chạy bộ và .zip

_Bước task: 7, 9_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-10-01 | Ma trận lấy số liệu từ RECON_RUN_SUMMARY của CURRENT_RUN_ID | So với màn kết quả từng run | Khớp từng cột | A | Cao |
| ☐ | T18-10-02 | KPI đầu trang | — | Khớp hết / Có lệch + tổng chênh / Lỗi-chưa chạy / Bỏ qua đúng | E | Cao |
| ☐ | T18-10-03 | So tháng trước | Có lần chạy DONE kỳ trước | Hiện chênh lệch tỷ lệ khớp; không có kỳ trước thì '—' | A | Trung bình |
| ☐ | T18-10-04 | Lọc, tìm | — | Lọc đúng; không ra kết quả có nút Xóa bộ lọc | E | Trung bình |
| ☐ | T18-10-05 | Tải .zip | build_zip | Tên <MA_BO>_<YYYYMM>_<ID>.zip; có 00_TONG_HOP + 1 file/mục có kết quả; mục lỗi/bỏ qua không có file nhưng có trong tổng hợp | A | Cao |
| ☐ | T18-10-06 | File con trong .zip | So với export của run | Giống hệt (sheet, cột, định dạng text cho mã) | A | Cao |
| ☐ | T18-10-07 | File tổng hợp | — | Có sheet Tham số và File | A | Trung bình |
| ☐ | T18-10-08 | Cache .zip | Tải 2 lần; rồi chạy lại 1 mục; tải lần 3 | Lần 2 dùng cache; lần 3 sinh mới | A | Trung bình |
| ☐ | T18-10-09 | Đánh dấu đã kiểm tra nhiều mục (có/không xóa dữ liệu tạm) | — | Gọi service hiện có cho từng run; chip cập nhật | E | Cao |
| ☐ | T18-10-10 | Xóa dữ liệu tạm hàng loạt | Gõ sai XOA / đúng XOA | Sai: không xóa; đúng: xóa, export vẫn tải được | E | Cao |
| ☐ | T18-10-11 | Lịch sử có lọc theo lần chạy bộ, run con có chip tên bộ | — | Hiển thị đúng | E | Thấp |

## 11. Bộ đối soát và hộp thoại Thêm template

_Bước task: 3, 8_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-11-01 | Tạo bộ, mã sai định dạng / trùng | — | Lỗi dưới ô | A | Cao |
| ☐ | T18-11-02 | Hộp thoại chỉ hiện template thêm được | Mặc định | Chỉ Active chưa có trong bộ | E | Cao |
| ☐ | T18-11-03 | Chọn 'Tất cả template' | — | Draft/Archived/Đã có trong bộ hiện mờ, checkbox khóa, có lý do | E | Cao |
| ☐ | T18-11-04 | Chi tiết template bên phải | Chọn 1 dòng | Mã, trạng thái, version Active, Data Source, profile, tham số mặc định (chỉ đọc) | E | Trung bình |
| ☐ | T18-11-05 | Mẫu tên file gợi ý sẵn, xóa trống rồi thêm | — | Chặn với thông báo thiếu mẫu | E | Cao |
| ☐ | T18-11-06 | Thêm 2 template | — | Bảng có 2 dòng chip 'Mới thêm'; phải bấm Lưu mới áp dụng | E | Cao |
| ☐ | T18-11-07 | Tham số ghi đè tên không có trong template | p_zzz=1 | BATCH_PARAM_UNKNOWN dưới ô | A | Cao |
| ☐ | T18-11-08 | Gỡ template chưa từng chạy / đã có lần chạy | remove_item | Chưa chạy: xóa dòng; đã chạy: IS_ACTIVE=N, lịch sử vẫn xem được | A | Cao |
| ☐ | T18-11-09 | Thêm lại template đã gỡ | — | Bật lại mục cũ, không tạo dòng trùng | A | Trung bình |
| ☐ | T18-11-10 | Template kích hoạt version mới sau khi vào bộ | — | Cột Version cập nhật; lần chạy sau dùng version mới | A | Cao |
| ☐ | T18-11-11 | Kích hoạt bộ khi còn mục thiếu mẫu / lỗi tham số | — | Bị chặn kèm danh sách lỗi | A | Trung bình |
| ☐ | T18-11-12 | Hai người cùng sửa bộ | ROW_VERSION cũ | STALE_DATA, không ghi đè | A | Trung bình |

## 12. Phân quyền

_Bước task: 3, 4_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-12-01 | Viewer: xem bộ, xem kết quả, tải .zip; không thấy nút tạo/chạy | — | Đúng; gọi service tạo/chạy → FORBIDDEN | A | Cao |
| ☐ | T18-12-02 | Operator: chạy bộ, đánh dấu kiểm tra; không sửa bộ, không xóa hàng loạt | — | Đúng; gọi service → FORBIDDEN | A | Cao |
| ☐ | T18-12-03 | Template Owner: sửa bộ, chạy; không xóa hàng loạt | — | Đúng | A | Cao |
| ☐ | T18-12-04 | Operator hủy lần chạy của người khác | — | FORBIDDEN; hủy lần chạy của mình được | A | Trung bình |
| ☐ | T18-12-05 | Gọi callback Dash trực tiếp bỏ qua UI | POST /_dash-update-component với user Viewer | Service chặn | A | Cao |

## 13. Audit

_Bước task: 3–7_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-13-01 | Mỗi thao tác ghi RECON_AUDIT_LOG cùng transaction | Tạo/sửa bộ, thêm/gỡ mục, bỏ qua mục, ghi đè tham số, bắt đầu chạy, chạy lại, thay file, hủy, tải .zip | Có bản ghi; rollback thì không có | A | Cao |
| ☐ | T18-13-02 | Audit bắt đầu chạy | — | Có danh sách mục chạy, mục không chạy và lý do | A | Trung bình |

## 14. Chuyển sang Oracle (spec 08)

_Bước task: 10_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-14-01 | Chép đủ 5 bảng mới, đúng thứ tự | Seed SQLite có 1 lần chạy bộ 5 mục | Số dòng khớp từng bảng | O | Cao |
| ☐ | T18-14-02 | Tham chiếu vòng | — | RECON_RUN.BATCH_RUN_ITEM_ID được cập nhật lại; CURRENT_RUN_ID đúng | O | Cao |
| ☐ | T18-14-03 | Phạm vi CONFIG_ONLY | — | Chỉ có BATCH_DEF, BATCH_DEF_ITEM | O | Trung bình |
| ☐ | T18-14-04 | Sau khi chạy trên Oracle | Mở kết quả lần chạy bộ cũ, chạy lần mới | Hoạt động; claim_job giới hạn song song đúng trên Oracle | O | Cao |

## 15. Giao diện, khả năng truy cập

_Bước task: 8, 9_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-15-01 | 4 trạng thái mỗi bảng (đang tải, trống, lỗi giữ dữ liệu cũ, bình thường) | Service giả | Đúng thiết kế Screen13 | E | Cao |
| ☐ | T18-15-02 | Bàn phím | Tab qua wizard, Enter/Space mở vùng upload, Esc đóng hộp thoại, focus trả về nút mở | Thao tác được không cần chuột | E | Cao |
| ☐ | T18-15-03 | Nút chính bị khóa luôn có lý do bên cạnh | — | Đúng ở cả 5 bước | E | Cao |
| ☐ | T18-15-04 | aria-live báo khi thêm file, chạy xong | — | Có thông báo | E | Trung bình |
| ☐ | T18-15-05 | 1440×900, 1366×768, 375px | — | Không tràn ngang; bảng cuộn trong khung | E | Trung bình |
| ☐ | T18-15-06 | Chế độ tối | — | Tương phản đạt, chip vẫn có chữ | M | Thấp |
| ☐ | T18-15-07 | So với preview.html | skill ra-soat-ui | Bảng khác biệt không có mục mức cao | M | Trung bình |

## 16. Hiệu năng

_Bước task: 6, 10_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-16-01 | Precheck 20 mục | Fetcher giả | ≤ 60 giây | A | Trung bình |
| ☐ | T18-16-02 | Tạo 20 run con khi bấm Chạy | — | ≤ 2 giây | A | Trung bình |
| ☐ | T18-16-03 | Lần chạy bộ 20 mục × 50.000 dòng, 2 worker | pytest -m bench | Ghi thời gian vào progress.md; không lỗi bộ nhớ | A | Thấp |
| ☐ | T18-16-04 | Lần chạy thật qua VPN 20 mục | Cuối tháng thử nghiệm | Ghi thời gian từng mục; không mục nào vượt timeout 600 giây | O | Trung bình |

## 17. Hồi quy

_Bước task: 10_

| ✓ | ID | Ca kiểm thử | Bước / dữ liệu | Kết quả mong đợi | Loại | Ưu tiên |
|---|---|---|---|---|---|---|
| ☐ | T18-17-01 | 12 golden case cũ (G01–G12) + G13 | uv run poe test-engine | Kết quả không đổi | A | Cao |
| ☐ | T18-17-02 | Luồng chạy 1 file (màn Chạy đối soát) | E2E cũ | Xanh | E | Cao |
| ☐ | T18-17-03 | Xóa dữ liệu tạm cũ (spec 04 mục 12) | Test cũ | Xanh; run con của bộ cũng áp dụng được | A | Cao |
| ☐ | T18-17-04 | typecheck, lint, test, e2e | uv run poe … | Tất cả xanh | A | Cao |

## Ghi nhận khi kiểm thử

| Ngày | Người | ID | Kết quả (Đạt / Không đạt / Chưa chạy) | Ghi chú, lỗi |
|---|---|---|---|---|
|  |  |  |  |  |
