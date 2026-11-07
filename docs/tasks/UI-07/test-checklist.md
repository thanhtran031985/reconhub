# TEST CHECKLIST — TASK UI-07: System & Auth

## 1. Functional Regression
- [ ] `/login`:
  - [ ] Đăng nhập đúng username/password (`admin` / `admin123`) redirect thành công về `/`.
  - [ ] Đăng nhập sai mật khẩu: Hiển thị Alert báo lỗi tiếng Việt có dấu, không redirect.
  - [ ] Tài khoản bị đánh dấu `MUST_CHANGE_PW='Y'`: Tự động chuyển sang `/login?step=change`.
  - [ ] Đổi mật khẩu bắt buộc thành công: Cập nhật mật khẩu mới và redirect vào hệ thống.
- [ ] `/account`:
  - [ ] Hiển thị đúng thông tin: Username (font mono), Họ tên, Email, Danh sách vai trò.
  - [ ] Form đổi mật khẩu tự nguyện:
    - [ ] Nhập sai mật khẩu cũ: Báo lỗi "Mật khẩu hiện tại không đúng".
    - [ ] Nhập mật khẩu mới không khớp xác nhận: Báo lỗi xác nhận.
    - [ ] Nhập đúng: Cập nhật thành công, phiên cũ bị hủy.
- [ ] `/forbidden`:
  - [ ] Truy cập trực tiếp hiển thị màn hình 403 rõ ràng.
  - [ ] Click nút "Về trang chủ" chuyển đúng tới `/`.
- [ ] `/suspended`:
  - [ ] Khi một chức năng bị Admin tạm ẩn trong `/menus`, truy cập menu đó chuyển hướng đúng về `/suspended`.
  - [ ] Hiển thị lý do và nút điều hướng về trang chủ.
- [ ] `/logout`:
  - [ ] Kích hoạt đăng xuất xóa sạch session và cookie, chuyển hướng an toàn về `/login`.

## 2. Layout & Styling (1366×768 & 1440×900)
- [ ] `/login`: Thẻ đăng nhập căn giữa màn hình cả chiều dọc và ngang, không cuộn trang.
- [ ] `/account`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/forbidden`: Căn giữa, không cuộn trang.
- [ ] `/suspended`: Căn giữa, không cuộn trang.
- [ ] Không còn màu `#f8fafc` hardcoded trong mã nguồn.

## 3. Mobile Responsiveness (390×844)
- [ ] `/login`: Thẻ co về độ rộng `95vw`, các ô nhập liệu bấm được dễ dàng, không tràn ngang.
- [ ] `/account`: Hai khối xếp dọc hợp lý, không tràn ngang.
- [ ] `/forbidden` và `/suspended`: Không tràn ngang.

## 4. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] `pytest tests/unit/test_auth.py` PASS.
- [ ] Ảnh baseline AFTER đã lưu tại `artifacts/ui-migration/UI-07/`.

