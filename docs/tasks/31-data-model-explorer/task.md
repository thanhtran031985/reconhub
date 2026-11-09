# 31-data-model-explorer — Data Model Explorer + Automatic ER Diagram (DATA-MODEL-01)

- Ngày tạo: 2026-11-09
- Giai đoạn: GĐ3
- Phụ thuộc: 19, 20
- Nhánh git: feat/31-data-model-explorer
- Task ID: DATA-MODEL-01
- Nguồn: `docs/tasks/DATA-MODEL-01_PROMT.md` (prompt gốc, 2221 dòng) + `designs/reference/reconhub-er-diagram.html` (prototype tham chiếu, đã có trong repo)

## Status

⬜ Task đã generate xong, **chưa duyệt implement**. Chỉ bắt đầu implement khi người dùng yêu cầu chính xác: "Làm DATA-MODEL-01".

## Dependencies

- Task 19 (menu permission) và 20 (menu admin): hệ thống menu/phân quyền mà page này dùng.
- Không phụ thuộc task 21–30 về nghiệp vụ (chỉ tái dùng mẫu UI Fluent Compact của task 29).

## Objective

Tạo page **Mô hình dữ liệu / Data Model Explorer** cho developer xem toàn bộ database structure của ReconHub mà không phải đọc toàn bộ source code hay database thủ công:

1. Xem toàn bộ database structure, ER Diagram trực quan.
2. Xem table → columns → datatype → PK/FK, relationships.
3. Tìm table hoặc column; lọc table theo module/domain.
4. Theo dõi database schema đã thay đổi thế nào qua từng task.
5. Phát hiện schema drift (DB lệch so với model/migration).
6. Đảm bảo task AI sau này thay đổi database phải tự cập nhật Data Model Explorer.

## Problem Statement

ReconHub phát triển theo workflow AI/vibe coding. Khi nhiều AI liên tục bổ sung page, feature, table, column, foreign key, index và database model, người phát triển khó hình dung database hiện được thiết kế như thế nào. Không có một nơi duy nhất, luôn đồng bộ để xem mô hình dữ liệu.

## Read First

Đọc theo thứ tự trước khi implement:

1. `AGENTS.md`
2. Cấu trúc thư mục `docs/tasks/` hiện tại (convention task số thứ tự, 4 file task/plan/progress/decisions + `test-checklist.md` riêng của task này)
3. 2–3 task gần nhất (29, 30) để hiểu convention
4. `.agents/rules/ui-dash.md`
5. `designs/tokens.json`
6. `designs/README.md`
7. `docs/DESIGN_SYSTEM.md`
8. `docs/ui-migration.md`
9. Database/model architecture hiện tại (`app/db/metadata.py`, `app/db/dialect.py`, `app/repo/`)
10. Migration architecture hiện tại (`migrations/versions/`, Alembic)
11. `designs/reference/reconhub-er-diagram.html` (prototype tham chiếu)

## Architecture

Kiến trúc thật của repo (đã audit lúc generate task, phải audit lại trước khi implement — prompt §6):

- **Ngôn ngữ/framework:** Python 3.12, Dash 3 + dash-mantine-components 2.x, Polars.
- **Database engine:** SQLite mặc định (`data/recon_app.db`); Oracle qua python-oracledb Thin (VPN). Khác biệt SQLite/Oracle gom ở `app/db/dialect.py`.
- **ORM/model technology:** SQLAlchemy **Core** (không phải ORM, không phải Pydantic ORM). 43 bảng khai báo bằng `Table(...)` trong `app/db/metadata.py`.
- **Migration technology:** Alembic, revisions `migrations/versions/0001`–`0006`, chạy được trên SQLite (batch mode) và Oracle.
- **Connection abstraction:** `app/db/engine.py` (`get_recon_engine`), repository layer `app/repo/`.
- **Nghiệp vụ:** chỉ ở `app/services` và `app/engine`; callback Dash chỉ gọi service. Service nhận `ctx`, trả `ServiceResult`; lỗi dùng `ServiceError`.
- **UI:** Dash pages (`dash.register_page`) trong `app/ui/pages/`; AppShell trong `app/ui/layout/shell.py`; menu/phân quyền theo task 19/20 (`app/services/menu_sync.py`, `app/services/perm.py`, `app/ui/menus.py`).
- **Lệnh:** poethepoet (`uv run poe …`, xem `pyproject.toml` `[tool.poe.tasks]`).
- **CI:** `.github/workflows/ci.yml`.

## Source of Truth

Không hardcode ER Diagram. Không manually maintain danh sách table hay relationship lines trong page.

