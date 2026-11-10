# Plan — 39-report-viewer

## Câu hỏi chốt

- **Q0 — Org trống thì SQL phải viết thế nào mới ra đúng dữ liệu?** Sửa ở
  app chỉ đảm bảo bind `:P_ORG` = NULL thay vì lỗi DPY-4010. Với SQL dạng
  `(:P_ORG IS NULL OR ORG = :P_ORG)` hoặc `ORG = NVL(:P_ORG, ORG)` thì
  để trống = lấy mọi Org. Với SQL dạng `ORG = :P_ORG` thuần thì để trống
  = 0 dòng (đúng ngữ nghĩa SQL, không phải lỗi app). **Cần người dùng
  xác nhận mẫu SQL của báo cáo "BC RM Updated"** (hoặc chấp nhận: sửa
  app trước, nếu ra 0 dòng thì sửa SQL theo mẫu NULL-tolerant).
- **Q1 — Sort trên AG Grid giữ server-side?** Có. Grid `sortable=True`
  nhưng click header chỉ đổi `columnState` → callback dịch thành sorts
  → sort-store → refetch từ server (như cơ chế nút sort hiện tại).
  `suppressMultiSort=True` (giữ sort 1 cột như hiện tại). Filter cột tắt
  (`filter=False`) vì filter client-side trong 1 trang sẽ sai.
- **Q2 — Export khi nào tạo run mới?** So `run_store["values"]` (lưu lúc
  bấm Xem) với form hiện tại: trùng → xuất lại run cũ; khác (hoặc chưa
  có run, hoặc mở từ `?run=`) → tạo + chạy run mới từ form rồi xuất.
  Lỗi tạo/chạy run khi export cũng hiện notification.
- **Q3 — Nút Xem cùng dòng đặt span bao nhiêu?** Ô nút span =
  min(phần còn lại của dòng cuối, 3), tối thiểu 2 cột; phần còn lại < 2
  cột thì xuống dòng mới (nút "Xem báo cáo" không nhét vừa 1 cột).
- **Q4 — Progress bar export dạng nào?** `dmc.Progress` animated +
  chữ "Đang xuất file…", vì service export không báo % tiến độ số.
  DONE → link tải; FAILED → notification lỗi.

## Các bước

1. Test đỏ: ngày `valueFormat` (DATE + DATE_RANGE); CUSTOM_SQL bind
   NULL cho optional vắng (service, SQLite); lỗi run → notification;
   nút Xem cùng dòng khi tổng span < 12; export luôn enable + tạo run
   mới khi form đổi; grid kết quả là AG Grid (columnDefs/rowData từ
   layout, totals pinned).
2. Sửa `report_widgets.py` (valueFormat, `render_param_form(action=...)`,
   `render_result_grid` mới — giữ `render_result_table` cho tới khi
   viewer chuyển hẳn), `report_run.py` (`build_run_query` CUSTOM_SQL),
   `report_viewer.py` (notification, AG Grid + sort columnState, export
   luôn mở + progress bar, run-store lưu values).
3. Kiểm chứng: typecheck + lint + test + Playwright trên viewer thật
   (form ngày yyyy-mm-dd, Org trống không lỗi, grid + phân trang 50/100,
   export có progress bar, nút Xem cùng dòng với 4 tham số mẫu).
4. Commit + xuất patch, giao cho người dùng.
