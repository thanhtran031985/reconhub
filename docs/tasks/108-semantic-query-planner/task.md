# 108-semantic-query-planner — Semantic Query Planner, Dialect & RLS Metadata Enforcement (REPORT-STUDIO-01C)

- Ngày tạo: 2026-11-26
- Giai đoạn: GĐ3
- Phụ thuộc: 106-semantic-model-core
- Nhánh git: feat/108-semantic-query-planner

## Mục tiêu
1. Xây dựng **Semantic Query Planner** (`app/engine/semantic_planner.py`) chuyển đổi *ý định báo cáo* (`SemanticQueryIntent` — chọn chiều, measure, bộ lọc, sắp xếp, phân trang, loại visual) thành câu lệnh `SELECT` chỉ đọc an toàn dựa trên đồ thị quan hệ của `RECON_RPT_MODEL_VER` đã phát hành (`ACTIVE`).
2. Đảm bảo toàn bộ ràng buộc an toàn ngữ nghĩa: **One Primary Fact Rule (V1)**, chặn xung đột Grain, chặn đường đi nhập nhằng (ambiguous path) và vòng lặp (loop), áp dụng **khung RLS V1 phía server** không thể vượt qua từ trình duyệt.
3. Mở rộng `app/engine/sql_dialect.py` hỗ trợ song song **Oracle** và **SQLite** (cắt ngày ảo `Virtual Date Hierarchy`, chia an toàn `NULLIF`, phân trang `OFFSET/FETCH` vs `LIMIT/OFFSET`) để test CI chạy không cần VPN và chạy thật trên Oracle.
4. Cung cấp service thực thi `execute_semantic_preview` có timeout riêng cho preview, giới hạn số dòng/điểm biểu đồ (Top-N), hỗ trợ `request_seq` chống response cũ ghi đè, qua `sql_guard.check_report_sql()` và bảo vệ nguồn `PROD` (`_check_prod_admin`).

## Phạm vi
- Schemas: `app/schemas/semantic_query.py`, bổ sung `ErrorCode` vào `app/schemas/errors.py` (nếu cần: `GRAIN_CONFLICT`, `AMBIGUOUS_PATH`, `MULTI_FACT_NOT_ALLOWED`, `RLS_SCOPE_MISSING`).
- Engine: `app/engine/sql_dialect.py` (mở rộng dialect Oracle + SQLite), `app/engine/semantic_planner.py`, `app/engine/semantic_sql.py`.
- Services: `app/services/semantic_query.py`, cấu hình giới hạn preview/cardinality trong `app/core/config.py` hoặc `RECON_APP_SETTING`.
- Tests: `tests/unit/test_semantic_planner.py`, `tests/unit/test_semantic_query_rls_security.py`, `tests/integration/test_semantic_query_sqlite.py`.

## Ngoài phạm vi
- Chưa dựng giao diện Report Studio UI hoặc nâng cấp `/reports/<id>` (triển khai ở task `109-report-studio-viewer`).
- Chưa hỗ trợ nhiều bảng Fact có Grain khác nhau trong cùng một visual (V1 chỉ cho 1 Primary Fact mỗi visual).
- Chưa làm bảng gán đơn vị người dùng (`RECON_USER_SCOPE`) — V1 dùng khung metadata RLS (`OWNER_USERNAME`, `ROLE_LIST`, `ORG_SCOPE_HOOK` fail-closed).

## Thiết kế
- Tham chiếu nghiệp vụ: `REPORT_STUDIO_TASK_PROMPT.md` (Phần E, I, K — §65–73, §80–81, §86).
- Quy chuẩn bảo mật: `.agents/rules/security.md`.

## Spec liên quan
- `docs/tasks/106-semantic-model-core/task.md`
- `app/engine/sql_guard.py` (`check_report_sql`, `_check_core`)
- `app/engine/sql_builder.py` (mẫu AST biểu thức & bind param)
- `app/services/report_run.py` (`_check_prod_admin`, `map_oracle_error`, `build_paged_query`)
- `app/services/report_source.py` (`build_report_query`, `open_checked_connection`)