```
Database metadata
      +
Application DB models (SQLAlchemy Core, app/db/metadata.py)
      +
Database migrations (Alembic)
      ↓
Schema Inspector
      ↓
Schema Manifest (generated artifact)
      ↓
Schema Diff / Drift
      ↓
Data Model Explorer UI
```

Source of truth vẫn là database/model/migration architecture hiện tại. `schema-manifest.json` chỉ là generated artifact, không phải source of truth.

**Lưu ý về prototype:** `designs/reference/reconhub-er-diagram.html` chỉ là tham chiếu về layout/interaction/hierarchy. Nó hiển thị 14 table đơn giản hoá (vd `APP_USER`, `ROLE`) trong khi schema thật có 43 bảng (`RECON_USER`, `RECON_USER_ROLE`, …). Prototype KHÔNG phải source of truth; inspector phải tự phát hiện schema thật.

## Schema Inspector

Tạo một command chung, ưu tiên theo convention:

```bash
uv run poe schema-introspect
```

Command phải:

1. đọc database metadata của app (qua SQLAlchemy inspector, chỉ database SQLite của app — `RECON_DB_URL`; không đọc các Oracle data source nghiệp vụ);
2. đọc model metadata nếu cần (`app/db/metadata.py`);
3. đọc migration metadata nếu cần (Alembic);
4. normalize schema;
5. generate schema-manifest;
6. generate schema diff/history;
7. validate PK/FK/index/constraint;
8. chạy drift comparison.

Command phải deterministic. Chạy hai lần khi schema không thay đổi: KHÔNG tạo fake diff. Không `git add`/`git commit`/`git push` (workflow Git do AI/task xử lý riêng).

## Schema Manifest

Generated artifact (không sửa tay):

```
docs/data-model/schema-manifest.json
```

Có header/metadata `GENERATED`. Ví dụ cấu trúc (đầy đủ trong prompt §7): `generated_at`, `database`, `schema`, `version`, `tables[]` — mỗi table có `name`, `domain`, `description`, `columns[]` (`name`, `type`, `nullable`, `primary_key`, `foreign_key`, `unique`, `default`), `primary_key`, `foreign_keys[]` (`column`, `references_table`, `references_column`, `constraint_name`), `unique_constraints`, `indexes`, `source` (`model`, `migration`).

## Schema History

Generated artifact:

```
docs/data-model/schema-history.json
```

Lưu change events: `TABLE_CREATED`, `TABLE_DROPPED`, `COLUMN_ADDED`, `COLUMN_REMOVED`, `COLUMN_CHANGED`, `PK_CHANGED`, `FK_CHANGED`, `INDEX_CHANGED`, `CONSTRAINT_CHANGED`. Mỗi record (nếu metadata cho phép): `timestamp`, `task_id`, `migration_id`, `entity`, `change_type`, `before`, `after`.

Production page KHÔNG chạy `git log`/`git diff` mỗi lần mở page; history lấy từ artifact đã generate.

## Schema Drift

Phát hiện khác nhau giữa database và application metadata/migration/model. Trạng thái: `SYNCED`, `DRIFT`, `UNKNOWN`, `ERROR`. Drift types: `TABLE_MISSING`, `TABLE_EXTRA`, `COLUMN_MISSING`, `COLUMN_EXTRA`, `TYPE_CHANGED`, `NULLABILITY_CHANGED`, `PK_CHANGED`, `FK_CHANGED`, `INDEX_CHANGED`, `CONSTRAINT_CHANGED`.

## Route

Page **Mô hình dữ liệu**, route:

```
/data-model
```

Page là Dash page (`dash.register_page(__name__, path="/data-model", ...)` trong `app/ui/pages/data_model.py`), theo convention các page hiện tại.

## Permission

Đây là metadata kỹ thuật nội bộ. Page bắt buộc authentication + authorization. Không mặc định expose cho tất cả user.

Tuân thủ permission/menu system hiện tại (task 19/20): page gắn với menu code `data_model`, service dùng `@requires_menu("data_model")`; ADMIN cấp quyền cho vai trò trên `/roles`. KHÔNG tự tạo permission dạng `VIEW_DATA_MODEL` — repo không dùng permission code riêng lẻ mà dùng menu.

## Menu

Menu group: **QUẢN TRỊ** (cùng nhóm với Data Sources, Danh mục hệ thống). Khai báo `MenuDef("data_model", "Mô hình dữ liệu", "QUAN_TRI", "/data-model", <order>, <icon>)` trong `app/ui/menus.py` (icon chọn từ icon library hiện tại, không dùng emoji; order sau `report_admin`). Menu được đồng bộ vào DB qua `menu_sync` (mới chỉ thêm dòng, KHÔNG tự gán cho vai trò — ADMIN cấp qua `/roles`, theo spec 11 §2.2).

