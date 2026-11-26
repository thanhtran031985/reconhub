# 109-report-studio-viewer — Report Studio UI, Persistence & Viewer / Per-Visual Export Integration (REPORT-STUDIO-01D)

- Ngày tạo: 2026-11-26
- Giai đoạn: GĐ3
- Phụ thuộc: 106-semantic-model-core, 107-model-studio-ui, 108-semantic-query-planner, 25, 26, 27, 29
- Nhánh git: feat/109-report-studio-viewer

## Mục tiêu
1. Mở rộng Reporting Core (`RECON_RPT_TPL_VER`, `RECON_REPORT_RUN`) và bổ sung bảng `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD` để lưu báo cáo thiết kế từ **Report Studio** mà vẫn tái sử dụng `RECON_REPORT`, `RECON_REPORT_TEMPLATE`, `RECON_RPT_PARAM` (LOV/Layout 12 cột), `RECON_RPT_PRESET` và lịch sử chạy/xuất.
2. Xây dựng **Report Studio Center** (`/report-studio`) và **Report Studio Designer** (`/report-studio/<report_id>/edit`) với bố cục 3 panel Fluent Compact (Trường & Chỉ số | Report Canvas lưới 12 cột đa visual | Thiết lập biểu đồ & dữ liệu), hỗ trợ 5 loại visual V1 (`Bảng`, `Matrix`, `KPI`, `Cột`, `Đường`), dropdown chọn hàm tổng hợp, bộ lọc xem thử trực tiếp, Kiểm tra báo cáo, Lưu nháp chống ghi đè và Phát hành (Publish) ghim chặt `MODEL_VERSION_ID`.
3. Nâng cấp **Report Viewer** (`/reports/<report_id>`) hiển thị báo cáo `SEMANTIC_MODEL` đa visual cùng thanh tham số/preset hiện tại, đồng thời tích hợp cơ chế **Xuất từng visual (per-visual XLSX/CSV)** chạy qua hạ tầng `RECON_REPORT_RUN` + `RECON_RPT_EXPORT` + `worker/export_runner.py` sẵn có.
4. Hoàn thiện **Impact Analysis** ở Task 106 kết nối dữ liệu `RECON_RPT_VISUAL` / `RECON_RPT_VISUAL_FIELD` thật và kiểm thử hồi quy, hiệu năng, bảo mật, E2E đa kích thước màn hình.

## Phạm vi
- Database & Migration: `app/db/metadata.py`, `migrations/versions/0019_report_studio.py`, `app/services/schema_inspector.py`, `app/services/metadata_migration.py`, regenerate `docs/data-model/schema-manifest.json` & `docs/data-model/schema-history.json`.
- Schemas & Services: `app/schemas/report_studio.py`, `app/services/report_studio.py`, cập nhật `app/services/semantic_model.py` (kích hoạt `impact_analysis` trên `RECON_RPT_VISUAL*`), `app/services/report_run.py` & `app/services/report_export.py` & `worker/export_runner.py` (hỗ trợ `VISUAL_ID` / `SOURCE_TYPE = 'SEMANTIC_MODEL'`).
- Menu & Breadcrumbs: `app/ui/menus.py` (thêm `report_studio` nhóm `CAU_HINH` route `/report-studio`), `app/ui/layout/shell.py`.
- UI Components & Pages: `app/ui/components/semantic_visuals.py` (render Plotly Bar/Line, `dag.AgGrid` Table, Matrix, `kpi_card`), `app/ui/pages/report_studio_center.py` (`/report-studio`), `app/ui/pages/report_studio.py` (`/report-studio/<report_id>/edit`), nâng cấp `app/ui/pages/report_viewer.py` (`/reports/<report_id>`), `app/ui/assets/studio_drag_drop.js` (tùy chọn kèm `SortableJS` nếu cần).
- Tests: `tests/unit/test_report_studio_persistence.py`, `tests/unit/test_report_studio_ui.py`, `tests/unit/test_report_viewer_semantic.py`, `tests/unit/test_report_export_visual.py`, `tests/e2e/test_report_studio_e2e.py`.

## Ngoài phạm vi
- Không lưu full Plotly figure JSON vào DB (Plotly figure luôn tái dựng từ metadata + kết quả Query Planner).
- Chưa làm `Drill-through` liên trang hoặc biểu đồ Pie/Gauge/Treemap ở V1 (để sang V2).
- Không sửa/xóa báo cáo `CUSTOM_SQL`/`VIEW`/`TABLE` hiện có; giữ tương thích ngược 100% ở `/reports`, `/report-admin`, `/report-runs`.
- Mobile (`390×844`) chỉ hỗ trợ xem/preview báo cáo ở `/reports/<id>` và thông báo giới hạn chỉnh sửa tại `/report-studio/<id>/edit`.

