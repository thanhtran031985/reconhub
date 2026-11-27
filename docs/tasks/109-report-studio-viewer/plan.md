# Kế hoạch — 109-report-studio-viewer

## Implementation Plan — `109-report-studio-viewer`

### Bước 1 — Schema DB (`RECON_RPT_VISUAL*`), Migration `0019`, `schema-introspect` & Menu `report_studio`
- **File tạo/sửa:**
  - `app/db/metadata.py`:
    - Mở rộng `RECON_RPT_TPL_VER`: thêm cột `MODEL_VERSION_ID` (`ForeignKey("RECON_RPT_MODEL_VER.ID")`, nullable), mở rộng `ck_recon_rpt_tpl_ver_source_type` thêm `'SEMANTIC_MODEL'`.
    - Thêm bảng `RECON_RPT_VISUAL` (`ID`, `VERSION_ID` FK -> `RECON_RPT_TPL_VER.ID`, `CODE`, `TITLE`, `VISUAL_TYPE` IN `'TABLE' | 'MATRIX' | 'KPI' | 'BAR' | 'LINE'`, `DISPLAY_ORDER`, `GRID_SPAN` trong `3/4/6/8/12`, `HEIGHT_SIZE` IN `'S' | 'M' | 'L'`, `CONFIG_JSON`, `ROW_VERSION`, `CREATED_AT`, `UPDATED_AT`).
    - Thêm bảng `RECON_RPT_VISUAL_FIELD` (`ID`, `VISUAL_ID` FK -> `RECON_RPT_VISUAL.ID` CASCADE, `WELL_ROLE`, `FIELD_ID` nullable FK -> `RECON_RPT_MODEL_FIELD.ID`, `MEASURE_ID` nullable FK -> `RECON_RPT_MODEL_MEASURE.ID`, `AGGREGATION`, `DATE_PART`, `ALIAS`, `LABEL_OVERRIDE`, `FORMAT_MASK`, `SORT_DIRECTION`, `DISPLAY_ORDER`; giữ đúng tên bảng/cột mà `app/services/semantic_model.py` đã chuẩn bị cho `impact_analysis()`).
    - Mở rộng `RECON_REPORT_RUN`: thêm `VISUAL_ID` (FK -> `RECON_RPT_VISUAL.ID`, nullable) và `QUERY_SPEC_JSON` (`JsonText`, snapshot `SemanticQueryIntent` lúc chạy/xuất).
  - Tạo `migrations/versions/0019_report_studio.py`: nâng cấp/hạ cấp tương thích cả SQLite (`batch_alter_table`, `recreate="always"`) và Oracle, đồng thời seed menu `report_studio` (`RECON_MENU`, `RECON_ROLE_MENU` cho `TEMPLATE_OWNER`) idempotent theo mẫu `0018_semantic_model.py`.
  - Cập nhật `app/services/schema_inspector.py` (mô tả bảng `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD`), chạy `uv run poe schema-introspect` cập nhật `docs/data-model/schema-manifest.json` & `schema-history.json`.
  - Cập nhật `app/services/metadata_migration.py` (`RECON_TABLES_ORDER`): đưa nhóm `RECON_RPT_MODEL*` lên trước `RECON_RPT_TPL_VER` (do FK mới `MODEL_VERSION_ID`) và đặt `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD` giữa `RECON_RPT_TPL_VER` và `RECON_REPORT_RUN`.
  - Cập nhật `app/ui/menus.py`: thêm `MenuDef("report_studio", "Report Studio", "CAU_HINH", "/report-studio", 47, "lucide:bar-chart-2")` và cấp cho `TEMPLATE_OWNER` trong `ROLE_MENUS_SEED` (chỉ `ADMIN` + `TEMPLATE_OWNER` thiết kế, `OPERATOR`/`VIEWER` xem/chạy ở `/reports`).