## Layout

Bắt buộc Fluent Compact + Master–Detail (`.agents/rules/ui-dash.md`, `designs/tokens.json`). Desktop >= 1280: **page không cuộn**. Không hardcode width trong page; dùng layout/token foundation. Không copy hardcoded CSS/hex từ prototype.

```
AppShell
└── PageContent
    ├── PageHeader
    ├── CommandBar
    ├── Workspace
    │   ├── Schema Explorer (internal scroll)
    │   ├── ER Canvas (pan / zoom / internal scroll)
    │   └── Detail Panel (internal scroll)
    └── Status Bar
```

Mobile 390×844: page cuộn được; thứ tự CommandBar → Schema Explorer → ER Canvas → Detail Panel; không horizontal page overflow; ER Canvas được internal horizontal scroll/pan.

## Component Specification

### Page Header

- Trái: Title "Mô hình dữ liệu"; description "ER Diagram được sinh tự động từ metadata database, migrations và model của ứng dụng."
- Phải: nút [Lịch sử thay đổi], nút [Đồng bộ schema].

### Command Bar

1. Search (placeholder "Tìm table hoặc column…"; tìm trên table name, column name, table description, constraint/index name nếu có; filter đồng thời Schema Explorer và ER Canvas).
2. Domain Filter (Tất cả phân hệ / Core / Đối soát / Báo cáo / Quản trị / Khác; mapping không hardcode trong page, lấy từ metadata/config — xem mục Domain Mapping bên dưới).
3. Display Mode (Hiển thị quan hệ / Chỉ tên table; đổi mode không mất selection).
4. Schema Health (badge read-only: ✓ Schema đồng bộ / ⚠ Schema drift / ? Không xác định / ✕ Lỗi metadata; không phải button).
5. Last Sync ("Cập nhật: DD/MM/YYYY HH:mm:ss", theo timezone đã cấu hình của app, không hardcode).

### Schema Explorer (panel trái)

- Header: "Schema Explorer", "N tables". Table group theo domain; group header có chevron + tên domain + số table; click collapse/expand (state giữ trong page; khi search, group có match tự expand).
- Mỗi table là compact row: status marker, `TABLE_NAME`, column count. Hover: tooltip description (nếu có), không gọi backend.
- Click table: cập nhật selection, row active, ER entity highlight, relationship liên quan highlight, Detail Panel load table, canvas tự pan/scroll tới table nếu cần, update URL query, không reload page.
- Double click: select table, center table trên canvas, zoom đủ để đọc columns. Không mở page khác.
- Context menu (nút More/ellipsis hoặc right-click nếu convention hỗ trợ): Center trong ER Diagram, Xem columns, Xem relationships, Xem lịch sử thay đổi (mở history filter theo table), Copy table name. TUYỆT ĐỐI KHÔNG có: Drop table, Alter table, Delete column, Run SQL.

### ER Canvas (panel giữa)

- Bounded viewport; hỗ trợ pan, scroll, zoom, fit-to-screen; không sinh giant SVG làm tăng page height.
- Entity card: header `TABLE_NAME` + column count; body: PK/FK marker, `COLUMN_NAME`, `DATA_TYPE`. PK/FK marker bằng icon/text (không chỉ phân biệt bằng màu); PK+FK thể hiện cả hai; Unique có marker nếu cần; Nullable thể hiện ở Detail Panel.
- Relationships vẽ từ FK → referenced PK/Unique Key, lấy từ metadata, không hardcode endpoints. Normal: neutral line. Khi chọn table: relationship liên quan = accent, không liên quan = lower emphasis.
- Click relationship (nếu technology cho phép): select relationship; source/target table highlight; line accent; Detail Panel chuyển sang Relationship Detail.
- Zoom In/Out: icon-only button, có tooltip + aria-label, có MAX/MIN_ZOOM. Fit: lấy bounding box của visible entities, tính scale, pan, fit graph vào viewport; không clear search/domain/selection.
- **Auto-layout:** vị trí entity KHÔNG hardcode per table; dùng graph layout algorithm hoặc deterministic grouping/layout logic (deterministic, hạn chế overlap, related entities gần nhau, preserve domain grouping nếu phù hợp).

### Detail Panel (panel phải)

