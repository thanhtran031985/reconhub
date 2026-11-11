# Task 53 — history-refresh (Lịch sử báo cáo không vẽ lại bảng khi không có gì đổi)

## Yêu cầu (user, 12:00 11/11/2026, sau khi áp patch 52 và kiểm chứng trên app thật)
Trang `http://127.0.0.1:8050/report-runs` có job chạy ngầm thì reload lại liên
tục? Có cách nào để không reload toàn bộ trang không?

## Phân tích
- Không phải reload cả trang web: `dcc.Interval` 10s ở task 52 kích
  `handle_runs_refresh`, callback này tải lại dữ liệu rồi gọi
  `render_runs_table` vẽ lại TOÀN BỘ bảng mỗi 10s — kể cả khi không có
  job nào đang chạy và không có gì đổi. Mỗi lần vẽ lại thì thanh cuộn
  trong bảng nhảy về đầu + spinner Loading nhấp nháy, nhìn như trang
  bị load lại liên tục.
- Mỗi lần tick vẫn phải tải dữ liệu (1 query danh sách run + export
  theo run, rẻ) vì user có thể nộp export từ tab viewer khác trong lúc
  tab Lịch sử đang mở — tắt hẳn interval khi "không có gì chạy" sẽ làm
  mất trường hợp này. Vì vậy giữ interval chạy, chỉ chặn việc VẼ LẠI
  khi dữ liệu không đổi.
- Bảng chỉ vẽ lại khi có thay đổi thật: run mới xuất hiện, run đổi
  trạng thái/số dòng/giờ kết thúc, export đổi trạng thái/% tiến trình,
  tổng số run hoặc trang hiện tại đổi. Mọi tương tác của user (đổi lọc,
  chuyển trang, bấm "Làm mới", bấm nút hành động export) vẫn vẽ lại
  như cũ.

## Phạm vi
- Chỉ sửa `app/ui/pages/report_runs.py` (layout + `handle_runs_refresh`
  + helper fingerprint) và test. Không sửa service, không migration,
  không đổi interval 10s.
