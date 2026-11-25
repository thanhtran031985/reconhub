# Checklist kiểm thử — 103-forgot-password-email

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Tạo token đặt lại mật khẩu cho user tồn tại có email | Sinh token thành công, lưu SHA-256 hash vào DB, gửi mail kèm URL | ✅ |
| **TC-FN-02** | Yêu cầu reset mật khẩu cho user không tồn tại, không có email hoặc tài khoản SSO | Trả về thông báo thành công chung (chống User Enumeration), không sinh token/gửi mail | ✅ |
| **TC-FN-03** | Xác thực token hợp lệ | Token hợp lệ, trả về thông tin user tương ứng | ✅ |
| **TC-FN-04** | Xác thực token quá hạn (hơn 20 phút) | Từ chối xác thực, báo lỗi token hết hạn | ✅ |
| **TC-FN-05** | Xác thực token đã sử dụng (`IS_USED = 'Y'`) | Từ chối xác thực, không cho phép tái sử dụng token | ✅ |
| **TC-FN-06** | Đặt lại mật khẩu mới thành công | Băm mật khẩu Argon2id, đánh dấu token `IS_USED='Y'`, tăng `SESSION_VERSION`, cập nhật `PW_CHANGED_AT`, mở khóa tài khoản | ✅ |
| **TC-FN-07** | Đăng nhập bằng mật khẩu mới sau khi reset | Đăng nhập thành công với mật khẩu mới, mật khẩu cũ bị từ chối | ✅ |
| **TC-FN-08** | Phiên đăng nhập cũ bị hủy tức thì sau khi reset mật khẩu | Xóa `_SESSION_CACHE` và tăng `SESSION_VERSION` khiến session cũ bị đá ra khỏi hệ thống | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Link "Quên mật khẩu?" trên trang `/login` | Bấm chuyển hướng mượt mà sang trang `/forgot-password` | ✅ |
| **TC-UI-02** | Giao diện trang `/forgot-password` | Form gồm 2 ô bắt buộc (Tên đăng nhập + Email), nút Gửi, tự khóa input/button và hiện progress bar khi đang xử lý, không hiện AppShell menu/header | ✅ |
| **TC-UI-03** | Giao diện trang `/reset-password` khi token hợp lệ | Hiển thị form nhập Mật khẩu mới + Xác nhận mật khẩu, nút Xác nhận đổi, không hiện AppShell | ✅ |
| **TC-UI-04** | Giao diện trang `/reset-password` khi token không hợp lệ / thiếu | Hiển thị Alert cảnh báo lỗi rõ ràng kèm nút "Quay lại đăng nhập" | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ✅ |
| **TC-REG-03** | `uv run poe e2e` & unit/integration liên quan | 38/38 E2E + 116/116 password-reset & Data Model + 19/19 auth/session/migration pass | ✅ |
| **TC-REG-04** | `uv run poe schema-introspect --check` | Manifest schema đồng bộ 100%, không drift | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | Không lưu plain-text token vào DB | DB chỉ lưu `TOKEN_HASH` (SHA-256), không thể đọc trộm token từ DB | ✅ |
| **TC-SEC-02** | Chống User Enumeration | Phản hồi giao diện đồng nhất, không tiết lộ user/email có tồn tại hay không | ✅ |
| **TC-SEC-03** | Ghi nhật ký kiểm toán `RECON_AUDIT_LOG` + `poe security-check` | Ghi nhận sự kiện `PASSWORD_RESET_SELF` với user/IP tương ứng; 6/6 security checks đạt | ✅ |
