# Test Checklist — DATA-MODEL-01 (31-data-model-explorer)

Checklist kiểm thử cho task DATA-MODEL-01. Đánh dấu `[x]` khi ca đã pass, ghi ngày + bằng chứng (lệnh/log/ảnh) khi cần.

## Preflight

- [ ] `git status --short` sạch; `git branch --show-current` đúng nhánh `feat/31-data-model-explorer`
- [ ] Baseline tests chạy trước khi implement (ghi số pass/fail baseline)
- [ ] Bug phát hiện được phân loại (PRE-EXISTING UNRELATED / PRE-EXISTING BLOCKER / INTRODUCED BY TASK / DISCOVERED RELATED BUG / UNKNOWN)

## Schema Inspector

- [ ] Table extraction đúng (đủ 43 bảng thật trong `app/db/metadata.py`)
- [ ] Column extraction đúng (tên, datatype, nullable, default)
- [ ] PK extraction đúng
- [ ] FK extraction đúng (column, referenced table/column, constraint name)
- [ ] Unique constraints đúng
- [ ] Indexes đúng
- [ ] Deterministic output (chạy 2 lần khi schema không đổi → manifest giống hệt, không fake diff)
- [ ] Chạy được trên SQLite và Oracle (Oracle: skip khi không VPN, ghi rõ chưa kiểm chứng)
- [ ] Không hardcode table list hay relationships

## Manifest

- [ ] `docs/data-model/schema-manifest.json` được sinh ra, có header GENERATED
- [ ] Manifest khớp schema thật (spot-check vài bảng: `RECON_RUN`, `RECON_TEMPLATE`, `RECON_REPORT`)
- [ ] Manifest không chứa credentials/connection string
- [ ] Chạy lại inspector không tạo diff giả

## History

- [ ] `docs/data-model/schema-history.json` được sinh ra, có header GENERATED
- [ ] Change events đúng type (TABLE_CREATED, COLUMN_ADDED, …)
- [ ] Mỗi record đủ trường khi metadata cho phép (timestamp, task_id, migration_id, entity, change_type, before, after)

## Drift

- [ ] TABLE_MISSING / TABLE_EXTRA
- [ ] COLUMN_MISSING / COLUMN_EXTRA
- [ ] TYPE_CHANGED
- [ ] NULLABILITY_CHANGED
- [ ] PK_CHANGED
- [ ] FK_CHANGED
- [ ] INDEX_CHANGED
- [ ] CONSTRAINT_CHANGED
- [ ] Trạng thái SYNCED / DRIFT / UNKNOWN / ERROR đúng

## Permissions

- [ ] Chưa đăng nhập vào `/data-model` → chuyển về `/login`
- [ ] Vai trò không được cấp menu `data_model` → `/forbidden`, không thấy menu ở sidebar
- [ ] ADMIN cấp menu trên `/roles` xong thì vai trò thấy menu và vào được page
- [ ] Service đọc manifest có `@requires_menu("data_model")`

## Page Layout

- [ ] Route `/data-model` đúng; title đúng
- [ ] Menu "Mô hình dữ liệu" ở nhóm QUẢN TRỊ
- [ ] Fluent Compact đúng (theo `.agents/rules/ui-dash.md`)
- [ ] Desktop >= 1280: page không cuộn (`scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`)
- [ ] Đủ 3 panel: Schema Explorer | ER Canvas | Detail Panel + Status Bar
- [ ] Light/Dark đúng

## Explorer

- [ ] Group theo domain, đủ số table mỗi nhóm
- [ ] Group expand/collapse; search tự expand group có match
- [ ] Table item compact: status marker, tên bảng, column count
- [ ] Hover table hiện tooltip description (không gọi backend)

## Search

- [ ] Search table name
- [ ] Search column name (vd `GRID_SPAN` → giữ `REPORT_PARAMETER` visible + highlight column)
- [ ] Search table description
- [ ] Search filter đồng thời Explorer và Canvas
- [ ] Empty search: "Không tìm thấy table hoặc column phù hợp." + nút "Xóa bộ lọc"

## Domain

- [ ] Filter Tất cả phân hệ
- [ ] Filter từng domain (Core / Đối soát / Báo cáo / Quản trị / Khác)
- [ ] Domain mapping không hardcode trong page

## ER Canvas

- [ ] Entity card đủ 43 bảng thật, đủ columns + PK/FK marker + datatype
- [ ] Relationship lines đúng theo FK metadata
- [ ] Auto-layout deterministic (2 lần render cùng vị trí, không hardcode toạ độ)
- [ ] Pan / scroll / zoom trong bounded viewport, không làm tăng chiều cao page
- [ ] Display mode: Hiển thị quan hệ vs Chỉ tên table (không mất selection)

## Table Selection

