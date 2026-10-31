# Screen10-Login

PRD C11, task 01. Trang không có AppShell, nền `nav-bg`, thẻ 400px ở giữa. Preview có 3 tab: Đăng nhập | Đổi mật khẩu bắt buộc | Tài khoản; thanh dưới: Bình thường, Đang tải (nút "Đang đăng nhập…"), Tạm khóa, Lỗi.
- **Đăng nhập**: logo, mô tả, Tên đăng nhập (mono, autocomplete username), Mật khẩu (`dmc.PasswordInput`), nút Đăng nhập rộng hết thẻ, ghi chú "Quên mật khẩu: liên hệ Admin". Lỗi chung: "Tên đăng nhập hoặc mật khẩu không đúng." (không lộ user có tồn tại). Khóa: "Tài khoản tạm khóa đến HH:mm do đăng nhập sai 5 lần…". Tài khoản đã tắt: "Tài khoản đã bị tắt. Liên hệ Admin."
- **Đổi mật khẩu bắt buộc** (`/login?step=change`, khi MUST_CHANGE_PW): lời chào, Mật khẩu mới, Nhập lại (lỗi khi không giống hoặc rỗng), Lưu và tiếp tục. Mật khẩu tự do, chỉ không được rỗng.
- **Tài khoản** (`/account`, trong AppShell ở code): tên đăng nhập, họ tên, vai trò, đăng nhập cuối; Đổi mật khẩu (hiện tại, mới, nhập lại), ghi chú đăng xuất phiên khác.
