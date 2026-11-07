# TEST CHECKLIST — TASK UI-04: Configuration Master–Detail

## 1. Functional Regression
- [x] `/data-sources`:
  - [x] Danh sách nguồn đối soát hiển thị đúng môi trường (DEV/UAT/PROD).
  - [x] Chọn một nguồn: Form bên phải hiển thị host, port, service, user.
  - [x] Nút "Thử kết nối" (Test connection) gọi đúng service và hiển thị badge Thành công / Thất bại.
  - [x] Tab "Lưu trữ": Hiển thị dung lượng tạm, ngưỡng cảnh báo và danh sách lịch sử dọn dẹp.
- [x] `/batches/<def_id>`:
  - [x] Danh sách template con bên trái hiển thị đầy đủ.
  - [x] Chọn một template con: Panel bên phải cho phép sửa thứ tự chạy, gán tham số.
  - [x] Thêm template con vào bộ thành công.
  - [x] Xóa template con khỏi bộ thành công.
- [x] `/templates/<id>/diagram`:
  - [x] Sơ đồ Mermaid render chính xác các bảng Excel, DB và phép so sánh.
  - [x] Các nút thu phóng (Zoom In, Zoom Out, Reset 100%) hoạt động trơn tru.
  - [x] Nút xuất SVG tải file về máy thành công.
- [x] `/report-admin` (Kiểm tra từng substep):
  - [x] **UI-04.1**: Danh sách báo cáo hiển thị, chọn báo cáo đổi ID đang xem.
  - [x] **UI-04.2**: Thay đổi tên báo cáo, mô tả, chọn nguồn dữ liệu (TABLE/VIEW/CUSTOM_SQL), SQL guard validate không báo lỗi cú pháp hợp lệ.
  - [x] **UI-04.3**: Thêm mới tham số động, đổi loại tham số (DATE, LOV...), cấu hình LOV tĩnh/động lưu thành công.
  - [x] **UI-04.4**: Ánh xạ cột, định dạng hiển thị (Tiền tệ, Ngày tháng), cấu hình export lưu thành công.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [x] `/data-sources`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/batches/<def_id>`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/templates/<id>/diagram`: `document.documentElement.scrollHeight <= innerHeight` (triệt tiêu 4132px về <= 768px).
- [x] `/report-admin`: `document.documentElement.scrollHeight <= innerHeight` (triệt tiêu 831px về <= 768px).
- [x] Nội dung các panel cuộn mượt mà độc lập khi form dài.

## 3. Code Cleanliness
- [x] Toàn bộ 65 inline style `style={"whiteSpace": ...}` trong `data_sources.py` được dọn sạch.
- [x] Không còn màu hex hardcoded trong `template_diagram.py` hay `batch_def_edit.py`.

## 4. Mobile Responsiveness (390×844)
- [x] Không có horizontal page overflow trên cả 4 trang (`scrollWidth <= clientWidth`).
- [x] Master và Detail tự động xếp dọc (stack).
- [x] Sơ đồ diagram co vừa khung nhìn mobile và cho phép touch zoom.

## 5. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] `pytest tests/e2e/test_batch_def.py` PASS.
- [x] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-04/`.