- Empty: "Chọn một table hoặc relationship để xem chi tiết."
- Table detail: header `TABLE_NAME` + description; KPI (Columns: N, Relationships: N); metadata badges (Domain, Schema status); Column List (mỗi row: `COLUMN_NAME`, `DATA_TYPE`, PK/FK/UNIQUE/NULLABLE-NOT NULL/DEFAULT); Relationships (Incoming/Outgoing: `SOURCE.TABLE_COLUMN → TARGET.TABLE_COLUMN` + constraint name); Index/Constraint section (Primary Key, Unique, Foreign keys, Indexes; dài thì collapsible, không hide PK/FK); Recent Changes (filter theo selected table, vd `COLUMN_ADDED REPORT_TEMPLATE.COLUMN_LAYOUT 09/11/2026 19:42`; không có thì "Chưa ghi nhận thay đổi schema cho table này.").
- Relationship Detail: Source (`BATCH_DEFINITION_ITEM.BATCH_DEF_ID`), Target (`BATCH_DEFINITION.BATCH_DEF_ID`), Constraint (`FK_BATCH_ITEM_BATCH`), Cardinality nếu derive được (N:1), Delete Rule nếu metadata có (CASCADE/RESTRICT/SET NULL); nút Source table / Target table (click thì select table đó).

### Status Bar

Bottom compact: `N tables`, `N columns`, `N relationships`; bên phải: metadata sources thực tế (vd "Oracle metadata + migrations + application models" — chỉ ghi technology thực tế).

## Button & Interaction Specification

### Lịch sử thay đổi

Mở Drawer hoặc Modal compact (không chuyển route). Nội dung: Search, Change Type Filter (Tất cả / TABLE_CREATED / TABLE_DROPPED / COLUMN_ADDED / COLUMN_REMOVED / COLUMN_CHANGED / FK_CHANGED / INDEX_CHANGED / CONSTRAINT_CHANGED), Timeline/List. Mỗi item: timestamp, change type, entity (vd `REPORT_TEMPLATE.COLUMN_LAYOUT`), Task, Migration, Before, After. Dữ liệu từ generated schema history, không hardcode.

### Đồng bộ schema

Click: trigger Schema Inspector → đọc metadata mới → regenerate manifest → compare drift → regenerate history nếu có change → reload Explorer/Canvas/Detail → update health status. State machine:

- **NORMAL:** [Refresh] Đồng bộ schema, enabled.
- **RUNNING:** [Spinner] Đang đồng bộ…, disabled; health "Đang kiểm tra schema…".
- **SUCCESS — NO CHANGE:** quay về normal; health "✓ Schema đồng bộ".
- **SUCCESS — CHANGED:** quay về normal; thông báo "✓ Đã cập nhật mô hình" (vd "2 tables changed, 4 columns changed").
- **DRIFT:** quay về normal; health "⚠ Schema drift"; hiện action "Xem khác biệt".
- **ERROR:** quay về normal; ErrorState "Không thể đọc metadata database."; action "Thử lại".

### Thử lại

Chỉ xuất hiện trong ErrorState. Gọi lại schema inspection/metadata loading. Không reload toàn browser nếu không cần.

### Xem khác biệt

Chỉ xuất hiện khi Health = DRIFT. Mở Drawer/Panel "Schema Drift": Database ↔ Application, liệt kê từng drift (+ COLUMN_EXTRA / ! TYPE_CHANGED kèm DB vs Model / - FK_MISSING …). Filters: Tất cả / Table / Column / Relationship / Index / Constraint. Nút "Copy report" (copy text report để developer gửi cho AI/task). TUYỆT ĐỐI KHÔNG có: Fix schema, Apply, Run migration, Auto repair.

### Search — Column Behavior

Vd search `GRID_SPAN`: ER Canvas giữ table `REPORT_PARAMETER` visible và highlight column `GRID_SPAN`; Detail Panel hiển thị search match (`REPORT_PARAMETER.GRID_SPAN`, NUMBER, Nullable…). Không chỉ hiển thị table mà bỏ highlight matching column.

### Domain Mapping (đã kiểm chứng từ code + hồ sơ task, 09/11/2026)

Mapping phân hệ cho toàn bộ 43 bảng thật, đối chiếu 3 nguồn: `app/db/metadata.py` (43 bảng), `migrations/versions/0001`–`0006` (bảng nào do migration nào tạo), hồ sơ task (bảng nào do task nào tạo/dùng). Tổng: Core 10, Đối soát 19, Báo cáo 11, Quản trị 3 = 43, không bảng nào rơi vào Khác.

