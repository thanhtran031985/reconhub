# Quyết định kiến trúc — 97-email-template-builder

## 1. Lưu trữ mẫu email
- Quyết định: Sử dụng bảng `RECON_EMAIL_TEMPLATE` với khóa chính `template_code` và cột phân loại `function_code`.
- Lý do: Cho phép mở rộng thêm bất kỳ chức năng gửi email nào trong tương lai (kết quả run, báo cáo, thông báo lỗi...) mà không cần thay đổi schema.

## 2. Cơ chế Fallback mặc định
- Quyết định: Khi một chức năng chưa có bản ghi cấu hình trong DB (hoặc người dùng bấm Khôi phục mặc định), hệ thống sẽ nạp mẫu mặc định chuẩn (Builtin Default Template) được khai báo tĩnh trong `app/engine/email_template.py`.
- Lý do: Đảm bảo độ tin cậy tuyệt đối (100% uptime) cho tính năng gửi email, không phụ thuộc hoàn toàn vào dữ liệu người dùng xóa hoặc sửa hỏng trong database.

## 3. Cú pháp token
- Quyết định: Cú pháp `{{tên_biến}}`, ví dụ `{{user_name}}`, `{{created_at}}`, `{{files_list}}`.
- Lý do: Cú pháp chuẩn, trực quan, thân thiện với người dùng và tương thích hoàn toàn với engine template tiêu chuẩn.
