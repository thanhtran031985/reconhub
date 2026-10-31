# Tiến độ — 05-db-fetch

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Builder kind=table | ✅ | 2026-11-01 | acacce8 |
| 2 | SQL gộp theo profile | ✅ | 2026-11-01 | dc57a11 |
| 3 | SQL guard | ✅ | 2026-11-01 | b294d46 |
| 4 | Fetch + describe | ✅ | 2026-11-01 |  |

## Nhật ký
### Bước 4 — 2026-11-01 00:46
- Đã làm:
  - Cài đặt `app/engine/fetch.py`:
    - `fetch_df(conn, sql, binds, max_rows=1_000_000, timeout=600)`:
      - Đặt `conn.call_timeout = timeout * 1000` ms và `cursor.arraysize = 10000`.
      - Kéo dữ liệu theo lô chuyển sang Polars DataFrame, bảo toàn Decimal chính xác.
      - Kiểm soát ngưỡng `max_rows`: ném lỗi `SOURCE_TOO_MANY_ROWS` nếu vượt quá giới hạn.
      - Bắt và ánh xạ lỗi Oracle sang mã chuẩn: lỗi quá thời gian -> `SOURCE_TIMEOUT`; lỗi mất kết nối VPN (ORA-03113, ORA-03114, ORA-03135,...) -> `SOURCE_CONNECTION_LOST`.
    - `MockFetcher`: hỗ trợ đọc dữ liệu giả lập từ Parquet/DataFrame cho testing offline và Golden cases.
  - Cài đặt `describe_sql(conn, sql)` trong `app/engine/catalog.py`: bọc câu lệnh `SELECT * FROM (<sql>) WHERE 1=0` để lấy danh sách cột và kiểu dữ liệu.
  - Cài đặt service trong `app/services/template.py`:
    - `preview_source_sql(ctx, template_id, version, profile_code, params)`: sinh câu lệnh SQL và danh sách binds phục vụ Wizard xem trước.
    - `describe_source(ctx, data_source_id, table_name, sql, schema)`: phân tích cấu trúc cột của bảng hoặc SQL tự viết có qua SQL guard.
  - Viết test `tests/unit/test_db_fetch.py`, `tests/integration/test_oracle_fetch.py`, bổ sung test `test_preview_source_sql` trong `tests/unit/test_template_service.py`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_db_fetch.py tests/integration/test_oracle_fetch.py tests/unit/test_template_service.py -v`: 13 passed, 1 skipped (test Oracle tự skip sạch sẽ khi thiếu VPN).
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 56 source files.
  - `uv run poe test`: 172 passed, 4 skipped.
- Suy ra (nếu có): Quá trình kéo dữ liệu từ Oracle Thin driver qua VPN cần thiết lập `call_timeout` trực tiếp trên connection object và đọc theo mẻ `fetchmany(10000)` để kiểm soát tràn bộ nhớ khi truy vấn trả về số lượng dòng khổng lồ.
### Bước 3 — 2026-11-01 00:40
- Đã làm:
  - Cài đặt `app/engine/sql_guard.py`:
    - `strip_comments_and_literals(sql)`: loại bỏ triệt để các khối chú thích dòng (`--`), chú thích khối (`/* ... */`) và chuỗi ký tự nháy đơn literal (`'...'`), bảo toàn chính xác cú pháp các từ khóa bên ngoài.
    - `check_sql(sql, allowed_params)`:
      - Kiểm tra bắt buộc không để trống và không chứa dấu chấm phẩy (`;`).
      - Bắt buộc từ khóa đầu tiên phải là `SELECT` hoặc `WITH` (hỗ trợ Subquery và CTE).
      - Chặn toàn bộ các từ khóa DML/DDL/DCL/PL-SQL nguy hiểm: `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `BEGIN`, `DECLARE`, `EXECUTE`, `EXEC`, `CALL`, `COMMIT`, `ROLLBACK`, `LOCK`.
      - Chặn mệnh đề khóa dòng `FOR UPDATE`.
      - Chặn liên kết cơ sở dữ liệu qua Database Link (`@`).
      - Chặn việc gọi các package hệ thống nguy hiểm của Oracle (`DBMS_*`, `UTL_*`).
      - Kiểm tra biến bind: phát hiện và chặn các biến bind không nằm trong danh sách cho phép; bắt buộc phải có `:p_from` và `:p_to`.
  - Viết test `tests/unit/test_sql_guard.py` với 31 test cases kiểm tra độ an toàn tuyệt đối của bộ lọc.
- Kiểm tra:
  - `uv run pytest tests/unit/test_sql_guard.py -v`: 31/31 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 55 source files.