- **Test viết trước:** `tests/unit/test_report_studio_persistence.py` (kiểm tra `alembic upgrade/downgrade`, constraint `VISUAL_TYPE`/`SOURCE_TYPE`, tương thích ngược report `CUSTOM_SQL`/`VIEW`/`TABLE`).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_report_studio_persistence.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py -v`, `uv run poe schema-introspect --check`.
- **Rủi ro:** Thay đổi CheckConstraint `ck_recon_rpt_tpl_ver_source_type` trên SQLite khi `ALTER TABLE` cần `batch_alter_table(..., recreate="always")` và giữ đúng tên constraint để `downgrade()` không lỗi.

### Bước 2 — Service Report Studio CRUD, Validate, Publish & Impact Analysis Connection
- **File tạo/sửa:**
  - Tạo `app/schemas/report_studio.py` (`StudioReportCreateDTO`, `StudioVisualFieldDTO`, `StudioVisualDTO`, `StudioDraftSaveDTO`, `StudioPublishDTO`, hằng `VISUAL_TYPES`/`WELL_ROLES`/`GRID_SPANS`/`HEIGHT_SIZES`).
  - Tạo `app/services/report_studio.py`:
    - `list_studio_reports`, `create_studio_report` (chặn nếu `model_version_id` không `ACTIVE` → `MODEL_VERSION_LOCKED`), `open_or_create_studio_draft` (clone cả `RECON_RPT_VISUAL*` & `RECON_RPT_PARAM*`), `get_studio_report_draft` (trả kèm model bundle + visuals + params).
    - `save_studio_draft` (kiểm tra `ROW_VERSION` chống ghi đè, lưu visuals/fields/filter params, đưa `DRY_RUN_OK` → `DRAFT`).
    - `validate_studio_report` (kiểm tra tương thích từng loại visual, gọi `resolve_semantic_plan` cho mỗi visual trên pinned `MODEL_VERSION_ID`, chuyển `DRY_RUN_OK` khi 0 lỗi).
    - `publish_studio_report` (khóa `REPORT_ACTIVATE_LOCK`, re-validate, kích hoạt `ACTIVE`, archive bản cũ, ghi `RECON_AUDIT_LOG`).
    - `clone_studio_report`, `archive_studio_report`, `build_visual_intent`, `preview_studio_visual` (gọi `execute_semantic_preview` và dựng bảng pivot cho `MATRIX` ở server với giới hạn kích thước an toàn).
  - Rà soát & hoàn thiện `impact_analysis()` trong `app/services/semantic_model.py` (đảm bảo xử lý cả breaking changes mức bảng/field/measure liên quan `RECON_RPT_VISUAL*`) và cập nhật `app/services/report_template.py` (`_version_dict` trả thêm `model_version_id`, giữ nguyên luồng wizard cũ cho `CUSTOM_SQL`/`VIEW`/`TABLE`).
- **Test viết trước:** mở rộng `tests/unit/test_report_studio_persistence.py` (chặn model `DRAFT`, optimistic lock `CONFLICT`, validate từng visual + `Matrix`, publish pin `MODEL_VERSION_ID`, và `impact_analysis` trả đúng report/visual ảnh hưởng khi thay đổi model).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_report_studio_persistence.py tests/unit/test_semantic_model_validation.py -v`.
- **Rủi ro:** Tham chiếu field/measure trong `RECON_RPT_VISUAL_FIELD` trỏ sang `RECON_RPT_MODEL_FIELD`/`MEASURE` của `MODEL_VERSION_ID` cụ thể; khi model mở Draft v2 có ID field mới thì `impact_analysis` phải map theo `SOURCE_OBJECT`/`FIELD_CODE`/`CODE` (tương thích cấu trúc `diff` của Task 106).

