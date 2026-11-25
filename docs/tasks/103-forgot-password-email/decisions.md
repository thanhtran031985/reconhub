# Quyết định kiến trúc — 103-forgot-password-email

- Ngày: 2026-11-24
- Quyết định:
  1. Sử dụng phương thức băm SHA-256 cho Reset Token khi lưu cơ sở dữ liệu (`RECON_PASSWORD_RESET_TOKEN.TOKEN_HASH`), token gốc sinh ngẫu nhiên qua `secrets.token_urlsafe(32)`.
  2. Thời hạn hiệu lực của Token là 20 phút.
  3. Khi đặt lại mật khẩu thành công, tăng `RECON_USER.SESSION_VERSION` lên 1 để tự động đăng xuất tất cả phiên đăng nhập cũ trên mọi thiết bị, đồng thời reset `FAILED_COUNT = 0` và `LOCKED_UNTIL = None`.
  4. Duy trì phản hồi đồng nhất (chống User Enumeration) tại trang yêu cầu quên mật khẩu.