- Suy ra (nếu có): Bóc tách chuỗi literal `'...'` trước khi kiểm tra từ khóa là tối quan trọng để cho phép các giá trị dữ liệu hợp lệ (như `WHERE status = 'DROP'`) mà không bị chặn nhầm bởi SQL guard.
### Bước 2 — 2026-11-01 00:38
- Đã làm:
  - Mở rộng `app/engine/sql_builder.py` hỗ trợ kỹ thuật pushdown aggregate:
    - Bọc câu lệnh truy vấn nguồn trong subquery `src` khi `pushdown_aggregate=True` và `profile.aggregate=True`.
    - Sinh biểu thức SQL theo cấu hình trường:
      - Áp dụng chuẩn hóa chuỗi `norm` phía Oracle (`UPPER`, `TRIM`, `LOWER`, `value_map` thành mệnh đề `CASE WHEN`).
      - Sinh biểu thức cho các trường phái sinh `derived` (`trunc_day` qua `TRUNC(col)`, `trunc_month` qua `TRUNC(col, 'MM')`, `concat` qua `||`, `substr`, `coalesce`).
    - Sinh các hàm đo lường (`measures`): `SUM`, `COUNT(*)`, `COUNT(col)`, `COUNT(DISTINCT col)`, `MIN`, `MAX`.
    - Hỗ trợ hàm `first_distinct`: sinh đồng thời `MIN(expr) AS col` và `COUNT(DISTINCT expr) AS col__CNT_DIST` để phát hiện dữ liệu không nhất quán (INCONSISTENT).
    - Sinh mệnh đề `GROUP BY` theo danh sách các trường trong `profile.group_by`.
    - Khi tắt cờ `pushdown_aggregate` hoặc `profile.aggregate=False`, trả về câu lệnh SELECT chi tiết không có GROUP BY.
  - Viết test `tests/unit/test_sql_builder_profiles.py` xác thực:
    - Profile `BY_INVOICE`: GROUP BY theo số hóa đơn `UPPER(TRIM("src"."INVOICE_NO"))`, các measures SUM AMOUNT/QTY, COUNT, first_distinct trên ngày HĐ.
    - Profile `BY_DAY_POINT`: GROUP BY ngày cắt TRUNC và điểm thu, đếm số hóa đơn duy nhất `COUNT(DISTINCT UPPER(TRIM("src"."INVOICE_NO")))`.
    - Profile `BY_LINE`: GROUP BY chi tiết dòng theo hóa đơn, mã dịch vụ, PIN.
    - Kiểm tra khi `pushdown_aggregate=False` trả về truy vấn phẳng không bọc `GROUP BY`.
- Kiểm tra:
  - `uv run pytest tests/unit/test_sql_builder_profiles.py -v`: 4/4 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 54 source files.
- Suy ra (nếu có): Đẩy việc chuẩn hóa text (`UPPER(TRIM(...))`) và tính toán `first_distinct` xuống câu lệnh SQL trên Oracle server giúp tận dụng tối đa sức mạnh xử lý của CSDL nguồn, giảm thiểu dung lượng dữ liệu truyền qua VPN.
### Bước 1 — 2026-11-01 00:35
- Đã làm:
  - Cài đặt `app/engine/sql_dialect.py`:
    - `quote_identifier(ident)`: quote định danh theo chuẩn Oracle (`"SCHEMA"."TABLE"`, `"COLUMN"`), bóc tách và chuẩn hóa tên bảng/view/cột.
    - Cài đặt các biểu thức chuẩn Oracle: `trunc_day` (`TRUNC(expr)`), `trunc_month` (`TRUNC(expr, 'MM')`), `concat` (`expr1 || expr2`), `substr`, `coalesce`.
  - Cài đặt `app/engine/sql_builder.py`:
    - `build_source_sql(config, profile=None, params=None)` cho chế độ `kind="table"`:
      - Thu thập danh sách cột trong whitelist từ các trường có mapping cơ sở dữ liệu (`f.db`), không dùng `SELECT *`.
      - Sinh câu lệnh `SELECT <columns> FROM "SCHEMA"."TABLE"`.
      - Sinh mệnh đề `WHERE` an toàn:
        - Xử lý các filters động liên kết với tham số (`p_from`, `p_to`,...), hỗ trợ ép kiểu `cast="trunc_day"`, bind parameter `:param`.
        - Hỗ trợ cờ `skip_if_empty`: tự động bỏ qua điều kiện lọc nếu tham số rỗng/None.
        - Xử lý các filters tĩnh (`static_where`: `=`, `!=`, `in`, `is null`, `is not null`).
  - Viết test `tests/unit/test_sql_builder_table.py` xác thực:
    - Sinh SQL mẫu DTP từ bảng `RECON_SRC.SRC_FACT_INVOICE_DTP` với đầy đủ các cột mapped và mệnh đề WHERE có bind.
    - Kiểm tra `skip_if_empty` khi có và không có giá trị tham số.
    - Kiểm tra các biểu thức `static_where` (IN list, IS NOT NULL, chuỗi ký tự).
- Kiểm tra:
  - `uv run pytest tests/unit/test_sql_builder_table.py -v`: 3/3 passed.
  - `uv run poe lint`: All checks passed.
  - `uv run poe typecheck`: Success, no issues found in 54 source files.
- Suy ra (nếu có): Quá trình quote định danh bảng trên Oracle cần tách theo dấu chấm `.` để quote riêng biệt từng thành phần `"SCHEMA"."TABLE"`, tránh để nguyên chuỗi `"SCHEMA.TABLE"` khiến Oracle hiểu nhầm là tên bảng có chứa ký tự chấm.
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
