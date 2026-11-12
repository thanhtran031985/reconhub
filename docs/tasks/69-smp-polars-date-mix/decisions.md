# Task 69 — Decisions

## Chẩn đoán (parent, 12/11/2026 — đã xác minh bằng repro)

- **Cơ chế lỗi (đã tái hiện chính xác)**: Polars dựng lại bảng từ các
  dòng (`pl.from_dicts(rows, schema=...)` hoặc `pl.DataFrame(rows)` dạng
  list-of-dicts) sẽ lỗi `could not append value: 2026-07-08 of type:
  date to the builder` khi một cột đã xác định kiểu Datetime nhưng có 1
  dòng chứa giá trị `date` thuần (không giờ). Repro: `pl.from_dicts` với
  schema Datetime + rows datetime×100 rồi 1 `date` → đúng message của
  run #1033; `pl.DataFrame` list-of-dicts datetime×100 rồi 1 `date` →
  cũng đúng message.
- **3 chỗ dựng lại bảng kiểu này trong đường chạy** (`app/engine/filters.py`):
  `apply_row_filters` (dòng 93), `apply_time_filter` (dòng 156),
  `apply_profile_filters` (dòng 204) — đều `pl.from_dicts(rows,
  schema=df.schema)`.
- **Không phải thủ phạm**: `fetch_df` (`pl.DataFrame(col_dict,
  strict=False)`, dict-of-lists — repro cho thấy mix date/datetime vẫn
  OK, Polars tự upcast); `normalize` / `aggregate` / `compare` (đều
  `infer_schema_length=None` — suy kiểu từ toàn bộ dòng nên an toàn).
- **Vì sao chỉ SMP lỗi, VTOS không**: bước lọc thời gian phía DB trong
  `run_pipeline` chỉ chạy khi cột lọc có mặt trong kết quả SQL
  (`if tf_field and tf_field in db_raw.columns`). SMP lọc theo
  INVOICE_DATE (có trong kết quả) → bước này chạy. VTOS lọc theo
  DATE_VALUE (câu SELECT ngoài không lấy cột này) → bước này bị bỏ qua.
  Kiểm tra trước không chạy bước lọc thời gian phía DB và không chạy lọc
  profile → báo OK nhưng thực thi lỗi (cùng khoảng trống như task 67 C1).
- **Nguồn gốc giá trị `date` lạc loài**: chưa xác định tuyệt đối từ code.
  Oracle DATE qua oracledb trả về `datetime` (kết nối plain thin mode,
  không outputtypehandler — `app/services/source_conn.py`); `normalize`
  trả về `date` đồng nhất cho field type "date" và `datetime` đồng nhất
  cho type "datetime". Giá trị lạc loài chỉ có thể xuất hiện ở bước dựng
  lại bảng với schema (3 chỗ filters.py) khi một dòng mang kiểu khác với
  schema đã suy ra. Fix làm 3 chỗ này chịu được mix bất kể nguồn (D1).

## Quyết định

- D1: ép giá trị về đúng kiểu schema ở 3 chỗ dựng lại bảng trong
  `filters.py` (date→datetime 00:00 cho cột Datetime; datetime→date cho
  cột Date), thay vì đổi schema hay bỏ schema.
- D2: không sửa `fetch_df`, `normalize`, `aggregate`, `compare`.
- D3: không đổi SQL của template SMP/VTOS, không đổi logic lọc thời gian.
- D4: nguồn gốc giá trị `date` lạc loài chưa xác định tuyệt đối từ code;
  xác nhận bằng cách user chạy lại batch #15 sau khi áp patch.

## D5 — Chẩn đoán đã sửa (12/11/2026, thực nghiệm)

**Chẩn đoán ban đầu SAI vị trí lỗi; plan D1 không làm được.** Thử nghiệm
chứng minh `filters.py` KHÔNG THỂ là chỗ lỗi: `df.to_dicts()` luôn trả
giá trị khớp `df.schema` — một DataFrame Polars không thể chứa `date`
trong cột Datetime (mọi đường dựng đều upcast hoặc lỗi ngay khi dựng:
dict-of-lists upcast; list-of-dicts lỗi cả với `infer_schema_length=None`;
`pl.Series(..., strict=False)` upcast; concat frame Date + Datetime
lỗi "type Date is incompatible"; cast từ Object sang Datetime lỗi).
Test theo plan (dựng frame Datetime chứa 1 `date` rồi chạy qua filter)
là **không dựng được** bằng API public của Polars.

**Vị trí lỗi thật**: `compare.py:290`
(`pl.from_dicts(sanitized_rows, infer_schema_length=None)`, qua
`pipeline.py:253`). Tái hiện end-to-end qua `run_pipeline` với config
kiểu SMP (field `NGAY_HD`, type "date", db `INVOICE_DATE`) + mock fetcher
trả datetime như Oracle → đúng message + traceback của run #1033.

**Cơ chế thật**: phía Excel `normalize` → `date` (field type "date");
phía DB `normalize(db_raw, side="db")` chỉ khớp cột theo `f.name`, nên
cột `INVOICE_DATE` (raw `datetime` từ Oracle) bị bỏ qua khi tên field
logic khác tên cột DB → giữ nguyên Datetime; `aggregate` cho excel_agg
Date / db_agg Datetime; `compare()` trộn `date` (key phía Excel) và
`datetime` (key phía DB) trong cùng cột group-by của `result_rows` →
`from_dicts` lỗi. Chỉ sửa `compare()` cũng sai: key đã tính trong
`aggregate` qua `format_key_value` (`date` → "2026-07-08",
`datetime` → "2026-07-08 10:30:00") → crash sẽ thành âm thầm toàn
MISSING.

**Fix (lệch plan D1/D2)**: `app/engine/normalize.py` — khi `side ==
"db"`, khớp cột theo `f.db` nữa (ưu tiên `f.name`, mỗi cột xử lý tối đa
1 lần); phía Excel không đổi. Nhờ đó phía DB normalize `INVOICE_DATE`
→ `date`, hai phía đồng nhất → key khớp (MATCHED, không chỉ hết crash).
`filters.py` giữ nguyên (3 chỗ đó không lỗi được); không thêm
`_coerce_rows_to_schema` như plan. Test mới
`tests/unit/test_normalize_db_columns69.py` (6 test) thay cho file test
filters theo plan.

**Chưa xác nhận trực tiếp với config thật**: BILL_SMART_PORT_BDP /
BILL_VTOS_BDP không có trong repo (nằm trong DB của user); giả thuyết
variant-C (field ngày SMP tên khác cột DB) là giải thích tốt nhất khớp
với crash. VTOS chạy được có lẽ vì tên field ngày trùng cột DB (hoặc
kiểu hai phía đồng nhất). Xác nhận cuối: user chạy lại batch #15 sau
khi áp patch (giống D4).
