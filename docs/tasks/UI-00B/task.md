# TASK UI-00B — Fluent Foundation

## Status

DONE

## Dependencies

- UI-00A (Done — Baseline inventory & screenshots)

## Objective

Xây dựng bộ khung giao diện Fluent Foundation và các component layout dùng chung chuẩn hóa (`AppShell`, `PageHeader`, `CommandBar`, `FilterBar`, `DataGrid`, `MasterDetailLayout`, `WizardShell`, `SkeletonGrid`, `ErrorState`, layout test harness).
Chuẩn bị sẵn sàng hạ tầng component để các task UI-01 đến UI-07 di chuyển giao diện mà không làm xáo trộn callback hay business logic.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-00B"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu UI-01 hay bất kỳ task nào khác.

## Pages

Không migrate bất kỳ trang cụ thể nào trong task này. Foundation được kiểm tra qua test harness và trang nội bộ dev (`/dev/ui`).

## Target Pattern

Foundation / Layout Framework

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/ui-migration.md` (mục 2 và 11: UI-00B Foundation Proposal)
4. `designs/tokens.json`
5. `designs/README.md`
6. `designs/reference/preview-fluent.html` (visual reference)

## Allowed Scope

- Cập nhật khung `AppShell` trong `app/ui/layout/shell.py`:
  - Giảm chiều cao header xuống 44px (token `--hdr: 44px`).
  - Chuẩn hóa width navbar về 200px (mở rộng) và 48px (thu gọn dạng rail), thêm vạch chỉ báo active 3px màu primary bên trái.
  - Bọc vùng nội dung `dash.page_container` trong container cố định không cuộn trang: `dmc.Box(h="100%", style={"minHeight": 0, "overflow": "hidden", "display": "flex", "flexDirection": "column"})`.
- Tạo các component dùng chung mới trong `app/ui/components/`:
  - `page_header.py`: Component `page_header(title, subtitle=None, actions=None, breadcrumbs=None)` chuẩn 1 dòng (Title order=4, size 18px + text dimmed 12px + nút hành động).
  - `command_bar.py`: Component `command_bar(search_id=None, search_placeholder=None, filters=None, actions=None)`.
  - `filter_bar.py`: Component `filter_bar(children, actions=None)`.
  - `data_grid.py`: Wrapper cho `dag.AgGrid` định nghĩa sẵn `GRID_DEFAULTS` (`rowHeight=32`, `headerHeight=34`, font Segoe UI / tabular nums, class `rh-diff`).
  - `master_detail.py`: Container `master_detail_layout(master_content, detail_content, detail_width=380, id=None)`.
  - `wizard_shell.py`: Component `wizard_shell(steps, current_step, content, footer_actions, id=None)`.
  - `skeleton_grid.py`: `skeleton_grid(rows=8, cols=4)` và `skeleton_panel()`.
  - Cập nhật `error_state.py` (hoặc mở rộng `alert_box.py`): Chuẩn hóa ErrorState có nút "Thử lại" và lưu giữ dữ liệu cũ.
- Thêm layout test harness trong `tests/unit/test_ui_foundation.py` hoặc `tests/e2e/test_ui_foundation.py`.

## Forbidden Scope

- **KHÔNG migrate bất kỳ page nào** trong `app/ui/pages/`.
- **KHÔNG đổi `dmc.Table` hiện tại của các trang thành AgGrid**.
- **KHÔNG sửa bất kỳ callback nào của các trang**.
- **KHÔNG đổi API của các service** trong `app/services/`.
- **KHÔNG sửa designs/tokens.json** hoặc bất kỳ file nào trong `designs/`.

## Preserve Contracts

- Giữ nguyên toàn bộ ID và event handler của `app-sidebar-toggle-btn`, `app-color-scheme-toggle`, `app-location`.
- Giữ nguyên các hàm helper hiện có trong `app/ui/components/` (`alert_box`, `kpi_card`, `status_chip`, `button_primary`, `modal_confirm`...) để không làm hỏng code hiện tại.

## Preflight

Trước khi viết bất kỳ code nào:
1. `git status --short`
2. `git branch --show-current`
3. `git log -1 --oneline`
4. Chạy baseline lint, typecheck, unit tests:
   - `uv run poe lint`
   - `uv run poe typecheck`
   - `uv run poe test`
5. Ghi lại các pre-existing failures (nếu có).

## Implementation Steps

1. **Step 1 — Foundation Data Models & Constants**:
   Tạo `app/ui/components/grid_defaults.py` định nghĩa `GRID_DEFAULTS` (`ROW_HEIGHT = 32`, `HEADER_HEIGHT = 34`, theme Quartz Fluent mapping, `cellClassRules`).
2. **Step 2 — DataGrid Wrapper**:
   Tạo `app/ui/components/data_grid.py` bọc `dag.AgGrid` tự động áp dụng `GRID_DEFAULTS`, xử lý infinite và clientSide model.
3. **Step 3 — PageHeader, CommandBar, FilterBar**:
   Tạo `page_header.py`, `command_bar.py`, `filter_bar.py` trong `app/ui/components/` theo đúng design token và preview-fluent.
4. **Step 4 — MasterDetailLayout & WizardShell**:
   Tạo `master_detail.py` và `wizard_shell.py` hỗ trợ responsive (tự động co về stack dọc trên màn hình <900px).
5. **Step 5 — 4-State Helpers**:
   Tạo `skeleton_grid.py` và hoàn thiện `error_state` (với nút "Thử lại").
6. **Step 6 — AppShell Fluent Refactoring**:
   Cập nhật `app/ui/layout/shell.py` đưa header về 44px, navbar về 200px/48px, khóa cuộn toàn trang desktop.
7. **Step 7 — Foundation Test Suite & Verification**:
   Viết `tests/unit/test_ui_foundation.py` kiểm tra import, default props, và test Playwright layout test harness tại 1366×768.

## Bug Safety Rules

Repository có thể chứa code do nhiều AI tạo trước đó. Mọi lỗi gặp phải phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Không sửa.
- `B. PRE-EXISTING BLOCKER`: Chỉ sửa mức tối thiểu nếu chặn trực tiếp task.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc scope, không đổi contract, có test.
- `E. UNKNOWN`: Không đoán, STOP và hỏi người dùng nếu có rủi ro nghiệp vụ.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/unit/test_ui_foundation.py`

