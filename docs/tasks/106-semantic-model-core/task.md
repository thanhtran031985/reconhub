# 106-semantic-model-core — Semantic Model Core, Catalog Constraints & Impact Analysis (REPORT-STUDIO-01A)

- Ngày tạo: 2026-11-26
- Giai đoạn: GĐ3
- Phụ thuộc: 02, 19, 20, 21, 22, 31
- Nhánh git: feat/106-semantic-model-core

## Mục tiêu
1. Xây dựng tầng dữ liệu và service lõi cho **Semantic Model** (`RECON_RPT_MODEL*`) phục vụ thiết kế mô hình phân tích (Fact / Dimension / Bridge, Grain bắt buộc cho Fact, Relationship `*:1` và `1:1`, Field metadata, Virtual Date Hierarchy, Simple Measure & Structured Calculated Measure, khung metadata RLS V1).
2. Mở rộng `app/engine/catalog.py` để trích xuất thêm khóa chính, khóa ngoại (`ALL_CONSTRAINTS` / `ALL_CONS_COLUMNS` trên Oracle; `PRAGMA` trên SQLite) và ước lượng số dòng (`NUM_ROWS`) phục vụ gợi ý bảng và kiểm tra quan hệ.
3. Cung cấp đầy đủ nghiệp vụ CRUD Model, Version Lifecycle (`DRAFT → VALIDATED → ACTIVE → ARCHIVED`), Clone, Archive, Optimistic Concurrency (`ROW_VERSION`), khóa Publish (`MODEL_PUBLISH_LOCK`), kiểm tra quan hệ 2 tầng (cấu trúc/đồ thị tức thì + profiling dữ liệu mẫu có timeout ngắn), phát hiện Breaking Change và Impact Analysis.

## Phạm vi
- Database & Migration: `app/db/metadata.py`, `migrations/versions/0018_semantic_model.py`, `app/services/schema_inspector.py`, `app/services/metadata_migration.py`, regenerate `docs/data-model/schema-manifest.json` và `docs/data-model/schema-history.json`.
- Engine Catalog: `app/engine/catalog.py` (`list_table_constraints`, `estimate_table_rows` / `list_tables` mở rộng tùy chọn).
- Schemas & Errors: `app/schemas/semantic_model.py`, `app/schemas/errors.py`.
- Menu & Permissions: `app/ui/menus.py` (thêm `report_model` nhóm `CAU_HINH`, route `/report-models`, cập nhật `ROLE_MENUS_SEED`).
- Services: `app/services/semantic_model.py`, `app/services/semantic_model_validate.py`.
- Tests: `tests/unit/test_semantic_model_schema.py`, `tests/unit/test_catalog_constraints.py`, `tests/unit/test_semantic_model_service.py`, `tests/unit/test_semantic_model_validation.py`.

## Ngoài phạm vi
- Chưa dựng giao diện Model Center / Model Studio UI (triển khai ở task `107-model-studio-ui`).
- Chưa dựng Semantic Query Planner thực thi truy vấn báo cáo (triển khai ở task `108-semantic-query-planner`).
- Chưa dựng Report Studio UI & nâng cấp Viewer/Export (triển khai ở task `109-report-studio-viewer`).
- V1 chỉ tạo **khung metadata RLS** (`RECON_RPT_MODEL_RLS`) và kiểm tra ngữ cảnh `ADMIN`/`username`, chưa tạo bảng gán đơn vị người dùng (`RECON_USER_SCOPE`).
- Không `ALTER` bất kỳ schema vật lý nào trên Oracle Data Source.

## Thiết kế
- Tham chiếu nghiệp vụ: `REPORT_STUDIO_TASK_PROMPT.md` (Phần A, B, F, G, K).
- Quy chuẩn kỹ thuật: `AGENTS.md`, `.agents/rules/security.md`.