- **Core (10)** — `RECON_USER`, `RECON_USER_ROLE` (task 01 auth), `RECON_MENU_GROUP`, `RECON_MENU`, `RECON_ROLE`, `RECON_ROLE_MENU` (task 19/20, migration 0003), `RECON_LOGIN_LOG` (task 01), `RECON_AUDIT_LOG`, `RECON_APP_SETTING` (migration 0001), `RECON_METADATA_MIGRATION` (task 13 chuyển RECON_APP SQLite → Oracle, hệ thống nền tảng).
- **Đối soát (19)** — `RECON_TEMPLATE`, `RECON_TEMPLATE_VERSION`, `RECON_FILE` (task 04), `RECON_EXCEL_LOAD`, `RECON_EXCEL_ROW`, `RECON_RUN`, `RECON_RESULT_ROW`, `RECON_RESULT_DIFF`, `RECON_INVALID_ROW`, `RECON_ISSUE`, `RECON_ISSUE_REASON` (migration 0001), `RECON_RUN_QUEUE`, `RECON_RUN_SUMMARY`, `RECON_PURGE_LOG` (task 07 run queue/worker; purge log ghi việc xóa dữ liệu tạm của đối soát theo spec 04 mục 12), `RECON_BATCH_DEF`, `RECON_BATCH_DEF_ITEM`, `RECON_BATCH_RUN`, `RECON_BATCH_RUN_ITEM`, `RECON_BATCH_RUN_FILE` (task 18, migration 0006).
- **Báo cáo (11)** — `RECON_REPORT`, `RECON_REPORT_TEMPLATE`, `RECON_RPT_TPL_VER`, `RECON_RPT_PARAM`, `RECON_RPT_PARAM_LOV`, `RECON_RPT_COLUMN`, `RECON_REPORT_RUN`, `RECON_RPT_EXPORT`, `RECON_RPT_FAVORITE`, `RECON_RPT_PRESET`, `RECON_RPT_LOV_CACHE` (task 21–28, migration 0004/0005).
- **Quản trị (3)** — `RECON_DATA_SOURCE` (task 02, Admin khai báo kết nối; prototype cũng xếp vào admin), `RECON_LOOKUP_TYPE`, `RECON_LOOKUP_CODE` (task 17, migration 0002).

Quy tắc suy ra từ mapping này (đã chốt — cách "lai", người dùng chọn option đề xuất lúc review task, 09/11/2026): `RECON_RPT_*` hoặc `RECON_REPORT*` → Báo cáo; `RECON_BATCH_*` → Đối soát; `RECON_LOOKUP_*` hoặc `RECON_DATA_SOURCE` → Quản trị; `RECON_USER*`, `RECON_ROLE*`, `RECON_MENU*`, `RECON_LOGIN_LOG`, `RECON_AUDIT_LOG`, `RECON_APP_SETTING`, `RECON_METADATA_MIGRATION` → Core; mặc định `RECON_*` còn lại → Đối soát; bảng nào không khớp quy tắc nào → Khác + inspector cảnh báo. Phân hệ được ghi vào manifest; page chỉ đọc `table.domain` từ manifest.

## URL State

Selection/filter quan trọng reflect trên URL nếu phù hợp với Dash routing: `/data-model?table=BATCH_DEFINITION`, `/data-model?domain=reconciliation&table=BATCH_DEFINITION`, có thể thêm `mode=compact`. Mục tiêu: refresh giữ context; copy URL gửi cho AI/người khác; Back/Forward hợp lý. Không đưa zoom/pan pixel vào URL nếu không cần. (Dash pages truyền query string thành kwargs cho `layout()` — mọi `layout()` phải nhận `**kwargs`.)

## Loading/Empty/Error/Data

- **Loading:** initial load — Explorer → skeleton rows, Canvas → loader/skeleton, Detail → SkeletonPanel; không block trắng toàn screen.
- **Empty schema:** "Không tìm thấy table trong schema hiện tại." + nút "Đồng bộ lại".
- **Empty search:** "Không tìm thấy table hoặc column phù hợp." + action "Xóa bộ lọc" (clear search + domain → All). Không gọi error state.
- **Error:** metadata load fail → "Không thể đọc metadata database." + nút "Thử lại". Sanitize error; không expose password/token/DB secret/full credential connection string.

## Security

Data Model Explorer chỉ expose metadata. Không expose: table row data, sample sensitive data, password, secret, token, raw credential, database password, connection string password. SQL DDL nếu hiển thị phải kiểm tra không chứa secrets. Page phải permission protected (menu `data_model`, xem mục Permission).

## Performance

- Schema <= 50 tables: render full interface.
- Schema > 50: cân nhắc domain filter, lazy column rendering, compact entity mode.
- Schema > 100: phải đánh giá virtualization/lazy graph strategy. Không để browser freeze.
- Schema thật hiện tại: 43 bảng (đếm trong `app/db/metadata.py` lúc generate task) — trong ngưỡng render full, nhưng thiết kế phải chịu được tăng trưởng.

## Responsive

- Desktop >= 1280: page không cuộn (`document.documentElement.scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`; canvas internal scroll được phép).
- Mobile 390×844: page cuộn được, thứ tự CommandBar → Explorer → Canvas → Detail; không horizontal page overflow.