## Visual Checks

- Mở `/dev/ui` hoặc test harness ở 1366×768: `document.documentElement.scrollHeight <= innerHeight`.
- Kiểm tra navbar mở rộng 200px, thu gọn 48px rail, hiển thị tooltip chuẩn xác.
- Kiểm tra header đúng 44px, không che khuất breadcrumb và user avatar.

## Acceptance Criteria

- [ ] `AppShell` header đạt chuẩn 44px, navbar đạt chuẩn 200px/48px.
- [ ] Desktop viewport 1366×768 không bị page-scroll ở shell container.
- [ ] `DataGrid` export đầy đủ, đóng gói sẵn `GRID_DEFAULTS`.
- [ ] `PageHeader`, `CommandBar`, `FilterBar` export đầy đủ từ `app/ui/components/`.
- [ ] `MasterDetailLayout` và `WizardShell` hoạt động đúng flex model và responsive.
- [ ] `SkeletonGrid` và `ErrorState` có retry action sẵn sàng.
- [ ] Không có page nào bị migrate trong task này.
- [ ] Tất cả test lint, typecheck, unit test hiện có tiếp tục PASS.

## Files Expected To Change

- `app/ui/layout/shell.py`
- `app/ui/components/__init__.py`
- `app/ui/components/grid_defaults.py` (tạo mới)
- `app/ui/components/data_grid.py` (tạo mới)
- `app/ui/components/page_header.py` (tạo mới)
- `app/ui/components/command_bar.py` (tạo mới)
- `app/ui/components/filter_bar.py` (tạo mới)
- `app/ui/components/master_detail.py` (tạo mới)
- `app/ui/components/wizard_shell.py` (tạo mới)
- `app/ui/components/skeleton_grid.py` (tạo mới)
- `tests/unit/test_ui_foundation.py` (tạo mới)

## Files Must Not Change

- Toàn bộ các file trong `app/ui/pages/`
- Toàn bộ các file trong `app/services/`
- Toàn bộ các file trong `app/db/` và `app/engine/`
- `designs/tokens.json`

## Completion Report Format

```markdown
## UI-00B Completed

Components created/extended:
- AppShell (extended: header 44px, nav 200px/48px, no page scroll container)
- PageHeader, CommandBar, FilterBar
- DataGrid (GRID_DEFAULTS: rowHeight=32, headerHeight=34)
- MasterDetailLayout, WizardShell
- SkeletonGrid, ErrorState

Tests run:
- lint: PASS
- typecheck: PASS
- unit tests: PASS

Bug classification (nếu có):
- ...

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định: `"Làm UI-01"` hoặc task khác.

