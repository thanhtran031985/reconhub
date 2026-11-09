# Test Checklist — DATA-MODEL-01 (31-data-model-explorer)

Checklist kiểm thử cho task DATA-MODEL-01. Đánh dấu `[x]` khi ca đã pass, ghi ngày + bằng chứng (lệnh/log/ảnh) khi cần.

## Preflight

- [x] `git status --short` sạch; `git branch --show-current` đúng nhánh `feat/31-data-model-explorer`
- [x] Baseline tests chạy trước khi implement (ghi số pass/fail baseline)
- [x] Bug phát hiện được phân loại (PRE-EXISTING UNRELATED / PRE-EXISTING BLOCKER / INTRODUCED BY TASK / DISCOVERED RELATED BUG / UNKNOWN)

## Schema Inspector

- [x] Table extraction đúng (đủ 43 bảng thật trong `app/db/metadata.py`)
- [x] Column extraction đúng (tên, datatype, nullable, default)
- [x] PK extraction đúng
- [x] FK extraction đúng (column, referenced table/column, constraint name)
- [x] Unique constraints đúng
- [x] Indexes đúng
- [x] Deterministic output (chạy 2 lần khi schema không đổi → manifest giống hệt, không fake diff)
- [x] Chạy được trên SQLite và Oracle (Oracle: skip khi không VPN, ghi rõ chưa kiểm chứng)
- [x] Không hardcode table list hay relationships

## Manifest

- [x] `docs/data-model/schema-manifest.json` được sinh ra, có header GENERATED
- [x] Manifest khớp schema thật (spot-check vài bảng: `RECON_RUN`, `RECON_TEMPLATE`, `RECON_REPORT`)
- [x] Manifest không chứa credentials/connection string
- [x] Chạy lại inspector không tạo diff giả

## History

- [x] `docs/data-model/schema-history.json` được sinh ra, có header GENERATED
- [x] Change events đúng type (TABLE_CREATED, COLUMN_ADDED, …)
- [x] Mỗi record đủ trường khi metadata cho phép (timestamp, task_id, migration_id, entity, change_type, before, after)

## Drift

- [x] TABLE_MISSING / TABLE_EXTRA
- [x] COLUMN_MISSING / COLUMN_EXTRA
- [x] TYPE_CHANGED
- [x] NULLABILITY_CHANGED
- [x] PK_CHANGED
- [x] FK_CHANGED
- [x] INDEX_CHANGED
- [x] CONSTRAINT_CHANGED
- [x] Trạng thái SYNCED / DRIFT / UNKNOWN / ERROR đúng

## Permissions

- [x] Chưa đăng nhập vào `/data-model` → chuyển về `/login`
- [x] Vai trò không được cấp menu `data_model` → `/forbidden`, không thấy menu ở sidebar
- [x] ADMIN cấp menu trên `/roles` xong thì vai trò thấy menu và vào được page
- [x] Service đọc manifest có `@requires_menu("data_model")`

## Page Layout

- [x] Route `/data-model` đúng; title đúng
- [x] Menu "Mô hình dữ liệu" ở nhóm QUẢN TRỊ
- [x] Fluent Compact đúng (theo `.agents/rules/ui-dash.md`)
- [x] Desktop >= 1280: page không cuộn (`scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`)
- [x] Đủ 3 panel: Schema Explorer | ER Canvas | Detail Panel + Status Bar
- [x] Light/Dark đúng

## Explorer

- [x] Group theo domain, đủ số table mỗi nhóm
- [x] Group expand/collapse; search tự expand group có match
- [x] Table item compact: status marker, tên bảng, column count
- [x] Hover table hiện tooltip description (không gọi backend)

## Search

- [x] Search table name
- [x] Search column name (vd `GRID_SPAN` → giữ `REPORT_PARAMETER` visible + highlight column)
- [x] Search table description
- [x] Search filter đồng thời Explorer và Canvas
- [x] Empty search: "Không tìm thấy table hoặc column phù hợp." + nút "Xóa bộ lọc"

## Domain

- [x] Filter Tất cả phân hệ
- [x] Filter từng domain (Core / Đối soát / Báo cáo / Quản trị / Khác)
- [x] Domain mapping không hardcode trong page

## ER Canvas

- [x] Entity card đủ 43 bảng thật, đủ columns + PK/FK marker + datatype
- [x] Relationship lines đúng theo FK metadata
- [x] Auto-layout deterministic (2 lần render cùng vị trí, không hardcode toạ độ)
- [x] Pan / scroll / zoom trong bounded viewport, không làm tăng chiều cao page
- [x] Display mode: Hiển thị quan hệ vs Chỉ tên table (không mất selection)

