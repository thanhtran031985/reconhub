# Checklist Test Cases: 102-fastapi-sso

## 1. Dịch vụ FastAPI SSO Server
- [x] `TC-SSO-01`: Đăng nhập đúng username/password -> Cấp cookie `company_sso_session` và sinh code chuyển hướng về `redirect_uri`.
- [x] `TC-SSO-02`: Đăng nhập sai username/password -> Trả về lỗi 400 và không cấp code.
- [x] `TC-SSO-03`: Đã có cookie SSO hợp lệ -> Truy cập `/login` tự động cấp code chuyển hướng ngay (Single Sign-On).
- [x] `TC-SSO-04`: `redirect_uri` không nằm trong Whitelist -> Bị từ chối (400 Bad Request) chống Open Redirect.
- [x] `TC-SSO-05`: Mã code chỉ dùng được 1 lần (dùng lần 2 báo lỗi mã đã sử dụng).
- [x] `TC-SSO-06`: Mã code quá 60 giây -> Báo lỗi hết hạn.

## 2. ReconHub SSO Client & JIT Provisioning
- [x] `TC-REC-01`: Nhận code hợp lệ -> Gọi SSO xác thực thành công -> Tạo mới user trong `RECON_USER` và `RECON_USER_ROLE` (JIT).
- [x] `TC-REC-02`: User đã tồn tại -> Lấy vai trò hiện tại và cập nhật đăng nhập.
- [x] `TC-REC-03`: Gọi `login_session` cấp phiên Flask chuẩn, người dùng vào được trang chủ `/`.
- [x] `TC-REC-04`: Khi `SSO_ENABLED=False` -> Nút SSO tự động ẩn trên giao diện `/login`, chuyển hướng về `/login` nếu truy cập trực tiếp route.

## 3. Giao diện Flow SSO
- [x] `TC-UI-01`: Truy cập `/sso-flow` -> Render đầy đủ sơ đồ Mermaid theo ảnh minh họa của người dùng.
- [x] `TC-UI-02`: Nút sao chép mã Mermaid và thẻ thông số cấu hình hoạt động bình thường.
