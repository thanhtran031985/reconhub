# Task 60 — progress

## Điều tra (xong, 11/11/2026, subagent)
- Kết luận: KHÔNG load lại layout thật; "reload giả" do spinner +
  vẽ lại toàn bộ bảng/card + mất focus. Xem task.md đầy đủ.
- Chờ user duyệt plan fix (plan.md) rồi mới làm.

## Fix bước 1 + 2 (xong, 11/11/2026 — KHÔNG làm bước 3 AG Grid, bước 4 TableTbody)
- /history (`app/ui/pages/history.py`):
  - Tách `render_runs_table` (chỉ phần bảng) + `render_history_pagination_bar`
    (footer cố định) + `_history_showing_text`.
  - `layout()`: bỏ `dcc.Loading(id="history-loading")`, vùng bảng là Div
    thường với trạng thái tải nhỏ lúc mở trang; footer phân trang là
    sibling cố định sau vùng bảng.
  - `handle_history_page` trả thêm `history-pagination.value` (reset về 1
    khi đổi lọc); `update_history_table` trả 4 output (bảng, tiêu đề,
    dòng "Hiển thị x–y", tổng số trang Pagination).
- Dashboard (`app/ui/pages/dashboard.py`):
  - Tách thân bảng 2 card ra `_recent_runs_table_content` /
    `_diff_rate_table_content`; card giữ header + footer trong Card,
    thân bảng nằm trong div `dashboard-recent-card-body` /
    `dashboard-diff-card-body` cố định.
  - `layout()`: bỏ `dcc.Loading(id="dashboard-loading")`, vùng nội dung
    hiện trạng thái tải nhỏ lúc mở trang.
  - `_update_recent_card` / `_update_diff_card` trả 3 output (body,
    dòng "Hiển thị x–y", tổng số trang); không trả giá trị Pagination
    (xem decisions.md D4).
- Lệch plan đã ghi ở `decisions.md` (D1–D5): bỏ Loading thay vì giữ
  spinner lúc tải lần đầu/lọc; callback history trả thêm prop `total`;
  footer dashboard giữ trong Card.
- Test (tests-first, đỏ rồi xanh): `tests/unit/test_page_history.py`,
  `tests/unit/test_page_dashboard.py`,
  `tests/unit/test_batch_run_pages.py` (2 chỗ gọi `render_runs_table`
  bỏ kwarg phân trang) — **59 passed**; `ruff check` sạch;
  `mypy` sạch trên 2 file sửa.
- Kiểm chứng live `~/workspace/check-60-paging.py` (seed 25 template +
  25 run DONE + 25 summary, cổng 8107, DB/storage riêng
  `/run/pytest-tmp/check60.*`): **24/24 pass** — cả 3 phân trang
  (/history sang trang 2 + về trang 1, dashboard Run gần đây, dashboard
  Tỉ lệ lệch): không spinner, node Pagination không bị hủy/vẽ lại,
  focus vẫn ở nút vừa bấm, dòng mới hiện đúng, URL không đổi, không lỗi
  JS (quét cả console error + pageerror).
- Chưa chạy full suite (parent chạy). Không commit (parent commit).
