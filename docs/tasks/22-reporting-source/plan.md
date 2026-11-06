# Implementation Plan — 22-reporting-source (Nguồn dữ liệu CUSTOM_SQL / VIEW / TABLE)

## Bối cảnh
- Phụ thuộc task 21 — đã xong, nhánh local `feat/21-reporting-core` ở `e9e649f`, patch đã giao 06/11 lúc 14:11, chưa có xác nhận áp/push.
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§4 bước 2, §5, §7), 12a, 12b (luồng A/B), Screen16 preview.
- Code hiện có tái dùng được:
  - `app/engine/sql_guard.py::check_sql` — chặn SELECT-only (SELECT/WITH, cấm `;`, DML/DDL/PLSQL, FOR UPDATE, DB link, DBMS_/UTL_), phát hiện bind; nhưng gắn với template đối soát (bắt buộc `:p_from`/`:p_to`, thông báo nhắc UI template).
  - `app/engine/catalog.py` — `list_tables` (UNION ALL_TABLES + ALL_VIEWS, cache 10 phút), `list_columns` (ALL_TAB_COLUMNS, cache 10 phút), `describe_sql` (SELECT * FROM (...) WHERE 1=0 + cursor.parse).
  - `app/engine/sql_builder.py::build_source_sql` — query builder whitelist cho nguồn table (quote_identifier, filter bind, static_where).
  - `app/services/source_conn.py::open_source_connection` — kết nối Oracle, call_timeout theo Data Source.
  - `app/services/data_source.py` — kiểm tra quyền ghi của account (DS_NOT_READ_ONLY).
  - Task 21 đã có: RECON_RPT_TPL_VER (SOURCE_TYPE/SQL_TEXT/SOURCE_OWNER/SOURCE_OBJECT/TIMEOUT_SEC), RECON_RPT_PARAM (FILTER_COLUMN/FILTER_OPERATOR, check operator), RECON_RPT_COLUMN, services report/report_template (create_template đã validate nguồn theo loại).
- Không thêm package mới (không sqlparse/sqlglot).

## Nhánh và tài liệu
- Nhánh mới `feat/22-reporting-source` từ đầu nhánh task 21 (xem Q0).
- Chép `docs/tasks/22-reporting-source/` từ nhánh docs vào nhánh mới khi tạo nhánh (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này sau khi duyệt).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 22.

## Các bước (theo progress.md)

