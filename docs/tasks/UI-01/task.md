# TASK UI-01 — Compact Lists

## Status

DONE

## Dependencies

- UI-00B (Fluent Foundation)

## Objective

Chuyển đổi 5 màn hình danh sách (`/templates`, `/history`, `/batches`, `/report-runs`, `/reports`) sang pattern **LIST** chuẩn Fluent Compact: `PageHeader` + `CommandBar` + `DataGrid` (AgGrid Compact).
Triệt tiêu hoàn toàn hiện tượng cuộn toàn trang desktop 1366×768 (đặc biệt là `/history` hiện cuộn 2181px), loại bỏ lưới Card lớn tại `/reports` để đưa về Compact List phân nhóm.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-01"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/templates` | `app/ui/pages/templates.py` | [03-template-config](../03-template-config/task.md), [08-app-shell-ui](../08-app-shell-ui/task.md) | [03_template_config.md](../../specs/03_template_config.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen02-Templates` |
| `/history` | `app/ui/pages/history.py` | [12-export-history](../12-export-history/task.md) | [04_excel_reader.md](../../specs/04_excel_reader.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen07-History` |
| `/batches` | `app/ui/pages/batch_defs.py` | [18-batch-run](../18-batch-run/task.md) | [10_batch_run.md](../../specs/10_batch_run.md), [10_batch_run_tables.md](../../specs/10_batch_run_tables.md) | `designs/components/Screen13-BatchRun` |
| `/report-runs` | `app/ui/pages/report_runs.py` | [25-reporting-execution](../25-reporting-execution/task.md), [27-reporting-ui](../27-reporting-ui/task.md) | Task 25-27 | `designs/components/Screen16-DynamicReporting` |
| `/reports` | `app/ui/pages/reports.py` | [27-reporting-ui](../27-reporting-ui/task.md) | [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen16-DynamicReporting` |

## Target Pattern

**LIST**:
- Vùng 1: `PageHeader` (1 hàng ngang: Title order=4 + subtitle + primary action)
- Vùng 2: `CommandBar` (`dmc.Paper` withBorder: Search input + filters + bulk action buttons)
- Vùng 3: `DataGrid` (`dag.AgGrid` bọc trong container `flex: 1`, internal scroll)

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/ui-migration.md` (mục 3, 4, 6 và 10 cho UI-01)
4. Yêu cầu & nghiệp vụ gốc:
   - [03-template-config/task.md](../03-template-config/task.md) & [08-app-shell-ui/task.md](../08-app-shell-ui/task.md) (Templates list)
   - [12-export-history/task.md](../12-export-history/task.md) (History & bulk purge)
   - [18-batch-run/task.md](../18-batch-run/task.md) (Batch definitions)
   - [27-reporting-ui/task.md](../27-reporting-ui/task.md) (Reports center & run history)
5. Baseline screenshots: `artifacts/ui-inventory/templates-before-1366x768.png`, `history-before-1366x768.png`, `reports-before-1366x768.png`
6. Foundation components từ UI-00B (`DataGrid`, `PageHeader`, `CommandBar`, `GRID_DEFAULTS`)

## Allowed Scope

- Thay thế bảng `dmc.Table` trong `templates.py`, `history.py`, `batch_defs.py`, `report_runs.py` bằng `DataGrid` (AgGrid).
  - `/history`: Dùng `rowModelType="infinite"` (hoặc pagination tích hợp virtual scroll) để xử lý hàng trăm run mà không sinh DOM thừa.
  - `/templates`, `/batches`, `/report-runs`: Dùng `rowModelType="clientSide"` với quick filter từ `CommandBar`.
- Thay thế lưới thẻ Card (`dmc.SimpleGrid` + `report-card`) trong `reports.py` bằng Compact Table / AgGrid có phân nhóm theo `GROUP` (Doi soat, Báo cáo tài chính...).
- Đưa các thanh tìm kiếm/lọc hiện có vào `CommandBar` chuẩn hóa.
- Tích hợp `PageHeader` thay thế cho các `dmc.Title` order 1/2 kích thước lớn.
- Bọc toàn bộ trang trong `dmc.Stack(h="100%", gap="xs", style={"minHeight": 0, "overflow": "hidden"})`.

## Forbidden Scope

- **KHÔNG đổi component IDs** đã dùng trong các callback hiện có (ví dụ: `history-search-input`, `history-status-filter`, `tmpl-table-container`, `tmpl-create-btn`, `bdef-search`...).
- **KHÔNG sửa logic nghiệp vụ**, callback Input/Output/State, hoặc gọi service khác đi.
- **KHÔNG chuyển đổi các form modal** sang Master–Detail trong task này (giữ nguyên các modal xác nhận hoặc modal tạo bộ hiện có).
- **KHÔNG chạm vào các trang Master–Detail** (`/users`, `/roles`, `/menus`, `/lookups`).

## Preserve Contracts

- Giữ nguyên các chức năng:
  - Chọn nhiều dòng và xóa hàng loạt trong `/history` (`history-bulk-purge-modal`).
  - Nút Tải file kết quả run trong `/history`.
  - Nút Nhân bản, Xuất JSON, Nhập JSON, Xóa, Lưu trữ trong `/templates`.
  - Phân quyền theo menu (`page_gate(ctx, MENU_CODE)`).

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Kiểm tra baseline screenshots tại `artifacts/ui-inventory/` cho 5 trang.
4. Chạy `uv run poe test` và `uv run poe e2e` để ghi nhận baseline hiện tại.

## Implementation Steps

1. **Step 1 — Templates List (`/templates`)**:
   - Thay `dmc.Title` bằng `PageHeader`.
   - Gom ô tìm kiếm, bộ lọc trạng thái và nút Đăng ký mới vào `CommandBar`.
   - Chuyển `dmc.Table` sang `DataGrid` (clientSide, columnDefs: Mã, Tên, Nguồn DB, Trạng thái, Thao tác).
   - Kiểm tra: `templates-before-1366x768.png` vs màn mới.
2. **Step 2 — Run History (`/history`)**:
   - Chuyển tiêu đề H1 lớn sang `PageHeader`.
   - Chuẩn hóa bộ lọc thời gian và thanh bulk purge vào `CommandBar`.
   - Chuyển bảng kết quả run (nguyên nhân gây cuộn 2181px) sang `DataGrid` với internal scroll.
   - Kiểm tra đo đạc: `scrollHeight <= innerHeight` tại 1366×768.
3. **Step 3 — Batch Definitions (`/batches`)**:
   - Tích hợp `PageHeader` và `CommandBar`.
   - Đưa danh sách bộ đối soát về `DataGrid` compact.
4. **Step 4 — Report Runs (`/report-runs`)**:
   - Đưa lịch sử xuất báo cáo về `DataGrid` compact, chuẩn hóa nút tải file và trạng thái.
5. **Step 5 — Reports Center (`/reports`)**:
   - Loại bỏ cấu trúc Grid + Card lớn gây lãng phí không gian.
   - Chuyển thành Compact Grouped List hoặc AgGrid với phân nhóm nhóm báo cáo.
6. **Step 6 — Chụp ảnh AFTER & Verification**:
   - Dùng Playwright chụp toàn bộ 5 trang tại 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-01/`.
   - Chạy test suite và e2e regression.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Chỉ sửa tối thiểu nếu chặn task.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 5 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_menus.py tests/e2e/test_batch_def.py`
- Đo đạc tự động Playwright: 5 trang đều `document.documentElement.scrollHeight <= innerHeight` ở 1366×768.

## Visual Checks

- Tại 1366×768: Cả 5 trang **KHÔNG có page scroll**.
- Cuộn chỉ xảy ra bên trong `DataGrid`.
- Chiều cao dòng bảng đúng 32px, tiêu đề cột 34px.
- Các nút hành động hiển thị rõ ràng, icon lucide 16px.

## Acceptance Criteria

- [ ] `/templates`, `/history`, `/batches`, `/report-runs`, `/reports` đã chuyển sang pattern LIST.
- [ ] Lưới Card tại `/reports` được thay thế bằng compact list.
- [ ] Không có page scroll trên desktop 1366×768 (`/history` giảm từ 2181px về đúng <= 768px).
- [ ] Toàn bộ callback hiện có tiếp tục hoạt động 100% bình thường.
- [ ] Ảnh chụp AFTER đã lưu tại `artifacts/ui-migration/UI-01/`.
- [ ] `uv run poe lint`, `uv run poe typecheck`, `uv run poe test` đều PASS.

## Files Expected To Change

- `app/ui/pages/templates.py`
- `app/ui/pages/history.py`
- `app/ui/pages/batch_defs.py`
- `app/ui/pages/report_runs.py`
- `app/ui/pages/reports.py`
- `tests/e2e/test_ui_compact_lists.py` (tạo mới test no-scroll)

## Files Must Not Change

- Toàn bộ các file trong `app/services/`
- Các trang khác trong `app/ui/pages/`
- `app/schemas/` và `app/repo/`

## Completion Report Format

```markdown
## UI-01 Completed

Pages migrated to Compact List:
- /templates (DataGrid clientSide)
- /history (DataGrid infinite scroll, page scroll eliminated: 2181px -> 768px)
- /batches (DataGrid clientSide)
- /report-runs (DataGrid clientSide)
- /reports (Replaced Card Grid with Compact Grouped List)

Screenshots:
- artifacts/ui-migration/UI-01/<page>-after-1366x768.png

Tests run:
- lint: PASS
- typecheck: PASS
- tests: PASS
- e2e: PASS

STOP. Chờ người dùng chỉ định task tiếp theo.
```

## STOP Condition

Sau khi hoàn thành và test xong: **STOP**.
Chờ người dùng review và chỉ định task tiếp theo.

