# Tiến độ – 22-reporting-source

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | SQL validator SELECT-only và bind discovery | ✅ | |
| 2 | Oracle metadata discovery | ⬜ | |
| 3 | VIEW/TABLE object picker và whitelist query builder | ⬜ | |
| 4 | Column/parameter diff khi source đổi | ⬜ | |

## Bước 1 — SQL validator SELECT-only và bind discovery (06/11/2026)
- `app/engine/sql_guard.py`: tách lõi `_check_core` (rỗng/`;`/SELECT-WITH/FOR UPDATE/từ khóa nguy hiểm/DB link/DBMS_/UTL_) dùng chung cho `check_sql` (giữ nguyên hành vi: bind theo allowlist + bắt buộc `:p_from`/`:p_to`) và `check_report_sql` mới (trả `(ok, lý do, binds)`, không bắt buộc `:p_from`/`:p_to`); thêm `discover_binds`.
- `app/services/report_source.py` mới: `validate_version_sql(ctx, sql_text, data_source_id, timeout_sec=300)` (`@requires_menu("report_admin")`) — validator rồi describe thử qua Oracle (0 dòng, `catalog.describe_sql`), timeout = min(timeout yêu cầu, CALL_TIMEOUT_S của Data Source); lỗi SQL → SQL_NOT_ALLOWED, describe lỗi → SQL_DESCRIBE_FAILED.
- Test: `tests/unit/test_report_sql_guard.py` (T22-01/T22-02/T22-03 phần validator), `tests/unit/test_report_source_validate.py` (service, kết nối Oracle giả lập). 65 test pass (gồm `test_sql_guard.py` cũ không đổi).
