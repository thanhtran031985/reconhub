# Quyết định — Task 41

- Padding chuẩn lấy theo `/report-admin` danh sách: `"8px 12px"` (trên/
  dưới 8px, trái/phải 12px).
- Không thêm `gap` vào root 5 trang: các trang đã có `mb="xs"` ở header/
  filter bar; thêm gap sẽ nhân đôi khoảng cách dọc.
- `/account` giữ padding trong `16px 20px` của vùng cuộn; chỉ thêm padding
  root + `mx="auto"` cho cột `maw=640` để canh giữa.
- Nhánh chưa đăng nhập của `/account` (`padding: 24px`) giữ nguyên.
- Không migration, không đổi nội dung/spacing nội bộ.
