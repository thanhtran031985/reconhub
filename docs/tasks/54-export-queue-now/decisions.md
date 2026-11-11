# Task 54 — decisions

- D1: Nới `request_export` nhận run QUEUED thay vì thêm service mới:
  worker đã tự chạy query theo PARAMS_JSON và stream, không phụ thuộc
  run DONE; chỉ mất % thật khi chưa biết tổng (đã có fallback ước
  lượng theo batch). RUNNING/FAILED/CANCELLED vẫn bị từ chối.
- D2: Viewer chạy ngầm KHÔNG đưa run QUEUED vào run-store: grid loader
  (`handle_result_render`) gọi `get_report_page` trên run QUEUED sẽ trả
  lỗi và xóa dữ liệu đang hiện. Grid giữ nguyên là hành vi đúng — user
  chưa chạy báo cáo thì chưa có gì để xem; bấm Xem sau đó vẫn chạy bình
  thường.
- D3: Chống bấm 2 lần bằng export-store (run_id + values) thay vì
  run-store: run-store phải giữ nguyên (D2) nên không dùng nó để
  dedup được; export-store vốn đã là nơi lưu trạng thái export.
- D4: Worker chốt run QUEUED → DONE khi export xong (UPDATE có điều
  kiện STATUS='QUEUED'): nếu không, Lịch sử hiện run "Đang chờ" mãi dù
  file đã xong. Không ghi thêm audit cho run — audit EXECUTE_EXPORT đã
  ghi row_count + DONE.
- D5: "Xuất ngay" không đổi: chế độ này cần run DONE để poll + tự tải
  file ngay trong phiên; user chỉ yêu cầu đổi chạy ngầm.
