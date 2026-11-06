# 23-reporting-parameters – Dynamic Parameter, LOV và layout 12 cột

- Phụ thuộc: 22
- Nhánh: `feat/23-reporting-parameters`

## Mục tiêu
Không cho qua bước nếu layout lỗi.

## Đọc trước
- docs/specs/12_dynamic_reporting.md
- docs/specs/12_dynamic_reporting_tables.md
- docs/specs/12_dynamic_reporting_dataflow.md
- designs/components/Screen16-DynamicReporting/preview.html

## Phạm vi
- Parameter CRUD/validation/default resolution
- LOV NONE/STATIC/SQL/LOOKUP + cache
- DISPLAY_ROW/ORDER/GRID_SPAN và tổng row <=12
- Auto-layout, drag/drop, preview

## Quy trình
1. Dùng skill lam-task, đọc code hiện tại và lập Implementation Plan.
2. Viết test đỏ trước; không sửa ngoài phạm vi.
3. Làm từng bước, cập nhật progress.md, dừng chờ continue.
4. Chạy typecheck, lint, test; task UI thêm e2e; task nguồn/migration thêm Oracle qua VPN.

## Chấp nhận
- Mọi ca ưu tiên Cao trong test-checklist.md đạt.
- Không phá golden/reconcile/batch/permission hiện có.
- Không dùng dữ liệu giả trong production path.
