# 11-run-result-ui — Màn Kết quả run, grid động, Đã kiểm tra xong

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ2
- Phụ thuộc: 07, 08
- Nhánh git: feat/11-run-result-ui

## Mục tiêu
Xem kết quả theo trạng thái với grid cột động, tìm, lọc, xem chi tiết dòng Excel gốc và DB, export; đánh dấu đã kiểm tra và xóa dữ liệu tạm của run.

## Phạm vi
- pages/run_result.py: header (chip dữ liệu tạm), KPI, thanh tỉ lệ, tabs trạng thái
- dag.AgGrid infinite, build_column_defs, cellClassRules rh-diff, chỉ cột lệch
- Drawer chi tiết (khi đã xóa: 'Dữ liệu Excel gốc đã xóa lúc …'; dùng chung chưa xóa: 'dùng chung với run #…'); tab Không hợp lệ; Export; Chạy lại
- Nút Đã kiểm tra xong + Modal (checkbox 'Xóa luôn dữ liệu tạm' mặc định bật; danh sách sẽ xóa / giữ lại)

## Ngoài phạm vi
- Xử lý chênh lệch (14), so sánh run (15)

## Thiết kế
- designs/components/Screen06-RunResult, DataGrid, Drawer, KpiCard, StatusChip

## Spec liên quan
- docs/PRD.md C6
- docs/specs/04 mục 12
- docs/specs/05 mục 2–3

## Quyết định kiến trúc
- Không code cột riêng theo template

## Các bước
### Bước 1 — Header + KPI + tabs
- Làm: Header + KPI + tabs
- Test viết trước: dựng tab từ statuses
- Kiểm tra: `uv run poe test`

### Bước 2 — Grid động
- Làm: Grid động
- Test viết trước: build_column_defs với 2 profile; e2e cuộn 190 dòng
- Kiểm tra: `uv run poe e2e`

### Bước 3 — Drawer + invalid + export
- Làm: Drawer + invalid + export
- Test viết trước: e2e mở dòng lệch thấy dòng Excel gốc; tải export
- Kiểm tra: `uv run poe e2e`

### Bước 4 — Đã kiểm tra xong
- Làm: Đã kiểm tra xong
- Test viết trước: e2e spec 07 mục 4.6; bỏ checkbox → chỉ đánh dấu, dữ liệu tạm còn
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Grid đúng với mọi profile
- [ ] Đếm và tổng khớp G01
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh, e2e xanh

## Câu hỏi mở
- —
