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

## Câu hỏi còn mở
- Kỳ khác tháng (quý, khoảng ngày)?
- Thông báo email/Teams khi xong?
