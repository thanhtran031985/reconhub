# Task 79 — Test checklist (NOTIFICATION-01, nghiệm thu theo ảnh thiết kế)

Ảnh thiết kế: `~/workspace/user/media_library/image/Designer__1.png`

## Chức năng

- [x] Lọc: tìm kiếm theo tiêu đề/nội dung; lọc loại sự kiện (Tất cả
      + 12 loại); lọc đã/chưa đọc; lọc thời gian (7 ngày qua / 30
      ngày / tất cả); Làm mới vẽ lại danh sách.
- [x] Nhóm theo ngày: HÔM NAY / HÔM QUA / ngày cũ; giờ tương đối
      ("2 phút", "1 giờ", "Hôm qua 16:20"); icon trạng thái theo
      loại; chấm xanh chưa đọc; dòng đang chọn highlight.
- [x] Panel chi tiết: chọn dòng → panel hiện badge loại + mã loại,
      ngày giờ, Mã lần chạy (+ copy), Bộ đối soát, Template, Thời
      gian chạy, hộp "Nguyên nhân" khi có lỗi; nút "Mở kết quả Run"
      (đánh dấu đã đọc rồi mới điều hướng); nút "Sao chép mã run".
- [x] Panel chi tiết cho từng loại entity (RUN / REPORT_RUN /
      EXPORT / BATCH) + fallback SYSTEM (chỉ title/message/link).
- [x] Nút "Sao chép mã run" là Button có nhãn (không phải icon
      trơ); bấm → toast "Đã sao chép mã ...".
- [x] Nút "Xóa" trong panel chi tiết: bấm → modal xác nhận nêu rõ
      sẽ xóa vĩnh viễn; Hủy đóng modal không xóa; Xác nhận → dòng
      biến mất, dòng còn lại tự chọn, toast thành công.
- [x] Footer: "N thông báo · M chưa đọc · Cập nhật HH:MM:SS" đúng
      sau mỗi lần làm mới/đánh dấu.
- [x] Popover chuông: tab Tất cả / Chưa đọc lọc đúng; "Đánh dấu
      tất cả đã đọc" trong popover về 0 + badge chuông về 0; "Xem
      tất cả" tới /notifications.
- [x] Cài đặt (Modal): công tắc tổng BẬT/TẮT; tắt tổng → run lỗi
      mới KHÔNG sinh thông báo; bật lại → sinh; đủ 12 switch theo
      nhóm; Hủy không lưu, Lưu thay đổi lưu được + tải lại giữ.
- [x] Menu "Thông báo" ở nhóm QUẢN TRỊ; mọi vai trò vẫn vào được.
- [x] Không còn style inline px trong trang thông báo; không cuộn
      trang ở desktop.

## Giao diện (Playwright, JS sạch: CẢ console error VÀ pageerror)

- [x] 1366×768: `scrollHeight <= innerHeight`, không cuộn ngang;
      screenshot đính báo cáo bước.
- [x] 1440×900: như trên; screenshot đính báo cáo bước.
- [x] 390×844: list + panel xếp dọc, trang cuộn được; screenshot
      đính báo cáo bước.
- [x] Đối chiếu ảnh chụp với ảnh thiết kế: mật độ, command bar,
      master–detail, footer.

## Hồi quy

- [x] Targeted tests + ruff + typecheck sạch.
- [ ] Full suite xanh.
- [ ] Patch `git am` sạch theo thứ tự user (sau patch 78);
      CẦN db-migrate (0011), khởi động lại app + worker.

## Ghi chú nghiệm thu 12/11/2026

- Check live 48/48 PASS (`~/workspace/check-79-notification-design.py`).
- 2 mục dưới do parent làm (subagent không commit/không chạy full suite):
  full suite + patch `git am` sau patch 78.
- Mobile: navbar AppShell là overlay fixed che toàn màn hình (hành vi
  chung của shell, ngoài scope task 79); screenshot mobile ẩn tạm navbar
  để chụp layout xếp dọc của trang. Tiêu đề trang ở 390px bị chữ
  "Người vận hành" ở header shell đè nhẹ — cũng thuộc shell, ngoài scope.
