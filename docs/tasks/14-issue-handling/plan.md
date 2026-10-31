# Kế hoạch thực hiện — 14-issue-handling

## Mục tiêu
Gán nguyên nhân, người xử lý (người dùng của ứng dụng), trạng thái cho dòng chênh lệch, từng dòng hoặc hàng loạt; run sau nhận diện dòng đã chấp nhận lệch (`ACCEPTED`). Xử lý hàng loạt 100 dòng < 2 giây.

---

## 1. Kiến trúc & Thiết kế kỹ thuật
- Bảng CSDL:
  - `RECON_ISSUE_REASON`: Mã danh mục (`CODE`), Tên hiển thị (`LABEL`), Trạng thái hoạt động (`IS_ACTIVE`).
  - `RECON_ISSUE`: Tách độc lập khỏi run, liên kết theo `(TEMPLATE_ID, PROFILE_CODE, KEY_HASH)`. Ghi nhận `FIRST_RUN_ID`, `LAST_RUN_ID`, `STATUS` (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `ACCEPTED`), `REASON_CODE`, `ASSIGNEE_ID`, `NOTE`, `ROW_VERSION`.
- Service `app/services/issue.py`:
  - `list_reasons(ctx)`
  - `get_issue(ctx, issue_id)`
  - `get_issue_for_row(ctx, run_id, row_no)`
  - `upsert_issue_for_row(ctx, run_id, row_no, reason_code, assignee_id, status, note)`
  - `bulk_upsert_issues(ctx, run_id, row_nos, reason_code, assignee_id, status, note)`
  - `list_issues(ctx, template_id, profile_code, status, assignee_id, search, page, page_size)`
- Liên kết run:
  - Khi xem hoặc xử lý run, truy vấn các issue liên kết theo `(TEMPLATE_ID, PROFILE_CODE, KEY_HASH)` để hiển thị trạng thái xử lý và cờ `ACCEPTED`.
- Giao diện:
  - Màn hình `/issues` (Screen09): KPI cards, bộ lọc đa chiều, danh sách issue, drawer cập nhật.
  - Màn hình Run Result `/runs/<id>` (Screen06): Khối xử lý chênh lệch trong Drawer chi tiết và modal xử lý hàng loạt.

---

## 2. Các bước triển khai

### Bước 1 — DB + Service (`app/services/issue.py`)
- Seed các lý do chuẩn trong `RECON_ISSUE_REASON`: `ROUNDING`, `TIMING`, `SYSTEM_BUG`, `DATA_INPUT`, `POLICY_EXCEPTION`, `OTHER`.
- Xây dựng `app/services/issue.py` với đầy đủ kiểm tra phân quyền (Viewer chỉ đọc; Operator/Owner/Admin được gán và cập nhật), ghi audit log `RECON_AUDIT_LOG`.
- Tối ưu hóa xử lý hàng loạt (`bulk_upsert_issues`) đạt hiệu năng < 2s cho 100 dòng.
- Viết test unit `tests/unit/test_issue_service.py`.

### Bước 2 — Liên kết run
- Cập nhật truy vấn dòng kết quả trong `app/services/run.py` để join / ánh xạ thông tin issue theo `KEY_HASH`.
- Nhận diện các dòng có issue trạng thái `ACCEPTED`.
- Viết test kiểm tra liên kết run qua nhiều lần chạy (run 1 tạo issue ACCEPTED -> run 2 nhận diện).

### Bước 3 — UI (Screen09 /issues & Drawer Screen06)
- Xây dựng `app/ui/pages/issues.py` (Screen09).
- Bổ sung khối Xử lý chênh lệch vào Drawer và xử lý hàng loạt trong `app/ui/pages/run_result.py` (Screen06).
- Thêm link menu điều hướng "Xử lý chênh lệch" trên AppShell.
- Viết test `tests/unit/test_page_issues.py` và cập nhật E2E test.