## Thiết kế
- `designs/components/AppShell`
- `designs/components/DataGrid`
- `designs/components/KpiCard`
- `designs/components/EmptyState`
- `designs/components/Button`
- `designs/components/StatusChip`
- `designs/components/Alert`
- `designs/reference/preview-fluent.html`, `.agents/rules/ui-dash.md`, `designs/tokens.json`
- Wireframe tham chiếu: `02 REPORT STUDIO` (sửa nhãn nút header thành `Xem trước`, `Kiểm tra`, `Lưu nháp`, `Phát hành`; bổ sung loại `Matrix` vào nhóm loại biểu đồ).

## Spec liên quan
- `docs/tasks/106-semantic-model-core/task.md`
- `docs/tasks/108-semantic-query-planner/task.md`
- `app/ui/pages/report_viewer.py` & `app/ui/components/report_widgets.py`
- `app/services/report_export.py` & `worker/export_runner.py`
- `app/ui/assets/mail_drag_drop.js`

## Quyết định kiến trúc
1. **Mở rộng Reporting Core thay vì tạo bảng Report song song:**
   - Thêm `SOURCE_TYPE = 'SEMANTIC_MODEL'` và `MODEL_VERSION_ID` vào `RECON_RPT_TPL_VER` (giữ trạng thái `DRAFT → DRY_RUN_OK → ACTIVE → ARCHIVED`).
   - Lưu visual bằng 2 bảng normalized `RECON_RPT_VISUAL` + `RECON_RPT_VISUAL_FIELD` gắn với `VERSION_ID` của `RECON_RPT_TPL_VER`, giúp Impact Analysis từ Model Studio truy vấn trực tiếp nhanh và chính xác.
2. **Lưới 12 cột an toàn (`GRID_SPAN` + `HEIGHT_SIZE` + Drag-Reorder):**
   - Dùng `dmc.Grid` 12 cột (tương đồng mô hình đã chứng minh ổn định ở `RECON_RPT_PARAM`), mỗi visual chọn `GRID_SPAN` (`3`, `4`, `6`, `8`, `12`), `HEIGHT_SIZE` (`S`, `M`, `L`) và đổi vị trí bằng kéo thả thứ tự hoặc nút lên/xuống. Không dùng resize pixel tự do gây chồng lấn visual hoặc vỡ E2E; trên mobile tự xếp 12 cột.
3. **Thư viện Visual V1:**
   - `Bar` / `Line`: `dcc.Graph` (`plotly 7.1.0` đã có sẵn trong môi trường), đồng bộ màu semantic và theme Light/Dark từ `tokens.json`, `displayModeBar=False` theo phong cách Fluent Compact.
   - `Table`: `dag.AgGrid` (`data_grid`) phân trang/cuộn chuẩn `GRID_DEFAULTS`.
   - `KPI`: `kpi_card` (`app/ui/components/kpi_card.py`) hỗ trợ giá trị, target (tùy chọn) và trend.
   - `Matrix`: tổng hợp server-side qua Query Planner (Rows × Columns × Values), dựng bảng pivot có giới hạn kích thước an toàn để không treo trình duyệt.
4. **Gắn trường linh hoạt & Accessible:** Hỗ trợ đồng thời tick checkbox ở cây `Trường & Chỉ số`, nút `+ Thêm trường` / `+ Thêm chỉ số` ngay trong Data Well, và kéo-thả HTML5 (`studio_drag_drop.js`, có thể cân nhắc nạp `SortableJS` vào `app/ui/assets/lazy/` nếu cần). Chặn invalid drop kèm lý do ngắn, không làm mất cấu hình hiện tại.
5. **Xuất từng visual (Per-Visual Export):**
   - Mở rộng `RECON_REPORT_RUN` thêm `VISUAL_ID` (nullable) và `QUERY_SPEC_JSON` (snapshot `SemanticQueryIntent` lúc chạy/xuất).
   - Mỗi visual trên `/reports/<id>` có nút `Xuất XLSX` / `Xuất CSV` tạo `RECON_REPORT_RUN` gắn `VISUAL_ID` đó và gọi `request_export` → `worker/export_runner.py` biên dịch lại qua Query Planner an toàn và stream file theo đúng pipeline hiện tại.