## Table Selection

- [x] Click table: row active, entity highlight, relationships liên quan highlight, Detail Panel load đúng table, URL query cập nhật, không reload page
- [x] Double click table: center table trên canvas, zoom đủ đọc columns
- [x] Context menu: Center trong ER Diagram, Xem columns, Xem relationships, Xem lịch sử thay đổi (filter theo table), Copy table name
- [x] Context menu KHÔNG có: Drop table, Alter table, Delete column, Run SQL

## Relationship Selection

- [x] Click relationship: source/target table highlight, line accent, Detail Panel chuyển sang Relationship Detail
- [x] Relationship Detail đủ: source, target, constraint, cardinality, delete rule (nếu metadata có)
- [x] Nút Source table / Target table chuyển selection đúng

## Detail Panel

- [x] Empty state: "Chọn một table hoặc relationship để xem chi tiết."
- [x] Table detail: header, KPI (Columns/Relationships), badges (Domain, Schema status)
- [x] Column List đủ metadata (PK/FK/UNIQUE/NULLABLE/NOT NULL/DEFAULT)
- [x] Relationships Incoming/Outgoing đúng
- [x] Index/Constraint section (collapsible khi dài, không hide PK/FK)
- [x] Recent Changes filter theo selected table

## Zoom & Fit

- [x] Zoom In (+1 step, có MAX_ZOOM, tooltip + aria-label)
- [x] Zoom Out (−1 step, có MIN_ZOOM)
- [x] Fit to screen (fit visible entities, không clear search/domain/selection)

## Sync State Machine

- [x] NORMAL: nút enabled "Đồng bộ schema"
- [x] RUNNING: spinner "Đang đồng bộ…", nút disabled, health "Đang kiểm tra schema…"
- [x] SUCCESS — NO CHANGE: health "✓ Schema đồng bộ"
- [x] SUCCESS — CHANGED: thông báo "✓ Đã cập nhật mô hình" kèm số table/column changed
- [x] DRIFT: health "⚠ Schema drift" + action "Xem khác biệt"
- [x] ERROR: ErrorState "Không thể đọc metadata database." + action "Thử lại"

## Drift Viewer

- [x] Mở drawer khi Health = DRIFT (và chỉ khi đó mới hiện nút)
- [x] Liệt kê đúng từng drift (Database ↔ Application)
- [x] Filters: Tất cả / Table / Column / Relationship / Index / Constraint
- [x] Copy report (copy text report)
- [x] KHÔNG có: Fix schema, Apply, Run migration, Auto repair

## Loading

- [x] Initial load: Explorer skeleton rows, Canvas loader/skeleton, Detail SkeletonPanel
- [x] Không block trắng toàn screen

## Empty

- [x] Empty schema: "Không tìm thấy table trong schema hiện tại." + nút "Đồng bộ lại"
- [x] Empty search (xem mục Search)

## Error

- [x] Metadata load fail: "Không thể đọc metadata database." + nút "Thử lại"
- [x] Error đã sanitize (không lộ password/token/connection string)
- [x] Retry gọi lại inspection, không reload toàn browser nếu không cần

## Security

- [x] Unauthorized access denied (xem mục Permissions)
- [x] Không credentials trong page DOM
- [x] Không credentials trong schema manifest
- [x] Không credentials trong history
- [x] Không credentials trong error messages / logs lộ ra page
- [x] Page không expose table row data hay sample sensitive data

## Responsive

- [x] 1366×768: desktop không page scroll
- [x] 1440×900: desktop không page scroll
- [ ] 390×844: page cuộn được, thứ tự CommandBar → Explorer → Canvas → Detail, không horizontal page overflow

## Accessibility

- [x] Icon button có tooltip + aria-label
- [x] Table item keyboard selectable + `aria-selected`
- [ ] Relationship keyboard selectable nếu feasible
- [x] PK/FK không chỉ phân biệt bằng màu
- [x] Focus visible
- [x] Status `aria-live="polite"`
- [x] Controls có label/aria-label

## CI Freshness

- [x] CI generate manifest vào temp, normalize, diff với committed manifest
- [x] Manifest stale → CI FAIL với message "Schema manifest is stale. Run: uv run poe schema-introspect"
- [x] Manifest đồng bộ → CI pass
- [x] `schema-introspect` không git add/commit/push

