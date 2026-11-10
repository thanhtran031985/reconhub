# Task 40 — report-viewer-fixes

Tiếp nối task 39 trên trang Xem báo cáo (`/reports/<id>`), sau khi người
dùng kiểm chứng trên app thật. Nhánh `feat/40-report-viewer-fixes`, rẽ từ
`8e2ee1d` (đỉnh `feat/39-report-viewer`).

## Yêu cầu (nguyên văn người dùng, 10/11/2026)

1. Bấm vào nút in báo cáo: chuyển nút in báo cáo sang dạng process (kiểm
   tra tài liệu dash) để user biết đang xử lý, hiện thấy đứng im và ngăn
   user bấm nhiều lần trước khi báo xử lý xong.
2. Org để trống thì không in ra giá trị, kiểm tra câu SQL và thêm tab SQL
   thực hiện, chỉ user quyền ADMIN mới nhìn thấy tab đó.
3. Xuất Excel khi bấm thì đang query dữ liệu? Tôi thấy hiện dữ liệu ra AG
   Grid, progress bar thì nên để theo % thực hiện cho tới đầy 100%, có thể
   ghi thêm các bước thực hiện trong hệ thống để biết hệ thống xử lý bước nào.
4. Bỏ nút Tải file Excel, khi xuất xong tự động download.
5. Header của AG Grid và dữ liệu trong grid nhỏ hơn 1 size so với hiện tại.

## Phạm vi

- Chỉ trang Xem báo cáo (`app/ui/pages/report_viewer.py`,
  `app/ui/components/report_widgets.py`, `app/services/report_export.py`,
  `app/services/report_run.py`) + migration cho tiến độ export (nếu duyệt)
  + CSS của grid viewer.
- Không sửa SQL của báo cáo "BC RM Updated" (dữ liệu của người dùng, sửa
  ở /report-admin nếu tab SQL cho thấy thiếu điều kiện NULL).
- Không đổi trang Lịch sử export (`report_runs.py` giữ link tải của nó).
