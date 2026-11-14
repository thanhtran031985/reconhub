# Task 94 — Báo run đối soát xong/lỗi qua Telegram cho người chạy

## Vấn đề
Khi run đối soát chạy xong (DONE) hoặc lỗi (FAILED), người chạy phải tự
mở app mới biết kết quả. Trung tâm thông báo trong app (task 78) đã báo
cho chủ run nhưng chỉ hiện trong app (chuông + trang /notifications).
Người dùng muốn hệ thống gửi tin nhắn tới Telegram của chính người chạy
khi run xong (user chốt 14/11/2026).

## Mục tiêu
1. ADMIN cấu hình bot Telegram 1 lần trên trang /settings: token bot
   (lưu mã hóa) + username bot.
2. Mỗi người dùng liên kết Telegram của mình 1 lần trên trang /account:
   app cấp mã, người dùng nhắn `/start <mã>` cho bot, hệ thống lưu
   chat Telegram của họ.
3. Run đối soát DONE/FAILED → gửi tin Telegram cho chủ run (người ở
   `RECON_RUN.CREATED_BY`), đúng lúc run_executor báo trong app hiện tại:
   - DONE: `Run #1040 đã xong — Doanh thu Vtos, kỳ 2026-07: Khớp 604 ·
     Lệch 0 · Thiếu trong DB 6.114 · Thiếu trong Excel 469.`
   - FAILED: `Run #1040 lỗi — <lý do, cắt 500 ký tự>.`
   - Không kèm link (app chạy localhost, trên điện thoại bấm không mở được).
4. Nút "Gửi thử" trên /settings để ADMIN kiểm tra bot đã nối chưa.

## Phạm vi
- Chỉ run đối soát DONE/FAILED. Báo cáo (REPORT_RUN), export, batch
  để task sau.
- Chỉ gửi cho chủ run, không gửi cho ADMIN khác (khác với thông báo hệ thống).

## Ràng buộc
- Gửi Telegram không bao giờ làm hỏng run: mọi lỗi gửi chỉ ghi log,
  không raise, không chặn luồng chạy (như quy tắc emit của task 78).
- Không thêm package ngoài Stack: gọi Bot API bằng `urllib` chuẩn của
  Python.
- Bot chỉ gửi được cho người đã nhắn bot trước (quy tắc của Telegram) —
  người chưa liên kết thì không nhận được, không phải lỗi.
- Token bot là bí mật: lưu mã hóa Fernet như mật khẩu Data Source,
  không ghi vào log/audit, không hiện lại dạng rõ trên UI sau khi lưu.
- Không đổi hành vi thông báo trong app hiện tại: pref trong app và
  chuông /notifications giữ nguyên.
