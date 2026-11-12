# Task 70 — Viewer: cỡ trang dạng badge, chế độ xuất dạng switch

## Yêu cầu (user 12/11/2026, trang /reports/5)

- Cột phân trang (cỡ trang): chuyển từ Select sang dạng badge
  "50 dòng/trang" / "100 dòng/trang" / "200 dòng/trang".
- Chế độ xuất Excel: chuyển Select "Xuất ngay" / "Chạy ngầm" sang Switch
  cho đẹp.

## Phạm vi

- Chỉ trang Xem báo cáo (`app/ui/pages/report_viewer.py`): đổi 2 control
  ở header kết quả. Không đổi logic phân trang, không đổi logic xuất
  (ngay/ngầm giữ nguyên hành vi task 52/54), không migration.
