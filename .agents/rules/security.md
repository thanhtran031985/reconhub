---
trigger: model_decision
description: Áp dụng khi làm việc với đăng nhập, người dùng, phân quyền, mật khẩu, upload file, SQL nguồn hoặc log.
---

# Bảo mật

- Chi tiết ở `docs/specs/06_security_ops.md`.
- Mật khẩu người dùng: argon2id (argon2-cffi, tham số mặc định), không giới hạn độ phức tạp nhưng không được rỗng; so sánh qua `PasswordHasher.verify`; `check_needs_rehash` khi đăng nhập thành công.
- Đăng nhập: sai `LOGIN_MAX_FAILS` lần liên tiếp thì khóa `LOGIN_LOCK_MINUTES`; thông báo lỗi chung "Tên đăng nhập hoặc mật khẩu không đúng" (không lộ user có tồn tại hay không); phiên Flask `HttpOnly`, `SameSite=Lax`, hết hạn `SESSION_HOURS`; đổi `SESSION_VERSION` của user khi đổi/đặt lại mật khẩu hoặc khóa để vô hiệu phiên cũ.
- Kiểm quyền trong service (`require_role(ctx, …)`), không dựa vào việc ẩn nút; callback Dash có thể bị gọi trực tiếp qua `/_dash-update-component`. Flask `before_request` chặn request chưa đăng nhập (trừ /login, /health, /assets).
- Mật khẩu Data Source: Fernet bằng `RECON_SECRET_KEY`; không trả về service, không đưa vào component, Store, log, audit.
- Upload: tối đa 50MB, kiểm phần mở rộng + magic bytes, chống zip bomb, không mở macro.
- SQL nguồn: user chỉ đọc, timeout, giới hạn dòng, bind param, whitelist định danh.
- Log JSON không chứa giá trị dữ liệu nghiệp vụ, SQL kèm giá trị bind, mật khẩu.
