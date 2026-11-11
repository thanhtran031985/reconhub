# Task 56 — plan

## Các bước
1. Docs + nhánh `feat/56-history-aggrid-ui` từ `db93556` (task 55).
2. Code:
   - `app/ui/assets/custom.css`: thêm `.rh-runs-grid { --ag-font-size: 12px; }`
     (pattern task 40) + class `.rh-grid-btn` / `.rh-grid-btn.danger` /
     `.rh-grid-link` (nút subtle xs: nền trong suốt, không viền, chữ
     xanh dương, hover nền xanh nhạt; Xóa chữ đỏ, hover nền đỏ nhạt;
     link xanh, hover gạch chân).
   - `app/ui/pages/report_runs.py`:
     - layout: `data_grid(..., className="ag-theme-quartz-auto-dark rh-runs-grid")`.
     - `_runs_grid_column_defs`: Tham số về cuối (sau Chạy lại); width
       mới — Nhóm 90, Trạng thái 100, Bắt đầu/Kết thúc 150, Báo cáo flex
       1 min 130, Tham số flex 2 min 140; các cột còn lại giữ nguyên.
   - `app/ui/assets/dashAgGridFunctions.js`: renderer nút dùng
     `className: 'rh-grid-btn'` (+ ' danger' cho Xóa), link dùng
     `className: 'rh-grid-link'`.
3. Test unit `tests/unit/test_history_aggrid55.py` (bổ sung): thứ tự cột
   (Tham số cuối), width các cột đã rà, layout có class rh-runs-grid,
   custom.css có `--ag-font-size: 12px` + class nút/link.
4. Kiểm chứng: typecheck + ruff; Playwright check-56.py — font tính
   toán của cell = 12px; header cuối là "Tham số"; ô Bắt đầu/Kết thúc
   hiện đủ ngày giờ (không bị cắt); nút Hủy nền trong suốt + chữ xanh,
   link Chạy lại màu xanh (không tím); tick cập nhật dòng vẫn chạy
   (không regression task 55). Full suite.
5. Commit + xuất patch `~/workspace/reconhub-task56.patch` (áp sau
   patch 55, không db-migrate), verify `git am` sạch trên worktree ở
   `db93556`.
