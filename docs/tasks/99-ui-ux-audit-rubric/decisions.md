# Quyết định kỹ thuật — 99-ui-ux-audit-rubric

## D-01: Học tập và tinh chỉnh tiêu chuẩn kiểm toán UI/UX từ Meta Astryx
- **Bối cảnh**: Meta Astryx (`https://github.com/meta/astryx`) sở hữu bảng kiểm định Component Audit Rubric gồm 11 tiêu chí đánh giá chất lượng giao diện rất chặt chẽ dành cho hệ thống nội bộ quy mô lớn.
- **Quyết định**: ReconHub chắt lọc và chuyển hóa thành **ReconHub Audit Rubric 6 tiêu chuẩn**, tương thích 100% với phong cách Fluent Compact và stack Dash Mantine Components (DMC 2.x). Ghi chú rõ nguồn gốc tham khảo từ `meta/astryx` trong skill `ra-soat-ui`.

## D-02: Lựa chọn trang Mail Template Studio làm mẫu đối chiếu Before/After
- **Bối cảnh**: Cần một màn hình có độ phức tạp cao, đa tương tác để kiểm chứng hiệu quả thực tế của Rubric mới.
- **Quyết định**: Chọn `/mail-template-studio` vì tích hợp cả 3 phân vùng Master-Detail, nhiều trạng thái form và component con, giúp việc chụp ảnh so sánh Trước và Sau thể hiện rõ rệt sự nâng cấp về tính tinh xảo, khoảng cách và tính toàn vẹn trạng thái.
