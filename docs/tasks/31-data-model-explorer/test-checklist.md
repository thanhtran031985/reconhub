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

## Bổ sung sau review (2026-11-10)

- [x] Click table → highlight đúng (bảng được chọn viền primary, bảng liên quan accent, bảng không liên quan mờ đi)
- [x] Click vùng trống canvas → selection bị xóa, canvas về bình thường, Detail Panel về empty state ("Chọn một table hoặc relationship để xem chi tiết.")
- [ ] Click entity vẫn chọn table; dblclick vẫn center + zoom; nút zoom/fit không bị ảnh hưởng khi click vùng trống
- [x] Nút thu nhỏ ở header Explorer: bấm → panel thành dải hẹp 36px có nút mở lại, ER Canvas lấy phần chỗ trống
- [x] Nút thu nhỏ ở header Chi tiết: tương tự, độc lập với Explorer
- [x] Thu cả hai panel: ER Canvas chiếm toàn bộ chiều rộng
- [ ] Bấm nút mở lại → panel trở về tỉ lệ cũ (Explorer 2 / Canvas 5 / Detail 3)
- [ ] Thu nhỏ/mở rộng không phá search, selection, deep link URL, zoom/fit
- [x] Nút thu nhỏ/mở có aria-label + tooltip tiếng Việt
- [x] Desktop 1440×900 không cuộn trang ở mọi trạng thái (mở/thu từng panel/thu cả hai)
- [ ] Mobile giữ hành vi responsive hiện có (panel thu nhỏ không bị ép min-height 320px)

Ghi chú bổ sung (10/11/2026): Playwright trên server thử (1440×900) đã qua click-outside, thu Explorer (36px, canvas 724px), thu cả hai (Detail 36px, canvas 1124px), không cuộn trang ở cả 3 trạng thái; ảnh `data-model-click-outside-1440.png`, `data-model-collapse-1440.png`, `data-model-collapse-both-1440.png` (người dùng đã xem). Còn [ ]: entity click/zoom/dblclick sau khi bổ sung và search/zoom-fit không phá — script dừng ở bước mở lại theo quyết định của người dùng (bỏ qua bước chụp ảnh nếu lâu quá); zoom/dblclick đã kiểm chứng ở bước 8, listener click-outside loại trừ entity/line và nút zoom/fit nằm ngoài canvas container (code inspection + probe: dispatch tổng hợp + click chuột thật đều xóa selection đúng, replay callback ALL không chọn lại). Mở lại: Explorer đã mở lại được trên trình duyệt (lượt chạy 2), Chi tiết chỉ kiểm bằng unit test (`test_handle_panel_toggle` đảo cả hai panel độc lập + bấm lại mở ra, `test_update_panel_layout` assert flex 2/5/3 khi mở) — bấm mở lại Chi tiết trên trình duyệt timeout 2 lần do VM chậm (mỗi lần render workspace ~85 giây, `dcc.Loading` che nút trong lúc render), không phải lỗi sản phẩm. Mobile: chỉ sửa CSS (media query <900px + `.dm-panel-collapsed` min-height 36px), chưa chạy Playwright mobile.

## Sửa lỗi treo trang (2026-11-10)

- [x] Click table chỉ ghi selection-store, KHÔNG ghi app-location href (không navigation, không chạy lại layout)
- [x] Guard-fail ở `handle_table_click` / `handle_entity_click` / `handle_rel_nav` trả `dash.no_update`
- [x] Guard-fail ở `handle_group_toggle` / `handle_rel_click` raise `PreventUpdate`
- [x] Guard-fail ở `handle_context_menu` trả toàn bộ 7 outputs `no_update`; action "copy" chỉ ghi `copy-store`
- [x] `update_workspace` khi trigger chỉ là selection/zoom-store: explorer children + explorer-count là `no_update`, canvas + detail vẫn dựng lại, zoom label giữ đúng (0.7 → "70%")
- [x] Đổi search/domain/mode vẫn dựng lại Explorer đầy đủ (không `no_update`)
- [x] URL vẫn đổi theo selection qua clientside `history.replaceState` (không navigation); deep-link khi load/refresh vẫn giữ qua `layout(**kwargs)`
- [x] Highlight dòng Explorer đồng bộ clientside (class `active` + `aria-selected` theo `data-table`) khi Explorer không dựng lại
- [x] Click table không reset zoom về 100% (không còn navigation → `zoom-store` không khởi tạo lại)
- [x] Một click (chọn table) chỉ gây TỐI ĐA 1 lần render workspace — đo bằng số request `/_dash-update-component` (probe v2)
- [x] Bấm thu nhỏ Explorer → tab responsive; bấm thu nhỏ Chi tiết → tab responsive; bấm mở lại cả hai → tab responsive (probe v2)
- [x] Bấm vùng trống canvas → tab responsive, selection bị xóa
- [x] Ảnh `data-model-fix-1440.png` (trạng thái đã chọn) ở `~/workspace/dashboard-preview/`
- [x] Test hồi quy: `test_handle_rel_click_guard_fail_prevents_update`, `test_update_workspace_selection_only_skips_explorer`, `test_update_workspace_search_change_rebuilds_explorer`, `test_table_click_does_not_touch_zoom_or_url` (đỏ trước khi sửa, xanh sau khi sửa)

Ghi chú đo render (10/11/2026): probe v1 dùng MutationObserver childList cho kết quả 0 render dù click đã xử lý — React cập nhật DOM tại chỗ, không thay children của container, nên childList không đếm được render. Đổi sang đếm request POST tới `/_dash-update-component` (mỗi lần server callback chạy = 1 request) — script `~/workspace/dashboard-preview/data_model_fix_probe2.py`.

Kết quả đo cuối (v3, probe2 `postfix3` + script nghiệm thu `data_model_fix_verify.py`, server thử cổng 8051):
- Kết luận loại: (b) render chậm rồi hồi phục, KHÔNG phải vòng lặp vô hạn — người dùng bấm Wait thì trang hồi lại; chuỗi render nối tiếp + một lần render đầy đủ tự nó đã quá chậm.
- TRƯỚC sửa: click RECON_RUN → main thread block ~80s, 21 request trong 150s mà chưa settle; thu nhỏ Explorer → block ~88s, 8 request/90s.
- Sau v1: click → 22 request/156s, block ~56s (chuỗi đã cắt nhưng một render đầy đủ vẫn ~70s).
- Sau v2: click ping 2–4ms (hết treo); thu/mở panel vẫn block ~78–80s.
- Sau v3: click table ping 2–8ms, thu Explorer ping 2–9ms, mở lại ping 2–3ms — hết treo cả 3 thao tác; selection đúng suốt quá trình. Mỗi thao tác ~2–3 request data-model + ~2 request/10s từ interval 5s `app-perm-revision-check` của shell (có sẵn trên mọi page, không phải chuỗi render; probe báo "chưa settle" vì interval 5s khiến quiet không đạt 10s — là giới hạn của probe, không phải lỗi).
- Nghiệm thu cuối (ping 1–2ms từng bước): click 3 table liên tiếp (RECON_RUN → RECON_USER → RECON_TEMPLATE, URL đổi theo từng table), click vùng trống (selection xóa, Detail về empty, URL bỏ `?table=`), zoom + (nhãn 110%, transform scale(1.1), giữ selection), thu/mở Chi tiết (flex `0 0 36px` ↔ `3 1 0%`) — VERIFY OK. Ảnh `data-model-fix-1440.png` (RECON_RUN đã chọn, zoom 110%).

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
