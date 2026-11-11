# Task 59 — progress

## Bước 0 — Khảo sát (xong, 11/11/2026)
- Đọc `app/ui/pages/report_admin.py` (5514 dòng) + `list_reports`
  + pattern phân trang `/report-runs`.
- Phát hiện: danh sách chính đã phân trang từ task 29 (10/trang)
  và chạy đúng live (check-59-paging.py 8/8, 25 báo cáo → 3
  trang); thiếu duy nhất Select chọn cỡ trang. Grid cột bước 4
  và dry-run bước 5 giữ nguyên (xem decisions.md D4).
- Nhánh làm việc: `feat/58-history-cancel-filter` (dùng chung
  với task 58; chỉ sửa file /report-admin + test của nó, không
  commit, không full suite).

## Bước 1 — Test trước + code (xong, 11/11/2026)
- Test `TestAdminPageSize` (6 test) đỏ đúng chỗ (Select
  `admin-page-size` chưa có) rồi xanh sau khi code.
- `app/ui/pages/report_admin.py`: hằng số
  `ADMIN_PAGE_SIZE_OPTIONS = [10, 20, 50, 100]` +
  `DEFAULT_ADMIN_PAGE_SIZE = 10`; Select "N dòng/trang" trong
  thanh phân trang của `render_report_list` (luôn hiện);
  `handle_admin_filter` thêm `Input("admin-page-size", "value")`,
  parse + kẹp về danh sách cho phép, đổi cỡ trang → về trang 1.
- Không đổi service, không migration.

## Bước 2 — Kiểm tra (xong, 11/11/2026)
- `tests/unit/test_page_report_admin.py`: 73 passed (cả file).
- `ruff check` sạch trên 2 file sửa; dòng mới sạch `ruff format`
  (phần format diff còn lại là drift cũ, không chạm).
- `mypy app/ui/pages/report_admin.py`: no issues.
- Live `~/workspace/check-59-paging.py`: **13/13** — phân trang
  cũ 8/8 + cỡ trang mới 5/5 (20 → 20 dòng, trang 2 còn 5 dòng;
  50 → 25 dòng 1 trang; về 10 → 10 dòng đầu; không lỗi JS).
- Lưu ý: 2 lần chạy live lỗi thoáng qua do máy bận (task 58 chạy
  song song: app lên chậm quá 90s một lần; một lần wait 10s
  timeout) — chạy lại đều pass. Không chạy `tasks-dashboard`
  (tránh làm bẩn dashboard.html trước khi xuất patch).
- Không commit (theo brief). Chưa chạy full suite.

## Bước 3 — Full suite + commit (parent, 11/11/2026)
- Full suite 1569 pass, 6 skipped (đã gồm 6 test task 58 + 6 test
  task 59). Commit + patch riêng, áp sau patch 58.