### Bước 1 — SQL validator SELECT-only và bind discovery
- Thêm `check_report_sql(sql) -> (ok, reason, binds)` vào `app/engine/sql_guard.py`, tái dùng `strip_comments_and_literals` + `DISALLOWED_KEYWORDS` của `check_sql`, nhưng KHÔNG bắt buộc `:p_from`/`:p_to` và thông báo lỗi chung (không nhắc UI template). Trả về danh sách bind đã phát hiện, sắp xếp.
- `check_sql` cũ giữ nguyên cho template đối soát (không đổi hành vi).
- Service `app/services/report_source.py`: `validate_version_sql(ctx, sql_text, data_source_id)` — gọi validator, rồi describe thử qua Oracle (0 dòng) để lấy column metadata khi có kết nối; lỗi SQL → SQL_NOT_ALLOWED / SQL_DESCRIBE_FAILED (mã đã có).
- Test trước: `tests/unit/test_report_sql_guard.py` — T22-01 (SELECT và WITH...SELECT hợp lệ), T22-02 (chặn INSERT/UPDATE/DELETE/MERGE/DDL/PLSQL/multi-statement/`;`/FOR UPDATE/DB link/DBMS_/UTL_), T22-03 (bind phát hiện đủ, giá trị luôn bind không nối chuỗi — kiểm tra ở builder bước 3).
- Kiểm tra: `uv run poe test` (phạm vi unit), `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Oracle metadata discovery
- Mở rộng `catalog.list_tables(ds_id, schema, q, object_type=None)`: `object_type="VIEW"` chỉ ALL_VIEWS, `"TABLE"` chỉ ALL_TABLES, None giữ UNION cũ (tương thích ngược). Thêm `map_oracle_type(oracle_type) -> report DATA_TYPE` (DATE/TIMESTAMP → DATETIME/DATE, NUMBER → NUMBER, VARCHAR2/CHAR → STRING, CLOB → STRING, BLOB → BINARY... theo T22-07).
- Service `app/services/report_source.py` (mới, `@service` + `@requires_menu("report_admin")`): `list_report_objects(ctx, data_source_id, source_type, q=None)` (VIEW/TABLE, chỉ object account có quyền SELECT — ALL_VIEWS/ALL_TABLES vốn đã chỉ trả object được cấp quyền), `list_report_columns(ctx, data_source_id, owner, object_name)` (qua `catalog.list_columns`, kèm DATA_TYPE đã map).
- T22-09 (một phần ở bước này): trước khi discover, kiểm tra account Data Source là read-only (tái dùng phép kiểm tra quyền ghi của data_source) → lỗi DS_NOT_READ_ONLY nếu có quyền ghi; timeout discovery dùng TIMEOUT_SEC của version (mặc định 300) giới hạn bởi CALL_TIMEOUT_S của Data Source (xem Q4).
- Test trước: `tests/unit/test_report_source_discovery.py` với kết nối Oracle giả lập (mẫu `tests/unit/test_catalog.py::catalog_env`) — T22-04, T22-05, T22-07 (nhánh mock); T22-07 nhánh Oracle thật cần VPN — kiểm chứng phía người dùng (ghi decisions.md).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — VIEW/TABLE object picker và whitelist query builder
- `build_report_query(...)` trong `app/services/report_source.py` (logic thuần, tái dùng `quote_identifier` của sql_builder): đầu vào là version (SOURCE_TYPE VIEW/TABLE, SOURCE_OWNER/SOURCE_OBJECT) + cột đã chọn (từ RECON_RPT_COLUMN, WEB_VISIBLE) + filter từ RECON_RPT_PARAM (FILTER_COLUMN/FILTER_OPERATOR + giá trị bind) + sort (cột + hướng). Sinh `SELECT <cột đã quote> FROM <owner.object đã quote> WHERE ... ORDER BY ...`, giá trị luôn bind, không nối chuỗi (T22-03).
- Mọi identifier (owner/object/cột/filter/sort) phải nằm trong metadata đã discover (whitelist); lạ hoặc không whitelist → SQL_NOT_ALLOWED (T22-06). Operator chỉ 7 loại trong check constraint đã có (=, >=, <=, BETWEEN, IN, LIKE_PREFIX, IS_NULL); LIKE_PREFIX thêm `%` ở cuối giá trị bind; IS_NULL không bind.
- CUSTOM_SQL không qua builder — dùng SQL snapshot của version sau khi `validate_version_sql` (bước 1).
- Test trước: `tests/unit/test_report_query_builder.py` — T22-06 (identifier lạ, object không tồn tại, cột không whitelist, operator lạ, sort lạ), T22-03 (bind tách khỏi SQL, IN nhiều giá trị bind từng phần tử).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Column/parameter diff khi source đổi
- `analyze_version_source(ctx, version_id)` (read-only): describe lại nguồn (CUSTOM_SQL qua `describe_sql`, VIEW/TABLE qua `list_report_columns`) rồi so với RECON_RPT_COLUMN + binds hiện tại của version; trả diff `{added: [...], removed: [...], type_changed: [...], new_binds: [...], missing_binds: [...]}` (T22-08).
- `apply_source_diff(ctx, version_id, diff)` (chỉ version DRAFT — ACTIVE không sửa trực tiếp, theo luật task 21): thêm cột mới (WEB/EXCEL_VISIBLE mặc định Y, DISPLAY_ORDER tiếp nối), đánh dấu cột mất (giữ dòng, WEB/EXCEL_VISIBLE='N' + ghi chú vào LABEL? — xem Q6), cập nhật DATA_TYPE cột đổi type; params theo binds mới/mất để task 23 xử lý tiếp (chỉ báo, không tự xóa param — param có thể gắn LOV/layout).
- Test trước: `tests/unit/test_report_source_diff.py` với Oracle giả lập — T22-08 (cột mới/mất/đổi type, bind mới/mất).
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path; không đổi hành vi `check_sql`/`list_tables` cũ (test cũ phải xanh).

## Câu hỏi chốt (Q0–Q7)
- Q0: Patch task 21 chưa có xác nhận áp/push. Làm nhánh `feat/22-reporting-source` từ local `e9e649f` (đầu nhánh task 21) ngay, và bạn áp patch task 21 trước rồi mới áp patch task 22 lên trên (thứ tự bắt buộc)? Hay chờ bạn áp/push task 21 xong mới bắt đầu task 22?
- Q1: Đặt code như đề xuất (validator mở rộng trong `sql_guard.py`, discovery/query builder/diff trong service mới `app/services/report_source.py`, tái dùng `catalog.py` + `sql_builder.quote_identifier`)? Hay muốn gom hết vào module mới riêng?
- Q2: Validator report tái dùng lõi `sql_guard` (strip comments/literals + DISALLOWED_KEYWORDS) nhưng bỏ bắt buộc `:p_from`/`:p_to`. Đồng ý?
- Q3: `list_tables` thêm tham số `object_type` ("VIEW"/"TABLE"/None) thay vì viết query mới. Đồng ý?
- Q4: Timeout khi discover/describe: dùng `min(TIMEOUT_SEC của version, CALL_TIMEOUT_S của Data Source)`. Đồng ý?
- Q5: Trước khi discover/describe, kiểm tra account Data Source là read-only (tái dùng phép kiểm tra quyền ghi của data_source), lỗi thì DS_NOT_READ_ONLY. Đồng ý? Hay chỉ tin vào chính sách account read-only (spec §2) và không kiểm tra lúc chạy?
- Q6: `apply_source_diff` với cột mất: giữ dòng cột nhưng tắt WEB/EXCEL_VISIBLE (để wizard/task 27 cho người xem lại rồi xóa tay), hay xóa luôn dòng cột? Đề xuất: giữ dòng + tắt hiển thị.
- Q7: Làm xong cả task rồi gửi xem như task 19/20/21, hay dừng sau mỗi bước chờ "continue"?
