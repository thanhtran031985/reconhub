# 06-compare-engine — Gộp, ghép, so sánh, trạng thái, summary, export

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ1
- Phụ thuộc: 04, 05
- Nhánh git: feat/06-compare-engine

## Mục tiêu
Engine chạy trọn pipeline: gộp theo profile, ghép full outer, so measure, phân trạng thái, summary, metadata cột, export Excel. Golden xanh.

## Phạm vi
- engine/aggregate.py, compare.py, summary.py, export.py (+ export_styles.py), pipeline.py (spec 04 mục 5–7, 10)
- Golden G01–G12 + `poe golden-update`

## Ngoài phạm vi
- Lưu DB, hàng đợi (task 07)

## Thiết kế
- designs/components/Screen06-RunResult

## Spec liên quan
- docs/specs/04 mục 5–7, 10
- docs/specs/07 mục 2

## Quyết định kiến trúc
- Decimal(38,4), ROUND_HALF_UP

## Các bước
### Bước 1 — Aggregate
- Làm: Aggregate
- Test viết trước: unit + G07, G08
- Kiểm tra: `uv run poe test-engine`

### Bước 2 — Compare
- Làm: Compare
- Test viết trước: unit + G10, G11
- Kiểm tra: `uv run poe test-engine`

### Bước 3 — Pipeline + summary
- Làm: Pipeline + summary
- Test viết trước: G01 (Khớp 184, Lệch 4, Thiếu DB 2, Thiếu Excel 2), G02, G06
- Kiểm tra: `uv run poe test-engine`

### Bước 4 — Export
- Làm: Export
- Test viết trước: mở bằng openpyxl: sheet đúng, khóa là text, ô lệch có fill
- Kiểm tra: `uv run poe test-engine`

### Bước 5 — Hiệu năng sơ bộ
- Làm: bench 200k dòng
- Test viết trước: pytest -m bench
- Kiểm tra: ghi thời gian vào progress.md

## Chấp nhận khi
- [ ] 12 golden xanh
- [ ] Export giữ số 0 ở đầu
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
