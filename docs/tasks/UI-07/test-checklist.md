# TEST CHECKLIST — TASK UI-07: System & Auth

## 1. Functional Regression
- [x] `/login`:
  - [x] Đăng nhập đúng username/password (`admin` / `admin123`) redirect thành công về `/`.
  - [x] Đăng nhập sai mật khẩu: Hiển thị Alert báo lỗi tiếng Việt có dấu, không redirect.
  - [x] Tài khoản bị đánh dấu `MUST_CHANGE_PW='Y'`: Tự động chuyển sang `/login?step=change`.
  - [x] Đổi mật khẩu bắt buộc thành công: Cập nhật mật khẩu mới và redirect vào hệ thống.
- [x] `/account`:
  - [x] Hiển thị đúng thông tin: Username (font mono), Họ tên, Email, Danh sách vai trò.
  - [x] Form đổi mật khẩu tự nguyện:
    - [x] Nhập sai mật khẩu cũ: Báo lỗi "Mật khẩu hiện tại không đúng".
    - [x] Nhập mật khẩu mới không khớp xác nhận: Báo lỗi xác nhận.
    - [x] Nhập đúng: Cập nhật thành công, phiên cũ bị hủy.
- [x] `/forbidden`:
  - [x] Truy cập trực tiếp hiển thị màn hình 403 rõ ràng.
  - [x] Click nút "Về trang chủ" chuyển đúng tới `/`.
- [x] `/suspended`:
  - [x] Khi một chức năng bị Admin tạm ẩn trong `/menus`, truy cập menu đó chuyển hướng đúng về `/suspended`.
  - [x] Hiển thị lý do và nút điều hướng về trang chủ.
- [x] `/logout`:
  - [x] Kích hoạt đăng xuất xóa sạch session và cookie, chuyển hướng an toàn về `/login`.

## 2. Layout & Styling (1366×768 & 1440×900)
- [x] `/login`: Thẻ đăng nhập căn giữa màn hình cả chiều dọc và ngang, không cuộn trang.
- [x] `/account`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/forbidden`: Căn giữa, không cuộn trang.
- [x] `/suspended`: Căn giữa, không cuộn trang.
- [x] Không còn màu `#f8fafc` hardcoded trong mã nguồn.

## 3. Mobile Responsiveness (390×844)
- [x] `/login`: Thẻ co về độ rộng `95vw`, các ô nhập liệu bấm được dễ dàng, không tràn ngang.
- [x] `/account`: Hai khối xếp dọc hợp lý, không tràn ngang.
- [x] `/forbidden` và `/suspended`: Không tràn ngang.

## 4. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] `pytest tests/unit/test_auth.py` PASS.
- [x] Ảnh baseline AFTER đã lưu tại `artifacts/ui-migration/UI-07/`.

