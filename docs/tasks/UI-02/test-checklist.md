# TEST CHECKLIST — TASK UI-02: Reports & Analytics

## 1. Functional Regression
- [ ] `/` (Dashboard):
  - [ ] Hiển thị chính xác 4 chỉ số KPI: Tổng số run, Run hoàn tất, Run lỗi, Tỷ lệ lỗi.
  - [ ] Bảng tỷ lệ lệch theo template hiển thị đúng số liệu.
  - [ ] Bảng 10 lần chạy gần nhất cho phép click xem chi tiết run.
  - [ ] Bộ chọn tháng/năm cập nhật đúng dữ liệu dashboard.
- [ ] `/runs/<id>`:
  - [ ] Bảng kết quả đối soát nạp đúng các dòng khớp, lệch, thiếu DB, thiếu Excel.
  - [ ] Các ô lệch giá trị có CSS class `rh-diff` hiển thị nổi bật.
  - [ ] Bộ lọc trạng thái dòng (MISMATCH, MATCHED...) lọc tức thì.
  - [ ] Click vào dòng mở đúng Drawer hiển thị chi tiết dòng dữ liệu thô.
  - [ ] Nút "Đã kiểm tra xong" và modal xóa dữ liệu tạm hoạt động tốt.
  - [ ] Nút "Xuất Excel" tạo file và tải về thành công.
- [ ] `/batch-runs/<id>/result`:
  - [ ] Hiển thị danh sách các template trong bộ và trạng thái tiến độ từng template.
  - [ ] Click xem chi tiết từng template con hoạt động.
- [ ] `/issues`:
  - [ ] Danh sách chênh lệch tải đúng, lọc được theo lý do.
  - [ ] Cập nhật lý do chênh lệch cho 1 dòng hoặc hàng loạt thành công.
- [ ] `/reports/<id>`:
  - [ ] Tab "Tham số": Nhập các tham số bắt buộc, chọn LOV dropdown, date picker hoạt động tốt.
  - [ ] Click "Chạy báo cáo" chuyển sang Tab "Kết quả".
  - [ ] Bảng kết quả render đúng các cột động từ metadata service.

## 2. Layout & Scroll (1366×768 & 1440×900)
- [ ] `/` (Dashboard): `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 1065px về <= 768px).
- [ ] `/runs/<id>`: `document.documentElement.scrollHeight <= innerHeight` (đã giảm từ 2644px về <= 768px).
- [ ] `/batch-runs/<id>/result`: `document.documentElement.scrollHeight <= innerHeight`.
- [ ] `/issues`: `document.documentElement.scrollHeight <= innerHeight`.
- [ ] `/reports/<id>`: `document.documentElement.scrollHeight <= innerHeight`.
- [ ] Không có horizontal scroll ở khung nhìn desktop.

## 3. Formatting & Data Standards
- [ ] Số tiền định dạng chuẩn: dấu chấm ngăn cách hàng nghìn (ví dụ: `24.114.547.250`), không hiện số thập phân thừa.
- [ ] Cột số căn phải, font monospace tabular nums.
- [ ] Thời gian định dạng chuẩn: `dd/MM/yyyy HH:mm:ss` giờ Việt Nam.
- [ ] Khi chưa có dữ liệu hiển thị `—`, không hiển thị `0` hoặc chuỗi rỗng.

## 4. Mobile Responsiveness (390×844)
- [ ] Không có horizontal page overflow trên cả 5 trang.
- [ ] Dashboard: 4 KPI Cards co giãn hợp lý (xếp lưới 2x2 hoặc 1 cột).
- [ ] Filter bar tự động xếp dọc.

## 5. Quality & Safety
- [ ] `uv run poe lint` PASS.
- [ ] `uv run poe typecheck` PASS.
- [ ] `uv run poe test` PASS.
- [ ] Ảnh baseline AFTER đã lưu đầy đủ tại `artifacts/ui-migration/UI-02/`.

