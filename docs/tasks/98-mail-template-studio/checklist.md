# Checklist kiểm thử — 98-mail-template-studio

## 1. Kiểm thử chức năng (Functional Test Cases)
| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Tạo bảng DB và Migration Alembic | Tạo thành công 3 bảng trên SQLite/Oracle, 0 drift | ⬜ |
| **TC-FN-02** | Event Schema Registry | Trả đúng danh sách event, payload schema và samples | ⬜ |
| **TC-FN-03** | Validate Design JSON | Bắt đúng các lỗi thiếu tên, biến không tồn tại, table thiếu cột | ⬜ |
| **TC-FN-04** | Table-based HTML Renderer | Sinh HTML chuẩn `<table>`, không có script/iframe độc hại | ⬜ |
| **TC-FN-05** | Condition Evaluation | Ẩn/hiện component chính xác theo điều kiện (vd: failed > 0) | ⬜ |
| **TC-FN-06** | Tạo mới và Lưu nháp (Save Draft) | Lưu Design JSON, sinh version Draft v1 thành công | ⬜ |
| **TC-FN-07** | Kích hoạt phiên bản (Activate Version) | Chuyển version sang ACTIVE, chuyển version cũ sang ARCHIVED trong transaction | ⬜ |
| **TC-FN-08** | Gửi thử nghiệm (Test Send) | Gửi email có tiền tố `[TEST]` tới đúng email người thiết kế | ⬜ |
| **TC-FN-09** | Tương thích ngược với `/templates` | Trang xuất template tiêu thụ đúng Active Template từ Studio | ⬜ |

## 2. Kiểm thử giao diện & Tương tác (UI/UX Test Cases)
| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Bố cục 3 vùng (Library, Canvas, Property) | Khớp 100% bố cục của prototype `preview.html` | ⬜ |
| **TC-UI-02** | Thao tác kéo thả component vào canvas | Kéo thả mượt mà, định vị chính xác vị trí chèn | ⬜ |
| **TC-UI-03** | Thao tác component toolbar (Lên, Xuống, Nhân bản, Xóa) | Di chuyển và sao chép component tức thì | ⬜ |
| **TC-UI-04** | Chuyển đổi Desktop / Mobile Preview | Co dãn độ rộng canvas 600px vs 360px mượt mà | ⬜ |
| **TC-UI-05** | Bộ chọn dữ liệu thử (Scenario Selector) | Đổi scenario (Có lỗi, Thành công, Rỗng) cập nhật preview ngay | ⬜ |

## 3. Kiểm thử bảo mật & Kỹ thuật (Security & Regression)
| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ⬜ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ⬜ |
| **TC-REG-03** | `uv run poe security-check` | Đạt 6/6 bài kiểm tra bảo mật, sanitize XSS | ⬜ |
| **TC-REG-04** | `uv run poe schema-introspect --check` | 0 drift | ⬜ |
| **TC-REG-05** | `uv run poe test` | Toàn bộ test suite xanh | ⬜ |
