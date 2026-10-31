# Kế hoạch thực hiện — Task 04: Đọc Excel, chuẩn hóa, control total, nạp dữ liệu tạm

## Mục tiêu
Xây dựng pipeline đọc Excel/CSV chuyên biệt bằng Polars + Calamine, đọc mọi cột thô dạng chuỗi, bảo toàn số 0 ở đầu và độ chính xác của số lớn; tự động ánh xạ cột logic theo template; chuẩn hóa dữ liệu và trích xuất dòng lỗi; kiểm tra tổng kiểm soát (Control Total); hỗ trợ gợi ý cấu hình (Inspect); lưu trữ file tập trung và nạp dữ liệu tạm theo lô vào `RECON_EXCEL_LOAD` và `RECON_EXCEL_ROW`.

## Các bước thực hiện

### Bước 1 — Reader (`app/engine/reader.py`)
- Cài đặt `list_sheets(path)` và `read_sheet(path, file_spec) -> tuple[pl.DataFrame, dict[str, str]]`:
  - Đọc file Excel (`.xlsx`, `.xls`) qua `calamine` và CSV (hỗ trợ phân cách `,`, `;`, `\t`, UTF-8 / UTF-8-SIG).
  - Đọc toàn bộ ô dạng `Utf8`, loại bỏ `.0` ở số nguyên, giữ nguyên số 0 ở đầu (e.g. `"0334"`), không mất chính xác.
  - Cắt dòng theo `header_row`, `data_start_row`, `skip_footer_rows`.
  - Sinh cột `__row_no` phản ánh chính xác số dòng thực tế trong file Excel (1-based index).
  - Xử lý header trùng lặp tự động (hậu tố `__2`, `__3`).
- Test viết trước (`tests/unit/test_excel_reader.py`):
  - Đọc `samples/dtp_sample_200.xlsx`: 201 dòng thô (gồm 1 dòng tổng), `__row_no` chuẩn, mã giao dịch và mã đơn vị giữ nguyên số 0 ở đầu.

### Bước 2 — Mapping + detect (`app/engine/mapping.py`)
- Cài đặt `resolve_columns(df, fields)`:
  - Khớp tên cột sau khi chuẩn hóa Unicode NFC, trim, loại bỏ khoảng trắng thừa, không phân biệt hoa thường.
  - Ưu tiên `field.excel` rồi đến `field.excel_aliases`.
  - Báo lỗi `EXCEL_COLUMN_MISSING` nếu thiếu cột required.
  - Đổi tên cột trong DataFrame sang định danh trường logic (`field.name`), giữ lại `__row_no`.
- Cài đặt `detect_template(file_path, templates)`:
  - Tự động nhận diện template dựa trên `detect_by_headers`.
- Test viết trước (`tests/unit/test_excel_mapping.py`).

### Bước 3 — Normalize + derive + invalid (`app/engine/normalize.py`)
- Cài đặt `normalize(df, fields, side="excel") -> tuple[pl.DataFrame, pl.DataFrame]`:
  - Áp dụng các toán tử chuẩn hóa `norm`: `trim`, `upper`, `lower`, `value_map`, `lpad`, `multiply`, `strip_chars`.
  - Chuyển đổi kiểu dữ liệu:
    - `number`: xử lý `thousand_sep` và `decimal_sep`, chuyển thành Decimal/chuỗi số chuẩn. Lỗi -> `PARSE_NUMBER`.
    - `date`/`datetime`: hỗ trợ format tùy biến, số ngày serial Excel (epoch 1899-12-30), chuỗi ISO. Lỗi -> `PARSE_DATE`.
    - `required`: kiểm tra rỗng -> `MISSING_REQUIRED`.
  - Tách riêng DataFrame hợp lệ (`valid_df`) và dòng lỗi (`invalid_df` kèm `__row_no`, `__raw_data`, `__invalid_reasons`).
- Cài đặt `derive(df, derived)`:
  - Tính các trường phái sinh: `trunc_day`, `trunc_month`, `concat`, `substr`, `coalesce`.
- Test viết trước (`tests/unit/test_excel_normalize.py` — Golden G04, G09).

### Bước 4 — Control total + filters (`app/engine/control_total.py`, `app/engine/filters.py`)
- Cài đặt `check_control_total(raw_df, valid_df, control_total_spec)`:
  - Tìm dòng tổng trong `raw_df` theo tiêu chí `locate` (`excel_col == equals`).
  - Tính tổng `calc_total = sum(value_col)` từ dữ liệu chi tiết `valid_df`.
  - So khớp `abs(calc_total - file_total) <= tolerance`. Khớp mẫu DTP: 366.732.000.
- Cài đặt `apply_row_filters(df, row_filters)`:
  - Lọc bỏ dòng tổng hoặc dòng rác trước khi chuẩn hóa (`drop_if`, `keep_if`).
- Cài đặt `apply_time_filter(df, time_spec, p_from, p_to, apply_range_excel=True)`:
  - Lọc dòng trong khoảng `[p_from, p_to]`, đếm dòng ngoài khoảng và ghi nhận tối đa 1000 số dòng vi phạm.
- Test viết trước (`tests/unit/test_excel_control_total_and_filters.py` — Golden G05, G06).

### Bước 5 — Inspect (`app/engine/inspect.py`)
- Cài đặt `inspect_sample(file_path, sheet_name=None)`:
  - Phân tích file: số dòng/cột, dòng tổng ứng viên, cột lẫn kiểu số/chữ, cột có số 0 ở đầu, cột ngày, cột ứng viên làm khóa và tỷ lệ duy nhất.
  - Gợi ý tên trường chuẩn (bỏ dấu tiếng Việt, UPPER_SNAKE_CASE) và kiểu dữ liệu phục vụ Wizard tạo template.
- Test viết trước (`tests/unit/test_excel_inspect.py`).

### Bước 6 — Service file + nạp dữ liệu tạm (`app/services/file_service.py`, `app/services/excel_load.py`)
- Cài đặt `app/services/file_service.py`:
  - `upload_file`: kiểm tra magic bytes (chống đổi đuôi file độc hại), kích thước, tính SHA-256, lưu `storage/files/<sha256>.<ext>`, ghi `RECON_FILE`.
  - `get_file`: kiểm tra quyền và trả đường dẫn file hoặc thông báo nếu file đã bị xóa tạm.
- Cài đặt `app/services/excel_load.py`:
  - `load_excel_to_temp`: tái sử dụng nếu đã nạp cùng file và version (chưa bị xóa); nạp theo lô vào `RECON_EXCEL_LOAD` và `RECON_EXCEL_ROW` (lô 5.000 dòng).
- Bổ sung Flask route `/download/file/<id>` kiểm tra phiên đăng nhập.
- Test viết trước (`tests/unit/test_file_service.py`, `tests/integration/test_excel_load_integration.py`).