## Quyết định kiến trúc
1. **Không nhận raw SQL từ browser:** Đầu vào duy nhất của Query Planner là `SemanticQueryIntent` chứa `model_version_id`, danh sách `field_id` / `measure_id` / `date_part` / `aggregation`, `filters`, `sorts`, `limit`/`offset`, `visual_type`.
2. **Hỗ trợ cả Oracle và SQLite dialect:** Dùng chung compiler cho cả SQLite (test unit/integration/demo không VPN) và Oracle (nguồn dữ liệu thật), bao gồm `Virtual Date Hierarchy` (`DAY`, `MONTH`, `QUARTER`, `YEAR`), `NULLIF` cho `DIVIDE`, và `OFFSET/FETCH` vs `LIMIT/OFFSET`.
3. **One Primary Fact & Ambiguous Path Safety:**
   - Nếu các measure/field đến từ nhiều Fact có Grain khác nhau → chặn với thông báo tiếng Việt nêu rõ tên Measure và Grain tương ứng.
   - Nếu từ một Dimension tới Fact có từ 2 active path trở lên → chặn và liệt kê đường đi để Model Admin xử lý.
4. **RLS Server-Side (Khung V1):** Server đọc `RECON_RPT_MODEL_RLS` theo các bảng tham gia truy vấn và áp predicate tự động từ `ctx` (`ADMIN` bỏ qua nếu `ADMIN_BYPASS='Y'`, `OWNER_USERNAME` bind `ctx.username`, `ROLE_LIST` bind vai trò hiện tại, `ORG_SCOPE_HOOK` fail-closed `1 = 0` hoặc lỗi nếu chưa cấu hình scope ở V2).
5. **Preview Limit & Stale Response Safety:** Giới hạn mặc định preview đọc từ cấu hình chung (`PREVIEW_MAX_ROWS` = 500–1000, không hardcode rải rác trong page); chart vượt ngưỡng cardinality tự áp Top-N + cờ cảnh báo `truncated=True`. Server gắn timeout ngắn cho Preview (20–30s) và trả kèm `request_seq` để UI bỏ qua response đến muộn.
6. **Thư viện ngoài (tùy chọn):** Có thể cân nhắc `sqlglot` nếu cần kiểm tra/chuẩn hóa AST đa dialect, hoặc tự viết SQL AST builder thuần Python kết hợp `sql_guard.check_report_sql()` (ghi rõ lựa chọn trong `decisions.md`).

## Các bước
### Bước 1 — Contract `SemanticQueryIntent`, ErrorCode & Mở rộng `app/engine/sql_dialect.py`
- Làm: Tạo `app/schemas/semantic_query.py` định nghĩa `SemanticQueryIntent`, `QueryFieldSelection`, `QueryMeasureSelection`, `QueryFilter`, `QuerySort`, `SemanticQueryPlan`, `SemanticQueryResult`. Bổ sung `ErrorCode` cần thiết vào `app/schemas/errors.py`. Mở rộng `app/engine/sql_dialect.py` hỗ trợ `ORACLE` và `SQLITE` cho `quote_identifier`, `date_part` (`DAY`, `MONTH`, `QUARTER`, `YEAR`), `safe_divide`, `paged_sql`, `top_limit_sql`.
- Test viết trước: `tests/unit/test_semantic_planner.py` (phần schema validation và dialect expression rendering Oracle vs SQLite).
- Kiểm tra: `uv run pytest tests/unit/test_semantic_planner.py -v`.

### Bước 2 — Graph Resolver, Primary Fact Rule & Ambiguity / Grain Safety
- Làm: Xây dựng bộ phân giải đồ thị quan hệ trong `app/engine/semantic_planner.py`:
  - Nạp `model_version` `ACTIVE` (từ chối `DRAFT`/`ARCHIVED` trong luồng chạy báo cáo).
  - Xác định tập bảng tham gia truy vấn; thực thi **One Primary Fact Rule** (chặn multi-fact, không tự join Fact-to-Fact).
  - Tìm đường join Dim → Fact (chỉ đi theo quan hệ `IS_ACTIVE='Y'`), phát hiện cycle và **ambiguous active paths** để chặn sớm.
  - Kiểm tra quy tắc aggregation theo `DATA_TYPE` và policy của Measure (khóa `SUM` trên non-numeric, kiểm tra tính nhất quán `*:1`).
- Test viết trước: mở rộng `tests/unit/test_semantic_planner.py` kiểm tra 1 Fact + nhiều Dim, multi-fact grain conflict, ambiguous path block, loop block, invalid aggregation, hidden/missing field block, pin version.
- Kiểm tra: `uv run pytest tests/unit/test_semantic_planner.py -v`.