## Accessibility

Icon button có tooltip + aria-label; table item keyboard selectable + `aria-selected`; relationship keyboard selectable nếu feasible; PK/FK không chỉ phân biệt bằng màu; focus visible; status `aria-live="polite"`; controls có label/aria-label.

## Auto-update Rule

Khi implement, bổ sung vào `AGENTS.md` (hoặc database rule phù hợp): khi task tạo/xóa/thay đổi TABLE/COLUMN/DATATYPE/NULLABILITY/PK/FK/UNIQUE/INDEX/CONSTRAINT, AI bắt buộc: (1) cập nhật migration/model đúng workflow; (2) chạy schema-introspect; (3) regenerate schema-manifest; (4) generate schema diff/history; (5) chạy schema drift; (6) chạy Data Model Explorer tests; (7) verify table/column mới xuất hiện; (8) bảo đảm generated artifacts được commit nếu project policy yêu cầu.

Đồng thời bổ sung vào template task (`docs/tasks/_template/task.md`) mục **Data Model Impact** trong Definition of Done: task không thay đổi database schema, HOẶC migration/model cập nhật + schema-introspect chạy + manifest regenerate + history cập nhật + drift = 0 hoặc documented + Explorer hiển thị thay đổi + regression tests pass.

## CI Freshness

Không chỉ dựa vào AI nhớ chạy generator. CI phải phát hiện stale manifest: (1) generate schema manifest vào temp; (2) normalize deterministic; (3) diff với committed manifest; (4) nếu khác → FAIL với message "Schema manifest is stale. Run: uv run poe schema-introspect". Thêm bước vào `.github/workflows/ci.yml` (CI hiện tại của repo).

## Allowed Scope

- Schema Inspector + manifest/history artifacts + drift.
- Page `/data-model` + menu `data_model` + service `@requires_menu("data_model")`.
- Poe task `schema-introspect` + CI freshness check.
- Cập nhật `AGENTS.md` (auto-update rule) + template task (Data Model Impact).
- Tests + docs liên quan trực tiếp.

## Forbidden Scope

- Mọi thao tác ghi schema từ UI (CREATE/ALTER/DROP TABLE, ADD/DROP/MODIFY COLUMN, CREATE/DROP INDEX, run/apply/rollback migration, fix schema tự động).
- Tự tạo schema change nghiệp vụ chỉ để demo.
- Sửa nếu không cần: business services, reconciliation algorithms, report SQL, permission semantics, authentication behavior, existing database schema.
- Đổi convention task, đổi design token, đổi menu/permission của các page khác.

## Bug Safety

Repo do nhiều AI cùng code. Trước khi implement: `git status --short`, `git branch --show-current`, `git log -1 --oneline`; chạy baseline tests. Phân loại bug: PRE-EXISTING UNRELATED / PRE-EXISTING BLOCKER / INTRODUCED BY TASK / DISCOVERED RELATED BUG / UNKNOWN. Không sửa PRE-EXISTING UNRELATED. Bug related chỉ sửa nếu thuộc scope, không đổi business contract, có regression test. Security/data-loss/permission bypass: STOP và báo user.

## Implementation Steps

### Bước 1 — Schema Inspector + manifest/history
- Làm: module inspector (đọc metadata qua SQLAlchemy inspector, chỉ database SQLite của app, không đọc Oracle data source nghiệp vụ + model `app/db/metadata.py` + Alembic migrations; normalize; validate PK/FK/index/constraint); CLI entry + poe task `schema-introspect`; sinh `docs/data-model/schema-manifest.json` và `docs/data-model/schema-history.json` (deterministic, có header GENERATED, không fake diff khi chạy lại); xử lý khác biệt dialect qua `app/db/dialect.py`.
- Test viết trước: table/column extraction, datatype, nullable, default, PK, FK, unique, index, constraint; deterministic output (chạy 2 lần ra cùng manifest); schema diff; drift cơ bản.
- Kiểm tra: `uv run poe schema-introspect` chạy được trên SQLite; manifest khớp 43 bảng thật; `uv run poe test -- tests/unit/test_schema_inspector.py -q` xanh.

### Bước 2 — Drift comparison + CI freshness
- Làm: service so sánh DB ↔ model/migration, trạng thái SYNCED/DRIFT/UNKNOWN/ERROR + các drift type (prompt §10); bước CI trong `.github/workflows/ci.yml` (generate manifest vào temp, normalize, diff với committed, FAIL khi stale).
- Test viết trước: từng drift type (TABLE_MISSING/EXTRA, COLUMN_MISSING/EXTRA, TYPE_CHANGED, NULLABILITY_CHANGED, PK/FK/INDEX/CONSTRAINT_CHANGED); CI fail khi manifest stale, pass khi đồng bộ.
- Kiểm tra: drift test xanh; CI step chạy được (mô phỏng local bằng cách sửa manifest rồi chạy lệnh CI).

