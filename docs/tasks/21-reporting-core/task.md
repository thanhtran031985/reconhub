# 21-reporting-core – Reporting Core và versioning

- Phụ thuộc: 19, 20
- Nhánh: `feat/21-reporting-core`

## Mục tiêu
Core metadata/version không phụ thuộc UI.

## Đọc trước
- docs/specs/12_dynamic_reporting.md
- docs/specs/12_dynamic_reporting_tables.md
- docs/specs/12_dynamic_reporting_dataflow.md
- designs/components/Screen16-DynamicReporting/preview.html

## Phạm vi
- Schema/migration cho 10 bảng
- Services Report Master, Template, Version clone/activate/archive
- Seed menu report_center/report_history/report_admin
- Audit và Oracle metadata migration

## Quy trình
1. Dùng skill lam-task, đọc code hiện tại và lập Implementation Plan.
2. Viết test đỏ trước; không sửa ngoài phạm vi.
3. Làm từng bước, cập nhật progress.md, dừng chờ continue.
4. Chạy typecheck, lint, test; task UI thêm e2e; task nguồn/migration thêm Oracle qua VPN.

## Chấp nhận
- Mọi ca ưu tiên Cao trong test-checklist.md đạt.
- Không phá golden/reconcile/batch/permission hiện có.
- Không dùng dữ liệu giả trong production path.
