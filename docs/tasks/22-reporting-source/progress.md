# Tiến độ – 22-reporting-source

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | SQL validator SELECT-only và bind discovery | ✅ | 04c8c40 |
| 2 | Oracle metadata discovery | ✅ | |
| 3 | VIEW/TABLE object picker và whitelist query builder | ⬜ | |
| 4 | Column/parameter diff khi source đổi | ⬜ | |

## Bước 2 — Oracle metadata discovery (06/11/2026)
- `app/engine/catalog.py`: `list_tables` thêm tham số `object_type` (None = UNION cũ, "TABLE" chỉ ALL_TABLES, "VIEW" chỉ ALL_VIEWS); cache key thêm object_type để cache riêng từng loại.
- `app/services/report_source.py`: `map_oracle_type` (DATE→DATE, TIMESTAMP→DATETIME, NUMBER→NUMBER, VARCHAR2/CHAR/CLOB→STRING, BLOB/RAW→BINARY, lạ→STRING); `_open_checked_connection` (context manager: siết timeout = min(timeout yêu cầu, CALL_TIMEOUT_S của Data Source) + kiểm tra read-only qua USER_SYS_PRIVS, lỗi → DS_NOT_READ_ONLY); `list_report_objects(ctx, ds_id, source_type, q)` (T22-04/T22-05, chỉ object account có quyền SELECT); `list_report_columns(ctx, ds_id, owner, object)` (T22-07 nhánh mock, trả data_type đã map + oracle_data_type gốc).
- `validate_version_sql` (bước 1) cũng dùng `_open_checked_connection` nên validate SQL cũng kiểm tra read-only (theo Q5 "trước khi discover/describe").
- Test: `tests/unit/test_report_source_discovery.py`, thêm `test_catalog_list_tables_object_type` vào `tests/unit/test_catalog.py`. 79 test pass (gồm bước 1 + test cũ).
- T22-07 nhánh Oracle thật chưa chạy được trên máy ảo (không VPN) — kiểm chứng phía người dùng.

## Bước 1 — SQL validator SELECT-only và bind discovery (06/11/2026)
- `app/engine/sql_guard.py`: tách lõi `_check_core` (rỗng/`;`/SELECT-WITH/FOR UPDATE/từ khóa nguy hiểm/DB link/DBMS_/UTL_) dùng chung cho `check_sql` (giữ nguyên hành vi: bind theo allowlist + bắt buộc `:p_from`/`:p_to`) và `check_report_sql` mới (trả `(ok, lý do, binds)`, không bắt buộc `:p_from`/`:p_to`); thêm `discover_binds`.
- `app/services/report_source.py` mới: `validate_version_sql(ctx, sql_text, data_source_id, timeout_sec=300)` (`@requires_menu("report_admin")`) — validator rồi describe thử qua Oracle (0 dòng, `catalog.describe_sql`), timeout = min(timeout yêu cầu, CALL_TIMEOUT_S của Data Source); lỗi SQL → SQL_NOT_ALLOWED, describe lỗi → SQL_DESCRIBE_FAILED.
- Test: `tests/unit/test_report_sql_guard.py` (T22-01/T22-02/T22-03 phần validator), `tests/unit/test_report_source_validate.py` (service, kết nối Oracle giả lập). 65 test pass (gồm `test_sql_guard.py` cũ không đổi).
