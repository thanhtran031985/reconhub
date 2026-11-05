# Quyết định — 18-batch-run

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-04 | Một hệ thống nhiều file/tháng → MULTI_FILE + gộp | Người dùng xác nhận | spec 10 mục 5.6; EXCEL_LOAD theo FILE_SET_HASH |
| 2026-11-04 | Cùng kỳ cho cả bộ; khác kỳ chạy riêng | Người dùng xác nhận | spec 10 D2 |
| 2026-11-04 | Không phụ thuộc thứ tự | Người dùng xác nhận | spec 10 D3 |
| 2026-11-04 | Xuất file riêng trong .zip | Người dùng xác nhận | spec 10 mục 6 |
| 2026-11-04 | Bộ tham chiếu template, không sao chép | Tránh lệch cấu hình | spec 10 D5 |
| 2026-11-04 | CURRENT_RUN_ID không khai báo FK | Tránh tham chiếu vòng khi tạo/chép | spec 10a mục 7 |

## Câu hỏi còn mở
- Kỳ khác tháng (quý, khoảng ngày)?
- Thông báo email/Teams khi xong?
