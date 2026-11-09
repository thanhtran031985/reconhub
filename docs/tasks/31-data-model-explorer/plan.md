# Kế hoạch — 31-data-model-explorer (DATA-MODEL-01)

> **ĐỀ XUẤT — CHƯA DUYỆT.** Plan này được generate cùng task (theo prompt DATA-MODEL-01 §82: chỉ generate task, STOP, không implement). Chỉ khi người dùng yêu cầu chính xác "Làm DATA-MODEL-01" thì plan mới được duyệt và implement. Khi duyệt, plan này (kèm câu trả lời Q0–Q3) được coi là plan đã duyệt.

## Bối cảnh

- Task ID: DATA-MODEL-01. Nhánh: `feat/31-data-model-explorer`, rẽ từ `c624236` (đỉnh `feat/30-menu-search`, đã gồm patch task 30 + 2 file người dùng push: prototype ER diagram và prompt DATA-MODEL-01).
- Vấn đề: ReconHub phát triển theo workflow AI/vibe coding; nhiều AI liên tục bổ sung table/column/FK/index nên developer khó hình dung database hiện được thiết kế như thế nào. Chưa có nơi duy nhất, luôn đồng bộ để xem mô hình dữ liệu.
- Prototype tham chiếu `designs/reference/reconhub-er-diagram.html` đã có trong repo (14 table đơn giản hoá, chỉ để tham chiếu layout/interaction — KHÔNG phải source of truth; schema thật có 43 bảng trong `app/db/metadata.py`).
- Kiến trúc thật đã audit lúc generate task: Python 3.12, Dash 3 + dmc 2.x, SQLAlchemy Core (43 bảng), Alembic (0001–0006), SQLite mặc định + Oracle qua Thin/VPN, menu/phân quyền theo task 19/20, CI `.github/workflows/ci.yml`. Trước khi implement phải audit lại (prompt §6).

## Cách làm (8 bước, test viết trước rồi code, mỗi bước cập nhật progress.md)

### Bước 1 — Schema Inspector + manifest/history
- Module inspector đọc metadata qua SQLAlchemy inspector (cả SQLite và Oracle) + model `app/db/metadata.py` + Alembic migrations; normalize; validate PK/FK/index/constraint. CLI entry + poe task `schema-introspect`. Sinh `docs/data-model/schema-manifest.json` và `docs/data-model/schema-history.json` (deterministic, header GENERATED, không fake diff khi chạy lại). Khác biệt dialect qua `app/db/dialect.py`.
- Test viết trước: extraction table/column/datatype/nullable/default/PK/FK/unique/index/constraint; deterministic (chạy 2 lần giống hệt); schema diff.
- Kiểm tra: `uv run poe schema-introspect` chạy được trên SQLite; manifest khớp 43 bảng thật; test inspector xanh.

### Bước 2 — Drift comparison + CI freshness
- Service so sánh DB ↔ model/migration, trạng thái SYNCED/DRIFT/UNKNOWN/ERROR + các drift type (prompt §10). Bước CI trong `.github/workflows/ci.yml` (generate manifest vào temp, normalize, diff với committed, FAIL khi stale kèm message "Schema manifest is stale. Run: uv run poe schema-introspect").
- Test viết trước: từng drift type; CI fail khi manifest stale, pass khi đồng bộ.
- Kiểm tra: drift test xanh; mô phỏng local bằng cách sửa manifest rồi chạy lệnh CI.

### Bước 3 — Menu + route + page skeleton + permission
- `MenuDef("data_model", "Mô hình dữ liệu", "QUAN_TRI", "/data-model", …)` trong `app/ui/menus.py`; page `app/ui/pages/data_model.py` (`dash.register_page`, `layout(**kwargs)` đọc query string); service đọc manifest + `@requires_menu("data_model")`; skeleton (header, command bar, 3 panel, status bar) với loading skeleton.
- Test viết trước: menu chỉ hiện với vai trò được cấp (ADMIN cấp qua `/roles`); chưa đăng nhập → `/login`; không quyền → `/forbidden`; `layout()` nhận `**kwargs`.
- Kiểm tra: test page xanh; Playwright vào `/data-model` thấy skeleton rồi đủ 3 panel.

