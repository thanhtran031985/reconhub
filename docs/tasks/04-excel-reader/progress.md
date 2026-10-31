# Tiến độ — 04-excel-reader

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Reader | ✅ | 2026-11-01 | 82133db |
| 2 | Mapping + detect | ✅ | 2026-11-01 | ed4906c |
| 3 | Normalize + derive + invalid | ✅ | 2026-11-01 | 53e8843 |
| 4 | Control total + filters | ✅ | 2026-11-01 |  |
| 5 | Inspect | 🔄 |  |  |
| 6 | Service file + nạp dữ liệu tạm | ⬜ |  |  |

## Nhật ký
### Bước 4 — 2026-11-01 00:18
- Đã làm:
  - Cài đặt `app/engine/control_total.py`:
    - `check_control_total(raw_df, valid_df, spec, fields, thousand_sep, decimal_sep)`: định vị dòng tổng trong dữ liệu thô `raw_df` theo điều kiện `spec.locate`, trích xuất giá trị số `file_total`; tính tổng `calc_total` từ cột chỉ định trên `valid_df`; kiểm tra sai lệch `diff <= tolerance`; trả về `ControlTotalResult(file_total, calc_total, diff, is_matched, warning, located_row_no)`. Cảnh báo `CONTROL_TOTAL_NOT_FOUND` nếu không tìm thấy dòng tổng.
  - Cài đặt `app/engine/filters.py`:
    - `apply_row_filters(df, row_filters)`: áp dụng các điều kiện lọc dòng `drop_if` và `keep_if` (hỗ trợ `is_null`, `not_null`, `equals`, `not_equals`, `in`, `regex`), dùng để loại bỏ dòng tổng/footer hoặc dòng rác trước khi chuẩn hóa.
    - `apply_time_filter(df, time_filter, p_from, p_to)`: lọc dòng theo khoảng thời gian `[p_from, p_to]` (giờ Việt Nam, gồm cả 2 đầu; hỗ trợ cắt theo ngày hoặc ngày giờ). Đếm số dòng ngoài khoảng `out_of_range_count` và ghi nhận danh sách `__row_no` (tối đa 1000 dòng đầu).
  - Viết test `tests/unit/test_excel_control_total_and_filters.py` xác thực:
    - Kiểm tra Golden G05 trên mẫu DTP: phát hiện dòng 202 là dòng tổng (`366732000`), tính tổng 200 dòng dữ liệu khớp chính xác 100% (`diff = 0`).
    - Kiểm tra sai số `tolerance` và trường hợp không khớp hoặc không tìm thấy dòng tổng.
    - Kiểm tra `drop_if` loại bỏ dòng tổng khỏi 201 dòng thô còn đúng 200 dòng hóa đơn.
    - Kiểm tra Golden G06: lọc thời gian theo khoảng rộng (giữ 200 dòng, `out_of_range = 0`) và lọc hẹp (đếm và ghi nhận chính xác dòng ngoài khoảng).
- Kiểm tra:
  - `uv run pytest tests/unit/test_excel_control_total_and_filters.py -v`: 6/6 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 48 source files.
- Suy ra (nếu có): Dòng tổng cần được định vị trên `raw_df` trước khi lọc dòng, nhưng việc tính `calc_total` phải được thực hiện trên `valid_df` sau khi đã loại bỏ dòng tổng bằng `row_filters` để tránh tính trùng lặp.
### Bước 3 — 2026-11-01 00:15
- Đã làm:
  - Cài đặt `app/engine/normalize.py`:
    - `normalize_value(val, field_spec)`: chuẩn hóa theo từng kiểu dữ liệu:
      - `string`: Unicode NFC, trim, bảo toàn số 0 đứng trước (e.g. `"0334"`).
      - `number`: xử lý định dạng số kiểu Việt Nam (`1.234.567,89`) và quốc tế (`1,234,567.89`), dấu ngoặc âm `(100)` -> `-100`, chuyển về `Decimal` chính xác, không dùng float.
      - `date` / `datetime`: phân tích số ngày Excel serial date (epoch 1899-12-30 tính cả leap year 1900 của Lotus 1-2-3), định dạng theo `field_spec.format` (hỗ trợ `DD/MM/YYYY`, `YYYY-MM-DD`,...), hoặc parse ISO string.
      - `boolean`: phân tích các chuỗi chân trị phổ biến (`true/false`, `1/0`, `có/không`, `t/f`, `yes/no`).
    - `normalize(df, fields)`: chuẩn hóa toàn bộ DataFrame đã mapping cột logic; tách các dòng lỗi sang danh sách invalid rows (`__row_no`, `field`, `raw_value`, `reason`), trả về `(df_valid, invalid_rows)`.
    - `derive(df, derived_fields)`: tính toán các trường phái sinh theo hàm cho phép (`trunc_day`, `concat`).
  - Viết test `tests/unit/test_excel_normalize.py` xác thực:
    - Chuẩn hóa toàn bộ mẫu DTP `dtp_sample_200.xlsx`.
    - Golden G04: phân tích cả số serial date và chuỗi ngày tháng.
    - Golden G09: phát hiện dòng dữ liệu không hợp lệ, phân loại nguyên nhân và tách riêng khỏi tập dòng hợp lệ.
    - Tính toán trường phái sinh `trunc_day` và `concat`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_excel_normalize.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 46 source files.
  - `uv run poe test-engine`: 113 passed.
