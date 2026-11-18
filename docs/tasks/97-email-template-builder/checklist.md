# Checklist kiểm thử — 97-email-template-builder

Mục đích: Theo dõi danh sách test case chức năng, UI/UX và hồi quy kỹ thuật cho phân hệ Email Template Builder.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Migration bảng `RECON_EMAIL_TEMPLATE` | Tạo bảng thành công trên SQLite và Oracle, schema manifest cập nhật | ✅ |
| **TC-FN-02** | Parser & Render Token (`email_template.py`) | Thay thế chính xác các placeholder `{{token}}` bằng dữ liệu context | ✅ |
| **TC-FN-03** | Xử lý token không tồn tại | Bỏ qua hoặc giữ nguyên không gây lỗi crash hệ thống | ✅ |
| **TC-FN-04** | Fallback về template mặc định | Khi chức năng chưa đăng ký template, tự động trả về built-in default template | ✅ |
| **TC-FN-05** | Lưu cấu hình template tùy biến | Lưu thành công vào DB, ghi audit log `UPDATE_EMAIL_TEMPLATE` | ✅ |
| **TC-FN-06** | Khôi phục mẫu mặc định (Reset) | Đưa mẫu về trạng thái gốc của hệ thống thành công | ✅ |
| **TC-FN-07** | Tích hợp gửi mail danh sách template | Email thực tế gửi đi áp dụng đúng mẫu tùy biến đã lưu | ✅ |

---

## 2. Kiểm thử giao diện & Live Preview (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Tab "Mẫu Email" trên trang `/settings` | Hiển thị đầy đủ 3 phân vùng: Chức năng/Tokens, Khung soạn thảo, Live Preview | ✅ |
| **TC-UI-02** | Chèn thẻ dữ liệu (Token insertion) | Click vào badge token chèn chính xác `{{token}}` vào vị trí soạn thảo | ✅ |
| **TC-UI-03** | Khung Live Preview thời gian thực | Nội dung email xem trước tự động cập nhật ngay khi người dùng gõ phím | ✅ |
| **TC-UI-04** | Chuyển đổi giữa các chức năng | Đổi chức năng tự động nạp template và tokens tương ứng của chức năng đó | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy (0 issues) | ✅ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ test suite xanh | ✅ |
| **TC-REG-04** | `uv run poe security-check` | 6/6 bài kiểm tra bảo mật đạt | ✅ |
| **TC-REG-05** | `uv run poe schema-introspect --check` | Không có schema drift | ✅ |
