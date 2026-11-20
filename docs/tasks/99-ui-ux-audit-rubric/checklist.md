# Checklist kiểm thử — 99-ui-ux-audit-rubric

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng & Chuẩn hóa Skill (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Cập nhật `.agents/skills/ra-soat-ui/SKILL.md` | Bổ sung đầy đủ bảng ReconHub Audit Rubric 6 tiêu chí và phần ghi chú tham khảo `https://github.com/meta/astryx` | ✅ |
| **TC-FN-02** | Chụp ảnh hiện trạng Before của `/mail-template-studio` | Đủ 4 ảnh ở 1440×900 và 1366×768 (Light & Dark) lưu vào `tests/e2e/__screens__/` | ✅ |
| **TC-FN-03** | Thêm EmptyState cho Panel Thuộc tính khi chưa chọn block | Hiển thị EmptyState thân thiện, không báo lỗi callback | ✅ |
| **TC-FN-04** | Tinh gọn form fields và viền Canvas Mail Studio | Form gọn gàng, viền sắc nét, không lỗi tương tác thuộc tính | ✅ |
| **TC-FN-05** | Chụp ảnh After và lập bảng so sánh Before vs After | Bảng đối chiếu minh bạch từng tiêu chí kèm ảnh minh họa | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Kiểm tra No-Scroll ở 1366×768 và 1440×900 | `document.documentElement.scrollHeight <= innerHeight` đạt yêu cầu, không cuộn toàn trang | ✅ |
| **TC-UI-02** | Kiểm tra chế độ Dark Theme | Màu sắc phân tầng rõ ràng, độ tương phản chữ/nền ≥ 4.5:1 | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy trong 162 source files | ✅ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ unit test liên quan pass 100% | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ các bài kiểm tra bảo mật tự động đạt | ✅ |
