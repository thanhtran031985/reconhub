# TEST CHECKLIST — TASK UI-03: Admin Master–Detail

## 1. Functional Regression
- [x] `/lookups`:
  - [x] Danh sách Lookup Types bên trái tải đầy đủ.
  - [x] Chọn một Lookup Type: Danh sách Codes tương ứng bên phải nạp tức thì.
  - [x] Thêm mới Lookup Code thành công, danh sách cập nhật ngay không cần reload trang.
  - [x] Xóa Lookup Code (qua modal xác nhận) thành công.
- [x] `/users`:
  - [x] Bảng người dùng bên trái hiển thị đúng username, họ tên, email, vai trò.
  - [x] Chọn một người dùng: Panel chi tiết bên phải điền sẵn thông tin.
  - [x] Sửa họ tên, email, thay đổi checkbox vai trò và click "Lưu" thành công.
  - [x] Nút "Thêm người dùng" chuyển panel Detail sang chế độ tạo mới.
  - [x] Nút "Đặt lại mật khẩu" mở đúng modal xác nhận và sinh mật khẩu mới.
  - [x] Không thể xóa hoặc tắt vai trò Admin của admin cuối cùng (`LAST_ADMIN`).
- [x] `/roles`:
  - [x] Danh sách vai trò bên trái tải đủ: ADMIN, TEMPLATE_OWNER, OPERATOR, VIEWER và vai trò tùy biến.
  - [x] Chọn một vai trò: Cây phân quyền menu bên phải hiển thị đúng trạng thái các checkbox menu.
  - [x] Tích chọn / bỏ chọn quyền và click "Lưu phân quyền" thành công.
  - [x] Kiểm tra user thuộc vai trò đó nhận được quyền mới sau khi cập nhật `PERM_REVISION`.
- [x] `/menus`:
  - [x] Cây phân cấp menu hiển thị đúng nhóm (Đối soát, Cấu hình, Quản trị).
  - [x] Chọn một menu: Panel chi tiết bên phải cho phép sửa tên hiển thị, icon, thứ tự order.
  - [x] Switch "Tạm ẩn menu" hoạt động: Menu chuyển sang trạng thái ẩn và sidebar cập nhật tương ứng.

## 2. Layout, Scroll & Overflow (1366×768 & 1440×900)
- [x] `/roles`:
  - [x] `document.documentElement.scrollWidth <= innerWidth` (đã triệt tiêu tràn ngang 1410px).
  - [x] `document.documentElement.scrollHeight <= innerHeight` (đã triệt tiêu cuộn dọc 1496px).
- [x] `/menus`:
  - [x] `document.documentElement.scrollWidth <= innerWidth` (đã triệt tiêu tràn ngang 1460px).
  - [x] `document.documentElement.scrollHeight <= innerHeight` (đã triệt tiêu cuộn dọc 3017px).
- [x] `/users`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/lookups`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] Master và Detail cuộn độc lập bên trong khi danh sách dài.

## 3. Mobile Responsiveness (390×844)
- [x] Không có horizontal page overflow trên cả 4 trang (`scrollWidth <= clientWidth`).
- [x] Master và Detail tự động chuyển thành dạng xếp chồng dọc (stack) mượt mà.

## 4. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] `pytest tests/e2e/test_menus.py` PASS.
- [x] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-03/`.

