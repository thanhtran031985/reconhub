# Quyết định — 96-smtp-email-export

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-18 | Cấu hình máy chủ SMTP qua trang quản trị thay vì file `.env` | Người dùng yêu cầu quản trị linh hoạt từ UI, không cần restart server hay truy cập file cấu hình máy chủ | Thêm card cấu hình SMTP trong `/settings` |
| 2026-11-18 | Dùng `smtplib` và `email` chuẩn Python | Không cài thêm package ngoài stack theo AGENTS.md, hỗ trợ MIME multipart in-memory | Không phụ thuộc thư viện thứ 3 |
| 2026-11-18 | Mật khẩu SMTP mã hóa Fernet trong `RECON_APP_SETTING` | Đảm bảo an toàn bảo mật, tái sử dụng cơ chế của Telegram token | An toàn bảo mật |

## Câu hỏi còn mở
- Không.
