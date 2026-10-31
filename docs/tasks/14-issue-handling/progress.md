# Tiến độ — 14-issue-handling

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | DB + service | ✅ | 2026-11-01 | |
| 2 | Liên kết run | ✅ | 2026-11-01 | |
| 3 | UI | ✅ | 2026-11-01 | |

## Nhật ký
### Bước 1 — 2026-11-01
- Lập kế hoạch thực hiện vào `plan.md`.
- Tạo nhánh `feat/14-issue-handling`.
- Triển khai `app/services/issue.py` với seed tự động 6 lý do chuẩn (`ROUNDING`, `TIMING`, `SYSTEM_BUG`, `DATA_INPUT`, `POLICY_EXCEPTION`, `OTHER`).
- Triển khai các service: `list_reasons`, `list_assignees`, `get_issue`, `get_issue_for_row`, `upsert_issue_for_row`, `bulk_upsert_issues`, `update_issue_by_id`, `bulk_update_issues_by_ids`, `list_issues`.
- Ghi audit log `RECON_AUDIT_LOG` cho mọi thao tác cập nhật đơn lẻ và hàng loạt.
- Viết unit test `tests/unit/test_issue_service.py`, đo thời gian xử lý hàng loạt 100 dòng đạt chuẩn (< 2 giây).

### Bước 2 — 2026-11-01
- Cập nhật `app/schemas/run.py` bổ sung lọc theo `issue_status`.
- Cập nhật `app/services/run_service.py` (`get_run_rows` và `get_row_detail`): ghép ngoài bảng `recon_issue`, `recon_issue_reason`, `recon_user` trả về trạng thái issue và cờ `is_accepted`.
- Cập nhật `app/services/run_executor.py`: tự động cập nhật `LAST_RUN_ID` cho các issue lặp lại.
- Thêm kiểm thử xác nhận run lần 2 tự động nhận diện dòng đã chấp nhận lệch (`is_accepted == True`).

### Bước 3 — 2026-11-01
- Xây dựng màn hình `app/ui/pages/issues.py` (Screen09): KPI cards, bộ lọc đa tiêu chí, bảng chênh lệch với checkbox chọn hàng loạt, Drawer cập nhật issue.
- Cập nhật `app/ui/pages/run_result.py` (Screen06): thêm khối Xử lý chênh lệch trong Drawer chi tiết; thêm cột chọn dòng và thanh thao tác hàng loạt trên grid.
- Cập nhật `app/ui/layout/shell.py`: bổ sung liên kết điều hướng và breadcrumb cho `/issues`.
- Bổ sung chip trạng thái issue trong `app/ui/components/status_chip.py`.
- Viết bộ unit test `tests/unit/test_page_issues.py` và cập nhật e2e tests `tests/e2e/test_e2e_screens.py`.
- Toàn bộ 314 tests passed, lint & typecheck xanh 100%.
