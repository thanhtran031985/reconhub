-- ReconHub – schema Oracle làm nơi lưu RECON_APP (đích chuyển từ SQLite, spec 08).
-- Chạy bằng user DBA. Môi trường test dùng RECON_APP_TEST; môi trường thật đổi thành RECON_APP.
CREATE USER RECON_APP_TEST IDENTIFIED BY "<mật khẩu>"
  DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO RECON_APP_TEST;
-- Sau khi tạo: ReconHub > Data Sources > tab Lưu trữ RECON_APP > Thêm đích Oracle,
-- nhập user/password ở trên, bấm Kiểm tra kết nối.
