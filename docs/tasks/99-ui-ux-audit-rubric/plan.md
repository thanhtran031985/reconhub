# Kế hoạch thực hiện — 99-ui-ux-audit-rubric

Trạng thái: ⬜ Chờ duyệt
Nhánh: `feat/99-ui-ux-audit-rubric`

## Mục tiêu
Chuẩn hóa quy trình rà soát giao diện trong `.agents/skills/ra-soat-ui/SKILL.md` dựa trên 6 tiêu chí kiểm toán giao diện tinh gọn, và thực nghiệm tinh chỉnh trang Mail Template Studio (`/mail-template-studio`) kèm ảnh đối chiếu Trước / Sau.

## Các bước triển khai

### Bước 1: Cập nhật skill `.agents/skills/ra-soat-ui/SKILL.md`
- Soạn bảng Rubric 6 tiêu chí (Token Integrity, Frame-First & No-Scroll, Information Density, State Completeness, Micro-interactions & A11y, Dark Mode Consistency).
- Hướng dẫn quy trình chấm điểm và lập bảng đối chiếu.

### Bước 2: Chụp ảnh hiện trạng ban đầu (Before)
- Khởi động dev server, đăng nhập admin.
- Dùng script Playwright tự động chụp trang `/mail-template-studio`:
  - Kích thước 1440×900 (Light & Dark).
  - Kích thước 1366×768 (Light & Dark).
- Lưu vào `tests/e2e/__screens__/99-mail-studio-before-*.png`.

### Bước 3: Tinh chỉnh giao diện `/mail-template-studio`
- Viết unit test kiểm tra layout và callbacks mới.
- Thêm `EmptyState` cho Panel Thuộc tính khi chưa chọn khối nào trên Canvas.
- Tinh gọn padding/spacing các input controls của Panel Phải.
- Chuẩn hóa viền Canvas mô phỏng Email Client.
- Đảm bảo `scrollHeight <= innerHeight` tại 1366×768.

### Bước 4: Chụp ảnh sau khi chỉnh sửa (After) và Báo cáo đối chiếu
- Chụp ảnh mới tại cùng các kích thước và chế độ.
- Tạo bảng so sánh Before vs After chi tiết cho từng tiêu chí rubric.