### Bước 3 — Report Studio Center (`/report-studio`) & Khung Designer 3 Panel
- **File tạo/sửa:**
  - Tạo `app/ui/pages/report_studio_center.py` (`/report-studio`, `MENU_CODE = "report_studio"`): header, command bar (tìm kiếm, lọc trạng thái/model), `data_grid` (`dag.AgGrid`) danh sách báo cáo Studio + cột thao tác (Thiết kế, Xem ở `/reports/<id>`, Clone, Phát hành, Lưu trữ, Impact Drawer), modal `+ Tạo báo cáo` (chỉ liệt kê Semantic Model đang `ACTIVE`).
  - Tạo `app/ui/pages/report_studio.py` (`/report-studio/<report_id>/edit` + `/report-studio/<report_id>`, `MENU_CODE = "report_studio"`): khung 3 panel Fluent Compact không cuộn cả trang (`Trường & Chỉ số` | `Report Canvas 12 cột` | `Thiết lập biểu đồ & dữ liệu`), header (`Xem trước`, `Kiểm tra`, `Lưu nháp`, `Phát hành`, menu `...`), Status Bar, tìm kiếm trường in-memory không query DB, ẩn field `HIDDEN`, nhóm Dimensions / Virtual Date Hierarchy / Measures, hỗ trợ checkbox + nút `+`.
  - Cập nhật `app/ui/layout/shell.py` (`build_breadcrumbs` cho `/report-studio` và `/report-studio/<id>/edit`) và `app/ui/assets/custom.css` (class bố cục 3 panel theo biến `tokens.css`).
- **Test viết trước:** `tests/unit/test_report_studio_ui.py` (phân quyền menu, không hiện trường `HIDDEN`, lọc search in-memory, 4 trạng thái UI, tạo/mở báo cáo).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_report_studio_ui.py -v`.
- **Rủi ro:** Đụng quy tắc `test_perm_registry.py` hoặc tràn chiều cao `1366×768` nếu không dùng `flex: 1; min-height: 0` + `ScrollArea` riêng từng panel (áp dụng đúng mẫu `report_model_studio.py`).

### Bước 4 — Canvas 12 Cột, 5 Visual Types (`semantic_visuals.py`), Data Wells, Filters & Preview
- **File tạo/sửa:**
  - Tạo `app/ui/components/semantic_visuals.py`: render 5 loại visual từ kết quả Query Planner (`Table` bằng `dag.AgGrid` + `GRID_DEFAULTS`, `Matrix` bảng pivot server-side có giới hạn hàng/cột an toàn, `KPI` dùng `kpi_card`, `Bar` & `Line` bằng `dcc.Graph` Plotly dùng màu từ `tokens.css`, `displayModeBar=False`, banner `truncated` + 4 trạng thái Loading/Empty/Error+Retry/Data).
  - Tạo `app/ui/assets/studio_drag_drop.js` (thuần HTML5 Drag & Drop theo mẫu `mail_drag_drop.js` / `drag_drop_reporting.js` + `window.dash_clientside.set_props`) hỗ trợ kéo field vào Data Wells và kéo đổi thứ tự visual, song song với nút `+` và nút lên/xuống cho accessibility.
  - Hoàn thiện panel phải & canvas trong `app/ui/pages/report_studio.py`: chọn/đổi loại visual (confirm khi rớt field không tương thích), `Tiêu đề biểu đồ`, `GRID_SPAN`, `HEIGHT_SIZE`, Data Wells kèm **Aggregation dropdown** (lọc theo `allowed_aggregations_for`), Format & Sort controls, Bộ lọc báo cáo/visual, thanh lọc xem thử trực tiếp trên canvas, debounce + **`request_seq` chống stale response**, Validation Drawer bấm vào lỗi nhảy đúng visual, chế độ `Xem trước` (`Quay lại thiết kế`).
- **Test viết trước:** mở rộng `tests/unit/test_report_studio_ui.py` (render đủ 5 loại visual, chặn invalid drop giữ nguyên config cũ, confirm đổi visual type, bỏ qua response có `request_seq` cũ, Matrix truncation warning).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_report_studio_ui.py -v`.
- **Rủi ro:** Theme Plotly `Light`/`Dark` không đổi màu kịp khi user chuyển theme → đồng bộ dựa trên `dmc.MantineProvider` color scheme + CSS token hoặc `relayout` chuẩn sáng/tối.

