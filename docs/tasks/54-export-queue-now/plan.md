# Task 54 — plan

## Các bước
1. Docs + nhánh `feat/54-export-queue-now` từ `03bdd29` (task 53).
2. Service `app/services/report_export.py`:
   - `request_export`: nhận run có STATUS QUEUED hoặc DONE; các trạng
     thái khác (RUNNING/FAILED/CANCELLED) vẫn lỗi như cũ. Cập nhật
     docstring + message lỗi.
   - `execute_export`: text tiến trình khi `total_rows == 0` thành
     "Đang ghi file Excel: N dòng" (bỏ "/ 0"); khi export DONE thì
     UPDATE run về DONE + ROW_COUNT=số dòng đã ghi + FINISHED_AT, chỉ
     khi run vẫn QUEUED (UPDATE có điều kiện theo STATUS).
   - Cập nhật test cũ `test_request_validation` (QUEUED giờ được phép).
3. Viewer `app/ui/pages/report_viewer.py` (`handle_export_click`):
   - Thêm State `viewer-export-store` (tham số cuối, có mặc định để
     test cũ gọi vị trí vẫn chạy).
   - Nhánh chạy ngầm khi chưa có run khớp: tạo run QUEUED → nếu
     export-store đã có run_id + values khớp thì dùng lại run đó (chống
     bấm 2 lần) → `request_export` → trả trạng thái chạy ngầm, KHÔNG
     gọi `execute_report_run`, KHÔNG đổi run-store/page (grid giữ
     nguyên). Export-store trả về gồm export_id + run_id + values.
   - Chế độ "Xuất ngay" và trường hợp đã có run DONE khớp: không đổi.
   - Cập nhật docstring.
4. Test unit `tests/unit/test_export_queue54.py`: request_export nhận
   QUEUED, từ chối RUNNING/FAILED; execute_export trên run QUEUED →
   export DONE + run DONE + ROW_COUNT đúng; viewer chạy ngầm không gọi
   execute_report_run, grid/run-store không đổi, bấm lại cùng tham số
   không tạo run mới.
5. Kiểm chứng: typecheck + ruff; Playwright check-54.py — viewer không
   Xem → Chạy ngầm → Xuất: trạng thái "chạy ngầm" hiện ngay, grid vẫn
   "Chưa chạy", DB run QUEUED + ROW_COUNT NULL + export QUEUED; worker
   chạy xong → run DONE + ROW_COUNT=55, Lịch sử hiện "Hoàn tất" + icon
   tải. Full suite.
6. Commit + xuất patch `~/workspace/reconhub-task54.patch` (áp sau
   patch 53, không db-migrate), verify `git am` sạch trên worktree ở
   `03bdd29`.
