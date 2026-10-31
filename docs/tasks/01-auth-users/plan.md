# Kế hoạch — 01-auth-users

Người dùng trên RECON_APP, đăng nhập, phân quyền 4 vai trò

## Chi tiết các bước thực hiện

### Bước 1 — ServiceResult, mã lỗi và Service Decorator
- **Mục tiêu:** Cung cấp lớp chuẩn hóa kết quả `ServiceResult[T]` theo Spec 05, bộ mã lỗi `ErrorCode` trong `app/schemas/errors.py`, và decorator `@service` tự động bắt ngoại lệ chưa lường trước chuyển thành `INTERNAL_ERROR` (kèm `request_id`), chuyển `pydantic.ValidationError` thành `VALIDATION_ERROR` với thông báo tiếng Việt có dấu.
- **File tạo / sửa:**
  - `app/schemas/errors.py`: Định nghĩa `ErrorCode` (enum/str constants theo Spec 05 mục 1) và `ServiceResult[T]` generic Pydantic model.
  - `app/schemas/__init__.py`
  - `app/services/__init__.py`: Decorator `@service` bọc mọi hàm nghiệp vụ, đảm bảo không có exception chưa bắt lọt ra UI.
  - `app/core/context.py`: Lớp `Ctx` (chứa `user_id`, `username`, `full_name`, `roles`) và hàm `require_role(ctx, *roles)`.
- **Test viết trước (TDD):**
  - `tests/unit/test_service_result.py`:
    - `@service` trả kết quả thành công `ok=True`, dữ liệu `data`.
    - `@service` khi gặp `ValidationError` tự động chuyển thành `VALIDATION_ERROR` tiếng Việt, kèm chi tiết `details` theo đường dẫn trường.
    - `@service` khi gặp lỗi bất ngờ tự động bắt lại, sinh `request_id`, log cảnh báo và trả về `INTERNAL_ERROR` không lộ stack trace.
    - `require_role`: Cho phép khi người dùng có vai trò phù hợp, ném lỗi có kiểm soát khi không có quyền.
- **Kiểm tra:** `uv run pytest tests/unit/test_service_result.py -v`

### Bước 2 — Băm mật khẩu + Login + Khóa tài khoản
- **Mục tiêu:** Cài đặt logic xác thực argon2id trong `app/core/auth.py`, ghi nhận nhật ký đăng nhập `RECON_LOGIN_LOG`, xử lý khóa tạm sau 5 lần sai liên tiếp (`LOGIN_MAX_FAILS=5`, `LOGIN_LOCK_MINUTES=15`), mở khóa khi hết giờ, thông báo lỗi chung bảo mật không làm lộ sự tồn tại của tài khoản.
- **File tạo / sửa:**
  - `app/core/auth.py`: Các hàm `hash_password`, `verify_password`, `needs_rehash`, và `authenticate_user(conn, username, password, ip) -> ServiceResult[Ctx]`.
- **Test viết trước (TDD):**
  - `tests/unit/test_auth_core.py`:
    - Băm mật khẩu bằng argon2id, kiểm tra đúng/sai mật khẩu, kiểm tra cờ `needs_rehash`.
    - Sai mật khẩu lần 1 đến 4: tăng `FAILED_COUNT`, trạng thái `LOGIN_FAILED`.
    - Sai mật khẩu lần 5: tài khoản chuyển sang `ACCOUNT_LOCKED`, `LOCKED_UNTIL` bằng thời điểm hiện tại + 15 phút.
    - Khi đang bị khóa: đăng nhập đúng mật khẩu vẫn bị từ chối với thông báo "Tài khoản tạm khóa đến HH:mm...".
    - Khi hết hạn khóa: tự động mở khóa, cho phép đăng nhập lại bình thường nếu đúng mật khẩu.
    - User không tồn tại và user sai mật khẩu đều trả thông báo chung: "Tên đăng nhập hoặc mật khẩu không đúng".
    - User bị tắt (`IS_ACTIVE='N'`): trả `ACCOUNT_INACTIVE` với thông báo "Tài khoản đã bị tắt. Liên hệ Admin".
    - Mọi lần đăng nhập (thành công hoặc thất bại) đều ghi 1 dòng vào `RECON_LOGIN_LOG`.
- **Kiểm tra:** `uv run pytest tests/unit/test_auth_core.py -v`

### Bước 3 — Quản lý phiên Flask & Hook before_request
- **Mục tiêu:** Cấu hình phiên làm việc Flask (`SESSION_HOURS=8`), kiểm tra `SESSION_VERSION` trong DB mỗi request (có cache bộ nhớ 60s để tránh quá tải CSDL), chặn mọi request chưa đăng nhập chuyển hướng về `/login` (ngoại trừ các endpoint cho phép), bảo vệ CSRF qua header `Origin` đối với các callback Dash `/_dash-update-component`, xử lý chuyển hướng bắt buộc `/login?step=change` khi tài khoản có cờ `MUST_CHANGE_PW='Y'`.
- **File tạo / sửa:**
  - `app/core/session.py`: Quản lý cookie phiên, lưu `user_id` và `session_version`, cơ chế cache xác thực `SESSION_VERSION`.
  - `app/routes/auth_routes.py`: Endpoint Flask `/login` (hỗ trợ POST đăng nhập), `/logout` (hủy phiên).
  - `app/ui/app.py`: Tích hợp hook `before_request` trên `server` Flask.
