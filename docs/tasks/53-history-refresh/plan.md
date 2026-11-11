# Task 53 — plan

## Các bước
1. Docs + nhánh `feat/53-history-refresh` từ `0e8a9ec` (task 52).
2. Helper `_runs_fingerprint(runs, exports_by_run, total, page) -> str`:
   chuỗi ổn định gồm tổng số run, trang hiện tại, và với mỗi run trên
   trang: `id:status:row_count:finished_at`, với mỗi export của run đó:
   `id:status:progress_pct`. Chỉ bao gồm những gì bảng đang hiện.
3. Layout thêm `dcc.Store(id="report-runs-fingerprint", data="")`.
   `handle_runs_refresh` thêm Output fingerprint (thứ 10) + State
   fingerprint (tham số cuối, có mặc định để test cũ gọi vị trí vẫn
   chạy): sau khi tải dữ liệu, tính fingerprint mới; nếu trigger là
   `report-runs-auto-refresh` và fingerprint mới == fingerprint đã lưu
   thì trả `dash.no_update` cho cả 10 output (không vẽ lại, không mất
   vị trí cuộn); ngược lại vẽ lại như cũ và lưu fingerprint mới. Mọi
   trigger khác (lọc, phân trang, "Làm mới", refresh-store) luôn vẽ
   lại — nút "Làm mới" không bao giờ bị coi là "không đổi".
4. Test unit `tests/unit/test_history_refresh53.py`: fingerprint ổn
   định khi dữ liệu giống nhau, đổi khi run/export đổi trạng thái hoặc
   % tiến trình đổi, đổi khi tổng/trang đổi; tick interval với dữ liệu
   không đổi → toàn bộ output là `no_update`; tick với export đổi trạng
   thái → vẽ lại; bấm "Làm mới" với dữ liệu không đổi → vẫn vẽ lại.
   Cập nhật test cũ nếu cần (test_console_cleanup45 chỉ đọc out[4..7]
   nên không ảnh hưởng).
5. Kiểm chứng: typecheck + ruff; Playwright check-53.py — mở Lịch sử,
   cuộn bảng xuống, đợi qua 1 tick 10s, assert vị trí cuộn không đổi và
   nội dung bảng không đổi; nộp 1 export chạy ngầm từ viewer rồi assert
   Lịch sử tự hiện trạng thái mới (không cần F5). Full suite.
6. Commit + xuất patch `~/workspace/reconhub-task53.patch` (áp sau
   patch 52, không db-migrate), verify `git am` sạch trên worktree ở
   `0e8a9ec`.