### Bước 3 — SQL Compiler (Simple & AST Measures, Virtual Date, Filters, RLS, SQL Guard)
- Làm: Tạo `app/engine/semantic_sql.py` nhận kế hoạch join đã duyệt từ `semantic_planner.py` để biên dịch SQL hoàn chỉnh:
  - Biên dịch `SELECT`, `FROM` + `LEFT OUTER JOIN` / `INNER JOIN` đúng chiều, `GROUP BY` (kể cả `Virtual Date Hierarchy`), Simple & Calculated AST Measure (`DIVIDE` bọc `NULLIF(..., 0)`).
  - Áp **RLS V1** từ server-side `ctx` vào mệnh đề `WHERE` (bind parameter).
  - Áp bộ lọc (`=`, `>=`, `<=`, `BETWEEN`, `IN`, `LIKE_PREFIX` có escape `%`/`_`, `IS_NULL`, `RELATIVE_DATE` theo giờ Việt Nam) toàn bộ bằng bind parameters.
  - Áp `ORDER BY`, `LIMIT/OFFSET` hoặc `OFFSET/FETCH` + cardinality Top-N cho chart.
  - Chạy `sql_guard.check_report_sql()` xác minh SQL sinh ra 100% read-only `SELECT` trước khi trả `SemanticQueryPlan`.
- Test viết trước: `tests/unit/test_semantic_query_rls_security.py` kiểm tra toàn bộ phép tổng hợp (`SUM`, `COUNT`, `COUNT_DISTINCT`, `AVG`, `MIN`, `MAX`), AST Measure chia 0, filter operators, chống SQL injection qua field/filter input, RLS không thể bypass, `check_report_sql` PASS.
- Kiểm tra: `uv run pytest tests/unit/test_semantic_query_rls_security.py -v`.

### Bước 4 — Execution Service, Caching, Timeout, Cardinality Guard & Admin SQL Debug
- Làm: Tạo `app/services/semantic_query.py`:
  - Cache metadata Model Version theo `model_version_id` (vì version `ACTIVE` là bất biến) + tùy chọn cache plan ngắn hạn.
  - `execute_semantic_preview(ctx, intent, request_seq=None)`: kiểm tra quyền menu (`report_center` / `report_studio`), kiểm tra `_check_prod_admin`, mở kết nối Data Source (hỗ trợ cả Oracle via `open_checked_connection` với `preview_timeout_sec` ngắn và SQLite test DB), thực thi bind param, trả dữ liệu + metadata cột + cờ `truncated` / warning cardinality + echo `request_seq`.
  - `execute_semantic_query_for_run(ctx, model_version_id, intent, page, page_size)` & `get_semantic_sql_debug(ctx, intent)` (chỉ `ADMIN`, format read-only SQL và che/đánh dấu bind values an toàn, không nút chạy SQL tự do).
- Test viết trước: `tests/integration/test_semantic_query_sqlite.py` chạy end-to-end Planner → SQLite Star Schema DB (Fact + Dim Customer + Dim Date + Dim Service) kiểm tra đúng số liệu `SUM`/`COUNT`, group by Month/Customer, filter, RLS, Top-N limit, stale `request_seq`, và test quyền Admin debug SQL.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe test-engine` → toàn bộ xanh.

## Chấp nhận khi
- [ ] Planner chỉ nhận `SemanticQueryIntent`, luôn ghim đúng `MODEL_VERSION_ID` `ACTIVE`, tuyệt đối không nhận SQL thô từ browser.
- [ ] Chặn chính xác multi-fact grain conflict, ambiguous path, relationship loop và non-numeric `SUM`.
- [ ] RLS được ép ở server-side từ `ctx` và bind params; `sql_guard.check_report_sql()` đạt 100% trên mọi câu SQL sinh ra.
- [ ] Chạy được cả trên SQLite (test không VPN) và Oracle (chuẩn dialect), giữ an toàn `_check_prod_admin` và timeout ngắn cho Preview.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe test-engine` xanh 100%.

### Data Model Impact
- [ ] Task không thay đổi database schema.

## Câu hỏi mở
- Bước 3 cân nhắc dùng compiler Python thuần hay `sqlglot` nếu cần kiểm tra cú pháp SQL đa dialect (ưu tiên Python thuần + `sql_guard` nếu không phát sinh nhu cầu phức tạp).
