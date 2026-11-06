# ReconHub Dynamic Reporting Add-on

Gói đặc tả để AI triển khai task 21–28 sau task 19/20. Ba loại nguồn được hỗ trợ ngay: CUSTOM_SQL, VIEW, TABLE.

## Tích hợp
- Giải nén vào root dự án.
- Thêm task 21–28 vào docs/tasks/README.md theo thứ tự.
- Đặt preview vào designs/components/Screen16-DynamicReporting/preview.html nếu muốn giữ cấu trúc designs hiện tại.

## Prompt cho AI
Làm task 21-reporting-core theo skill lam-task. Đọc spec 12, tables, dataflow và preview. Lập plan, chỉ rõ migration, service interface, security boundary và test; chưa code khi chưa duyệt. Sau mỗi task chạy checklist task đó và toàn bộ hồi quy liên quan.
