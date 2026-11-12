# Task 68 — Phân trang cho card "Lần chạy gần đây của bộ" (/batch-runs)

## Yêu cầu (user 12/11/2026)

Trang `http://127.0.0.1:8050/batch-runs`, card 2 "Lần chạy gần đây của bộ"
hiện chỉ hiện 5 lần chạy gần nhất, không có phân trang — thêm phân trang
cho card này.

## Hiện trạng (đã xác minh trong code)

- `app/ui/pages/batch_run_wizard.py::layout()` (nhánh không có `run_id`)
  gọi `list_batch_runs(ctx, page=1, page_size=5)` rồi vẽ
  `render_recent_runs_card(recent)` — bảng tĩnh, không Pagination, không
  chọn cỡ trang.
- Service `list_batch_runs` (`app/services/batch_run.py:613`) ĐÃ hỗ trợ phân
  trang server-side (`page`, `page_size`, trả `{items, total, page,
  page_size}`) — không cần đổi service.

## Phạm vi

1. Card 2 có footer phân trang: dòng "Hiển thị x – y trong tổng số N lần
   chạy" + Select cỡ trang (10/20/50/100, mặc định 10) + `dmc.Pagination`.
2. Đổi cỡ trang → về trang 1; giá trị cỡ trang ngoài danh sách → mặc định 10.
3. Bấm phân trang chỉ vẽ lại thân bảng + dòng hiển thị + `total` của
   Pagination (không vẽ lại footer, không `dcc.Loading`) — theo mẫu task 60.
4. Không đổi service, không đổi các bước wizard 1–5, không đổi card 1.

## Ngoài phạm vi

- Không thêm lọc/tìm kiếm cho card này.
- Không đổi phân trang ở các trang khác.
