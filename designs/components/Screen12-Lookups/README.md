# Screen12: Danh mục hệ thống

Route /lookups, ADMIN. Master 35%, Detail 65%, giữ ngôn ngữ thiết kế v4. Prototype tự chứa HTML/CSS/JS, dữ liệu mẫu local trong bộ nhớ; không thay cho code Dash production.

## Component Dash Mantine
- AppShell/NavLink theo v4; Master là Paper + TextInput + danh sách UnstyledButton; badge count và System.
- Detail: Group tiêu đề + Badge mã; TextInput tìm kiếm, Select trạng thái, Button thêm.
- Table cho danh mục nhỏ, AgGrid nếu nhiều; Switch active có label và lý do disabled.
- Modal type/code, TextInput, NumberInput, Select màu/icon, Switch, Badge preview dùng cùng adapter với bảng thật.
- Alert policy, Notifications aria-live, Skeleton, EmptyState, Alert lỗi + Thử lại.
- dcc.Interval 2 giây kiểm revision ở page cần lookup, không chạy lại đối soát.

## Trải nghiệm
Chọn nhóm trái để xem phải; nhóm đóng khóa thêm mã với lý do; mã System khóa tắt/xóa. Nhóm mở cho thêm/sửa/tắt. Xóa mã đã dùng mở hộp thoại đề xuất vô hiệu hóa; không tự tắt khi bấm Xóa. Mã chưa dùng xóa sau xác nhận. Tìm theo mã/nhãn, lọc active. Modal có preview màu/icon, key readonly khi sửa, lỗi dưới ô, Cancel/Esc, trả focus.

## Prototype
Chọn ISSUE_REASON để thử thêm mã và xóa ROUNDING (đã dùng). CURRENCY để thử xóa mã chưa dùng. Chuyển trạng thái mô phỏng tải/trống/lỗi bằng thanh trên. Mở dialog sửa, đổi nhãn/màu/icon để xem badge preview. Không có lưu bền, phân quyền hay audit thật.

## Áp dụng hướng dẫn UI UX Pro Max
Đã đọc tài liệu skill công khai, áp dụng checklist keyboard/focus, labels, contrast, badge có chữ, modal xác nhận, trạng thái tải/trống/lỗi, light/dark. CLI chưa chạy được vì tải repository bị chặn; bước UI task 17 yêu cầu chạy skill trên máy người dùng. Không tạo mới palette/font trái token v4.