### Bước 3 — Menu + route + page skeleton + permission
- Làm: `MenuDef("data_model", "Mô hình dữ liệu", "QUAN_TRI", "/data-model", …)` trong `app/ui/menus.py`; page `app/ui/pages/data_model.py` (`dash.register_page`, `layout(**kwargs)` đọc query string); service đọc manifest + `@requires_menu("data_model")`; page skeleton (header, command bar, 3 panel, status bar) với loading skeleton.
- Test viết trước: menu chỉ hiện với vai trò được cấp (ADMIN cấp qua `/roles`; chưa cấp thì không thấy); chưa đăng nhập → `/login`; vai trò không có quyền → `/forbidden`; `layout()` nhận `**kwargs`.
- Kiểm tra: `uv run poe test -- tests/unit/test_page_data_model.py -q` xanh; Playwright vào `/data-model` thấy skeleton rồi đủ 3 panel.

### Bước 4 — Schema Explorer + command bar
- Làm: Explorer group theo domain (expand/collapse, search tự expand group có match), table item compact + tooltip, click/double-click/context menu (center, xem columns/relationships/history, copy tên), search (table/column/description, filter đồng thời Explorer + Canvas, highlight matching column), domain filter, display mode, health badge, last sync.
- Test viết trước: search table, search column + highlight, domain filter, display mode, group expand/collapse, click table (selection + URL query), double click (center), context menu actions, copy table name, deep link URL (`?table=`, `?domain=`, `mode=`).
- Kiểm tra: `uv run poe test` xanh; Playwright kiểm chứng search `GRID_SPAN` highlight đúng column.

### Bước 5 — ER Canvas
- Làm: entity card (PK/FK marker, datatype), relationship lines từ FK metadata, auto-layout deterministic (không hardcode toạ độ), pan/scroll/zoom/fit, click table → highlight entity + relationships liên quan, click relationship → relationship detail.
- Test viết trước: entity render đủ 43 bảng thật; relationship đúng theo FK metadata; auto-layout deterministic (2 lần render cùng vị trí); zoom in/out/fit; click relationship.
- Kiểm tra: `uv run poe test` xanh; Playwright đo canvas vừa viewport, không làm tăng chiều cao page.

### Bước 6 — Detail Panel + History + Drift viewer
- Làm: Detail Panel (empty/table/relationship detail, column list, relationships in/out, index/constraint collapsible, recent changes theo table); Drawer Lịch sử thay đổi (search + filter change type + timeline); Drawer Xem khác biệt (drift list + filters + Copy report).
- Test viết trước: detail đủ sections; history filter theo type và theo table; drift viewer hiển thị đúng từng drift type; copy drift report.
- Kiểm tra: `uv run poe test` xanh; Playwright mở history và drift drawer.

### Bước 7 — Sync state machine + loading/empty/error
- Làm: nút Đồng bộ schema với state machine (normal/running/success no-change/success changed/drift/error) + health status; loading skeleton; empty schema/search; error + Thử lại.
- Test viết trước: từng trạng thái của state machine; empty schema; empty search + Xóa bộ lọc; error + retry.
- Kiểm tra: `uv run poe test` xanh; Playwright mô phỏng sync thành công, sync lỗi, drift.

### Bước 8 — Auto-update rule + docs + visual tests + regression
- Làm: bổ sung auto-update rule vào `AGENTS.md`; bổ sung mục Data Model Impact vào `docs/tasks/_template/task.md`; cập nhật `docs/USER_GUIDE.md` nếu cần; visual tests 1366×768, 1440×900, 390×844 (desktop không page scroll, mobile không horizontal overflow).
- Test viết trước: regression — reconciliation, reporting, permissions, data-source logic vẫn hoạt động (full suite).
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh; ảnh chụp 3 cỡ.

## Tests

- **Generator:** table/column extraction, datatype, nullable, default, PK, FK, unique, index, constraint, deterministic output, schema diff, drift.
- **UI:** permission, loading, empty, error, data, search table, search column, domain filter, display mode, group expand/collapse, click table, double click table, context menu, copy table, deep link URL, relationship highlight, relationship click, relationship detail, source/target navigation, zoom in/out/fit, history, history filter, sync success/changed/drift/error, retry, view diff, copy drift report.
- **Security:** unauthorized access denied; no credentials trong page DOM, schema manifest, history, error messages, logs.
- **Regression:** reconciliation, reporting, permissions, data-source logic không đổi.
- Chi tiết từng ca trong `test-checklist.md`.

