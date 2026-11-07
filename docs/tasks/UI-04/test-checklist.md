# TEST CHECKLIST — TASK UI-04: Configuration Master–Detail

## 1. Functional Regression
- [ ] `/data-sources`:
  - [ ] Danh sách nguồn đối soát hiển thị đúng môi trường (DEV/UAT/PROD).
  - [ ] Chọn một nguồn: Form bên phải hiển thị host, port, service, user.
  - [ ] Nút "Thử kết nối" (Test connection) gọi đúng service và hiển thị badge Thành công / Thất bại.
  - [ ] Tab "Lưu trữ": Hiển thị dung lượng tạm, ngưỡng cảnh báo và danh sách lịch sử dọn dẹp.
- [ ] `/batches/<def_id>`:
  - [ ] Danh sách template con bên trái hiển thị đầy đủ.
  - [ ] Chọn một template con: Panel bên phải cho phép sửa thứ tự chạy, gán tham số.
  - [ ] Thêm template con vào bộ thành công.
  - [ ] Xóa template con khỏi bộ thành công.
- [ ] `/templates/<id>/diagram`:
  - [ ] Sơ đồ Mermaid render chính xác các bảng Excel, DB và phép so sánh.
  - [ ] Các nút thu phóng (Zoom In, Zoom Out, Reset 100%) hoạt động trơn tru.
  - [ ] Nút xuất SVG tải file về máy thành công.
- [ ] `/report-admin` (Kiểm tra từng substep):
  - [ ] **UI-04.1**: Danh sách báo cáo hiển thị, chọn báo cáo đổi ID đang xem.
  - [ ] **UI-04.2**: Thay đổi tên báo cáo, mô tả, chọn nguồn dữ liệu (TABLE/VIEW/CUSTOM_SQL), SQL guard validate không báo lỗi cú pháp hợp lệ.
  - [ ] **UI-04.3**: Thêm mới tham số động, đổi loại tham số (DATE, LOV...), cấu hình LOV tĩnh/động lưu thành công.
  - [ ] **UI-04.4**: Ánh xạ cột, định dạng hiển thị (Tiền tệ, Ngày tháng), cấu hình export lưu thành công.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [ ] `/data-sources`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/batches/<def_id>`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/templates/<id>/diagram`: `document.documentElement.scrollHeight <= innerHeight` (triệt tiêu 4132px về <= 768px).
- [ ] `/report-admin`: `document.documentElement.scrollHeight <= innerHeight` (triệt tiêu 831px về <= 768px).
- [ ] Nội dung các panel cuộn mượt mà độc lập khi form dài.

## 3. Code Cleanliness
- [ ] Toàn bộ 65 inline style `style={"whiteSpace": ...}` trong `data_sources.py` được dọn sạch.
- [ ] Không còn màu hex hardcoded trong `template_diagram.py` hay `batch_def_edit.py`.

## 4. Mobile Responsiveness (390×844)
- [ ] Không có horizontal page overflow trên cả 4 trang (`scrollWidth <= clientWidth`).
- [ ] Master và Detail tự động xếp dọc (stack).
- [ ] Sơ đồ diagram co vừa khung nhìn mobile và cho phép touch zoom.

## 5. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] `pytest tests/e2e/test_batch_def.py` PASS.
- [ ] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-04/`.