## Regression

- [x] Reconciliation vẫn hoạt động (full suite)
- [x] Reporting vẫn hoạt động
- [x] Permissions vẫn hoạt động
- [x] Data-source logic vẫn hoạt động

## Lint

- [x] `uv run poe lint` sạch

## Typecheck

- [x] `uv run poe typecheck` sạch (không tăng số lỗi so với baseline)

## Unit

- [x] `uv run poe test` xanh (ghi số pass/skip)

## E2E

- [x] `uv run poe e2e` xanh (ghi số pass/skip)

## Screenshot

- [x] 1366×768 (dashboard + dropdown/history/drift nếu có)
- [x] 1440×900
- [x] 390×844 (`data-model-final-390.png`; không tràn ngang, nội dung bị shell che — xem ghi chú Mobile bên dưới)

## Ghi chú kiểm chứng (09/11/2026, bước 8)

- Baseline trước khi implement: full suite trừ e2e 1212 passed, 6 skipped (213s); typecheck 0 lỗi (baseline "21 lỗi" trong ghi chú cũ đã lỗi thời).
- Inspector chỉ đọc SQLite theo Q3 (người dùng chốt "chỉ ER database SQLite") — mục "Chạy được trên SQLite và Oracle" được đánh [x] vì SQLite chạy đúng (extract 43 bảng + drift live), Oracle ngoài scope theo Q3 nên không kiểm chứng.
- Copy report clipboard thật trong headless Chromium chưa kiểm chứng (chỉ unit test text report).
- Light/Dark: đã kiểm chứng ở bước 8 — dark 1440 (`data-model-dark-1440.png`): panel + entity card tối, chữ đọc được, không cuộn trang. Phát hiện và sửa: `.dm-entity` dùng token `--p` không tồn tại → luôn trắng (chữ trắng trên nền trắng ở dark); đã chuyển 4 khai báo `.dm-*` sang biến Mantine (`--mantine-color-body`, `--mantine-color-default-hover`, `--mantine-color-primary-light`), chụp lại light 1440 không đổi. Còn lại (ngoài scope task 31, pre-existing): khối `[data-theme="dark"]` trong tokens.css là dead code (không code nào đặt `data-theme`, app chỉ dùng `data-mantine-color-scheme`) nên token custom kẹt ở giá trị sáng khi dark — dải tiêu đề/command bar/status bar vẫn nền sáng ở dark do AppShellMain dùng `var(--bg)` (shell.py:856); đề xuất task follow-up cho design system. Xem decisions.md 09/11/2026.
- Mobile 390×844: không tràn ngang [đo scrollW 390 = innerW 390]; nhưng nội dung không tới được tay người dùng do shell sẵn có (navbar thành overlay full-width <768px, không có burger; AppShellMain height cố định + overflow:hidden) — đã kiểm chứng trên cả dashboard `/` nên là lỗi pre-existing, ảnh hưởng mọi page, ngoài scope task 31. Page tự thân đã xếp dọc đúng (workspace column). Đề xuất task follow-up cho mobile shell. Xem decisions.md 09/11/2026.
- Relationship keyboard selectable: chưa feasible với div xoay (html.Div không focusable mặc định); quan hệ vẫn chọn được bằng click chuột và qua danh sách Relationships ở Detail Panel.
- Status aria-live: đã bổ sung `aria-live="polite"` vào `#data-model-health-container` ở bước 8 (test page 57 pass sau khi sửa).
- Bug phân loại: mobile shell 390×844 = PRE-EXISTING UNRELATED (xem decisions.md 09/11/2026); 5 test fail ở full suite lần 1 (test_menu_sync ×3, test_page_roles ×1, test_menu_admin_service ×1) = INTRODUCED BY TASK — menu mới `data_model` nâng tổng số menu 16 → 17, chỉ cập nhật số đếm hardcode trong test, không đổi hành vi; đã sửa xong, 3 file 65 pass.
- Full suite lần 2 (sau khi sửa 5 test đếm menu 16 → 17 + bổ sung aria-live + sửa dark-mode CSS): **1341 passed, 6 skipped, 0 failed** (224,68s). Typecheck 0 lỗi (141 file), lint sạch. E2E (`pytest tests/e2e/ -v`): **35 passed** (13,5s; suite e2e hiện có, chưa có test e2e riêng cho /data-model — page này kiểm chứng bằng script Playwright). Full suite lần 3 trên code cuối: **1341 passed, 6 skipped, 0 failed** (233,55s) — chốt.
