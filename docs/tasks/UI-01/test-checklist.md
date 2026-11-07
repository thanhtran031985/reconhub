# TEST CHECKLIST — TASK UI-01: Compact Lists

## 1. Functional Regression
- [ ] `/templates`:
  - [ ] Tìm kiếm template theo từ khóa hoạt động.
  - [ ] Lọc theo trạng thái hoạt động.
  - [ ] Click nút "Đăng ký mới" chuyển đúng tới `/templates/new`.
  - [ ] Các hành động trên từng dòng: Nhân bản, Xuất JSON, Lưu trữ, Xóa hoạt động bình thường.
- [ ] `/history`:
  - [ ] Tìm kiếm lịch sử run theo từ khóa hoạt động.
  - [ ] Bộ lọc trạng thái run (DONE, FAILED, RUNNING) lọc chính xác.
  - [ ] Chọn nhiều dòng checkbox và mở modal xóa hàng loạt (`history-bulk-purge-modal`) hoạt động.
  - [ ] Click xem chi tiết chuyển đúng tới `/runs/<id>`.
  - [ ] Click nút tải file kết quả tải đúng file từ Flask route.
- [ ] `/batches`:
  - [ ] Danh sách bộ đối soát hiển thị đầy đủ các cột: Mã, Tên, Số template, Trạng thái.
  - [ ] Click vào bộ chuyển sang `/batches/<id>`.
  - [ ] Modal tạo bộ đối soát mở và tạo thành công.
- [ ] `/report-runs`:
  - [ ] Danh sách lịch sử báo cáo hiển thị đúng thời gian, mã báo cáo, định dạng file.
  - [ ] Tải file báo cáo xuất ra hoạt động tốt.
- [ ] `/reports`:
  - [ ] Danh mục báo cáo hiển thị nhóm rõ ràng, tên báo cáo, mô tả.
  - [ ] Click chọn báo cáo chuyển đúng tới `/reports/<id>`.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [ ] `/templates`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/history`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 2181px về đúng viewport).
- [ ] `/batches`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/report-runs`: `document.documentElement.scrollHeight <= innerHeight`, không cuộn ngang.
- [ ] `/reports`: `document.documentElement.scrollHeight <= innerHeight`, không còn lưới Card lớn.
- [ ] Toàn bộ cuộn dữ liệu diễn ra bên trong AgGrid/ScrollArea.

## 3. Mobile Responsiveness (390×844)
- [ ] Cả 5 trang không có hiện tượng horizontal page overflow (`scrollWidth <= clientWidth`).
- [ ] `CommandBar` tự động wrap các nút thao tác xuống dòng hợp lý.
- [ ] AgGrid cho phép vuốt ngang nội bộ mượt mà.

## 4. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] Không đổi bất kỳ ID component nào liên quan đến callback.
- [ ] Không có console error / JavaScript exception trên browser.
- [ ] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-01/`.

