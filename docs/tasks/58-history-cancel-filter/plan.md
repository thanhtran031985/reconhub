# Task 58 — plan (user duyệt "làm đi bạn" 17:46 11/11/2026)

## Các bước
1. Fix 1 (`app/services/report_export.py`):
   - `_iter_batches` loop trong `execute_export`: kiểm tra
     `_is_cancelled` mỗi batch (bỏ điều kiện `batch_no % 10 == 0`).
   - Ngay sau vòng lặp (trước khi chốt DONE): kiểm tra hủy lần nữa;
     nếu đã hủy thì xóa file dở + trả về, không chốt DONE.
   - UPDATE chốt DONE thêm `.where(STATUS == "RUNNING")`; chỉ ghi
     run DONE + audit khi UPDATE export áp dụng được (rowcount > 0).
   - `_fail_export`: cũng chỉ ghi FAILED khi còn RUNNING (cùng lỗi
     ghi đè CANCELLED).
2. Fix 2 (`app/ui/assets/dashAgGridFunctions.js`):
   - `reconRunsActionsCell`: luôn render 4 vị trí theo thứ tự
     [Hủy/Thử lại] [Xóa] [Xuất lại] [Chạy lại]; nút không phù hợp vẽ
     bằng DMC Button thật với `visibility: hidden` + `disabled`
     (cùng kích thước, không bấm được, không chiếm tab).
3. Fix 3 (`app/ui/pages/report_runs.py`):
   - Thêm `dmc.Select(id="report-runs-filter-status")` vào hàng lọc:
     Tất cả trạng thái / Đang chờ (QUEUED) / Đang chạy (RUNNING) /
     Hoàn tất (DONE) / Lỗi (FAILED) / Đã hủy (CANCELLED).
   - `_filters_to_kwargs` thêm `status` ("all"/rỗng = không lọc);
     `handle_runs_refresh` thêm Input status, đổi lọc → về trang 1,
     "Xóa lọc" reset về "all".
4. Test: file mới `tests/unit/test_history_cancel_filter58.py` —
   hủy giữa chừng (nguồn chậm, 1 batch) → CANCELLED, không file;
   hủy đúng lúc chốt (hook `_update_export_progress` pct=90) →
   vẫn CANCELLED, không bị ghi đè DONE; JS có nút ẩn giữ chỗ;
   lọc status đi qua `_filters_to_kwargs` + service.
   Cập nhật test cũ nếu chạm tới.
5. Kiểm chứng: typecheck + ruff; Playwright check-58.py — hủy
   export đang chạy → CANCELLED + file dở bị xóa + export chờ được
   nhận ngay (slot giải phóng); vị trí nút Xuất lại/Chạy lại không
   đổi sau khi Xóa (đo x); lọc "Lỗi" chỉ hiện run FAILED; không
   lỗi JS. Full suite.
6. Commit + xuất patch `~/workspace/reconhub-task58.patch` (áp sau
   patch 57, không db-migrate), verify `git am` sạch trên worktree ở
   `4cdafb3`.
