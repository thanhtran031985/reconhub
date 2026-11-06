# 28-reporting-integration – Permission, audit, Oracle migration và hồi quy

- Phụ thuộc: 27
- Nhánh: `feat/28-reporting-integration`

## Mục tiêu
Đóng module chỉ khi checklist 21–28 đạt.

## Đọc trước
- docs/specs/12_dynamic_reporting.md
- docs/specs/12_dynamic_reporting_tables.md
- docs/specs/12_dynamic_reporting_dataflow.md
- designs/components/Screen16-DynamicReporting/preview.html

## Phạm vi
- Task19 menu + owner_filter tất cả endpoints
- Audit hoàn chỉnh
- Metadata migration SQLite→Oracle
- Performance/security/E2E/regression

## Quy trình
1. Dùng skill lam-task, đọc code hiện tại và lập Implementation Plan.
2. Viết test đỏ trước; không sửa ngoài phạm vi.
3. Làm từng bước, cập nhật progress.md, dừng chờ continue.
4. Chạy typecheck, lint, test; task UI thêm e2e; task nguồn/migration thêm Oracle qua VPN.

## Chấp nhận
- Mọi ca ưu tiên Cao trong test-checklist.md đạt.
- Không phá golden/reconcile/batch/permission hiện có.
- Không dùng dữ liệu giả trong production path.
