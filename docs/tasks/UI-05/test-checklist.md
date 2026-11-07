# TEST CHECKLIST — TASK UI-05: Template Wizard

## 1. Functional Regression Suite (7 Kịch bản bắt buộc)
- [ ] **Kịch bản 1 — Tạo mới Template (New)**:
  - [ ] Nhập mã template, tên template, chọn đơn vị thành công.
  - [ ] Upload file Excel mẫu DTP và kiểm tra hệ thống đọc được sheet/cột.
- [ ] **Kịch bản 2 — Chỉnh sửa Template có sẵn (Edit)**:
  - [ ] Mở `/templates/6/edit`: Dữ liệu cấu hình hiện tại nạp đầy đủ vào các bước.
  - [ ] Tự động chuyển trạng thái sang bản nháp (Draft) nếu template đang Active.
- [ ] **Kịch bản 3 — Chuyển bước kế tiếp (Next)**:
  - [ ] Nhấn "Tiếp theo": Kiểm tra validation bước hiện tại.
  - [ ] Nếu hợp lệ, chuyển sang bước tiếp theo mượt mà, Stepper cập nhật icon bước hoàn thành.
- [ ] **Kịch bản 4 — Quay lại bước trước (Back)**:
  - [ ] Nhấn "Quay lại": Quay lại bước trước đó mà không mất dữ liệu đã nhập ở các bước sau.
- [ ] **Kịch bản 5 — Lưu nháp (Save Draft)**:
  - [ ] Nhấn "Lưu nháp" thủ công: Hệ thống lưu vào DB và hiển thị thông báo thành công.
  - [ ] Tự động lưu nháp (`dcc.Interval` 30s) hoạt động khi có thay đổi.
- [ ] **Kịch bản 6 — Bắt lỗi hợp lệ (Validation Error)**:
  - [ ] Để trống trường bắt buộc hoặc nhập trùng mã: Hiển thị lỗi rõ ràng, không cho chuyển bước.
  - [ ] Nhập sai số âm hoặc công thức SQL không hợp lệ: SQL Guard bắt đúng lỗi.
- [ ] **Kịch bản 7 — Khôi phục bản nháp (Reload draft)**:
  - [ ] Đang sửa dở, refresh lại trang web: Hệ thống hỏi hoặc tự động khôi phục đúng dữ liệu nháp gần nhất.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [ ] `/templates/new`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 938px về <= 768px).
- [ ] `/templates/<id>/edit`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 1778px về <= 768px).
- [ ] Không có horizontal scroll ở khung nhìn desktop.
- [ ] Stepper cố định 1 hàng ở đỉnh, chiều cao <= 48px.
- [ ] Footer cố định ở chân trang, chiều cao <= 52px.
- [ ] Vùng nội dung các bước cuộn độc lập bên trong khi form dài.

## 3. Mobile Responsiveness (390×844)
- [ ] Không có horizontal page overflow (`scrollWidth <= clientWidth`).
- [ ] Stepper co gọn (hiển thị số bước hoặc thanh tiến độ).
- [ ] Nút điều hướng chân trang co giãn vừa vặn màn hình điện thoại.

## 4. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] `pytest tests/e2e/test_template_wizard_regression.py` PASS toàn bộ 7 kịch bản.
- [ ] Không có console error / JavaScript exception.
- [ ] Ảnh baseline AFTER đã lưu tại `artifacts/ui-migration/UI-05/`.

