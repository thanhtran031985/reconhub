# Task 87 — /issues: sửa lọc "Chưa giao", trạng thái đọc từ lookup, thêm lọc theo lần chạy

## Yêu cầu (user 16:38 13/11/2026, sau khi parent kiểm tra cách lấy điều kiện ở /issues)
Chỉnh 2 điểm parent đã báo + thêm điều kiện run để tìm kiếm.

## Phân tích (parent đọc code trước khi giao)
- Trang: `app/ui/pages/issues.py` (827 dòng), service: `app/services/issue.py::list_issues` (dòng 651).
- (1) "Chưa giao" không có tác dụng: option `UNASSIGNED` ở `render_filter_bar` nhưng `update_issues_view` chỉ map giá trị là số (`assignee_val.isdigit()`) thành `assignee_id`, còn `UNASSIGNED` rơi về `None` → `list_issues` không thêm điều kiện nào → giống hệt "Tất cả".
- (2) Trạng thái hardcode 4 mục (OPEN/IN_PROGRESS/RESOLVED/ACCEPTED) ở 3 chỗ trên trang: `render_filter_bar` (lọc), `layout()` drawer `issues-drawer-status`, `render_bulk_action_bar` (bulk `issues-bulk-status`) — trong khi task 85 đã đưa drawer trang kết quả run sang đọc lookup `ISSUE_STATUS` (`list_active_lookup_codes`, fallback 4 mặc định). Thêm trạng thái mới ở /lookups sẽ không hiện ở /issues.
- (3) Chưa có lọc theo lần chạy. Issue chỉ gắn 1 run đầu tiên qua `RECON_ISSUE.FIRST_RUN_ID`. Có sẵn `list_runs` (`app/services/run_service.py:417`, `@requires_menu("result")`, `RunListFilter(page, page_size)`, xếp `CREATED_AT` desc, scope-aware task 19) để lấy danh sách run cho Select. Tất cả vai trò mở được /issues (ADMIN/OPERATOR/TEMPLATE_OWNER) đều có menu "result" (`app/ui/menus.py` ROLE_MENUS_SEED); VIEWER có "result" nhưng không có menu "issue" nên không vào được trang.
- Các điểm KHÔNG đổi (đã nói rõ với user): KPI đếm theo toàn bộ phạm vi, không theo bộ lọc; trang vẫn trang 1 / 100 dòng, không phân trang.
