# Tiến độ — 15-dashboard-compare

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Service | ✅ | 2026-11-01 | feat/15-dashboard-compare |
| 2 | UI Dashboard | ✅ | 2026-11-01 | feat/15-dashboard-compare |
| 3 | So sánh run | ✅ | 2026-11-01 | feat/15-dashboard-compare |

## Nhật ký
### Bước 1 — 2026-11-01
- Lập kế hoạch thực hiện vào `plan.md`.
- Tạo nhánh `feat/15-dashboard-compare`.
- Triển khai `app/services/dashboard.py` (`get_dashboard_summary`, `compare_runs`, `get_previous_run`).
- Viết unit test `tests/unit/test_dashboard_service.py` kiểm tra phân loại chuẩn 3 nhóm so sánh run và dashboard summary.
- Hoàn thiện `update_issue_by_id`, `bulk_update_issues_by_ids`, `list_assignees` trong `app/services/issue.py`.
- Toàn bộ unit tests, ruff lint và mypy typecheck xanh 100%.

### Bước 2 — 2026-11-01
- Hoàn thiện UI Dashboard Screen01 (`app/ui/pages/dashboard.py`):
  - Kết nối trực tiếp `get_dashboard_summary(ctx)`.
  - Hiển thị 4 thẻ KPI chỉ số chuẩn thiết kế (Run trong kỳ, Tỉ lệ khớp trung bình, Chưa kiểm tra / Dữ liệu tạm, Việc của tôi).
  - Thêm thẻ Card `render_diff_rate_by_template` thể hiện trực quan tỉ lệ lệch theo từng template với thanh tiến trình tiến triển.
  - Bảng "Run gần đây" 10 lần chạy với 7 cột chuẩn thông tin và chip trạng thái.
- Unit tests `test_page_dashboard.py` và toàn bộ E2E tests xanh 100%.

### Bước 3 — 2026-11-01
- Hoàn thiện UI So sánh 2 run trên Screen06 (`app/ui/pages/run_result.py`):
  - Thêm nút "So với run trước" trên header.
  - Thêm Drawer `run-res-compare-drawer` hiển thị so sánh hai run với 4 KPI cards (Chỉ có ở A, Chỉ có ở B, Đổi trạng thái, Giữ nguyên).
  - Tabs bộ lọc phân loại 3 nhóm chênh lệch kèm số đếm bản ghi.
  - Bảng chi tiết dòng đối chiếu so sánh trạng thái và chênh lệch giữa 2 run.
  - Thêm unit test `test_render_compare_drawer_content` và `test_handle_compare_runs_callback` trong `tests/unit/test_page_run_result.py`.
- Toàn bộ 325 tests (320 passed, 5 skipped), ruff lint, mypy typecheck và E2E tests xanh 100%. Hoàn thành Task 15.
