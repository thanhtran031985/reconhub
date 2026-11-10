# Plan — Task 42

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_report_viewer_button42.py`: layout viewer →
  nút `#viewer-run-btn` có `size == "sm"`; control ngày mặc định size
  sm (không đặt size tường minh). Chạy test đỏ trước khi sửa.

## Bước 2 — Sửa nút Xem

- `app/ui/pages/report_viewer.py`: `dmc.Button("Xem báo cáo", ...)`
  đổi `size="xs"` → `size="sm"`. Không sửa `render_param_form`,
  không sửa nút Xuất Excel.

## Bước 3 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-42.py`: đo chiều cao thực tế
  `#viewer-run-btn` so với ô nhập Từ ngày — bằng nhau (36px).
- Commit, xuất patch từ `10919d3` (tip task 41), verify `git am` sạch.