## Các bước
### Bước 1 — Schema DB `RECON_RPT_VISUAL*`, Migration `0019`, `schema-introspect` & Menu `report_studio`
- Làm: Cập nhật `app/db/metadata.py` (`RECON_RPT_TPL_VER` thêm `MODEL_VERSION_ID` và mở rộng `SOURCE_TYPE`; thêm `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD`; `RECON_REPORT_RUN` thêm `VISUAL_ID`, `QUERY_SPEC_JSON`). Tạo `migrations/versions/0019_report_studio.py` (SQLite batch mode + Oracle). Cập nhật `app/services/schema_inspector.py`, `app/services/metadata_migration.py`, `app/ui/menus.py` (thêm menu `report_studio` nhóm `CAU_HINH`, cập nhật `ROLE_MENUS_SEED`), chạy `uv run poe schema-introspect`.
- Test viết trước: `tests/unit/test_report_studio_persistence.py` (kiểm tra migration 0019 upgrade/downgrade, constraint `VISUAL_TYPE`, tương thích ngược report `CUSTOM_SQL`/`VIEW`/`TABLE`).
- Kiểm tra: `uv run pytest tests/unit/test_report_studio_persistence.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py -v`, `uv run poe schema-introspect --check`.

### Bước 2 — Service Report Studio CRUD, Validate, Publish & Impact Analysis Connection
- Làm: Tạo `app/schemas/report_studio.py` và `app/services/report_studio.py` (`create_studio_report` chỉ nhận `MODEL_VERSION_ID` `ACTIVE`, `get_studio_report_draft`, `save_studio_draft` với `ROW_VERSION` optimistic concurrency, `validate_studio_report`, `publish_studio_report` pin exact `MODEL_VERSION_ID` + diff + Change Note + audit log, `clone_studio_report`, `archive_studio_report`). Hoàn thiện `impact_analysis()` trong `app/services/semantic_model.py` truy vấn thật từ `RECON_RPT_VISUAL*`.
- Test viết trước: mở rộng `tests/unit/test_report_studio_persistence.py` kiểm tra từ chối model `DRAFT`, validate visual bindings, publish immutable version pin `MODEL_VERSION_ID`, và `impact_analysis` phát hiện chính xác report/visual bị ảnh hưởng khi sửa model.
- Kiểm tra: `uv run pytest tests/unit/test_report_studio_persistence.py tests/unit/test_semantic_model_validation.py -v`.

### Bước 3 — Report Studio Center (`/report-studio`) & Khung Designer 3 Panel
- Làm: Tạo `app/ui/pages/report_studio_center.py` (`/report-studio` — lưới danh sách report Studio, lọc/tìm kiếm, `+ Tạo báo cáo`, Mở, Clone, Xem trước, Publish, Archive, Impact Drawer). Tạo `app/ui/pages/report_studio.py` (`/report-studio/<report_id>/edit` và `/report-studio/<report_id>`) với khung 3 panel không cuộn trang, header (`Xem trước`, `Kiểm tra`, `Lưu nháp`, `Phát hành`, `...`), Status Bar, panel trái `Trường & Chỉ số` (search metadata không query DB, nhóm Dimensions/Virtual Date/Measures/Hierarchies, ẩn field `HIDDEN`, checkbox + drag). Cập nhật `build_breadcrumbs` trong `app/ui/layout/shell.py`.
- Test viết trước: `tests/unit/test_report_studio_ui.py` (kiểm tra phân quyền, search field expand/filter, layout 3 panel, empty report/empty visual states).
- Kiểm tra: `uv run pytest tests/unit/test_report_studio_ui.py -v`.

### Bước 4 — Canvas 12 Cột, 5 Visual Types (`semantic_visuals.py`), Data Wells, Filters & Preview
- Làm: Tạo `app/ui/components/semantic_visuals.py` dựng `Table` (`dag.AgGrid`), `Matrix` (server-side pivot), `KPI` (`kpi_card`), `Bar` & `Line` (`dcc.Graph` Plotly theo `tokens.json`). Tạo `app/ui/assets/studio_drag_drop.js` hỗ trợ kéo field vào Data Wells và kéo đổi thứ tự visual. Hoàn thiện panel phải `Thiết lập biểu đồ & dữ liệu` trong `report_studio.py` (đổi loại visual có confirm nếu mất field không tương thích, `Tiêu đề biểu đồ`, Data Wells với **Aggregation dropdown**, Bộ lọc cấp Report/Visual tái sử dụng LOV/Dynamic Param, Format panel) + thanh lọc thử trên canvas + cơ chế debounce & `request_seq` chống stale response + chế độ `Xem trước` (`Quay lại thiết kế`) + điều hướng lỗi `Kiểm tra`.
- Test viết trước: mở rộng `tests/unit/test_report_studio_ui.py` kiểm tra bind từng loại visual, invalid drop không phá config, đổi visual type incompatible có cảnh báo, stale `request_seq`, 4 trạng thái Loading/Empty/Error+Retry/Data.
- Kiểm tra: `uv run pytest tests/unit/test_report_studio_ui.py -v`.

