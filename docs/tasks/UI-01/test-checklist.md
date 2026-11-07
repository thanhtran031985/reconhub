# TEST CHECKLIST — TASK UI-01: Compact Lists

## 1. Functional Regression
- [x] `/templates`:
  - [x] Tìm kiếm template theo từ khóa hoạt động.
  - [x] Lọc theo trạng thái hoạt động.
  - [x] Click nút "Đăng ký mới" chuyển đúng tới `/templates/new`.
  - [x] Các hành động trên từng dòng: Nhân bản, Xuất JSON, Lưu trữ, Xóa hoạt động bình thường.
- [x] `/history`:
  - [x] Tìm kiếm lịch sử run theo từ khóa hoạt động.
  - [x] Bộ lọc trạng thái run (DONE, FAILED, RUNNING) lọc chính xác.
  - [x] Chọn nhiều dòng checkbox và mở modal xóa hàng loạt (`history-bulk-purge-modal`) hoạt động.
  - [x] Click xem chi tiết chuyển đúng tới `/runs/<id>`.
  - [x] Click nút tải file kết quả tải đúng file từ Flask route.
- [x] `/batches`:
  - [x] Danh sách bộ đối soát hiển thị đầy đủ các cột: Mã, Tên, Số template, Trạng thái.
  - [x] Click vào bộ chuyển sang `/batches/<id>`.
  - [x] Modal tạo bộ đối soát mở và tạo thành công.
- [x] `/report-runs`:
  - [x] Danh sách lịch sử báo cáo hiển thị đúng thời gian, mã báo cáo, định dạng file.
  - [x] Tải file báo cáo xuất ra hoạt động tốt.
- [x] `/reports`:
  - [x] Danh mục báo cáo hiển thị nhóm rõ ràng, tên báo cáo, mô tả.
  - [x] Click chọn báo cáo chuyển đúng tới `/reports/<id>`.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [x] `/templates`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/history`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 2181px về đúng viewport).
- [x] `/batches`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/report-runs`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [x] `/reports`: `document.documentElement.scrollHeight <= innerHeight`, không còn lưới Card lớn.
- [x] Toàn bộ cuộn dữ liệu diễn ra bên trong AgGrid/ScrollArea.

## 3. Mobile Responsiveness (390×844)
- [x] Cả 5 trang không có hiện tượng horizontal page overflow (`scrollWidth <= clientWidth`).
- [x] `CommandBar` tự động wrap các nút thao tác xuống dòng hợp lý.
- [x] AgGrid cho phép vuốt ngang nội bộ mượt mà.

## 4. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] Không đổi bất kỳ ID component nào liên quan đến callback.
- [x] Không có console error / JavaScript exception trên browser.
- [x] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-01/`.

