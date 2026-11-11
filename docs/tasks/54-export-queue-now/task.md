# Task 54 — export-queue-now (bấm Xuất chạy ngầm thì vào hàng đợi luôn)

## Yêu cầu (user, 12:28 11/11/2026)
"Bấm xuất và đưa vào hàng đợi luôn nha bạn (chạy ngầm)."

## Bối cảnh
Kiểm chứng live task 52/53 cho thấy: bấm Xuất Excel mà chưa bấm Xem
trước thì hệ thống tạo run mới rồi chạy báo cáo (đếm tổng + tải trang 1)
xong mới đưa export vào hàng đợi — với báo cáo ~1.000.000 dòng thì câu
đếm tổng trên Oracle có thể mất nhiều phút, user vẫn phải ngồi chờ dù
đã chọn chạy ngầm. User muốn: bấm Xuất (chế độ Chạy ngầm) là export vào
hàng đợi ngay, không chạy gì ở web process trước.

## Thiết kế
- `request_export` vốn chỉ nhận run DONE (task 26). Nới ra nhận cả run
  QUEUED (run vừa tạo, chưa chạy): worker `execute_export` vốn đã
  tự chạy lại câu query theo PARAMS_JSON đã lưu và stream từng batch,
  không cần run DONE — chỉ cần tổng dòng để tính % thật; khi run chưa
  có ROW_COUNT thì % ước lượng theo số batch (đã có sẵn fallback).
- Viewer, chế độ "Chạy ngầm", khi chưa có run khớp tham số: chỉ tạo run
  QUEUED rồi `request_export` — KHÔNG gọi `execute_report_run` (không
  đếm tổng, không tải trang 1). Grid giữ nguyên ("Chưa chạy" nếu chưa
  Xem, hoặc dữ liệu run cũ nếu đã Xem với tham số khác); run-store
  không đổi. Chế độ "Xuất ngay" giữ nguyên (vẫn chạy báo cáo trước vì
  cần poll + tự tải file).
- Worker chạy xong thì chốt luôn run QUEUED thành DONE + ROW_COUNT =
  số dòng đã ghi + FINISHED_AT (chỉ khi run vẫn QUEUED — không đụng run
  DONE đã có ROW_COUNT từ viewer). Nhờ đó Lịch sử hiện run "Hoàn tất"
  + số dòng đúng, thay vì run "Đang chờ" mãi.
- Text tiến trình khi chưa biết tổng: "Đang ghi file Excel: N dòng"
  (trước đây "N / 0 dòng").
- Chống bấm 2 lần: export-store lưu thêm run_id + values của lần nộp
  chạy ngầm; bấm lại cùng tham số thì dùng lại run đó, `request_export`
  dedup trả export đang chờ sẵn — không sinh run mới.

## Ngoài phạm vi
- Nút "Xuất lại" ở Lịch sử (rerun_and_export) vẫn chạy báo cáo đồng bộ
  trước rồi mới xuất — user chưa yêu cầu đổi; có thể làm theo sau.
- Câu hỏi refresh từng dòng ở Lịch sử (Dash table vs AG Grid) là task
  riêng (task 55, chờ duyệt).