### Bước 5 — Tích hợp Report Viewer (`/reports/<id>`) & Xuất từng Visual (`RECON_RPT_EXPORT`)
- **File tạo/sửa:**
  - Cập nhật `app/services/report_run.py`: `create_report_run` hỗ trợ `visual_id` + `query_spec`; `execute_report_run` và `get_run_sql` (ADMIN-only) hỗ trợ version `SOURCE_TYPE = 'SEMANTIC_MODEL'` gọi qua Query Planner / `execute_semantic_query_for_run` / `get_semantic_sql_debug`, giữ 100% hành vi cũ cho `CUSTOM_SQL`/`VIEW`/`TABLE`.
  - Cập nhật `app/services/report_export.py` và `worker/export_runner.py`: `execute_export` nhận biết `SOURCE_TYPE = 'SEMANTIC_MODEL'` từ `RECON_REPORT_RUN` (`VISUAL_ID`, `QUERY_SPEC_JSON`), biên dịch lại an toàn bằng `resolve_semantic_plan` + `compile_semantic_query` (ép RLS theo `Ctx` chủ export + `check_report_sql`), stream lô `FETCH_BATCH_SIZE` ra XLSX/CSV/ZIP giống luồng SQL hiện có.
  - Cập nhật `app/ui/pages/report_viewer.py`: tự nhận biết active version có `SOURCE_TYPE = 'SEMANTIC_MODEL'` để render thanh tham số (`RECON_RPT_PARAM`, Preset, Favorite) + lưới 12 cột đa visual (`semantic_visuals.py`), nút **Xuất XLSX / CSV trên từng visual**, và tab `SQL thực hiện` (chỉ ADMIN); giữ nguyên giao diện bảng cũ cho báo cáo `CUSTOM_SQL`/`VIEW`/`TABLE`.
- **Test viết trước:** `tests/unit/test_report_viewer_semantic.py` và `tests/unit/test_report_export_visual.py` (test chạy từng visual, per-visual export XLSX/CSV qua worker/service, kiểm tra owner scope + RLS, hồi quy report `CUSTOM_SQL`/`VIEW`/`TABLE` cũ).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_report_viewer_semantic.py tests/unit/test_report_export_visual.py -v`.
- **Rủi ro:** Đụng quy tắc `owner_filter` hoặc lộ `SQL thực hiện` cho non-ADMIN; cần giữ chặn ở server lúc render layout lẫn trong `get_run_sql`.

### Bước 6 — Hardening, Security, Regression & Playwright E2E Đa Kích Thước
- **File tạo/sửa:**
  - Tạo `tests/e2e/test_report_studio_e2e.py`: kiểm thử Playwright end-to-end từ `/report-models` (tạo + publish model) → `/report-studio` (tạo báo cáo, thêm Bar + Table + KPI, preview, save draft, publish) → `/reports/<id>` (xem, lọc tham số, xuất 1 visual XLSX/CSV).
  - Kiểm tra 2 kích thước Desktop `1366×768` & `1440×900` (Light + Dark, `scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`), Mobile `390×844` (`/reports/<id>` xem được, `/report-studio/<id>/edit` báo giới hạn chỉnh sửa sạch, không tràn ngang), zero console/callback error, chụp ảnh kiểm chứng và kiểm tra `/data-model`.
- **Test viết trước:** `tests/e2e/test_report_studio_e2e.py`.
- **Lệnh kiểm tra:** `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run pytest tests/unit/test_perm_registry.py -v`, `uv run poe test-engine`, `uv run poe e2e`.

### Điểm tự suy ra & quyết định kỹ thuật đã chốt
1. **Menu & phân quyền `report_studio`:** thêm vào nhóm `CAU_HINH` (order `47`, icon `lucide:bar-chart-2`), cấp sẵn cho `TEMPLATE_OWNER` (chỉ `ADMIN` + `TEMPLATE_OWNER` thiết kế, `OPERATOR`/`VIEWER` xem/chạy ở `/reports`).
2. **Thứ tự bảng trong `metadata_migration.py`:** đưa cụm `RECON_RPT_MODEL*` lên trước `RECON_RPT_TPL_VER` do FK `MODEL_VERSION_ID`, và đặt `RECON_RPT_VISUAL*` trước `RECON_REPORT_RUN`.
3. **Drag & Drop không cần cài thêm thư viện:** dùng HTML5 Drag & Drop thuần (`studio_drag_drop.js`) kết hợp nút `+` và nút lên/xuống, không cài `SortableJS`.
4. **Thư viện biểu đồ:** dùng `dcc.Graph` từ `plotly` sẵn có trong môi trường, `displayModeBar=False`, màu từ `tokens.css`.

### Thư viện cần cài thêm
- Không có.
