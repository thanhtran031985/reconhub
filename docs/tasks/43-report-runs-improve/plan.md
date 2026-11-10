# Plan — Task 43 (đã duyệt)

## Bước 1 — Docs + test đỏ

- Tài liệu task/plan/progress/decisions.
- Test mới `tests/unit/test_report_runs_history43.py`: service trả tên +
  nhóm báo cáo và lọc (ngày chạy, nhóm, tên, người chạy); bảng có cột
  mới, dòng `14,585`, icon tải, không còn nút Xem, link chạy lại
  `?rerun_from=`; viewer `layout(rerun_from=...)` điền sẵn tham số.
- Chạy test đỏ trước khi sửa.

## Bước 2 — Service `list_report_runs`

- JOIN `RECON_REPORT` để `_run_dict` trả thêm `report_name`,
  `category_code` (giữ mọi key cũ).
- Thêm tham số lọc: `from_date`, `to_date` (theo `CREATED_AT`, đến ngày
  tính hết ngày), `category_code`, `report_name` (LIKE không phân biệt
  hoa/thường, escape ký tự `%`/`_`), `created_by`.
- Thêm `list_run_creators(ctx)` trả danh sách người đã chạy (theo đúng
  owner scope) cho ô chọn Người chạy.

## Bước 3 — Trang /report-runs

- Bảng thêm cột: Nhóm (nhãn theo `CATEGORY_LABELS`, mã lạ hiện nguyên mã),
  Tham số (`mã=giá trị`, ngày `DD/MM/YYYY`, trống → `—`, `title` đầy đủ),
  Bắt đầu / Kết thúc (`DD/MM/YYYY HH:mm:ss` qua `format_datetime`),
  Tổng (`FINISHED_AT − CREATED_AT`, 1 chữ số thập phân, dấu phẩy thập phân,
  chưa xong → `—`); Dòng `f"{n:,}"` (`14,585`); File → icon Excel
  (`lucide:file-spreadsheet`) + mũi tên xuống trong `dmc.Tooltip`.
- Bỏ nút Xem và callback `handle_rerun` (chạy luôn); "Chạy lại" thành
  `dcc.Link` sang `/reports/<id>?rerun_from=<run_id>`.
- Thanh lọc: Từ ngày / Đến ngày (`dmc.DateInput`), Nhóm (`dmc.Select`),
  Tên báo cáo (`dmc.TextInput`, debounce), Người chạy (`dmc.Select`),
  nút "Xóa lọc"; đổi lọc → về trang 1.
- Phân trang: giữ `dmc.Pagination`, thêm chọn cỡ trang 20/50/100
  (mặc định 50) + text "Tổng N run".

## Bước 4 — Viewer `?rerun_from=`

- `layout(..., **kwargs)`: có `rerun_from` thì `get_report_run` lấy
  `PARAMS_JSON`, ghi đè `entry["value"]` của preview theo mã tham số
  (khớp mã hiện có ở version ACTIVE, mã lạ bỏ qua); run không tồn tại /
  không có quyền / khác báo cáo thì hiện alert và để form trắng.
- Không tự chạy, không tự nạp kết quả cũ (run-store vẫn trống).

## Bước 5 — Kiểm chứng + xuất patch

- Typecheck + lint + targeted test + full suite.
- Playwright `~/workspace/check-43.py`: lọc theo ngày/tên/người/nhóm,
  đổi cỡ trang, bấm Chạy lại → sang viewer với form điền sẵn tham số,
  bấm Xem ra kết quả; bấm icon tải được file.
- Commit, xuất patch từ `b015955` (tip task 42), verify `git am` sạch.
