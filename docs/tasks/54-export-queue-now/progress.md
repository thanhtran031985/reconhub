# Task 54 — progress

## Bước 1 — Docs + nhánh (xong, 11/11/2026)
- Nhánh `feat/54-export-queue-now` từ `03bdd29` (task 53).

## Bước 2–3 — Code + test unit (xong)
- `request_export` nhận run QUEUED/DONE; `execute_export` chốt run
  QUEUED → DONE + ROW_COUNT, text tiến trình bỏ "/ 0 dòng".
- Viewer chạy ngầm: tạo run QUEUED → vào hàng đợi luôn, không gọi
  `execute_report_run`, không đổi run-store/grid; chống bấm 2 lần bằng
  export-store (run_id + values). "Xuất ngay" không đổi.
- Test mới 7 pass (test_export_queue54.py); test cũ
  test_request_validation cập nhật theo hành vi mới.
- Lưu ý: `viewer-tabs` là tab chọn template (value = template_id),
  không phải tab Kết quả/SQL — nên State tabs gắn đúng vào tham số
  template_id.

## Bước 4 — Kiểm chứng live (xong)
- Playwright check-54.py 8/8: không Xem → Chạy ngầm → Xuất 0,09s là
  hiện "chạy ngầm", grid vẫn "Chưa chạy"; DB run QUEUED + ROW_COUNT
  NULL + export QUEUED; worker xong → run DONE + ROW_COUNT=55, Lịch
  sử hiện "Hoàn tất" + icon tải; không lỗi JS.
- Bài học: Mantine Badge hiển thị chữ hoa (text-transform) nên
  innerText ra "HOÀN TẤT" — assert text badge phải dùng textContent.
