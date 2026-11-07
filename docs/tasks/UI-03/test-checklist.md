# TEST CHECKLIST — TASK UI-03: Admin Master–Detail

## 1. Functional Regression
- [ ] `/lookups`:
  - [ ] Danh sách Lookup Types bên trái tải đầy đủ.
  - [ ] Chọn một Lookup Type: Danh sách Codes tương ứng bên phải nạp tức thì.
  - [ ] Thêm mới Lookup Code thành công, danh sách cập nhật ngay không cần reload trang.
  - [ ] Xóa Lookup Code (qua modal xác nhận) thành công.
- [ ] `/users`:
  - [ ] Bảng người dùng bên trái hiển thị đúng username, họ tên, email, vai trò.
  - [ ] Chọn một người dùng: Panel chi tiết bên phải điền sẵn thông tin.
  - [ ] Sửa họ tên, email, thay đổi checkbox vai trò và click "Lưu" thành công.
  - [ ] Nút "Thêm người dùng" chuyển panel Detail sang chế độ tạo mới.
  - [ ] Nút "Đặt lại mật khẩu" mở đúng modal xác nhận và sinh mật khẩu mới.
  - [ ] Không thể xóa hoặc tắt vai trò Admin của admin cuối cùng (`LAST_ADMIN`).
- [ ] `/roles`:
  - [ ] Danh sách vai trò bên trái tải đủ: ADMIN, TEMPLATE_OWNER, OPERATOR, VIEWER và vai trò tùy biến.
  - [ ] Chọn một vai trò: Cây phân quyền menu bên phải hiển thị đúng trạng thái các checkbox menu.
  - [ ] Tích chọn / bỏ chọn quyền và click "Lưu phân quyền" thành công.
  - [ ] Kiểm tra user thuộc vai trò đó nhận được quyền mới sau khi cập nhật `PERM_REVISION`.
- [ ] `/menus`:
  - [ ] Cây phân cấp menu hiển thị đúng nhóm (Đối soát, Cấu hình, Quản trị).
  - [ ] Chọn một menu: Panel chi tiết bên phải cho phép sửa tên hiển thị, icon, thứ tự order.
  - [ ] Switch "Tạm ẩn menu" hoạt động: Menu chuyển sang trạng thái ẩn và sidebar cập nhật tương ứng.

## 2. Layout, Scroll & Overflow (1366×768 & 1440×900)
- [ ] `/roles`:
  - [ ] `document.documentElement.scrollWidth <= innerWidth` (đã triệt tiêu tràn ngang 1410px).
  - [ ] `document.documentElement.scrollHeight <= innerHeight` (đã triệt tiêu cuộn dọc 1496px).
- [ ] `/menus`:
  - [ ] `document.documentElement.scrollWidth <= innerWidth` (đã triệt tiêu tràn ngang 1460px).
  - [ ] `document.documentElement.scrollHeight <= innerHeight` (đã triệt tiêu cuộn dọc 3017px).
- [ ] `/users`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/lookups`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] Master và Detail cuộn độc lập bên trong khi danh sách dài.

## 3. Mobile Responsiveness (390×844)
- [ ] Không có horizontal page overflow trên cả 4 trang (`scrollWidth <= clientWidth`).
- [ ] Master và Detail tự động chuyển thành dạng xếp chồng dọc (stack) mượt mà.

## 4. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] `pytest tests/e2e/test_menus.py` PASS.
- [ ] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-03/`.

