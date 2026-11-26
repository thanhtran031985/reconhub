# Implementation Plan — `106-semantic-model-core`

## 0. Chuẩn bị ngay sau khi được duyệt
- Lưu kế hoạch này vào `docs/tasks/106-semantic-model-core/plan.md`.
- Tạo nhánh `feat/106-semantic-model-core`, đổi trạng thái `⬜ → 🔄` trong `docs/tasks/README.md` và `docs/tasks/106-semantic-model-core/progress.md`.
- Chạy baseline preflight (`git status --short`, `uv run poe lint`, `uv run poe typecheck`, `uv run pytest tests/unit/test_schema_inspector.py tests/unit/test_menu_sync.py tests/unit/test_catalog.py -v`) để phân loại trước mọi lỗi nền.

---

## 1. Chi tiết từng bước

### Bước 1 — Schema DB `RECON_RPT_MODEL*`, Migration `0018`, `schema-introspect` & Menu `report_model`
- **File sửa / tạo:**
  - `app/db/metadata.py`: định nghĩa 7 bảng mới dùng `pk_id_column()`, `JsonText`, `BigInteger().with_variant(Integer, "sqlite")`:
    1. `RECON_RPT_MODEL` (`ID`, `CODE` unique, `NAME`, `DESCRIPTION`, `DATA_SOURCE_ID` FK `RECON_DATA_SOURCE.ID`, `ACTIVE_VERSION_ID` FK `RECON_RPT_MODEL_VER.ID` với `use_alter=True`, `IS_ARCHIVED`, `CREATED_BY/AT`, `UPDATED_BY/AT`, `ROW_VERSION`)
    2. `RECON_RPT_MODEL_VER` (`ID`, `MODEL_ID` FK, `VERSION_NO`, `STATUS IN ('DRAFT','VALIDATED','ACTIVE','ARCHIVED')`, `CHANGE_NOTE`, `VALIDATION_JSON`, `PUBLISHED_BY`, `PUBLISHED_AT`, audit + `ROW_VERSION`, unique `(MODEL_ID, VERSION_NO)`)
    3. `RECON_RPT_MODEL_TABLE` (`ID`, `MODEL_VERSION_ID` FK, `SOURCE_OWNER`, `SOURCE_OBJECT`, `OBJECT_TYPE IN ('TABLE','VIEW')`, `ALIAS`, `DISPLAY_NAME`, `TABLE_ROLE IN ('FACT','DIMENSION','BRIDGE','UNCLASSIFIED')`, `GRAIN_DESC`, `GRAIN_KEYS_JSON`, `DEFAULT_DATE_FIELD`, `IS_HIDDEN`, `POS_X`, `POS_Y`, `DESCRIPTION`, unique `(MODEL_VERSION_ID, ALIAS)`)
    4. `RECON_RPT_MODEL_REL` (`ID`, `MODEL_VERSION_ID` FK, `NAME`, `FROM_TABLE_ID` FK, `FROM_COLUMN`, `TO_TABLE_ID` FK, `TO_COLUMN`, `CARDINALITY IN ('MANY_TO_ONE','ONE_TO_ONE')`, `JOIN_TYPE IN ('LEFT_OUTER','INNER')`, `CROSS_FILTER IN ('SINGLE')`, `IS_ACTIVE`, `VALIDATION_STATUS`, `VALIDATION_JSON`)
    5. `RECON_RPT_MODEL_FIELD` (`ID`, `TABLE_ID` FK, `SOURCE_COLUMN`, `FIELD_CODE`, `DISPLAY_NAME`, `DESCRIPTION`, `DATA_TYPE`, `FIELD_ROLE IN ('DIMENSION','MEASURE_CANDIDATE','KEY','HIDDEN')`, `DEFAULT_AGG`, `FORMAT_MASK`, `IS_VISIBLE`, `IS_FILTERABLE`, `SORT_BY_FIELD_ID` nullable, `FOLDER`, `ENABLE_DATE_HIERARCHY`, `SENSITIVITY`, unique `(TABLE_ID, FIELD_CODE)`)
    6. `RECON_RPT_MODEL_MEASURE` (`ID`, `MODEL_VERSION_ID` FK, `TABLE_ID` FK nullable, `CODE`, `NAME`, `MEASURE_TYPE IN ('SIMPLE','CALCULATED')`, `BASE_FIELD_ID` FK nullable, `AGGREGATION`, `EXPR_JSON`, `FORMAT_MASK`, `FOLDER`, `DESCRIPTION`, unique `(MODEL_VERSION_ID, CODE)`)
    7. `RECON_RPT_MODEL_RLS` (`ID`, `MODEL_VERSION_ID` FK, `TABLE_ID` FK, `COLUMN_NAME`, `POLICY_TYPE IN ('OWNER_USERNAME','ROLE_LIST','ORG_SCOPE_HOOK')`, `SCOPE_ATTR`, `ADMIN_BYPASS`, `IS_ACTIVE`, `DESCRIPTION`)
  - `migrations/versions/0018_semantic_model.py`: `down_revision = "0017_multi_sso_oidc"`; tạo 7 bảng, xử lý vòng FK `RECON_RPT_MODEL.ACTIVE_VERSION_ID` bằng `batch_alter_table` sau khi tạo `RECON_RPT_MODEL_VER`; seed khóa `MODEL_PUBLISH_LOCK` vào `RECON_APP_SETTING`.
  - `app/services/schema_inspector.py`: thêm mô tả 7 bảng vào `TABLE_DESCRIPTIONS`.
  - `app/services/metadata_migration.py`: bổ sung 7 bảng vào `RECON_TABLES_ORDER` và `CONFIG_ONLY_TABLES` theo thứ tự cha → con.
  - `app/schemas/errors.py`: bổ sung `ErrorCode` mới (`MODEL_NOT_FOUND`, `MODEL_VERSION_LOCKED`, `MODEL_INVALID`, `RELATIONSHIP_LOOP`, `AMBIGUOUS_PATH`, `GRAIN_REQUIRED`...).
  - `app/ui/menus.py`: thêm `MenuDef("report_model", "Mô hình báo cáo", "CAU_HINH", "/report-models", 35, "lucide:boxes")` và thêm `"report_model"` vào `ROLE_MENUS_SEED["TEMPLATE_OWNER"]`.
  - `docs/data-model/schema-manifest.json` & `schema-history.json`: regenerate qua `uv run poe schema-introspect`.
  - Cập nhật assertion số lượng bảng (`52 → 59`) trong `tests/unit/test_schema_inspector.py` và `tests/unit/test_page_data_model.py`.
