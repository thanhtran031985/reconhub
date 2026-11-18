# Checklist kiểm thử — 96-smtp-email-export

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Lưu cấu hình SMTP trong `RECON_APP_SETTING` | Cấu hình được lưu thành công, mật khẩu được mã hóa Fernet | ✅ |
| **TC-FN-02** | Lấy cấu hình SMTP | Giải mã mật khẩu chính xác cho service, trên UI hiển thị placeholder/che mật khẩu | ✅ |
| **TC-FN-03** | Quyền quản trị SMTP settings | Chỉ ADMIN mới có quyền xem và sửa cấu hình SMTP | ✅ |
| **TC-FN-04** | Kiểm tra kết nối SMTP (Test email) | Gửi email thử nghiệm thành công tới địa chỉ test hoặc báo lỗi rõ ràng nếu sai host/port | ✅ |
| **TC-FN-05** | Dựng email MIME multipart kèm đính kèm (`mailer.py`) | Message có đủ Subject, From, To, Body HTML, file đính kèm đúng tên và Content-Type | ✅ |
| **TC-FN-06** | Gửi email danh sách template kèm file Excel (.xlsx) | Gửi mail thành công với file Excel đính kèm chính xác | ✅ |
| **TC-FN-07** | Gửi email danh sách template kèm file Word (.docx) và PDF (.pdf) | Gửi mail thành công với cả 2 file đính kèm chính xác | ✅ |
| **TC-FN-08** | Ghi nhận nhật ký kiểm toán (Audit log) | Ghi nhận hành vi `SEND_TEMPLATE_EMAIL` vào bảng `RECON_AUDIT_LOG` | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Khối cấu hình SMTP trên trang `/settings` | Hiển thị đầy đủ các input: Host, Port, Bảo mật, User, Pass, From; nút Lưu và nút Gửi thử | ✅ |
| **TC-UI-02** | Menu Xuất danh sách trên `/templates` | Có mục "Gửi qua Email" (icon mail) | ✅ |
| **TC-UI-03** | Modal Gửi qua Email trên `/templates` | Mở modal chọn định dạng file (Excel/Word/PDF), gợi ý email người dùng, cho phép sửa tiêu đề & nội dung | ✅ |
| **TC-UI-04** | Trạng thái loading khi gửi email | Nút gửi hiển thị trạng thái loading trong lúc gửi, thông báo toast thành công/lỗi khi kết thúc | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ✅ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ test suite xanh | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ kiểm tra bảo mật tự động đạt (zero leaks/injections) | ✅ |
| **TC-SEC-02** | Phân quyền truy cập (RBAC) | Cấu hình SMTP yêu cầu vai trò ADMIN (`require_role(ctx, Role.ADMIN)`) | ✅ |
| **TC-SEC-03** | Bảo vệ dữ liệu & Bí mật | Mật khẩu SMTP mã hóa Fernet, không hiển thị dạng rõ trên UI / log | ✅ |
