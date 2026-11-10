# Progress — 39-report-viewer

| Bước | Nội dung | Trạng thái | Ngày | Commit |
| --- | --- | --- | --- | --- |
| 0 | Task + nhánh `feat/39-report-viewer` từ `b79f660` + plan | Xong | 2026-11-10 |  |
| 1 | Test đỏ cho 6 mục (15 test mới) | Xong | 2026-11-10 |  |
| 2 | Sửa viewer + form + service | Xong | 2026-11-10 |  |
| 3 | Kiểm chứng cuối + xuất patch | Đang làm | 2026-11-10 |  |

## Số liệu kiểm chứng (10/11/2026)

- Test mới 16 (15 đỏ ban đầu + 1 hồi quy Loading): `test_page_report_viewer.py`
  35 pass, `test_report_run_execute.py` +2 (bind NULL CUSTOM_SQL, VIEW không
  đổi). Typecheck 0 lỗi, lint sạch.
- Full suite (chạy lại sau comparator dagfuncs, 17:28): **1414 pass / 6 skipped**.
- Playwright `~/workspace/check-39.py`: **17/17 PASS** — form ngày
  yyyy-mm-dd, Org trống chạy OK (55 dòng, không DPY-4010), AG Grid + hàng
  Tổng 1.275.000, sort DESC đầu 55.000, trang 2 đầu 5.000, 100 dòng/trang
  dòng cuối 1.000, export luôn mở + progress bar + link tải (cả khi chưa
  xem), nút Xem cùng dòng (dy=6px), console không lỗi mới.
- Seed kiểm chứng: nguồn SQLITE (nguồn SQLITE dùng recon engine nên chạy
  được end-to-end không cần Oracle), 55 dòng fin_revenue, SQL placeholder
  thường `:p_org` (sqlite3 bind phân biệt hoa/thường; Oracle thật dùng
  `:P_ORG` hoa, bind key vẫn là code thường — đã kiểm chứng ở ảnh 1 của
  người dùng).