## Visual Tests

Chụp 1366×768, 1440×900, 390×844. Desktop: `document.documentElement.scrollHeight <= innerHeight`, `scrollWidth <= innerWidth` (canvas internal scroll được phép). Mobile: không horizontal page overflow.

## Acceptance Criteria

- [ ] DATA-MODEL page tồn tại; route `/data-model` đúng; menu đúng (nhóm QUẢN TRỊ); permission đúng (menu `data_model`, ADMIN cấp qua `/roles`).
- [ ] Fluent Compact đúng; desktop không page scroll; mobile không horizontal overflow; Light/Dark đúng.
- [ ] Không hardcode table list; không hardcode relationships; inspector tồn tại; manifest/history generate tự động; drift check tồn tại.
- [ ] Search table/column hoạt động; matching column highlight; domain filter; display mode; group collapse/expand.
- [ ] Click table; double click center canvas; context actions; URL deep-link.
- [ ] ER auto-layout không hardcode coordinates; PK/FK hiển thị; relationships đúng; click relationship; relationship detail.
- [ ] Zoom In/Out/Fit; Detail Panel đầy đủ; History + filter; sync state machine đầy đủ; Drift View + Copy report.
- [ ] Loading/empty/error + Retry; không credential exposure.
- [ ] Unit tests pass; E2E tests pass; schema freshness CI tồn tại.
- [ ] AGENTS/database rule được cập nhật; Database task Definition of Done đã bổ sung.
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

## Expected Files

- `app/services/schema_inspector.py` (tên module chính xác do implementer chốt sau audit)
- `app/services/schema_drift.py` (hoặc gộp vào inspector)
- `app/ui/pages/data_model.py`
- `app/ui/components/` (component dùng chung cho Explorer/Canvas/Detail nếu tách ra)
- `app/ui/layout/` nếu cần menu integration (thường chỉ `app/ui/menus.py`)
- `app/ui/menus.py` (thêm `MenuDef data_model`)
- `app/ui/assets/` (JS/CSS cho canvas pan/zoom nếu cần, theo pattern `drag_drop_reporting.js`)
- `docs/data-model/schema-manifest.json` (generated)
- `docs/data-model/schema-history.json` (generated)
- `scripts/schema_introspect.py` (entry CLI nếu cần)
- `pyproject.toml` (poe task `schema-introspect`)
- `.github/workflows/ci.yml` (schema freshness check)
- `AGENTS.md` (auto-update rule)
- `docs/tasks/_template/task.md` (Data Model Impact)
- `tests/unit/test_schema_inspector.py`, `tests/unit/test_schema_drift.py`, `tests/unit/test_page_data_model.py`, `tests/e2e/` (tên file chính xác do implementer chốt)
- `docs/tasks/31-data-model-explorer/` (hồ sơ task này)

## Files Must Not Change

Không sửa nếu không cần: business services, reconciliation algorithms, report SQL, permission semantics, authentication behavior, existing database schema. DATA-MODEL-01 không được tự tạo schema change nghiệp vụ chỉ để demo.

## Completion Report Format

Khi implement xong, report theo mẫu (đầy đủ trong prompt §80): Architecture (schema source, inspector, manifest, history, drift strategy), UI (route, permission, tables/columns/relationships discovered), Automated Update (command, CI validation), Files Changed, Tests (lint/typecheck/unit/E2E/drift/console), Visual Validation (1366×768, 1440×900, 390×844), Screenshots, Existing Bugs Discovered (bảng Bug/Existing-New/Severity/Action), Safety (Data Model Explorer READ ONLY, Database schema changed by this page: NO).

## STOP Condition

Sau khi DATA-MODEL-01 hoàn thành: STOP. Không tự bắt đầu task khác. Không tự sửa drift phát hiện được. Không tự tạo migration. Không tự sửa database.

## Câu hỏi mở

- Q0: ✅ Đã chốt — menu `data_model` hiện luôn sau khi ADMIN cấp quyền (người dùng chốt lúc review task, 09/11/2026).
- Q1: ✅ Đã chốt — domain mapping theo cách "lai": quy tắc tiền tố làm mặc định + danh sách ngoại lệ nhỏ trong inspector + bảng không khớp → Khác + inspector cảnh báo (người dùng chọn option đề xuất lúc review task, 09/11/2026).
- Q2: ✅ Đã chốt — manifest/history commit vào repo (người dùng chốt lúc review task, 09/11/2026).
- Q3: ✅ Đã chốt — inspector chỉ đọc database của app (SQLite), không đọc Oracle data source nghiệp vụ, nên không cần kiểm chứng Oracle cho task này (người dùng chốt "chỉ ER database SQLite", 09/11/2026).