## Spec liên quan
- `app/db/metadata.py` (Reporting Core `RECON_REPORT*`)
- `app/services/report_template.py` (mẫu version lifecycle & activate lock)
- `app/services/report_source.py` (`ORACLE_TYPE_MAP`, `effective_column_label`)
- `app/services/perm.py` (`@requires_menu`, `is_admin`)

## Quyết định kiến trúc
1. **Không tạo `app/repo/` mới:** Codebase dùng SQLAlchemy Core trực tiếp trong `app/services/` với bảng định nghĩa tại `app/db/metadata.py`.
2. **Trạng thái Version thống nhất với Reporting Core:** `RECON_RPT_MODEL_VER.STATUS` dùng `DRAFT`, `VALIDATED`, `ACTIVE`, `ARCHIVED`; mỗi `RECON_RPT_MODEL` trỏ `ACTIVE_VERSION_ID` về đúng 1 version `ACTIVE` bất biến (immutable). Sửa model đã phát hành phải clone sang bản `DRAFT` mới.
3. **Nhãn cột tiếng Việt tự động:** Khi nạp cột từ Data Source vào `RECON_RPT_MODEL_FIELD`, dùng `effective_column_label()` kết hợp lookup `DB_COLUMN_MAPPING` sẵn có để tự gợi ý `DISPLAY_NAME`.
4. **Virtual Date Hierarchy:** Cho phép đánh dấu cột `DATE`/`DATETIME` hỗ trợ tách phần ngày ảo (`DAY`, `MONTH`, `QUARTER`, `YEAR`) ngay trong metadata để báo cáo phân tích theo thời gian hoạt động tốt dù Oracle nguồn không có bảng `DIM_DATE`.
5. **Calculated Measure V1 dạng AST có cấu trúc:** Lưu biểu thức dưới dạng JSON AST whitelist (`DIVIDE`, `ROUND`, `COALESCE`, `CASE`, `+`, `-`, `*`, `/`, `SUM`, `COUNT`, `COUNT_DISTINCT`, `AVG`, `MIN`, `MAX`) tham chiếu theo `FIELD_ID`/`MEASURE_ID`; tuyệt đối không lưu hoặc chạy raw SQL tự do.
6. **Validation quan hệ 2 tầng:**
   - *Tầng 1 (Tức thì — Structural & Graph):* kiểm tra kiểu dữ liệu tương thích, quy tắc `*:1`/`1:1`, loại join (`LEFT OUTER`/`INNER`), không vòng lặp (cycle), không đa đường active (ambiguous path), Fact bắt buộc có Grain.
   - *Tầng 2 (Profiling dữ liệu mẫu có kiểm soát):* nút/hành động riêng chạy có `call_timeout` ngắn (10–15s) và giới hạn mẫu để kiểm tra `duplicate dimension keys`, `null rate`, `orphan fact keys`, `join coverage` mà không làm treo bảng Fact lớn.
7. **Khung metadata RLS V1:** Lưu cấu hình chính sách trên bảng `RECON_RPT_MODEL_RLS` (`TABLE_ID`, `COLUMN_NAME`, `POLICY_TYPE` = `OWNER_USERNAME` | `ROLE_LIST` | `ORG_SCOPE_HOOK`, `SCOPE_ATTR`, `ADMIN_BYPASS`, `IS_ACTIVE`) và validate sự tồn tại của cột tham chiếu; chưa mở rộng bảng phạm vi đơn vị người dùng ở V1.
8. **Thư viện ngoài (tùy chọn):** Có thể giữ graph algorithm bằng Python thuần (~30 dòng BFS/DFS) hoặc đánh giá `networkx` nếu cần thuật toán đồ thị nâng cao (ghi rõ trong `decisions.md`).

