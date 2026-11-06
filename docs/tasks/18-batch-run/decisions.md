# Quyết định — 18-batch-run

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-04 | Một hệ thống nhiều file/tháng → MULTI_FILE + gộp | Người dùng xác nhận | spec 10 mục 5.6; EXCEL_LOAD theo FILE_SET_HASH |
| 2026-11-04 | Cùng kỳ cho cả bộ; khác kỳ chạy riêng | Người dùng xác nhận | spec 10 D2 |
| 2026-11-04 | Không phụ thuộc thứ tự | Người dùng xác nhận | spec 10 D3 |
| 2026-11-04 | Xuất file riêng trong .zip | Người dùng xác nhận | spec 10 mục 6 |
| 2026-11-04 | Bộ tham chiếu template, không sao chép | Tránh lệch cấu hình | spec 10 D5 |
| 2026-11-04 | CURRENT_RUN_ID không khai báo FK | Tránh tham chiếu vòng khi tạo/chép | spec 10a mục 7 |
| 2026-11-06 | Migration 0006 gộp bản nạp trùng nội dung trước khi đổi UQ | Upload không dedup theo SHA-256 nên cùng file có nhiều FILE_ID; UQ mới (FILE_SET_HASH, SHEET, TEMPLATE, VERSION) làm migration lỗi trên DB có 19 bản nạp trùng (dev DB: 19 load → 1). Giữ bản nạp ID nhỏ nhất, xóa dòng trùng, trỏ run sang bản nạp giữ lại | spec 10a §6 (backfill); bước 1 |
| 2026-11-06 | `load_excel_to_temp` dedup thêm theo FILE_SET_HASH (dùng lại bản nạp cùng nội dung dưới FILE_ID khác; cả đường purge và đường đua IntegrityError) | UQ mới chặn INSERT trùng nội dung; không sửa thì nạp lại file đã upload 2 lần sẽ lỗi INTERNAL_ERROR | spec 10a §6; bước 1 |
| 2026-11-06 | `_reused_response` đếm rows_valid thật trong RECON_EXCEL_ROW thay vì ROWS_READ - ROWS_INVALID | ROWS_READ còn tính dòng tổng control-total nên công thức cũ trả 201 thay vì 200 khi dùng lại bản nạp | bước 1 |
| 2026-11-06 | Cột FK trên bảng đã có thêm qua batch mode, không dùng `op.add_column` | SQLite không cho ADD COLUMN kèm REFERENCES | migration 0006 |
| 2026-11-06 | Kỳ chỉ tháng (Q0), không email/Teams (Q1), owner scope như Lịch sử run (Q2), seed mẫu (Q3), xác nhận PROD một lần (Q4) | Người dùng duyệt theo đề xuất ngày 06/11/2026 | plan.md |
| 2026-11-06 | `resolve_params` chỉ chặn p_from > p_to (INVALID_RANGE), không chặn max_range_days | Spec 10 §4.4 ghi "kiểm như run đơn lẻ"; run đơn lẻ đã bỏ chặn max_range_days (run_service.py) | spec 10 §4.4 |
| 2026-11-06 | `compute_file_set_hash` là hàm chung duy nhất (1 file = sha256(SHA256); nhiều file = sha256(danh sách đã sắp + sheet + template + version) | Tránh 2 công thức lệch nhau giữa migration backfill và runtime | spec 10a §6; bước 2 |
| 2026-11-06 | Thêm `activate_batch_def` dù spec 10 mục 8 không liệt kê | Spec 10a mục 1 yêu cầu điều kiện kích hoạt (≥1 mục, có mẫu file, không lỗi tham số kỳ hiện tại); không có hàm này thì bộ không bao giờ ACTIVE để chạy | spec 10a §1; bước 3 |
| 2026-11-06 | Không thêm/sửa/gỡ mục ở bộ đã ARCHIVED (BATCH_NOT_ACTIVE) | Bộ lưu trữ là đóng băng | bước 3 |
| 2026-11-06 | Thêm/sửa mục chỉ kiểm tham số lạ (BATCH_PARAM_UNKNOWN) + cú pháp công thức (BATCH_FORMULA_INVALID); lỗi kiểu lộ ở preview/chạy | Kiểu tham số phụ thuộc giá trị tính với kỳ thật | bước 3 |
| 2026-11-06 | RECON_BATCH_RUN dùng `CNT_ITEMS` (không phải `CNT_TOTAL`); RECON_BATCH_RUN_ITEM có `SEQ_NO` bắt buộc, không có `FILE_PATTERN` (mẫu nằm ở RECON_BATCH_DEF_ITEM, ghép phải join); RECON_BATCH_RUN_FILE có `NORMALIZED_NAME` bắt buộc, không có `IS_INCLUDED` (trạng thái IGNORED thay thế) | Schema bước 1 khác tên cột trong spec 10; service đọc đúng cột thật | bước 4 |
| 2026-11-06 | `add_files` tải 2 giai đoạn: (1) tải từng file lên RECON_FILE, mỗi lần một transaction riêng; (2) một transaction ghi RECON_BATCH_RUN_FILE + ghép | Gọi `upload_file` (tự mở transaction) trong `engine.begin()` của add_files gây "database is locked" trên SQLite | bước 4 |
| 2026-11-06 | Mục có template đã lưu trữ vẫn snapshot version/profile/Data Source như thường nhưng STATUS=SKIPPED/TEMPLATE_ARCHIVED | RECON_BATCH_RUN_ITEM.DATA_SOURCE_ID NOT NULL nên không thể để trống; version vẫn đọc được dù template đã lưu trữ | bước 4 |
| 2026-11-06 | Tạo lần chạy bộ lỗi NOT_FOUND khi template chưa cấu hình Data Source (cả ở bộ lẫn version) | Không có DS thì không thể chạy; lỗi nêu rõ template id để sửa cấu hình | bước 4 |
| 2026-11-06 | File .zip lưu vào RECON_FILE bằng helper riêng trong batch_run (chỉ kiểm magic `PK`), không dùng `upload_file` | `upload_file` chỉ nhận .xlsx/.xls/.csv, từ chối .zip | bước 4 |
| 2026-11-06 | File trong .zip không phải Excel/CSV hoặc vượt 50 MB được bỏ qua và báo trong `skipped`, không hủy cả .zip | Lỗi một file không hủy các file khác (spec 10 §9) | bước 4 |
| 2026-11-06 | Gộp file: EXCEL_ROWS_READ của 3 file (204) khác 1 file nối tay (202) vì mỗi file có 1 dòng tổng riêng — so sánh G14 bỏ qua EXCEL_ROWS_READ/DURATION_MS, chỉ so summary còn lại + từng dòng kết quả | Dòng tổng là dòng thô của từng file, không phải dữ liệu trùng | bước 5 |
| 2026-11-06 | `__row_nos` trong engine mang tên file (`{"f": tên, "r": dòng}`), executor đổi tên → file_id khi ghi RECON_RESULT_ROW qua SOURCE_FILES_JSON của bản nạp | Engine thuần không có file_id; tên hiển thị là cầu nối duy nhất (trùng basename trong .zip vẫn phân biệt được nhờ tên gốc "zip/thư mục/file") | bước 5 |
| 2026-11-06 | `load_excel_files_to_temp` không tái dùng `load_excel_to_temp` mà viết riêng theo FILE_SET_HASH (dùng lại/ghi lại bản purge/đua IntegrityError) | Đường 1 file có logic dedup theo FILE_ID; đường tập file phải key theo FILE_SET_HASH ngay từ đầu | bước 5 |
| 2026-11-06 | start() chỉ chạy mục READY (hoặc WARN khi include_warn); mục PENDING chưa precheck → NOT_RUN, không tự chạy | Precheck là bước bắt buộc trong luồng wizard (spec 10 §5.4 → §5.5); chạy mục chưa kiểm sẽ bỏ qua kiểm tra file/DS | bước 6 |
| 2026-11-06 | Giới hạn song song đếm hàng đợi PROCESSING cùng batch+DS, không đếm RECON_RUN STATUS='RUNNING' | Claim và đếm nguyên tử trong cùng transaction; run vừa claim chưa kịp chuyển RUNNING nên đếm RUNNING sẽ để 2 worker cùng vượt giới hạn | bước 6 |
| 2026-11-06 | Claim Oracle: chọn ứng viên bằng câu JOIN rồi khóa dòng queue riêng (FOR UPDATE SKIP LOCKED), không khóa trên câu JOIN | Oracle không cho FOR UPDATE trên câu truy vấn có JOIN phức tạp; 2 worker cùng chọn một ứng viên thì một bên khóa trượt và poll lại | bước 6 |
| 2026-11-06 | Thứ tự claim: PRIORITY/SEQ_NO của mục batch trước, run không thuộc bộ xếp sau (PRIORITY NULL = 999999) | Spec chỉ định thứ tự cho mục batch; run đơn lẻ vẫn được claim sau khi hết run batch chờ | bước 6 |

## Câu hỏi còn mở
- Kỳ khác tháng (quý, khoảng ngày)?
- Thông báo email/Teams khi xong?
