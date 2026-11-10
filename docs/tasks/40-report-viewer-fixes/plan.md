# Plan — 40-report-viewer-fixes

## 1. Nút Xem báo cáo sang dạng loading (giả định: "nút in báo cáo" = nút "Xem báo cáo", vì viewer không có nút In nào)

- Gốc: `handle_run_click` chạy đồng bộ tạo run + chạy query Oracle (nhiều
  giây), trong lúc đó Dash không trả gì về trình duyệt nên nút đứng im;
  bấm lại tạo thêm run trùng (report run không có chặn trùng như /runs/new).
- Theo tài liệu DMC Button (Loading State): `clientside_callback` đặt
  `loading=True` ngay khi bấm (nút tự disable khi loading), callback chính
  trả `loading=False` ở cuối mọi đường (kể cả lỗi). Áp cho cả nút Xem và
  nút Xuất Excel (Xuất cũng chạy query đồng bộ trước khi xếp hàng đợi).

## 2. Org trống ra 0 dòng + tab SQL thực hiện (chỉ ADMIN)

- Task 39 sửa bind NULL chỉ hết lỗi DPY-4010 khi SQL có điều kiện bảo vệ
  NULL (`:P_ORG IS NULL OR ...` / `NVL`). Ra 0 dòng trên app thật nghĩa là
  SQL thật của /reports/5 nhiều khả năng không có điều kiện đó (ví dụ
  `ORG IN (:P_ORG)` hoặc `ORG = :P_ORG` thuần — NULL cho 0 dòng), hoặc
  bind sai mã. Không có DB thật nên không kết luận được từ code — cần tab
  SQL để nhìn thấy câu chạy thật.
- Thêm service `get_run_sql(ctx, run_id)` (ADMIN-only, người thường →
  FORBIDDEN, không rò rỉ SQL): trả SQL_TEXT gốc, binds đã resolve (vắng →
  NULL), câu COUNT và câu phân trang thực thi, source_type, version_id.
- Viewer: tab "SQL thực hiện" trong khu vực Kết quả, chỉ render khi
  `is_admin(ctx)` (chặn ở server lúc dựng layout, không chỉ ẩn CSS).
  Hiển thị SQL dạng mono + bảng binds + cảnh báo khi CUSTOM_SQL dùng bind
  mà không có điều kiện IS NULL/NVL (kiểm tra heuristic trên SQL_TEXT).
- Nếu tab cho thấy SQL thiếu điều kiện NULL thì sửa SQL_TEXT của version ở
  /report-admin (dữ liệu), không sửa code để viết lại SQL của người dùng.

## 3. Export: % thật + các bước

- Trả lời câu hỏi: đúng là bấm Xuất Excel thì hệ thống query dữ liệu
  trước — export cần run DONE nên khi điều kiện tìm kiếm khác run đang xem
  (hoặc chưa xem) thì tạo + chạy run mới đồng bộ, và run-store mới cũng làm
  grid hiện dữ liệu (thiết kế task 39). Giữ nguyên hành vi này: grid hiện
  đúng dữ liệu sẽ xuất. Giai đoạn chạy báo cáo này chưa có % thật (chưa
  biết tổng dòng cho tới khi COUNT xong) nên chỉ hiện loading trên nút
  Xuất + dòng trạng thái "Đang chạy báo cáo…".
- % thật chỉ có khi worker export bắt đầu: cần lưu tiến độ xuống DB để
  poll đọc được. Thêm migration 0007 cho `RECON_RPT_EXPORT`:
  `PROGRESS_PCT INTEGER DEFAULT 0`, `PROGRESS_STEP VARCHAR(100)`.
  Worker `execute_export` cập nhật theo mốc: 5% Chuẩn bị → 10% Truy vấn
  dữ liệu → 10–85% Ghi file (theo số dòng đã ghi / tổng dòng của run DONE,
  cập nhật mỗi batch 5000 dòng) → 90% Hoàn tất file / Nén file → 100%.
  `get_export`/`_export_dict` trả thêm `progress_pct`, `progress_step`,
  `written_rows`; `retry_export` reset về 0.
- Poll hiển thị `dmc.Progress(value=pct)` + dòng "Bước: … — X% (đã ghi
  N / tổng M dòng)". `db-migrate` bắt buộc khi áp patch (xem Q0).
- Nếu không duyệt migration: chỉ hiện tên bước + thanh indeterminate,
  không có % thật (không bịa % theo thời gian).

## 4. Tự động tải file, bỏ nút Tải file Excel

- Bỏ cả hai link "Tải file Excel" (lúc export DONE ngay trong
  `handle_export_click` và trong `handle_export_poll`). Thêm
  `dcc.Download(id="viewer-download")` vào layout; khi DONE, poll (hoặc
  click, nếu cache DONE) trả `dcc.send_file(path)` qua service
  `download_export` (giữ kiểm quyền owner/ADMIN + audit DOWNLOAD_EXPORT
  như route `/download/report-export/<id>`), kèm notification "Đã tải
  file …". Poll tắt sau DONE nên chỉ tải một lần.

## 5. Font AG Grid nhỏ hơn 1 size

- Hiện tại theme quartz mặc định 14px cho cả header và ô. Đặt
  `--ag-font-size: 13px` chỉ trên grid của viewer (class riêng trong
  `custom.css`), không đổi `rowHeight` 32 / `headerHeight` 34, không ảnh
  hưởng grid cột bước 4 (dùng `data_grid` chung nhưng class riêng).

## Kiểm chứng

- Typecheck 0 lỗi, lint sạch, test mới cho 5 mục, full suite xanh.
- Playwright trên seed SQLITE như task 39: bấm Xem 2 lần liên tiếp chỉ
  tạo 1 run + nút loading; Org trống → tab SQL (admin thấy, viewer không
  thấy) hiện SQL + binds; export 55 dòng → progress tăng dần tới 100% +
  bước ghi dòng, file tự tải (bắt sự kiện download), không còn link Tải;
  font grid tính được 13px.
