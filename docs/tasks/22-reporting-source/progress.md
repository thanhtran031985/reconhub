# Tiến độ – 22-reporting-source

Trạng thái: ✅

## Hồi quy cuối (06/11/2026)
- `uv run poe test`: **749 pass, 5 skip, 0 fail** (670 cuối task 21 + 79 test mới task 22).
- `uv run poe e2e`: **12 pass**.
- `uv run poe typecheck`: **21 lỗi = baseline, 0 mới** (đã sửa 11 lỗi mới trong `report_source.py`: annotation `Any`/`dict[str, Any]`/`Iterator`/`Sequence`/`Connection`).
- `uv run poe lint`: sạch (đã bỏ import thừa `recon_report` trong test diff).
- `tasks-dashboard` đã chạy lại (29 task, 20 xong).
- T22-01..T22-06, T22-08, T22-09 ☑; T22-07 nhánh mock đạt, nhánh Oracle thật ☐ — kiểm chứng phía người dùng khi có VPN.

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | SQL validator SELECT-only và bind discovery | ✅ | 04c8c40 |
| 2 | Oracle metadata discovery | ✅ | |
| 3 | VIEW/TABLE object picker và whitelist query builder | ✅ | |
| 4 | Column/parameter diff khi source đổi | ✅ | |

## Bước 4 — Column/parameter diff khi source đổi (06/11/2026)
- `app/services/report_source.py`: tách `_describe_custom_sql` và `_discover_object_columns` thành hàm thuần dùng chung; `analyze_version_source(ctx, version_id)` (chỉ đọc) — describe lại nguồn (CUSTOM_SQL qua describe, VIEW/TABLE qua list columns) rồi so với RECON_RPT_COLUMN + RECON_RPT_PARAM, trả `{added, removed, type_changed, new_binds, missing_binds}` (CUSTOM_SQL: binds so theo CODE tham số; VIEW/TABLE: missing_binds là tham số có FILTER_COLUMN đã mất); `apply_source_diff(ctx, version_id, diff)` — chỉ version DRAFT, một transaction: cột mới thêm (WEB/EXCEL_VISIBLE='Y', DISPLAY_ORDER nối tiếp +10), cột mất giữ dòng nhưng tắt WEB/EXCEL_VISIBLE (Q6), cột đổi type cập nhật DATA_TYPE, tham số chỉ báo không tự thêm/xóa (task 23), audit UPDATE_VERSION_SOURCE cùng transaction.
- Test: `tests/unit/test_report_source_diff.py` (T22-08). 12 test pass.

## Bước 3 — VIEW/TABLE object picker và whitelist query builder (06/11/2026)
- `app/services/report_source.py`: `build_report_query(source_type, owner, object_name, columns, selected, filters, sorts)` thuần (không DB): sinh `SELECT <cột> FROM <owner.object>` với `quote_identifier` (sql_dialect); cột select/filter/sort phải nằm trong whitelist metadata (so khớp không phân biệt hoa/thường, dùng tên chuẩn); owner/object/mã tham số qua regex identifier (chặn nháy/khoảng trắng/`;`); operator chỉ 7 loại theo check constraint (BETWEEN → 2 bind `_from`/`_to`, IN → 1 bind mỗi phần tử, LIKE_PREFIX cộng `%` vào giá trị bind, IS_NULL không bind); filter rỗng (None/""/[]) bỏ qua; selected rỗng = tất cả cột; giá trị không bao giờ nối vào SQL (T22-03). CUSTOM_SQL không qua builder (dùng SQL snapshot sau validate, lỗi VALIDATION_ERROR nếu gọi nhầm).
- Test: `tests/unit/test_report_query_builder.py` (T22-03/T22-06). 23 test pass.

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
