# Task 70 — Decisions

- D1: cỡ trang dùng `dmc.SegmentedControl` (dạng pill/badge bấm chọn)
  thay vì Badge bấm tay — SegmentedControl expose prop `value` giống
  Select nên 3 callback đọc `viewer-page-size` không cần đổi.
- D2: switch xuất dùng label "Chạy ngầm", tắt = Xuất ngay (mặc định như
  cũ), bật = Chạy ngầm (mẫu switch "Chạy ngầm" ở bước Thực thi, task 67).
- D3: giữ nguyên id 2 control (`viewer-page-size`, `viewer-export-mode`).
- D4: làm song song với task 69 (subagent riêng, file khác nhau:
  task 69 sửa `app/engine/filters.py`, task 70 sửa
  `app/ui/pages/report_viewer.py`). Full suite chỉ chạy 1 lần chung sau
  khi cả 2 xong — không chạy 2 bộ pytest cùng lúc.
