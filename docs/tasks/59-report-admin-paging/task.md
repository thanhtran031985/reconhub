# Task 59 — report-admin-paging

## Yêu cầu (user, 17:48 11/11/2026)
"thêm phân trang cho trang này" — http://127.0.0.1:8050/report-admin.

## Phát hiện trước khi làm (kiểm chứng live 11/11/2026)
- Danh sách báo cáo chính ĐÃ có phân trang từ task 29 (commit
  2ff4e3a, có trong nhánh làm việc của user): 10 dòng/trang,
  `dmc.Pagination` id `admin-pagination`, thanh "Hiển thị X – Y
  trong tổng số Z mục". Kiểm chứng live với 25 báo cáo:
  trang 1 = 10 dòng, sang trang 2/3 đúng, về trang 1 đúng, không
  lỗi JS (check-59-paging.py 8/8).
- Cái thiếu: **không chọn được cỡ trang** — cố định 10 dòng/trang,
  không có Select đổi 20/50/100 như trang Lịch sử báo cáo
  (`report-runs-page-size`, task 55). Với nhiều báo cáo, lật từng
  trang 10 dòng rất mất công.
- Các danh sách khác trên trang không phân trang và giữ nguyên:
  grid cột bước 4 (AG Grid, kéo-thả đổi thứ tự — phân trang sẽ
  phá kéo-thả qua trang), dry-run bước 5 (đã giới hạn 10 dòng,
  task 36), canvas tham số bước 3.

## Phạm vi
Thêm Select chọn cỡ trang 10/20/50/100 (mặc định 10, giữ hành vi
cũ) cho danh sách báo cáo chính ở /report-admin, theo đúng pattern
/report-runs. Không đổi service (phân trang vẫn cắt slice ở
`render_report_list`), không migration.