- **Test viết trước:** `tests/unit/test_semantic_model_schema.py`.
- **Lệnh kiểm tra:** `uv run poe schema-introspect; uv run pytest tests/unit/test_semantic_model_schema.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py tests/unit/test_page_data_model.py -v`.
- **Rủi ro:** Vòng FK `RECON_RPT_MODEL ↔ RECON_RPT_MODEL_VER` gây lỗi SQLite nếu tạo constraint ngay trong `create_table`; xử lý bằng `batch_alter_table`.

### Bước 2 — Mở rộng `app/engine/catalog.py` đọc PK/FK & ước lượng dòng
- **File sửa:** `app/engine/catalog.py`: thêm `list_table_constraints(ds_id, schema, table_name)` và `estimate_table_rows(ds_id, schema, table_name)` hỗ trợ Oracle (`ALL_CONSTRAINTS` / `ALL_CONS_COLUMNS` / `ALL_TABLES.NUM_ROWS`) và SQLite (`PRAGMA`), giữ cache 10 phút và signature cũ của `list_tables`/`list_columns`.
- **Test viết trước:** `tests/unit/test_catalog_constraints.py`.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_catalog.py tests/unit/test_catalog_constraints.py -v`.
- **Rủi ro:** `VIEW` Oracle không có constraint hay `NUM_ROWS` → trả về rỗng / `None` an toàn.

### Bước 3 — Schemas & Service CRUD Model, Versioning, Clone, Archive & Concurrency
- **File tạo:** `app/schemas/semantic_model.py`, `app/services/semantic_model.py` (`list_models`, `get_model`, `get_model_version_detail`, `create_model`, `open_or_create_draft`, `save_draft_state` với `ROW_VERSION` optimistic concurrency, `clone_model`, `archive_model`, ghi `RECON_AUDIT_LOG`).
- **Test viết trước:** `tests/unit/test_semantic_model_service.py`.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_semantic_model_service.py -v`.
- **Rủi ro:** Clone/Open Draft phải map chuẩn `old_id → new_id` cho các FK nội bộ.

### Bước 4 — Quản lý Table (Grain), Field, Virtual Date Hierarchy, Measure Studio & RLS Metadata
- **File sửa:** `app/services/semantic_model.py`: `add_table_to_draft`, `remove_table_from_draft`, `update_table_props`, `update_field_props` (aggregation rules theo datatype, Virtual Date Hierarchy, Sort By, Sensitivity), `upsert_measure`/`delete_measure` (Simple + Structured AST whitelist), `upsert_rls_policy`/`delete_rls_policy`.
- **Test viết trước:** mở rộng `tests/unit/test_semantic_model_service.py`.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_semantic_model_service.py -v`.
- **Rủi ro:** Vòng lặp phụ thuộc giữa các Calculated Measure → kiểm tra đồ thị AST trước khi lưu.

### Bước 5 — Relationship Validation 2 tầng, Model Validate, Diff, Impact Analysis & Publish
- **File tạo / sửa:** `app/services/semantic_model_validate.py`, `app/services/semantic_model.py`: CRUD relationship (`*:1`/`1:1`, `LEFT OUTER`/`INNER`, `SINGLE`), Validation Tầng 1 (Cấu trúc/Đồ thị), Validation Tầng 2 (Profiling mẫu có timeout ngắn & limit), `validate_model`, `diff_model_versions`, `impact_analysis` (tự nhận diện bảng `RECON_RPT_VISUAL` nếu đã tồn tại), `publish_model_version` dùng `MODEL_PUBLISH_LOCK` + bắt buộc `change_note` + audit log.
- **Test viết trước:** `tests/unit/test_semantic_model_validation.py`.
- **Lệnh kiểm tra:** `uv run poe typecheck; uv run poe lint; uv run poe security-check; uv run poe schema-introspect --check; uv run poe test-engine`.
- **Rủi ro:** Profiling dữ liệu mẫu trên Oracle lớn → giới hạn mẫu `FETCH FIRST` / `LIMIT` và timeout ngắn.
