# Screen08-DataSources

PRD C8, C10; task 02/08 (2 tab, dữ liệu tạm), task 13 (chuyển, bản lưu cũ). Chỉ ADMIN. Preview: tab Lưu trữ → Xem trước → Xóa 9 run (gõ XOA); Xóa bản lưu SQLite cũ (gõ tên file).

## Tab Nguồn đối soát
Bảng: Tên, Env, Host:port/Service, User, Schema mặc định, Kiểm tra gần nhất ("Chỉ đọc · ms" ok, "Có quyền ghi" warn, "Không kết nối được (kiểm tra VPN)" crit), Template dùng, Kiểm tra, Sửa.

## Tab Lưu trữ RECON_APP
- **DB đang dùng**: loại, file/host, phiên bản schema, dung lượng, người dùng/template/run, sao lưu gần nhất.
- **Dữ liệu tạm**: 3 KpiCard (dung lượng – warn khi vượt ngưỡng; run chưa kiểm tra; giữ quá N ngày), ngưỡng cảnh báo GB/ngày + Lưu ngưỡng, Alert "không tự xóa".
- **Xóa dữ liệu tạm theo điều kiện**: Template, Kiểm tra, Chạy từ/đến ngày, Người chạy, Xem trước → Alert kết quả + nút "Xóa n run" (danger) → hộp thoại gõ XOA. **Nhật ký xóa**: thời gian, phạm vi, số run, dòng đã xóa, giải phóng, người xóa.
- **Đích Oracle đã đăng ký**: script tạo schema (CodeBlock), Thêm đích; bảng.
- **Chuyển dữ liệu sang Oracle**: đích, phạm vi, Kiểm tra trước, gõ tên schema, tiến độ theo bảng.
- **Bản lưu SQLite cũ** (chỉ khi đã chạy trên Oracle): file, dung lượng, ngày chuyển, nút Xóa bản lưu (gõ đúng tên file).

## Drawer Thêm/Sửa
Mục đích, Môi trường, Tên, Host, Port, Service name, User (nhãn đổi theo mục đích), Mật khẩu (không hiển thị lại), Schema mặc định/đích, Timeout (mặc định 600 giây, qua VPN) và Số dòng tối đa (chỉ nguồn); Kiểm tra kết nối, Hủy, Lưu.

Banner cảnh báo dữ liệu tạm hiện ở đầu trang khi vượt ngưỡng. 4 trạng thái.