### Bước 5 — Tích hợp Report Viewer (`/reports/<id>`) & Xuất từng Visual (`RECON_RPT_EXPORT`)
- Làm: Cập nhật `app/ui/pages/report_viewer.py` để khi active version có `SOURCE_TYPE = 'SEMANTIC_MODEL'`, render thanh tham số động (`RECON_RPT_PARAM` + `RECON_RPT_PRESET`) + lưới đa visual tương tác, tab `SQL thực hiện` (chỉ `ADMIN`, hiển thị SQL read-only theo từng visual), và nút **Xuất XLSX / CSV trên từng visual**. Cập nhật `app/services/report_run.py`, `app/services/report_export.py` và `worker/export_runner.py` để thực thi và stream export cho `SOURCE_TYPE = 'SEMANTIC_MODEL'` theo `VISUAL_ID` + `QUERY_SPEC_JSON`.
- Test viết trước: `tests/unit/test_report_viewer_semantic.py` và `tests/unit/test_report_export_visual.py` (test tạo run per-visual, worker export XLSX/CSV thành công, bảo vệ quyền `owner_filter`, và hồi quy report `CUSTOM_SQL`/`VIEW`/`TABLE` cũ).
- Kiểm tra: `uv run pytest tests/unit/test_report_viewer_semantic.py tests/unit/test_report_export_visual.py -v`.

### Bước 6 — Hardening, Security, Regression & Playwright E2E Đa Kích Thước
- Làm: Viết và chạy `tests/e2e/test_report_studio_e2e.py` kiểm chứng luồng end-to-end (Tạo Model ở `/report-models` → Publish → Tạo Report ở `/report-studio` → Kéo/chọn field tạo Bar + Table + KPI → Preview → Save Draft → Publish → Mở xem ở `/reports/<id>` → Xuất 1 visual). Kiểm tra `1366×768`, `1440×900` (Light/Dark, `scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`), `390×844` (viewer xem được, studio hiện thông báo giới hạn sạch), zero JS console/callback errors, chụp ảnh kiểm chứng. Chạy toàn bộ bộ kiểm tra hệ thống.
- Test viết trước: `tests/e2e/test_report_studio_e2e.py`.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run poe test-engine`, `uv run poe e2e` → toàn bộ xanh.

## Chấp nhận khi
- [ ] Report Studio Center (`/report-studio`), Designer (`/report-studio/<id>/edit`) và Viewer (`/reports/<id>`) hoạt động liền mạch trên `RECON_REPORT*` và pin chặt `MODEL_VERSION_ID` `ACTIVE`.
- [ ] Đủ 5 loại visual V1 (`Table`, `Matrix`, `KPI`, `Bar`, `Line`), Aggregation dropdown (không chỉ checkbox SUM), Format panel, Report/Visual filters và chế độ Preview.
- [ ] Xuất từng visual (XLSX/CSV) hoạt động qua `RECON_REPORT_RUN` + `RECON_RPT_EXPORT` + `worker/export_runner.py` mà không làm hỏng báo cáo cũ.
- [ ] Impact Analysis trên Model Studio (Task 106/107) liệt kê chính xác report/visual phụ thuộc.
- [ ] Desktop `1366×768`, `1440×900` không page-scroll (Light/Dark); Mobile `390×844` không tràn ngang; toàn bộ `typecheck`, `lint`, `security-check`, `schema-introspect --check`, `test-engine`, `e2e` xanh 100%.

### Data Model Impact
- [ ] Migration cập nhật (`0019_report_studio.py`).
- [ ] DB model cập nhật (`RECON_RPT_TPL_VER`, `RECON_REPORT_RUN`, `RECON_RPT_VISUAL`, `RECON_RPT_VISUAL_FIELD`).
- [ ] `uv run poe schema-introspect` đã chạy.
- [ ] `docs/data-model/schema-manifest.json` đã regenerate.
- [ ] `docs/data-model/schema-history.json` đã cập nhật.
- [ ] Schema drift = 0 hoặc đã ghi rõ lý do.
- [ ] Page `/data-model` hiển thị thay đổi đúng phân hệ `report`.
- [ ] Regression tests pass.

## Câu hỏi mở
- Bước 4 đánh giá dùng thuần HTML5 Drag & Drop (mẫu `app/ui/assets/mail_drag_drop.js`) hay tích hợp `SortableJS` vào `app/ui/assets/lazy/`.
