# Kế hoạch thực hiện TASK UI-03 — Admin Master–Detail

## Mục tiêu
Chuyển đổi 4 màn hình quản trị hệ thống (`/lookups`, `/users`, `/roles`, `/menus`) sang pattern **MASTER_DETAIL** chuẩn Fluent: `PageHeader` + `CommandBar` + `MasterDetailLayout` (Master bên trái chiếm `flex: 1` | Detail panel bên phải rộng 380–420px, viền trái, cuộn độc lập).
Triệt tiêu hoàn toàn lỗi **tràn ngang desktop** hiện có ở `/roles` (1410px) và `/menus` (1460px), chấm dứt việc cuộn dọc hàng nghìn pixel (`menus` cuộn 3017px, `roles` cuộn 1496px), loại bỏ modal dài che khuất bảng.

## Kế hoạch từng bước

### Bước 1: Lookups (`app/ui/pages/lookups.py`)
- Sử dụng `master_detail`:
  - Master (Trái): Danh sách Lookup Types (mã, tên, số lượng code, nút thêm type) trong flex container có internal scroll.
  - Detail (Phải): Panel hiển thị các Lookup Codes của Type đang chọn, form thêm/sửa code nhanh.
- Tích hợp `page_header` + `command_bar`.
- Chạy `pytest tests/unit/test_page_lookups.py`.

### Bước 2: Users (`app/ui/pages/users.py`)
- Sử dụng `master_detail`:
  - Master (Trái): Bảng người dùng compact sticky headers, internal scroll trong `dmc.Paper`.
  - Detail (Phải): Panel chi tiết thông tin người dùng được chọn + Form chỉnh sửa họ tên, email, checklist gán vai trò.
- Giữ nguyên các modal xác nhận ngắn (reset mật khẩu, khóa người dùng).
- Chạy `pytest tests/unit/test_page_users.py`.

### Bước 3: Roles & Permissions Matrix (`app/ui/pages/roles.py`)
- Khắc phục triệt để lỗi tràn ngang 1410px và cuộn 1496px:
  - Master (Trái): Danh sách các vai trò (Mã, Tên, Số user, Loại hệ thống, Trạng thái) trong bảng compact có sticky header.
  - Detail (Phải): Checklist phân quyền menu cho vai trò đang chọn (nhóm theo danh mục cha, các quyền con, nút "Lưu phân quyền").
- Triệt tiêu hoàn toàn ma trận HTML bảng tĩnh khổng lồ.
- Chạy `pytest tests/unit/test_page_roles.py`.

### Bước 4: Menus Administration (`app/ui/pages/menus.py`)
- Khắc phục triệt để lỗi tràn ngang 1460px và cuộn dọc 3017px:
  - Master (Trái): Cây danh sách phân cấp menu (Group, Tên menu, Đường dẫn, Icon, Badge Ẩn/Hiện) trong table scroll nội bộ.
  - Detail (Phải): Panel chỉnh sửa thuộc tính menu đang chọn (Tên hiển thị, Icon picker, thứ tự order, switch tạm ẩn/hiện, nút Lưu thuộc tính).
- Loại bỏ các modal dài, chỉnh sửa trực tiếp trên Detail panel.
- Chạy `pytest tests/unit/test_menus_page.py`.

### Bước 5: Regression Tests & Complete
- Chạy toàn bộ 75 unit tests của 4 trang.
- Chạy lint check (`ruff check`).
- Cập nhật tiến độ UI-03, tasks-dashboard, commit và push lên `feat/UI-03`.