- [ ] Click table: row active, entity highlight, relationships liên quan highlight, Detail Panel load đúng table, URL query cập nhật, không reload page
- [ ] Double click table: center table trên canvas, zoom đủ đọc columns
- [ ] Context menu: Center trong ER Diagram, Xem columns, Xem relationships, Xem lịch sử thay đổi (filter theo table), Copy table name
- [ ] Context menu KHÔNG có: Drop table, Alter table, Delete column, Run SQL

## Relationship Selection

- [ ] Click relationship: source/target table highlight, line accent, Detail Panel chuyển sang Relationship Detail
- [ ] Relationship Detail đủ: source, target, constraint, cardinality, delete rule (nếu metadata có)
- [ ] Nút Source table / Target table chuyển selection đúng

## Detail Panel

- [ ] Empty state: "Chọn một table hoặc relationship để xem chi tiết."
- [ ] Table detail: header, KPI (Columns/Relationships), badges (Domain, Schema status)
- [ ] Column List đủ metadata (PK/FK/UNIQUE/NULLABLE/NOT NULL/DEFAULT)
- [ ] Relationships Incoming/Outgoing đúng
- [ ] Index/Constraint section (collapsible khi dài, không hide PK/FK)
- [ ] Recent Changes filter theo selected table

## Zoom & Fit

- [ ] Zoom In (+1 step, có MAX_ZOOM, tooltip + aria-label)
- [ ] Zoom Out (−1 step, có MIN_ZOOM)
- [ ] Fit to screen (fit visible entities, không clear search/domain/selection)

## Sync State Machine

- [ ] NORMAL: nút enabled "Đồng bộ schema"
- [ ] RUNNING: spinner "Đang đồng bộ…", nút disabled, health "Đang kiểm tra schema…"
- [ ] SUCCESS — NO CHANGE: health "✓ Schema đồng bộ"
- [ ] SUCCESS — CHANGED: thông báo "✓ Đã cập nhật mô hình" kèm số table/column changed
- [ ] DRIFT: health "⚠ Schema drift" + action "Xem khác biệt"
- [ ] ERROR: ErrorState "Không thể đọc metadata database." + action "Thử lại"

## Drift Viewer

- [ ] Mở drawer khi Health = DRIFT (và chỉ khi đó mới hiện nút)
- [ ] Liệt kê đúng từng drift (Database ↔ Application)
- [ ] Filters: Tất cả / Table / Column / Relationship / Index / Constraint
- [ ] Copy report (copy text report)
- [ ] KHÔNG có: Fix schema, Apply, Run migration, Auto repair

## Loading

- [ ] Initial load: Explorer skeleton rows, Canvas loader/skeleton, Detail SkeletonPanel
- [ ] Không block trắng toàn screen

## Empty

- [ ] Empty schema: "Không tìm thấy table trong schema hiện tại." + nút "Đồng bộ lại"
- [ ] Empty search (xem mục Search)

## Error

- [ ] Metadata load fail: "Không thể đọc metadata database." + nút "Thử lại"
- [ ] Error đã sanitize (không lộ password/token/connection string)
- [ ] Retry gọi lại inspection, không reload toàn browser nếu không cần

## Security

- [ ] Unauthorized access denied (xem mục Permissions)
- [ ] Không credentials trong page DOM
- [ ] Không credentials trong schema manifest
- [ ] Không credentials trong history
- [ ] Không credentials trong error messages / logs lộ ra page
- [ ] Page không expose table row data hay sample sensitive data

## Responsive

- [ ] 1366×768: desktop không page scroll
- [ ] 1440×900: desktop không page scroll
- [ ] 390×844: page cuộn được, thứ tự CommandBar → Explorer → Canvas → Detail, không horizontal page overflow

## Accessibility

- [ ] Icon button có tooltip + aria-label
- [ ] Table item keyboard selectable + `aria-selected`
- [ ] Relationship keyboard selectable nếu feasible
- [ ] PK/FK không chỉ phân biệt bằng màu
- [ ] Focus visible
- [ ] Status `aria-live="polite"`
- [ ] Controls có label/aria-label

## CI Freshness

- [ ] CI generate manifest vào temp, normalize, diff với committed manifest
- [ ] Manifest stale → CI FAIL với message "Schema manifest is stale. Run: uv run poe schema-introspect"
- [ ] Manifest đồng bộ → CI pass
- [ ] `schema-introspect` không git add/commit/push

## Regression

- [ ] Reconciliation vẫn hoạt động (full suite)
- [ ] Reporting vẫn hoạt động
- [ ] Permissions vẫn hoạt động
- [ ] Data-source logic vẫn hoạt động

## Lint

- [ ] `uv run poe lint` sạch

## Typecheck

- [ ] `uv run poe typecheck` sạch (không tăng số lỗi so với baseline)

## Unit

- [ ] `uv run poe test` xanh (ghi số pass/skip)

## E2E

- [ ] `uv run poe e2e` xanh (ghi số pass/skip)

## Screenshot

- [ ] 1366×768 (dashboard + dropdown/history/drift nếu có)
- [ ] 1440×900
- [ ] 390×844
