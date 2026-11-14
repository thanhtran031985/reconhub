# Plan — Task 93

1. Đọc `app/ui/pages/run_result.py`: `layout()` (1659+), `run-res-main-tabs`
   (1720+), `render_sql_tab_content` (849+), `_profile_main_measure`
   (148+), `render_kpi_cards` (358+); đọc test hiện có
   `tests/unit/test_page_run_result.py`.
2. Viết test đỏ trước (file mới `tests/unit/test_run_flow_tab93.py`):
   - Run mẫu BILL_VTOS đầy đủ số liệu (seed theo `check-88f-followup.py`):
     tab hiện tên file, bảng `DATARAW.FACT_BILL`, nguồn `GMD_DEV`,
     group_by `[INVOICE_DATE, INVOICE_NO]`, measure chính, các CNT_*,
     4 chặng + 4 thẻ + ô ví dụ (nhóm đầu tiên của `initial_rows`).
   - Run thứ 2 với template tên khác (không phải BILL_VTOS): assert
     tab hiện đúng tên template/bảng của run đó (chống hardcode).
   - Run FAILED không có summary: tab vẫn render, số thiếu hiện "—",
     có alert lỗi.
   - Hồi quy: 2 tab cũ render như trước (assert `render_sql_tab_content`
     và grid không đổi).
3. Code (chỉ `app/ui/pages/run_result.py`, không sửa service, không sửa
   helper dùng chung):
   - Helper MỚI `_flow_context(ctx, run_info)` (không sửa
     `_profile_main_measure`): gọi `get_template` 1 lần, trích
     `db_source` (table, source_id), profile đã chạy (group_by, measures,
     main_measure + compare/tolerance/round), số trường; trả dict, lỗi
     thì trả None (nơi gọi dự phòng "—").
   - Hàm MỚI `render_flow_tab_content(run_info, summary, initial_rows)`:
     dựng nội dung tab theo D1–D9; mọi khối lấy dữ liệu đều bọc
     try/except, lỗi thì thay bằng "—" hoặc alert trong tab.
   - `layout()`: thêm `TabsTab("Luồng xử lý", value="flow")` + `TabsPanel`
     (value="flow", children=`render_flow_tab_content(...)` bọc try/except
     ngoài cùng — lỗi thì panel chỉ hiện alert, trang vẫn mở được).
   - Không thêm callback, không thêm Store, không đổi id hiện có.
4. Chạy test mới + test trang run + typecheck + ruff; sửa tới khi xanh.
5. Live check `~/workspace/check-93-run-flow-tab.py` (Playwright, port
   8149, seed như check-88f): mở run mẫu, bấm tab "Luồng xử lý", assert
   4 chặng + 4 thẻ + ví dụ hiện, không console error/pageerror; bấm lại
   2 tab cũ, assert grid + SQL vẫn hiện.
6. Full suite (`TMPDIR=/run/pytest-tmp uv run poe test`); cập nhật
   `progress.md`; chạy `uv run poe tasks-dashboard` (sau đó REVERT
   `docs/tasks/dashboard.html` trước khi commit).
7. Parent rà soát diff, commit `93-run-flow-tab: ...`, xuất patch,
   verify `git am` trên worktree sạch tại `06d6327`, giao user.