- Suy ra (nếu có): Xử lý Excel serial date cần tính theo mốc `1899-12-30` do Excel kế thừa lỗi năm nhuận 1900 từ Lotus 1-2-3; việc chuyển đổi float thành `timedelta(days=int(serial), seconds=...)` bảo toàn chính xác giờ/phút/giây.
### Bước 2 — 2026-11-01 00:10
- Đã làm:
  - Cài đặt `app/engine/mapping.py`:
    - `resolve_columns(df, fields)`: so khớp tên cột thô với các trường `FieldSpec`, chuẩn hóa Unicode NFC, trim, gộp khoảng trắng thừa, không phân biệt hoa thường; ưu tiên `excel`, sau đó `excel_aliases`, cuối cùng `name`; báo lỗi `EXCEL_COLUMN_MISSING` nếu thiếu cột bắt buộc (`required=True`); đổi tên cột DataFrame sang định danh trường logic và trả kèm `rename_map`.
    - `detect_template(file_path, templates)`: tự động nhận diện template phù hợp dựa trên danh sách header đặc trưng `detect_by_headers` của cấu hình.
  - Viết test `tests/unit/test_excel_mapping.py` kiểm tra mapping template mẫu DTP, nhận diện alias và sai khác chữ hoa/thường/khoảng trắng, bắt lỗi thiếu cột bắt buộc, tự động nhận diện template từ file mẫu.
- Kiểm tra:
  - `uv run pytest tests/unit/test_excel_mapping.py -v`: 5/5 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 45 source files.
  - `uv run poe test-engine`: 109 passed.
- Suy ra (nếu có): Chuẩn hóa Unicode NFC và gộp khoảng trắng liên tiếp (`\s+ -> ' '`) trên cả header file thô và cấu hình template giúp giải quyết triệt để lỗi người dùng gõ thừa khoảng trắng hoặc dùng tổ hợp ký tự tiếng Việt rời rạc trong Excel.
### Bước 1 — 2026-11-01 00:07
- Đã làm:
  - Cài đặt `app/engine/reader.py`:
    - `list_sheets(path)`: trích xuất danh sách sheet qua `fastexcel` (trả `["Sheet1"]` cho file CSV).
    - `read_sheet(path, file_spec)`: đọc dữ liệu thô qua `calamine` (Excel) hoặc `polars.read_csv` (hỗ trợ phân cách `,`, `;`, `\t` và UTF-8 BOM `\ufeff`).
    - Cắt dòng theo `header_row`, `data_start_row`, `skip_footer_rows`.
    - Sinh cột `__row_no` phản ánh chính xác số dòng thực tế trong file Excel (1-based index).
    - Giữ mọi ô dữ liệu ở kiểu chuỗi (`pl.Utf8`), bảo toàn số 0 ở đầu (e.g. `"0334"`), loại bỏ BOM và tự động gắn hậu tố `__2`, `__3` khi phát hiện header trùng lặp kèm cảnh báo.
  - Viết test `tests/unit/test_excel_reader.py` kiểm tra danh sách sheet, đọc file mẫu `dtp_sample_200.xlsx` 201 dòng thô, header trùng lặp và CSV phân cách `;` kèm UTF-8 BOM.
- Kiểm tra:
  - `uv run pytest tests/unit/test_excel_reader.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 44 source files.
  - `uv run poe test-engine`: 104 passed.
- Suy ra (nếu có): Loại bỏ BOM `\ufeff` ở dòng header CSV là bắt buộc để tránh Polars nhận diện sai tên cột đầu tiên khi file được lưu dưới dạng UTF-8-SIG từ Excel.
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
