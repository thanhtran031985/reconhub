# 27-reporting-ui – UI Report Center, Viewer và Wizard

- Phụ thuộc: 26
- Nhánh: `feat/27-reporting-ui`

## Mục tiêu
Dùng prototype làm source of truth.

## Đọc trước
- docs/specs/12_dynamic_reporting.md
- docs/specs/12_dynamic_reporting_tables.md
- docs/specs/12_dynamic_reporting_dataflow.md
- designs/components/Screen16-DynamicReporting/preview.html

## Phạm vi
- Report Center cards/search/favorite
- Viewer tabs/dynamic form/grid
- Wizard 6 bước theo prototype v5
- Loading/empty/error/accessibility/responsive

## Quy trình
1. Dùng skill lam-task, đọc code hiện tại và lập Implementation Plan.
2. Viết test đỏ trước; không sửa ngoài phạm vi.
3. Làm từng bước, cập nhật progress.md, dừng chờ continue.
4. Chạy typecheck, lint, test; task UI thêm e2e; task nguồn/migration thêm Oracle qua VPN.

## Chấp nhận
- Mọi ca ưu tiên Cao trong test-checklist.md đạt.
- Không phá golden/reconcile/batch/permission hiện có.
- Không dùng dữ liệu giả trong production path.
