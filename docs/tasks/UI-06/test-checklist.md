# TEST CHECKLIST — TASK UI-06: Batch & Run Wizards

## 1. Functional Regression
- [x] `/runs/new`:
  - [x] Chọn Template từ dropdown danh sách template Active hoạt động.
  - [x] Chọn khoảng ngày giờ `p_from`, `p_to` hoạt động; các nút tắt (Hôm nay, Hôm qua, 7 ngày trước) điền đúng giờ 00:00:00 và 23:59:59.
  - [x] Vùng upload: Kéo thả file Excel hoặc click chọn file tải lên thành công.
  - [x] Hệ thống tiền kiểm tra (Precheck): Đọc đúng số dòng, kiểm tra cột bắt buộc, phát hiện dòng ngoài khoảng ngày giờ nếu có.
  - [x] Chọn Data Source PROD: Modal cảnh báo mở ra yêu cầu xác nhận gõ đúng text trước khi chạy.
  - [x] Nhấn "Chạy đối soát": Tạo run thành công và tự động chuyển sang trang kết quả `/runs/<id>`.
- [x] `/batch-runs`:
  - [x] Chọn Bộ đối soát: Danh sách các template con hiển thị đầy đủ.
  - [x] Upload file cho từng template con trong bộ thành công.
  - [x] Tiền kiểm tra toàn bộ các file trong bộ chạy chính xác.
  - [x] Nhấn "Khởi chạy bộ": Tạo batch run và các run con trong hàng đợi thành công, chuyển sang `/batch-runs/<id>/result`.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [x] `/runs/new`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/batch-runs`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] Footer thanh điều hướng nằm cố định ở đáy màn hình.
- [x] Vùng upload và danh sách file kiểm tra cuộn nội bộ khi có nhiều file.

## 3. Mobile Responsiveness (390×844)
- [x] Không có horizontal page overflow (`scrollWidth <= clientWidth`).
- [x] Bộ chọn ngày giờ tự động co cột vừa màn hình di động.
- [x] Vùng upload file hiển thị nút chọn file rõ ràng trên màn hình cảm ứng.

## 4. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] `pytest tests/e2e/test_batch_run.py` PASS.
- [x] Tái sử dụng đúng `WizardShell` từ UI-00B / UI-05, không tạo component thừa.
- [x] Ảnh baseline AFTER đã lưu tại `artifacts/ui-migration/UI-06/`.

