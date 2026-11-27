# Kế hoạch — 108-semantic-query-planner

## Implementation Plan — `108-semantic-query-planner`

### Bước 1 — Contract `SemanticQueryIntent`, ErrorCode & Mở rộng `app/engine/sql_dialect.py`
- **File tạo/sửa:**
  - Tạo `app/schemas/semantic_query.py`: định nghĩa Pydantic schemas `QueryFieldSelection` (`field_id`, `date_part` tùy chọn `DAY`/`MONTH`/`QUARTER`/`YEAR`, `alias`), `QueryMeasureSelection` (`measure_id` hoặc ad-hoc `field_id` + `aggregation`, `alias`), `QueryFilter` (`field_id`, `operator` trong `=`/`>=`/`<=`/`BETWEEN`/`IN`/`LIKE_PREFIX`/`IS_NULL`/`RELATIVE_DATE`, `value`), `QuerySort` (`target_type`: `FIELD`|`MEASURE`, `id`, `direction`), `SemanticQueryIntent` (`model_version_id`, `dimensions`, `measures`, `filters`, `sorts`, `visual_type`: `TABLE`|`BAR`|`LINE`|`KPI`, `limit`, `offset`, `request_seq`), `SemanticQueryPlan` (`sql`, `binds`, `dialect`, `primary_fact_table_id`, `tables_used`, `output_columns`, `rls_applied`, `warnings`), `SemanticQueryResult` (`columns`, `rows`, `row_count`, `truncated`, `warning_message`, `request_seq`, `elapsed_ms`).
  - Rà soát `app/schemas/errors.py`: giữ nguyên các `ErrorCode` đã có từ task 106 (`MODEL_NOT_FOUND`, `MODEL_VERSION_LOCKED`, `MODEL_INVALID`, `MODEL_ARCHIVED`, `GRAIN_REQUIRED`, `RELATIONSHIP_LOOP`, `AMBIGUOUS_PATH`, `MULTI_FACT_NOT_ALLOWED`, `GRAIN_CONFLICT`, `RLS_SCOPE_MISSING`).
  - Mở rộng `app/engine/sql_dialect.py` (giữ tương thích ngược 100% các hàm Oracle cũ): bổ sung `dialect` (`ORACLE` | `SQLITE`) cho `quote_identifier`, `date_part_expr(expr, part, dialect)`, `safe_divide(left_expr, right_expr)`, `paged_sql(sql, limit, offset, dialect)`, `top_limit_sql(sql, limit, dialect)`.
- **Test viết trước:** `tests/unit/test_semantic_planner.py` (kiểm tra validation Pydantic `SemanticQueryIntent`, chặn identifier/operator lạ, và render đúng biểu thức Oracle vs SQLite cho `date_part`, `safe_divide`, `paged_sql`).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_semantic_planner.py -v`.
- **Rủi ro:** Lệch kiểu trả về giữa `TRUNC(...)` của Oracle và `DATE/STRFTIME` của SQLite khiến format/sort ngày ở chart khác nhau giữa môi trường test và thật -> xử lý bằng chuẩn hóa output ISO string thống nhất giữa 2 dialect.

### Bước 2 — Graph Resolver, Primary Fact Rule & Ambiguity / Grain Safety
- **File tạo/sửa:**
  - Tạo `app/engine/semantic_planner.py` (hàm thuần, không đụng DB trực tiếp):
    - Kiểm tra version ở trạng thái `ACTIVE` (nếu `DRAFT` hoặc `ARCHIVED` -> ném `MODEL_VERSION_LOCKED`).
    - Phân giải tập bảng cần dùng từ `dimensions`, `measures` (kể cả AST lồng nhau `MEASURE`/`FIELD`), `filters`, `sorts`, và `RLS` đang kích hoạt.
    - Kiểm tra visibility/field existence/aggregation rule (`ALLOWED_AGG_BY_TYPE`: khóa `SUM`/`AVG` trên `STRING`/`DATE`/`BOOLEAN`, khóa field `HIDDEN`).
    - Thực thi **One Primary Fact Rule (V1):**
      - Xác định bảng `FACT` tham gia từ measures/fields. Nếu có từ `>= 2` bảng `FACT` có Grain khác nhau hoặc không cùng 1 bảng Fact chính -> chặn với `MULTI_FACT_NOT_ALLOWED` / `GRAIN_CONFLICT`, nêu rõ tên measure & bảng Fact/Grain xung đột.
      - Nếu chỉ chọn thuộc tính từ `DIMENSION` (không có measure) hoặc 1 `FACT` + `N` `DIMENSION` -> chọn đúng anchor root và xây cây join (BFS/DFS trên đồ thị các quan hệ `IS_ACTIVE = True`).
    - Chặn vòng lặp (`RELATIONSHIP_LOOP`) và đường đi nhập nhằng (`AMBIGUOUS_PATH`: >= 2 active path từ một bảng Dim tới Fact, liệt kê rõ tên quan hệ xung đột).
    - Trả về cấu trúc kế hoạch logic (`ResolvedSemanticPlan`: `root_table`, `join_steps` có thứ tự topo từ root ra ngoài, `selected_dims`, `selected_measures`, `resolved_filters`, `resolved_rls`, `resolved_sorts`, `warnings`).
- **Test viết trước:** mở rộng `tests/unit/test_semantic_planner.py` cho Star Schema 1 Fact + 3 Dim, query chỉ Dim, multi-fact grain conflict, ambiguous path (>= 2 active edge hoặc 2 đường qua bảng trung gian), cycle/loop, non-numeric `SUM`, hidden/missing field, từ chối version `DRAFT`/`ARCHIVED`.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_semantic_planner.py -v`.
- **Rủi ro:** Nếu chỉ có bảng Dim + Measure `COUNT` trên chính bảng Dim (không dùng bảng Fact) -> cho phép `root_table` là Dim duy nhất đó miễn tất cả field/rel đi qua 1 cây hợp lệ không ambiguity/loop.

