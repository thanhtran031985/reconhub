# TEST CHECKLIST — TASK UI-02: Reports & Analytics

## 1. Functional Regression
- [x] `/` (Dashboard):
  - [x] Hiển thị chính xác 4 chỉ số KPI: Tổng số run, Run hoàn tất, Run lỗi, Tỷ lệ lỗi.
  - [x] Bảng tỷ lệ lệch theo template hiển thị đúng số liệu.
  - [x] Bảng 10 lần chạy gần nhất cho phép click xem chi tiết run.
  - [x] Bộ chọn tháng/năm cập nhật đúng dữ liệu dashboard.
- [x] `/runs/<id>`:
  - [x] Bảng kết quả đối soát nạp đúng các dòng khớp, lệch, thiếu DB, thiếu Excel.
  - [x] Các ô lệch giá trị có CSS class `rh-diff` hiển thị nổi bật.
  - [x] Bộ lọc trạng thái dòng (MISMATCH, MATCHED...) lọc tức thì.
  - [x] Click vào dòng mở đúng Drawer hiển thị chi tiết dòng dữ liệu thô.
  - [x] Nút "Đã kiểm tra xong" và modal xóa dữ liệu tạm hoạt động tốt.
  - [x] Nút "Xuất Excel" tạo file và tải về thành công.
- [x] `/batch-runs/<id>/result`:
  - [x] Hiển thị danh sách các template trong bộ và trạng thái tiến độ từng template.
  - [x] Click xem chi tiết từng template con hoạt động.
- [x] `/issues`:
  - [x] Danh sách chênh lệch tải đúng, lọc được theo lý do.
  - [x] Cập nhật lý do chênh lệch cho 1 dòng hoặc hàng loạt thành công.
- [x] `/reports/<id>`:
  - [x] Tab "Tham số": Nhập các tham số bắt buộc, chọn LOV dropdown, date picker hoạt động tốt.
  - [x] Click "Chạy báo cáo" chuyển sang Tab "Kết quả".
  - [x] Bảng kết quả render đúng các cột động từ metadata service.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [x] `/` (Dashboard): `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 1065px về <= 768px).
- [x] `/runs/<id>`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 2644px về <= 768px).
- [x] `/batch-runs/<id>/result`: `document.documentElement.scrollHeight <= innerHeight`.
- [x] `/issues`: `document.documentElement.scrollHeight <= innerHeight`.
- [x] `/reports/<id>`: `document.documentElement.scrollHeight <= innerHeight`.
- [x] Không có horizontal scroll ở khung nhìn desktop.

## 3. Formatting & Data Standards
- [x] Số tiền định dạng chuẩn: dấu chấm ngăn cách hàng nghìn (ví dụ: `24.114.547.250`), không hiện số thập phân thừa.
- [x] Cột số căn phải, font monospace tabular nums.
- [x] Thời gian định dạng chuẩn: `dd/MM/yyyy HH:mm:ss` giờ Việt Nam.
- [x] Khi chưa có dữ liệu hiển thị `—`, không hiển thị `0` hoặc chuỗi rỗng.

## 4. Mobile Responsiveness (390×844)
- [x] Không có horizontal page overflow trên cả 5 trang.
- [x] Dashboard: 4 KPI Cards co giãn hợp lý (xếp lưới 2x2 hoặc 1 cột).
- [x] Filter bar tự động xếp dọc.

## 5. Quality & Safety
- [x] `uv run poe lint` PASS.
- [x] `uv run poe typecheck` PASS.
- [x] `uv run poe test` PASS.
- [x] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-02/`.

