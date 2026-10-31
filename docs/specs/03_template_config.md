# Spec 03 – Cấu hình template (TemplateConfig)

`RECON_TEMPLATE_VERSION.CONFIG_JSON` theo schema dưới. Pydantic model ở `app/schemas/template_config.py`; form wizard dựng từ model này. Ví dụ đầy đủ: `samples/templates/DTP_HOA_DON_TAC_NGHIEP.json`.

## 1. Cấu trúc tổng
```jsonc
{ "schema_version": 1, "file": {…}, "fields": […], "derived": […], "db_source": {…},
  "time_filter": {…}, "profiles": […], "control_total": {…} }
```

## 2. FileSpec

| Thuộc tính | Kiểu | Mặc định | Ghi chú |
|---|---|---|---|
| sheet | string | – | Tên sheet chính xác |
| sheet_pattern | string? | null | Regex khi tên sheet đổi theo kỳ |
| header_row | int ≥ 1 | 1 | |
| data_start_row | int > header_row | 2 | |
| skip_footer_rows | int ≥ 0 | 0 | |
| detect_by_headers | string[] | [] | Header bắt buộc để nhận diện template |
| row_filters | `{drop_if: RowFilter[], keep_if: RowFilter[]}` | rỗng | Áp trước chuẩn hóa |
| thousand_sep / decimal_sep | "," "." "" | "," / "." | |

RowFilter: `{ "field" | "excel_col": …, "op": "is_null" | "not_null" | "equals" | "not_equals" | "in" | "regex", "value": … }`.

## 3. FieldSpec

| Thuộc tính | Kiểu | Ghi chú |
|---|---|---|
| name | `^[A-Z][A-Z0-9_]{0,29}$` | Duy nhất trong template |
| label | string | |
| excel / excel_aliases | string? / string[] | Tên header Excel và tên thay thế |
| db | string? | Cột DB (HOA); null nếu chỉ có ở Excel |
| type | text \| number \| date \| datetime | |
| format | string? | `dd/MM/yyyy HH:mm:ss`… |
| norm | NormOp[] | `trim`, `upper`, `lower`, `{lpad:[n,"0"]}`, `{value_map:{…}}`, `{multiply:n}`, `{strip_chars:"…"}` |
| required | bool | Thiếu → INVALID |

## 4. DerivedSpec
`{ "name": "INV_DATE", "label": "Ngày HĐ", "type": "date", "expr": { "fn": "trunc_day", "args": ["INV_DATETIME"] } }`. Hàm: `trunc_day`, `trunc_month`, `concat`, `substr`, `coalesce`. Phía Oracle dịch thành `TRUNC(col)`, `TRUNC(col,'MM')`, `||`, `SUBSTR`, `COALESCE`.

## 5. DbSourceSpec

Mặc định `kind=table`: chọn bảng/view và cột lọc trên giao diện, hệ thống sinh SELECT. `kind=sql` chỉ khi cần JOIN/biểu thức phức tạp.

| Thuộc tính | Kiểu | Ghi chú |
|---|---|---|
| kind | table \| sql | |
| table | string? | `SCHEMA.TABLE` hoặc `TABLE` (dùng DEFAULT_SCHEMA của Data Source) |
| filters | SourceFilter[] | Điều kiện WHERE gắn với tham số |
| static_where | StaticFilter[] | Điều kiện cố định `{column, op, value}`, giá trị vẫn là bind |
| sql | string? | kind=sql: dữ liệu chi tiết, có `:p_from`, `:p_to` |
| params | ParamSpec[] | Bắt buộc `p_from`, `p_to` (datetime, source "user") |
| pushdown_aggregate | bool | Mặc định true |

SourceFilter: `{ "param": "p_from", "column": "INVOICE_DATE", "op": ">=" | "<=" | "=" | "in" | "like", "cast": "none" | "trunc_day", "skip_if_empty": false }`.

ParamSpec: `{ "name", "type": "text"|"number"|"date"|"datetime", "source": "user"|"default", "default", "label", "required", "suggest": "yesterday"|"last_month"|"none" }`. `p_from`, `p_to` luôn `source=user`.

Validator (kind=table): bảng tồn tại (kiểm khi kết nối được; không kết nối được → cảnh báo, không chặn); mọi cột trong filters, static_where, `fields[].db` có trong danh sách cột; phải có filter cho p_from, p_to và cột của chúng kiểu DATE/TIMESTAMP; tham số required phải có filter.

## 6. TimeFilterSpec

| Thuộc tính | Ghi chú |
|---|---|
| excel_field | Trường logic lọc Excel; null = không lọc |
| db_column | kind=table lấy tự động từ filter của p_from |
| granularity | datetime \| date |
| max_range_days | Mặc định 93 |

## 7. ProfileSpec

| Thuộc tính | Ghi chú |
|---|---|
| code, name, is_default | Đúng một profile mặc định |
| group_by | ≥ 1 trường; mọi trường phải có ở cả hai phía |
| aggregate | true gộp; false so chi tiết (phát hiện DUPLICATE) |
| filters | `{field, op, value}` áp cả hai phía trước khi gộp |
| measures | ≥ 1 MeasureSpec |
| drilldown_to, main_measure | |

MeasureSpec: `name`, `label`, `agg` (sum, count, count_distinct, min, max, first_distinct, value), `field`, `compare` (exact, abs_tol, pct_tol, display_only), `tolerance`, `round`, `ignore_case`, `null_as` (null, zero, empty).
Ràng buộc: tham chiếu trường tồn tại; `sum` chỉ cho number; `value` chỉ khi aggregate=false; drilldown không vòng.

## 8. ControlTotalSpec
`{ "locate": { "excel_col": "Dịch vụ", "equals": "Tổng tiền" }, "value_col": "Thành tiền", "tolerance": 0 }`. Dòng tổng luôn bị loại khỏi dữ liệu.

## 9. Version
- Lưu nháp: version mới nhất là DRAFT và chưa có run → ghi đè; ngược lại tạo DRAFT mới = max+1.
- Kích hoạt: cần `DRY_RUN_OK='Y'` với đúng cấu hình đó (hash lưu trong DRY_RUN_JSON); ACTIVE cũ thành RETIRED.
- ARCHIVED không chạy được, vẫn xem run cũ.
