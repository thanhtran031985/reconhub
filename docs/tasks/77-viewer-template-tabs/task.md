# Task 77 — Viewer: chuyển tab template không đổi form/kết quả

## Bối cảnh

- User báo 17:21 12/11/2026 ở /reports/15 ("Báo cáo doanh thu RM",
  2 template: "Báo cáo doanh thu catos" + "Doanh thu vtos"): bấm Xem
  báo cáo ở tab catos thì dữ liệu hiện lên table, nhưng bấm sang tab
  vtos thì không load page của vtos.

## Nguyên nhân gốc (xác minh từ code)

- `layout()` ở report_viewer.py dựng form tham số (`preview_layout`
  + `render_param_form` vào `#viewer-param-form`) **một lần duy nhất
  cho template ĐẦU TIÊN** (`first = active_templates[0]`).
- `viewer-tabs` chỉ xuất hiện 3 chỗ trong file: định nghĩa Tabs
  (:258), `State` ở `handle_run_click` (:428) và `State` ở
  `handle_export_click` (:758). **Không có callback nào với
  `Input("viewer-tabs", "value")`** — bấm đổi tab chỉ đổi trạng thái
  active của tab trên giao diện, form tham số và kết quả không bao
  giờ vẽ lại.
- Hệ quả: sau khi đổi tab, form vẫn là tham số của catos, kết quả vẫn
  là run của catos. Bấm "Xem báo cáo" thì có chạy với template_id của
  tab đang chọn (nhờ State), nhưng với bộ tham số của template cũ —
  sai mã tham số / thiếu tham số bắt buộc của vtos thì lỗi hoặc rỗng.

## Thiết kế

- Thêm callback đổi tab: `Input("viewer-tabs", "value")` → vẽ lại
  form tham số cho version ACTIVE của template vừa chọn
  (`preview_layout` + `_lov_options` + `render_param_form`), cập
  nhật `viewer-version-store`, **xóa kết quả cũ** (run-store → {},
  page → 1, xóa lỗi) vì kết quả đó thuộc template kia.
- Đổi tab KHÔNG tự chạy báo cáo: người dùng bấm "Xem báo cáo" để
  tải dữ liệu template mới (tránh tạo run không ai yêu cầu, và tham
  số 2 template có thể khác nhau).

## Phạm vi

- Chỉ app/ui/pages/report_viewer.py (+ test + check live). Dùng
  service/helper đã có (`preview_layout`, `render_param_form`,
  `_lov_options`, `get_version`). Không migration.
