# Kế hoạch — 05-db-fetch

### Mục tiêu
Xây dựng module truy vấn và kéo dữ liệu nguồn Oracle:
- `app/engine/sql_dialect.py`: Định nghĩa cú pháp Oracle (quote identifiers, bind parameter `:name`, các hàm `trunc_day`, `trunc_month`, `concat`, `substr`, `case/when` cho value_map).
- `app/engine/sql_builder.py`: Sinh SELECT nguồn an toàn từ bảng/view và sinh SQL gộp theo Profile (pushdown aggregate).
- `app/engine/sql_guard.py`: Kiểm duyệt chặt chẽ các câu lệnh SQL tùy biến (loại bỏ comment/literal, chặn DML/DDL/PL-SQL/DBMS_/DB link `@`, bắt buộc bind `p_from`, `p_to`).
- `app/engine/fetch.py`: Kéo dữ liệu từ kết nối Oracle với timeout, chunking arraysize, bảo toàn Decimal, kiểm soát `max_rows`, xử lý ngắt kết nối VPN (`SOURCE_CONNECTION_LOST`, `SOURCE_TIMEOUT`).
- Service `preview_source_sql` phục vụ Wizard bước 3 và bước 4.

---

### Bước 1 — Builder kind=table (`app/engine/sql_dialect.py`, `app/engine/sql_builder.py`)
- Cài đặt `app/engine/sql_dialect.py`:
  - `quote_identifier(name)`: Quote tên bảng/cột chuẩn Oracle (`"SCHEMA"."TABLE"`).
  - Định nghĩa biểu thức hàm Oracle: `TRUNC(..., 'DDD')`, `CONCAT`, `SUBSTR`, `CASE WHEN`.
- Cài đặt `app/engine/sql_builder.py`:
  - `build_source_sql(config, profile=None, params=None)`:
    - Khi `kind == "table"`: chỉ SELECT các cột trong whitelist `config.fields` (có `db` khác None), không dùng `SELECT *`.
    - Sinh mệnh đề WHERE từ `config.db_source.filters` và `static_where`.
    - Xử lý `skip_if_empty`: nếu param rỗng và có cờ `skip_if_empty=True` thì bỏ qua điều kiện.
    - Trả về `(sql_string, binds_dict)`.
- Test viết trước: `tests/unit/test_sql_builder_table.py` (Snapshot SQL mẫu DTP, whitelist cột, skip_if_empty).

---

### Bước 2 — SQL gộp theo profile (`app/engine/sql_builder.py`)
- Mở rộng `build_source_sql`:
  - Khi `profile` có `pushdown_aggregate = True`:
    - Bọc câu lệnh SELECT nguồn làm derived table / subquery `src`.
    - Áp dụng các norm text (`UPPER`, `TRIM`, `value_map` qua `CASE WHEN`).
    - Sinh các biểu thức trường phái sinh `derived`.
    - Sinh mệnh đề `GROUP BY` theo danh sách `profile.group_by`.
    - Sinh các hàm đo lường `measures`: `SUM(col)`, `COUNT(*)`, `COUNT(DISTINCT col)`, `MIN(col)`, `MAX(col)`, `first_distinct` (`MIN(col)` + `COUNT(DISTINCT col)`).
- Test viết trước: `tests/unit/test_sql_builder_profiles.py` (Kiểm tra snapshot 3 profiles: `BY_INVOICE`, `BY_DAY_POINT`, `BY_LINE`).

---

### Bước 3 — SQL guard (`app/engine/sql_guard.py`)
- Cài đặt `check_sql(sql, allowed_params)`:
  - Loại bỏ comment (`--` và `/* ... */`) và chuỗi ký tự literal `'...'`.
  - Phải bắt đầu bằng `SELECT` hoặc `WITH`.
  - Không chứa dấu chấm phẩy `;`.
  - Chặn các từ khóa độc hại: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `BEGIN`, `DECLARE`, `EXECUTE`, `EXEC`, `CALL`, `COMMIT`, `ROLLBACK`, `LOCK`, `FOR UPDATE`, `DBMS_`, `UTL_`, `@`.
  - Kiểm tra bind variables: mọi `:param` phải nằm trong `allowed_params` và phải có `p_from`, `p_to`.
- Test viết trước: `tests/unit/test_sql_guard.py` (≥ 25 test cases bao gồm các kỹ thuật ẩn lệnh, DB link, thiếu bind, injection).

---

### Bước 4 — Fetch + describe (`app/engine/fetch.py`, service)
- Cài đặt `app/engine/fetch.py`:
  - `fetch_df(conn, sql, binds, max_rows=1_000_000, timeout=600)`:
    - Cấu hình cursor `arraysize=10000`, `fetch_decimals=True`.
    - Đặt timeout `call_timeout`.
    - Đọc theo lô, chuyển đổi sang Polars DataFrame, kiểm soát ngưỡng `max_rows` (`SOURCE_TOO_MANY_ROWS`).
    - Bắt các lỗi ngắt kết nối (ORA-03113, ORA-03114, ORA-03135, DatabaseError, TimeoutError) và ánh xạ sang `SOURCE_CONNECTION_LOST` / `SOURCE_TIMEOUT`.
  - Cung cấp `MockFetcher` nạp dữ liệu từ file `parquet` giả lập khi chạy Golden test / dev offline.
- Cài đặt service `preview_source_sql` trong `app/services/template.py`.
- Test viết trước: `tests/unit/test_db_fetch.py` và integration `tests/integration/test_oracle_fetch.py` (auto-skip nếu thiếu VPN).
