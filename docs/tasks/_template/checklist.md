# Checklist kiểm thử — NN-slug

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** |  |  | ⬜ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** |  |  | ⬜ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ⬜ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ⬜ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ test suite xanh | ⬜ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ 6/6 kiểm tra bảo mật tự động đạt (zero leaks/injections) | ⬜ |
| **TC-SEC-02** | Phân quyền truy cập (RBAC) | Service gọi `require_role(ctx, ...)` đúng vai trò quy định | ⬜ |
| **TC-SEC-03** | Bảo vệ dữ liệu & Bí mật | Mật khẩu argon2id, kết nối Fernet, không leak ra UI/Store/log | ⬜ |