- **Test viết trước (TDD):**
  - `tests/integration/test_session_middleware.py`:
    - Truy cập trang chủ `/` khi chưa đăng nhập → chuyển hướng 302 về `/login`.
    - Truy cập endpoint công khai `/health`, `/assets/...` khi chưa đăng nhập → không bị chặn.
    - Đăng nhập thành công → tạo phiên hợp lệ, truy cập được trang chủ `/`.
    - Đổi mật khẩu hoặc tăng `SESSION_VERSION` trong DB → phiên cũ lập tức bị đăng xuất ở request kế tiếp.
    - Người dùng có cờ `MUST_CHANGE_PW='Y'` truy cập các trang khác → bị chuyển hướng về `/login?step=change`.
    - Gửi request callback `/_dash-update-component` với Origin lạ không khớp Host → nhận HTTP 403 Forbidden.
- **Kiểm tra:** `uv run pytest tests/integration/test_session_middleware.py -v`

### Bước 4 — Service User, bảo vệ LAST_ADMIN & Ghi Audit Log
- **Mục tiêu:** Xây dựng `app/services/user.py` và `app/core/audit.py` quản lý toàn diện vòng đời người dùng: danh sách, tạo mới, cập nhật họ tên/email/vai trò, bật/tắt, đặt lại mật khẩu, mở khóa, đổi mật khẩu cá nhân; bảo vệ bất biến `LAST_ADMIN` (không cho phép khóa/tắt/bỏ vai trò Admin duy nhất còn lại); ghi nhật ký `RECON_AUDIT_LOG` trong cùng transaction với mật khẩu luôn được che `***`.
- **File tạo / sửa:**
  - `app/core/audit.py`: Hàm `write_audit_log(conn, entity, entity_id, action, actor, old_data, new_data)`.
  - `app/schemas/user.py`: DTO Pydantic (`UserCreateDto`, `UserUpdateDto`, `UserDto`, `ChangePasswordDto`).
  - `app/services/user.py`: Toàn bộ các hàm service quản lý người dùng theo Spec 05 mục 2.
- **Test viết trước (TDD):**
  - `tests/unit/test_user_service.py`:
    - Tạo người dùng mới thành công, từ chối nếu username trùng (`USERNAME_EXISTS`), từ chối nếu mật khẩu rỗng (`PASSWORD_EMPTY`).
    - Chỉ tài khoản có vai trò `ADMIN` mới gọi được các hàm quản trị; vai trò `VIEWER` gọi vào nhận mã lỗi `FORBIDDEN`.
    - Không thể khóa hoặc bỏ vai trò `ADMIN` của Admin duy nhất còn hoạt động (`LAST_ADMIN`).
    - Đổi mật khẩu cá nhân: xác minh mật khẩu cũ, cập nhật hash mới, tắt cờ `MUST_CHANGE_PW`.
    - Mọi thao tác thay đổi người dùng đều ghi vào `RECON_AUDIT_LOG`, trong đó `PASSWORD_HASH` trong `old_json` và `new_json` luôn luôn là `"***"`.
- **Kiểm tra:** `uv run pytest tests/unit/test_user_service.py -v`

### Bước 5 — Lệnh CLI Quản trị & Seed dữ liệu mẫu
- **Mục tiêu:** Kích hoạt chức năng hoàn chỉnh cho `app/cli.py` (`create-admin`, `reset-password`, `seed` tạo 4 user mẫu đại diện cho 4 vai trò trong môi trường dev/test), đảm bảo tính idempotent (chạy `seed` nhiều lần không lỗi/không trùng).
- **File tạo / sửa:**
  - `app/cli.py`: Cài đặt logic cho `create-admin`, `reset-password`, `seed`.
- **Test viết trước (TDD):**
  - `tests/unit/test_cli.py`:
    - `create-admin`: Tạo tài khoản Admin đầu tiên thành công; nếu đã có Admin thì từ chối (trừ khi có cờ `--force`).
    - `reset-password`: Đặt lại mật khẩu thành công và bật cờ `MUST_CHANGE_PW='Y'`.
    - `seed`: Nạp đủ 4 tài khoản mẫu (`admin`, `to_user`, `operator`, `viewer`); chạy lần 2 vẫn thành công mà không tạo trùng lặp.
- **Kiểm tra:**
  - `uv run pytest tests/unit/test_cli.py -v`
  - `uv run python -m app.cli seed`

### Bước 6 — Giao diện Trang Đăng nhập, Đổi mật khẩu & Tài khoản
- **Mục tiêu:** Dựng giao diện trang `/login` (đăng nhập + bước đổi mật khẩu bắt buộc khi `step=change`), trang `/account` (đổi mật khẩu và xem thông tin cá nhân), trang `/forbidden` (thông báo không có quyền) theo đúng đặc tả Screen10; tích hợp menu người dùng tối thiểu (Tài khoản, Đăng xuất) trên thanh trên của ứng dụng.
- **File tạo / sửa:**
  - `app/ui/pages/login.py`: Form đăng nhập, căn giữa 400px trên nền `nav-bg`, xử lý callback đăng nhập, hiển thị thông báo lỗi/khóa tài khoản, bước đổi mật khẩu bắt buộc.
  - `app/ui/pages/account.py`: Màn hình tài khoản cá nhân, thông tin vai trò và form đổi mật khẩu.
  - `app/ui/pages/forbidden.py`: Trang báo lỗi 403 thân thiện.
  - `app/ui/layout.py`: Bổ sung Header tối thiểu chứa thông tin người dùng đang đăng nhập và menu Tài khoản / Đăng xuất.
- **Test viết trước (TDD):**
  - `tests/test_ui_auth.py`:
    - Khởi tạo layout các trang `/login`, `/account`, `/forbidden` không có exception.
    - Callback xử lý đăng nhập đúng trả kết quả chuyển hướng trang; đăng nhập sai hiển thị Alert báo lỗi.
- **Kiểm tra:**
  - `uv run pytest tests/test_ui_auth.py -v`
  - `uv run poe lint`
  - `uv run poe typecheck`
  - `uv run poe test`