### Bước 4 — Schema Explorer + command bar
- Explorer group theo domain (expand/collapse, search tự expand group có match), table item compact + tooltip, click/double-click/context menu, search (table/column/description, filter đồng thời Explorer + Canvas, highlight matching column), domain filter, display mode, health badge, last sync.
- Test viết trước: search table/column + highlight, domain filter, display mode, group expand/collapse, click table (selection + URL query), double click (center), context menu, copy table name, deep link URL.
- Kiểm tra: test xanh; Playwright search `GRID_SPAN` highlight đúng column.

### Bước 5 — ER Canvas
- Entity card (PK/FK marker, datatype), relationship lines từ FK metadata, auto-layout deterministic (không hardcode toạ độ), pan/scroll/zoom/fit, click table → highlight entity + relationships liên quan, click relationship → relationship detail.
- Test viết trước: entity render đủ 43 bảng thật; relationship đúng theo FK metadata; auto-layout deterministic; zoom in/out/fit; click relationship.
- Kiểm tra: test xanh; Playwright đo canvas vừa viewport, không làm tăng chiều cao page.

### Bước 6 — Detail Panel + History + Drift viewer
- Detail Panel (empty/table/relationship detail, column list, relationships in/out, index/constraint collapsible, recent changes theo table); Drawer Lịch sử thay đổi (search + filter change type + timeline); Drawer Xem khác biệt (drift list + filters + Copy report).
- Test viết trước: detail đủ sections; history filter theo type và theo table; drift viewer đúng từng drift type; copy drift report.
- Kiểm tra: test xanh; Playwright mở history và drift drawer.

### Bước 7 — Sync state machine + loading/empty/error
- Nút Đồng bộ schema với state machine (normal/running/success no-change/success changed/drift/error) + health status; loading skeleton; empty schema/search; error + Thử lại.
- Test viết trước: từng trạng thái của state machine; empty schema; empty search + Xóa bộ lọc; error + retry.
- Kiểm tra: test xanh; Playwright mô phỏng sync thành công, sync lỗi, drift.

### Bước 8 — Auto-update rule + docs + visual tests + regression
- Bổ sung auto-update rule vào `AGENTS.md`; bổ sung mục Data Model Impact vào `docs/tasks/_template/task.md`; cập nhật `docs/USER_GUIDE.md` nếu cần; visual tests 1366×768, 1440×900, 390×844 (desktop không page scroll, mobile không horizontal overflow).
- Test viết trước: regression — reconciliation, reporting, permissions, data-source logic vẫn hoạt động (full suite).
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh; ảnh chụp 3 cỡ.

## Thứ tự commit (mỗi bước 1 commit)

1. `31-data-model-explorer: step 1 — schema inspector + manifest/history`
2. `31-data-model-explorer: step 2 — drift + CI freshness`
3. `31-data-model-explorer: step 3 — menu + route + page skeleton`
4. `31-data-model-explorer: step 4 — explorer + command bar`
5. `31-data-model-explorer: step 5 — ER canvas`
6. `31-data-model-explorer: step 6 — detail panel + history + drift viewer`
7. `31-data-model-explorer: step 7 — sync state machine + loading/empty/error`
8. `31-data-model-explorer: step 8 — auto-update rule + docs + visual tests`

## Kiểm chứng cuối

- `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh (full suite).
- Chụp màn hình 1366×768, 1440×900, 390×844 cho người dùng xem trước rồi mới xuất patch.
- Report hoàn thành theo mẫu prompt §80, rồi STOP (không tự bắt đầu task khác, không tự sửa drift, không tự tạo migration).

## Rủi ro

- **Prototype lệch schema thật (14 vs 43 bảng):** prototype chỉ là tham chiếu visual; inspector phải tự phát hiện schema thật. Nếu implementer lấy danh sách bảng từ prototype thì sai — test bước 1 bắt đủ 43 bảng.
- **Oracle chưa kiểm chứng:** inspector phải chạy được cả SQLite và Oracle; kiểm chứng Oracle cần VPN — ghi rõ ca nào chưa kiểm chứng, không chặn implement (như các task trước).
- **Auto-layout:** ER canvas với 43 bảng dễ overlap; layout phải deterministic và test được (2 lần render cùng vị trí).
- **Canvas render:** nếu dùng SVG/DOM thuần thì đơn giản nhưng cần đo hiệu năng ở > 50 bảng; nếu cần thư viện graph thì phải hỏi trước khi cài (repo quy tắc: không cài package ngoài Stack khi chưa hỏi).
- **CI freshness:** manifest commit vào repo hay gitignore vẫn là câu hỏi mở (Q2) — quyết định này ảnh hưởng bước 2, cần chốt trước khi làm bước 2.
