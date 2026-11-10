# Plan — Task 44

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_report_runs_fit44.py`: layout root có
  `height: calc(100vh - 48px)`; nút Chạy lại chứa icon `play-circle`.
- Chạy test đỏ trước khi sửa.

## Bước 2 — Sửa trang

- Root `dmc.Box` của `layout()`: `height` từ `"100%"` →
  `"calc(100vh - 48px)"` (đúng rule các trang khác). Giữ nguyên flex
  column + `overflow: hidden`; bảng đã cuộn nội bộ qua
  `TableScrollContainer` nên phân trang luôn nằm trong màn hình.
- Nút "Chạy lại": thêm `leftSection=DashIconify(icon="lucide:play-circle",
  width=14)` — icon của menu "Chạy đối soát".

## Bước 3 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-44.py`: seed 25 run, viewport
  1440×900 và 1366×768 ở zoom 100% — khung phân trang (Tổng N run +
  chọn cỡ trang + nút trang) nằm trong màn hình, bảng cuộn được; nút
  Chạy lại có icon.
- Commit, xuất patch từ `2b9f924` (tip task 43), verify `git am` sạch.