## Các bước
### Bước 1 — Schema DB `RECON_RPT_MODEL*`, Migration `0018` & Menu `report_model`
- Làm: Thêm 7 bảng (`RECON_RPT_MODEL`, `RECON_RPT_MODEL_VER`, `RECON_RPT_MODEL_TABLE`, `RECON_RPT_MODEL_REL`, `RECON_RPT_MODEL_FIELD`, `RECON_RPT_MODEL_MEASURE`, `RECON_RPT_MODEL_RLS`) vào `app/db/metadata.py` (tương thích `BigInteger().with_variant(Integer, "sqlite")` và Oracle). Tạo migration `migrations/versions/0018_semantic_model.py` (hỗ trợ SQLite batch mode và Oracle). Cập nhật `app/services/schema_inspector.py` (domain `report`), `app/services/metadata_migration.py`, `app/schemas/errors.py`, `app/ui/menus.py` (thêm menu `report_model` nhóm `CAU_HINH`, seed cho `TEMPLATE_OWNER`).
- Test viết trước: `tests/unit/test_semantic_model_schema.py` kiểm tra upgrade/downgrade migration trên SQLite, constraint kiểm tra trạng thái/cardinality/role, và menu `report_model` phân quyền đúng.
- Kiểm tra: `uv run pytest tests/unit/test_semantic_model_schema.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py -v`, `uv run poe schema-introspect` → drift = 0.

### Bước 2 — Mở rộng `app/engine/catalog.py` đọc PK/FK & ước lượng dòng
- Làm: Thêm `list_table_constraints(ds_id, schema, table_name)` vào `app/engine/catalog.py` để lấy PK, Unique Key, Foreign Key (Oracle qua `ALL_CONSTRAINTS` + `ALL_CONS_COLUMNS`; SQLite qua `PRAGMA table_info` + `PRAGMA foreign_key_list` + `PRAGMA index_list`) và đọc `NUM_ROWS` ước lượng (`ALL_TABLES.NUM_ROWS` trên Oracle, cache 10 phút cùng TTL catalog, không làm thay đổi signature cũ của `list_tables`/`list_columns`).
- Test viết trước: `tests/unit/test_catalog_constraints.py` kiểm tra trên SQLite test DB và mock cursor Oracle (bao gồm View không có constraint).
- Kiểm tra: `uv run pytest tests/unit/test_catalog_constraints.py -v`.

### Bước 3 — Schemas & Service CRUD Model, Versioning, Clone, Archive & Concurrency
- Làm: Tạo `app/schemas/semantic_model.py` và `app/services/semantic_model.py` với các hàm `@service @requires_menu("report_model")`: `list_models`, `get_model`, `create_model` (Code bất biến sau lần lưu đầu), `open_or_create_draft`, `save_draft_layout_and_props` (kiểm tra `ROW_VERSION` tránh ghi đè đồng thời → trả `STALE_DATA`), `clone_model` (clone cấu trúc sang Draft mới, không clone report), `archive_model` (chặn dùng cho report mới, giữ nguyên report đang pin version cũ), ghi `RECON_AUDIT_LOG`.
- Test viết trước: `tests/unit/test_semantic_model_service.py` kiểm tra CRUD, immutability của `ACTIVE` version, optimistic concurrency conflict, clone, archive và phân quyền.
- Kiểm tra: `uv run pytest tests/unit/test_semantic_model_service.py -v`.

### Bước 4 — Quản lý Table (Grain), Field, Virtual Date Hierarchy, Measure Studio & RLS Metadata
- Làm: Bổ sung vào `app/services/semantic_model.py`: `add_table_to_draft` (nạp cột từ catalog + tự gắn nhãn `effective_column_label` + gợi ý `FACT`/`DIMENSION` nhưng không tự publish), `remove_table_from_draft`, `update_table_props` (Role, Grain Description/Keys, Default Date Field, Canvas X/Y), `update_field_props` (Role, Aggregation rules theo `DATA_TYPE` — khóa `SUM` cho non-numeric, Format, Visible, Filterable, Sort By, Folder, Virtual Date Hierarchy, Sensitivity), `upsert_measure` / `delete_measure` (Simple + Structured AST Calculated Measure validation), `upsert_rls_policy` / `delete_rls_policy`.
- Test viết trước: mở rộng `tests/unit/test_semantic_model_service.py` kiểm tra Grain, aggregation rules theo datatype, AST Measure validation (từ chối biểu thức ngoài whitelist / tham chiếu field không tồn tại) và RLS metadata.
- Kiểm tra: `uv run pytest tests/unit/test_semantic_model_service.py -v`.

