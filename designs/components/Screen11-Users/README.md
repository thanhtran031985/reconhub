# Screen11-Users

PRD C12, task 08 (service task 01). Chỉ ADMIN.
- H1 đếm tài khoản, số đang tạm khóa. Lọc: tìm (username, họ tên, email), vai trò, trạng thái.
- Bảng: Username (mono), Họ tên, Email, Vai trò (chip plain, nhiều), Trạng thái (Hoạt động ok · Tạm khóa đến HH:mm warn · Đã tắt off · Chờ đổi mật khẩu info), Đăng nhập cuối; hành động Sửa, Đặt lại mật khẩu, Mở khóa (khi đang khóa).
- Drawer Thêm: Tên đăng nhập (quy tắc, không đổi sau khi tạo), Họ tên, Email, Vai trò (checkbox nhiều, bắt buộc ≥ 1), Mật khẩu ban đầu (không rỗng), Bắt đổi mật khẩu lần đầu (mặc định bật).
- Drawer Sửa: như trên trừ username/mật khẩu; khối Trạng thái: Tắt/Bật tài khoản (danger, hỏi xác nhận), Lịch sử đăng nhập (thời gian, kết quả, IP).
- Hộp thoại Đặt lại mật khẩu: mật khẩu mới, bắt đổi lần sau, thông báo phiên cũ bị đăng xuất và tài khoản được mở khóa.
- Không cho tắt/bỏ vai trò Admin của Admin cuối cùng: nút bị khóa kèm lý do.
- 4 trạng thái (trống = chỉ có tài khoản của bạn).
