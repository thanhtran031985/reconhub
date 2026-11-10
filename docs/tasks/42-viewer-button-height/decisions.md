# Quyết định — Task 42

- Đổi nút Xem sang `size="sm"` thay vì hardcode `style height 36px`:
  đúng token Mantine, cao đúng bằng ô nhập mặc định sm (36px), không
  viết px trong page.
- Chỉ sửa nút Xem ở form tham số; nút "Xuất Excel" không nằm trong yêu
  cầu nên giữ nguyên.
- SQL guard `or org_code is null` là dữ liệu của người dùng (version
  SQL trong /report-admin), code không tự viết lại — chỉ hướng dẫn sửa.