### Bước 3 — SQL Compiler (Simple & AST Measures, Virtual Date, Filters, RLS, SQL Guard)
- **File tạo/sửa:**
  - Tạo `app/engine/semantic_sql.py`: nhận `ResolvedSemanticPlan`, `ctx` (hoặc snapshot quyền server-side `username`/`roles`/`is_admin`), `dialect` (`ORACLE` | `SQLITE`), `preview_max_rows`, `chart_max_points`:
    - Đặt alias bảng chuẩn (`t0`, `t1`, ...) từ danh sách bảng đã duyệt, mọi tên bảng/schema/cột đều qua whitelist metadata và `quote_identifier`.
    - Biên dịch `FROM` + `LEFT OUTER JOIN` / `INNER JOIN` theo đúng hướng nhiều -> một từ `root_table`.
    - Biên dịch Simple Measure & AST Calculated Measure (`ADD`, `SUB`, `MUL`, `DIV`/`DIVIDE` bọc `NULLIF(..., 0)` + fallback `COALESCE`/`ROUND`/`CASE`, hỗ trợ đệ quy `MEASURE` nội bộ an toàn không vòng lặp).
    - Biên dịch `GROUP BY` theo dimensions (kể cả `Virtual Date Hierarchy`: `DAY`, `MONTH`, `QUARTER`, `YEAR`).
    - Biên dịch **RLS V1** từ `RECON_RPT_MODEL_RLS` (chỉ server đọc từ `ctx`): bỏ qua nếu `ADMIN` và `ADMIN_BYPASS=True`; `OWNER_USERNAME` bind `ctx.username`; `ROLE_LIST` bind `ctx.roles`; `ORG_SCOPE_HOOK` chưa gán scope -> fail-closed ném `RLS_SCOPE_MISSING` (hoặc `1 = 0` khi có scope rỗng).
    - Biên dịch toàn bộ bộ lọc (`=`, `>=`, `<=`, `BETWEEN`, `IN`, `LIKE_PREFIX` có escape `\`/`%`/`_`, `IS_NULL`, `RELATIVE_DATE` tính theo múi giờ Việt Nam `UTC+7`: `TODAY`, `YESTERDAY`, `LAST_7_DAYS`, `THIS_MONTH`, `LAST_MONTH`, `THIS_YEAR`) hoàn toàn qua bind parameters.
    - Biên dịch `ORDER BY`, phân trang `LIMIT/OFFSET` hoặc `OFFSET/FETCH` (thêm tie-breaker ổn định khi phân trang Oracle) + giới hạn Top-N cho chart (`BAR`/`LINE` lấy `chart_max_points + 1` để phát hiện `truncated`).
    - Kiểm chứng cuối cùng qua `sql_guard.check_report_sql(sql)` trước khi trả `SemanticQueryPlan`.
- **Test viết trước:** `tests/unit/test_semantic_query_rls_security.py` kiểm tra đủ 6 phép tổng hợp, AST lồng nhau + chia 0 trả `NULL`, mọi filter operator, `RELATIVE_DATE` theo `Asia/Ho_Chi_Minh`, RLS `OWNER_USERNAME`/`ROLE_LIST`/`ORG_SCOPE_HOOK` fail-closed + không bypass được từ payload, chống SQL injection qua alias/field/filter/sort, và 100% SQL pass `check_report_sql`.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_semantic_query_rls_security.py -v`.
- **Rủi ro:** SQLite không hỗ trợ `SELECT a, SUM(b) FROM ... ORDER BY c` nếu thiếu trong `GROUP BY` -> dùng tên cột/expression nhất quán và test trực tiếp trên SQLite ở Bước 4.

### Bước 4 — Execution Service, Caching, Timeout, Cardinality Guard & Admin SQL Debug
- **File tạo/sửa:**
  - Cập nhật `app/core/config.py` và `.env.example` (nếu cần biến cấu hình preview): thêm `PREVIEW_MAX_ROWS: int = 500`, `PREVIEW_TIMEOUT_SECONDS: int = 25`, `CHART_MAX_POINTS: int = 50` (đọc tập trung từ `Settings`, không hardcode rải rác).
  - Tạo `app/services/semantic_query.py`:
    - Cache bất biến metadata `model_version` `ACTIVE` theo `version_id` (`invalidate_semantic_query_cache` cho test/reset).
    - Hàm trợ giúp mở kết nối read-only hỗ trợ cả Oracle (dùng `open_checked_connection` với `preview_timeout_sec` ngắn + `map_oracle_error`) và SQLite (mở đúng `FILE_PATH` của Data Source nếu có, tương thích `test_semantic_query_sqlite`).
    - `execute_semantic_preview(ctx, intent_payload, request_seq=None)`: kiểm tra quyền `@requires_menu("report_center", "report_admin", "report_model", any_of=True)`, kiểm tra `_check_prod_admin`, lập kế hoạch -> thực thi bind param -> cắt tối đa `PREVIEW_MAX_ROWS` / `CHART_MAX_POINTS` -> trả `SemanticQueryResult` gồm `truncated`, `warning_message`, `request_seq` (chống stale response).
    - `execute_semantic_query_for_run(ctx, model_version_id, intent_payload, page=1, page_size=100)`: kiểm tra quyền `@requires_menu("report_center")`, `_check_prod_admin`, thực thi phân trang + đếm `total` (cho Task 109 / Report Runs).
    - `get_semantic_sql_debug(ctx, intent_payload)`: `@requires_menu("report_admin")` + `require_role(ctx, Role.ADMIN)`, trả SQL read-only kèm danh sách tên bind param (che giá trị nhạy cảm ở log, không cho chạy SQL tự do).
- **Test viết trước:** `tests/integration/test_semantic_query_sqlite.py` (tạo Star Schema SQLite `FACT_SALES` + `DIM_CUSTOMER` + `DIM_DATE` + `DIM_SERVICE`, publish model `ACTIVE`, test `execute_semantic_preview`, `GROUP BY` tháng/khách hàng, AST chia 0, filter + `RELATIVE_DATE`, RLS theo user/role và fail-closed `ORG_SCOPE_HOOK`, cardinality `truncated=True`, `request_seq` echo, `_check_prod_admin` chặn non-admin trên `ENV='PROD'`, `get_semantic_sql_debug` chỉ ADMIN).
- **Lệnh kiểm tra:** `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run pytest tests/unit/test_semantic_planner.py tests/unit/test_semantic_query_rls_security.py tests/integration/test_semantic_query_sqlite.py -v`, và `uv run poe test-engine`.
- **Rủi ro:** Trên SQLite kết hợp `:param_1` với SQLAlchemy raw DBAPI cursor (`sqlite3`), cần truyền `dict` bind param khớp tên `:key` giống `oracledb`.

### Điểm tự suy ra từ spec & quyết định kỹ thuật
1. **Không cài thêm thư viện ngoài (`sqlglot`):** dùng SQL AST compiler thuần Python + `sql_guard.check_report_sql()` để giữ kiến trúc nhất quán với `sql_builder.py` / `report_source.py`.
2. **Menu code cho `execute_semantic_preview`:** hiện `app/ui/menus.py` chưa có mã `report_studio` (dự kiến thêm ở Task 109); dùng `@requires_menu("report_center", "report_admin", "report_model", any_of=True)` để khớp `test_perm_registry.py`.
3. **Chuẩn hóa `Virtual Date Hierarchy` (`DAY`, `MONTH`, `QUARTER`, `YEAR`):** đều trả về chuỗi định dạng thống nhất (`YYYY-MM-DD`, `YYYY-MM`, `YYYY-QQ`, `YYYY`) trên cả Oracle (`TO_CHAR`/`TRUNC`) và SQLite (`DATE`/`STRFTIME`/`PRINTF`).
4. **Cấu hình Preview/Chart Limits:** đặt tại `app/core/config.py` (`PREVIEW_MAX_ROWS=500`, `PREVIEW_TIMEOUT_SECONDS=25`, `CHART_MAX_POINTS=50`) — không thêm migration DB.

### Thư viện cần cài thêm
- Không có.
