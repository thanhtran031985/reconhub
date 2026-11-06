# 24-reporting-columns – Column mapping và result layout

- Phụ thuộc: 23
- Nhánh: `feat/24-reporting-columns`

## Mục tiêu
Web và Excel dùng cùng metadata.

## Đọc trước
- docs/specs/12_dynamic_reporting.md
- docs/specs/12_dynamic_reporting_tables.md
- docs/specs/12_dynamic_reporting_dataflow.md
- designs/components/Screen16-DynamicReporting/preview.html

## Phạm vi
- Auto-discover column metadata
- Editable mapping grid và row drag
- Format/alignment/width/visibility/total
- Preview và schema diff

## Quy trình
1. Dùng skill lam-task, đọc code hiện tại và lập Implementation Plan.
2. Viết test đỏ trước; không sửa ngoài phạm vi.
3. Làm từng bước, cập nhật progress.md, dừng chờ continue.
4. Chạy typecheck, lint, test; task UI thêm e2e; task nguồn/migration thêm Oracle qua VPN.

## Chấp nhận
- Mọi ca ưu tiên Cao trong test-checklist.md đạt.
- Không phá golden/reconcile/batch/permission hiện có.
- Không dùng dữ liệu giả trong production path.