### Bước 5 — Relationship Validation 2 tầng, Model Validate, Diff, Impact Analysis & Publish
- Làm: Tạo `app/services/semantic_model_validate.py` và hoàn thiện `publish_model_version` trong `app/services/semantic_model.py`:
  - CRUD relationship (`upsert_relationship`, `delete_relationship`, hỗ trợ `*:1` và `1:1`, mặc định `LEFT OUTER JOIN` và single cross-filter `DIM → FACT`).
  - `validate_relationship_structure` & `validate_model`: kiểm tra Fact thiếu Grain, datatype mismatch, cycle/loop, ambiguous active paths, measure/field/RLS references, kiểm tra đối tượng/cột vật lý còn tồn tại ở Data Source (không sửa DB).
  - `profile_relationship_data`: kiểm tra dữ liệu mẫu có timeout ngắn + limit (duplicate dim key, null rate, orphan fact keys, join coverage).
  - `diff_model_versions` & `impact_analysis`: phát hiện breaking changes (field removed/hidden, datatype changed, relationship/measure/grain/RLS changed) và liệt kê report/visual bị ảnh hưởng (trả cấu trúc rỗng an toàn nếu `RECON_RPT_VISUAL` chưa tồn tại trước Task 109).
  - `publish_model_version`: dùng `MODEL_PUBLISH_LOCK` trong `RECON_APP_SETTING`, yêu cầu model không có ERROR và có `change_note`, chuyển version cũ sang `ARCHIVED`, set version mới thành `ACTIVE` bất biến, ghi `RECON_AUDIT_LOG`.
- Test viết trước: `tests/unit/test_semantic_model_validation.py` kiểm tra toàn bộ ca PASS/WARNING/ERROR (loop, ambiguous path, duplicate dim key, orphan keys, missing grain, breaking changes, lock publish, audit).
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run poe test-engine` → toàn bộ xanh.

## Chấp nhận khi
- [ ] Migration `0018_semantic_model` chạy upgrade/downgrade sạch trên SQLite (Oracle sẵn sàng syntax chuẩn) và `uv run poe schema-introspect --check` không báo stale/drift.
- [ ] Service Semantic Model tuân thủ `@service`, `@requires_menu("report_model")`, không có raw SQL từ input, không lộ secret Data Source.
- [ ] Fact thiếu Grain không thể Publish; Published (`ACTIVE`) version là bất biến.
- [ ] Validation phát hiện chính xác cycle/loop, ambiguous path, invalid measure AST, datatype mismatch và profiling mẫu không gây hang.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe test-engine` xanh 100%.

### Data Model Impact
- [ ] Migration cập nhật (`0018_semantic_model.py`).
- [ ] DB model cập nhật (`RECON_RPT_MODEL`, `RECON_RPT_MODEL_VER`, `RECON_RPT_MODEL_TABLE`, `RECON_RPT_MODEL_REL`, `RECON_RPT_MODEL_FIELD`, `RECON_RPT_MODEL_MEASURE`, `RECON_RPT_MODEL_RLS`).
- [ ] `uv run poe schema-introspect` đã chạy.
- [ ] `docs/data-model/schema-manifest.json` đã regenerate.
- [ ] `docs/data-model/schema-history.json` đã cập nhật.
- [ ] Schema drift = 0 hoặc đã ghi rõ lý do.
- [ ] Page `/data-model` hiển thị thay đổi đúng phân hệ `report`.
- [ ] Regression tests pass.

## Câu hỏi mở
- Không có (đã chốt: chia 4 task, V1 tạo khung metadata RLS).
