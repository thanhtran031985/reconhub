# Task 69 — Plan: sửa lỗi Polars `date` lạc trong cột Datetime

## Chẩn đoán (đã xác minh bằng repro, xem decisions.md)

- Lỗi là của Polars khi dựng lại bảng từ các dòng: một cột đã xác định
  kiểu Datetime nhưng có 1 dòng chứa giá trị `date` thuần (2026-07-08,
  không giờ) → `could not append value ... of type: date to the builder`.
  Tái hiện chính xác bằng `pl.from_dicts(rows, schema={'d': Datetime})`
  với rows chứa `datetime` rồi 1 `date`, và bằng `pl.DataFrame(rows)`
  dạng list-of-dicts (100 dòng datetime rồi 1 dòng date).
- 3 chỗ dựng lại bảng kiểu này trong đường chạy: `app/engine/filters.py`
  — `apply_row_filters` (dòng 93), `apply_time_filter` (dòng 156),
  `apply_profile_filters` (dòng 204), đều `pl.from_dicts(rows,
  schema=df.schema)`.
- `fetch_df` (dict-of-lists) và `normalize` / `aggregate` / `compare`
  (`infer_schema_length=None`) đều chịu được mix date/datetime — đã
  kiểm bằng repro, không phải thủ phạm.
- Vì sao chỉ SMP lỗi, VTOS không: ở bước lọc thời gian phía DB, code chỉ
  chạy khi cột lọc có mặt trong kết quả SQL. SMP lọc theo INVOICE_DATE
  (có trong kết quả) → bước này chạy → gặp giá trị `date` lạc → lỗi.
  VTOS lọc theo DATE_VALUE (câu SELECT ngoài không lấy cột này) → bước
  này bị bỏ qua → không lỗi. Kiểm tra trước không chạy bước lọc thời gian
  phía DB và không chạy lọc profile → báo OK nhưng thực thi lỗi.
- Giá trị `date` lạc loài đó từ đâu ra: chưa xác định được 100% từ code
  (phụ thuộc config template + dữ liệu thật, nằm ở DB của user) — xem D4.

## Các bước

1. **Repro test (đỏ trước)**: test mới `tests/unit/test_filters_date_mix69.py`
   — dựng frame có cột Datetime chứa 1 giá trị `date` rồi chạy qua
   `apply_time_filter` / `apply_profile_filters` / `apply_row_filters`
   → hiện tại lỗi đúng như run #1033.
2. **Fix `app/engine/filters.py`**: thêm helper `_coerce_rows_to_schema(rows,
   schema)` — trước mỗi `pl.from_dicts(rows, schema=...)`, ép giá trị về
   đúng kiểu của schema: cột Datetime + giá trị `date` (không phải
   `datetime`) → `datetime(y, m, d)` lúc 00:00; cột Date + giá trị
   `datetime` → `.date()`. Áp dụng ở cả 3 chỗ dựng lại bảng. Không đổi
   logic lọc, chỉ làm cho việc dựng lại bảng chịu được mix date/datetime.
3. **Tests**: test bước 1 xanh; thêm test ngược (cột Date chứa datetime →
   ép về date) và test hồi quy (frame chuẩn không đổi kết quả lọc).
4. **Check live** `~/workspace/check-69-date-mix.py` (port 8119, DB/storage
   riêng `/run/pytest-tmp/check69.*`): chạy batch qua app thật với
   template kiểu SMP (cột lọc thời gian có trong kết quả SQL) trên dữ
   liệu chứa giá trị ngày không giờ → run DONE thay vì FAILED; quét CẢ
   console error VÀ pageerror. Lưu ý: không có Oracle/VPN trên VM nên
   phần DB Oracle chỉ kiểm bằng unit test + mock fetcher; check live dùng
   DS SQLite của app.
5. **Parent**: review diff → chạy lại targeted tests → chạy lại check live
   → typecheck + ruff → full suite → commit 1 commit
   `69-smp-polars-date-mix: ...` → export patch
   `~/workspace/reconhub-task69.patch` → verify `git am` sạch trên
   worktree ở commit task 67 → cập nhật MEMORY.md → giao patch (áp sau
   patch 67, KHÔNG cần db-migrate, chỉ khởi động lại app).

## Quyết định

- D1: ép giá trị về đúng kiểu schema ở 3 chỗ dựng lại bảng trong
  `filters.py` (date→datetime 00:00 cho cột Datetime; datetime→date cho
  cột Date), thay vì đổi schema hay bỏ schema.
- D2: không sửa `fetch_df` (dict-of-lists đã chịu được mix date/datetime
  theo repro) và không sửa `normalize`/`aggregate`/`compare`
  (`infer_schema_length=None` đã an toàn).
- D3: không đổi SQL của template SMP/VTOS, không đổi logic lọc thời gian
  (vẫn chạy khi cột lọc có trong kết quả).
- D4: nguồn gốc giá trị `date` lạc loài chưa xác định tuyệt đối từ code
  (phụ thuộc config template + dữ liệu thật ở DB user); fix làm pipeline
  chịu được mix này bất kể nguồn. Để xác nhận tuyệt đối, sau khi áp patch
  user chạy lại batch #15: nếu SMP chạy xong thì đúng là mix kiểu ở bước
  lọc; nếu vẫn lỗi ở bước khác thì lỗi thật mới sẽ hiện ở card lỗi (task 67).
