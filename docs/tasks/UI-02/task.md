# TASK UI-02 — Reports & Analytics

## Status

TODO

## Dependencies

- UI-00B (Fluent Foundation)

## Objective

Chuyển đổi 5 màn hình báo cáo và kết quả (`/` Dashboard, `/runs/<id>`, `/batch-runs/<id>/result`, `/issues`, `/reports/<id>`) sang pattern **REPORT** chuẩn Fluent Compact: `PageHeader` + `FilterBar` (compact 1 hàng) + Vùng kết quả / `DataGrid` (`flex: 1`, internal scroll).
Triệt tiêu hoàn toàn hiện tượng page-scroll desktop (Dashboard hiện cuộn 1065px, Run Result cuộn 2644px), giữ nguyên quy chuẩn highlight ô lệch `rh-diff`, định dạng tiền tệ `24.114.547.250` và metadata-driven columnDefs của Report Viewer.

> [!IMPORTANT]
> **EXECUTION POLICY**:
> AI chỉ được thực hiện task này khi người dùng chỉ định chính xác: `"Làm UI-02"`.
> Sau khi hoàn thành task này: **STOP**. Không tự động bắt đầu task tiếp theo.

## Pages

| Route | Page Module | Task Gốc Sinh Ra | Spec Liên Quan | Màn Thiết Kế Gốc |
|---|---|---|---|---|
| `/` | `app/ui/pages/dashboard.py` | [12-export-history](../12-export-history/task.md) & [15-dashboard-compare](../15-dashboard-compare/task.md) | [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen01-Dashboard` |
| `/runs/<id>` | `app/ui/pages/run_result.py` | [11-run-result-ui](../11-run-result-ui/task.md) | [04_recon_engine.md](../../specs/04_recon_engine.md), [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen06-RunResult` |
| `/batch-runs/<id>/result` | `app/ui/pages/batch_run_result.py` | [18-batch-run](../18-batch-run/task.md) | [10_batch_run.md](../../specs/10_batch_run.md) | `designs/components/Screen13-BatchRun` |
| `/issues` | `app/ui/pages/issues.py` | [14-issue-handling](../14-issue-handling/task.md) | [05_services_pages.md](../../specs/05_services_pages.md) | `designs/components/Screen09-Issues` |
| `/reports/<id>` | `app/ui/pages/report_viewer.py` | [27-reporting-ui](../27-reporting-ui/task.md) | [05_services_pages.md](../../specs/05_services_pages.md), task 23-25 | `designs/components/Screen16-DynamicReporting` |

## Target Pattern

**REPORT**:
- Vùng 1: `PageHeader` (Title order=4 + breadcrumb/subtitle + nút xuất file/hành động chính)
- Vùng 2: `FilterBar` (Một hàng co giãn tự động bằng `dmc.SimpleGrid` hoặc group gọn gàng)
- Vùng 3: Result Area (KPI cards compact hoặc `DataGrid` chiếm trọn chiều cao còn lại `flex: 1`)

## Read First

1. `AGENTS.md`
2. `.agents/rules/ui-dash.md`
3. `docs/ui-migration.md` (mục 3, 4, 6, 8 cho UI-02)
4. Yêu cầu & nghiệp vụ gốc:
   - [11-run-result-ui/task.md](../11-run-result-ui/task.md) (Run result, rh-diff highlight, drawer xem chi tiết dòng)
   - [12-export-history/task.md](../12-export-history/task.md) & [15-dashboard-compare/task.md](../15-dashboard-compare/task.md) (Dashboard KPI & so sánh run)
   - [14-issue-handling/task.md](../14-issue-handling/task.md) (Xử lý chênh lệch & lý do)
   - [18-batch-run/task.md](../18-batch-run/task.md) (Batch run result)
   - [27-reporting-ui/task.md](../27-reporting-ui/task.md) (Metadata-driven Report Viewer)
5. Baseline screenshots: `artifacts/ui-inventory/dashboard-before-1366x768.png`, `run-result-before-1366x768.png`, `report-viewer-before-1366x768.png`
6. Foundation components từ UI-00B (`DataGrid`, `PageHeader`, `FilterBar`, `GRID_DEFAULTS`)

## Allowed Scope

- `/` (Dashboard):
  - Co gọn 4 thẻ KPI (`kpi_card`) về padding compact `p="sm"`, icon nét mảnh 16px.
  - Gom 2 bảng tổng hợp (Tỷ lệ lệch, Run gần nhất) về `dmc.ScrollArea` hoặc `DataGrid` nhỏ gọn để toàn bộ Dashboard hiển thị trọn vẹn trong màn hình 1366×768 (không cuộn 1065px).
- `/runs/<id>`:
  - Thay thế 2 bảng `dmc.Table` cuộn trôi trang (2644px) bằng `DataGrid` (infinite row model).
  - Áp dụng class `rh-diff` cho các ô số liệu chênh lệch giữa Excel và DB.
  - Tích hợp thanh lọc trạng thái (Khớp, Lệch, Thiếu DB, Thiếu Excel...) vào `FilterBar` compact 1 hàng.
  - Giữ nguyên Drawer xem chi tiết dòng (`run-res-row-drawer`).
- `/batch-runs/<id>/result`:
  - Chuẩn hóa KPI header và bảng tiến độ chạy từng template con vào `DataGrid`.
- `/issues`:
  - Thu gọn thanh lọc trạng thái và loại lý do chênh lệch thành 1 hàng `FilterBar`.
  - Chuyển bảng chênh lệch sang `DataGrid` với infinite model.
- `/reports/<id>`:
  - Giữ nguyên cấu trúc Tabs (Tham số / Kết quả).
  - Tối ưu form tham số động (`render_param_form`) co giãn compact 12 cột.
  - Chuyển `render_result_table` sang `DataGrid` metadata-driven (tự động nhận `columnDefs` từ metadata service).

## Forbidden Scope

- **KHÔNG thay đổi logic query, pagination, hay business service** trong `app/services/run.py`, `app/services/report_exec.py`, `app/services/issue.py`.
- **KHÔNG thay đổi định dạng số tiền** (`24.114.547.250`) hoặc thời gian (`dd/MM/yyyy HH:mm:ss`).
- **KHÔNG đổi component IDs** quan trọng trong callback (như `run-res-grid`, `run-res-filter-status`, `report-param-container`, `report-run-btn`...).
- **KHÔNG sửa các trang quản trị** hay wizard trong task này.

## Preserve Contracts

- Bảng kết quả run phải highlight chính xác ô lệch theo CSS class `rh-diff`.
- Report Viewer phải render đúng các loại tham số động: DATE, DATETIME, TEXT, NUMBER, LOV_SINGLE, LOV_MULTI.
- Các nút xuất file Excel/CSV/ZIP phải tiếp tục kích hoạt download từ Flask route an toàn.

## Preflight

1. `git status --short`
2. `git branch --show-current`
3. Xem baseline screenshots tại `artifacts/ui-inventory/` của 5 màn hình.
4. Chạy `uv run poe test-engine` đảm bảo logic so sánh và tính toán dữ liệu đang xanh.

## Implementation Steps

1. **Step 1 — Dashboard Compact (`/`)**:
   - Tối ưu spacing: thay H1 bằng `PageHeader`.
   - Thu nhỏ kích thước 4 KPI Cards, căn chỉnh lại lưới bảng tổng hợp.
   - Kiểm tra đo đạc: `dashboard` đạt `scrollHeight <= innerHeight` tại 1366×768.
2. **Step 2 — Run Result View (`/runs/<id>`)**:
   - Chuyển 2 bảng kết quả sang `DataGrid` infinite model.
   - Giữ nguyên logic `cellClassRules` gán class `rh-diff`.
   - Đảm bảo bảng cuộn nội bộ, trang không cuộn dọc (triệt tiêu cuộn 2644px).
   - Kiểm tra hoạt động của Drawer chi tiết dòng.
3. **Step 3 — Batch Run Result (`/batch-runs/<id>/result`)**:
   - Đưa bảng tiến độ chạy của bộ đối soát về `DataGrid` compact.
4. **Step 4 — Issues Resolution (`/issues`)**:
   - Tích hợp bộ lọc vào `FilterBar`.
   - Chuyển bảng xử lý chênh lệch sang `DataGrid`.
   - Kiểm tra callback cập nhật lý do chênh lệch.
5. **Step 5 — Metadata-driven Report Viewer (`/reports/<id>`)**:
   - Tối ưu form tham số compact.
   - Kết nối `render_result_table` vào `DataGrid` nhận `columnDefs` từ service report.
6. **Step 6 — Chụp ảnh AFTER & Verification**:
   - Chụp 5 trang ở 1366×768, 1440×900, 390×844 lưu vào `artifacts/ui-migration/UI-02/`.
   - Chạy test suite.

## Bug Safety Rules

Mọi lỗi gặp phải phân loại:
- `A. PRE-EXISTING UNRELATED`: Ghi nhận, không sửa.
- `B. PRE-EXISTING BLOCKER`: Sửa tối thiểu nếu chặn hiển thị dữ liệu.
- `C. INTRODUCED BY CURRENT TASK`: Bắt buộc sửa và kèm regression test.
- `D. DISCOVERED RELATED BUG`: Chỉ sửa nếu thuộc phạm vi 5 trang trên và không đổi contract.
- `E. UNKNOWN`: DỪNG và hỏi người dùng.

## Tests

- Chạy `uv run poe lint`
- Chạy `uv run poe typecheck`
- Chạy `uv run poe test`
- Chạy `pytest tests/e2e/test_e2e_screens.py`
- Đo đạc tự động: Cả 5 trang đều `document.documentElement.scrollHeight <= innerHeight` ở 1366×768.

## Visual Checks

- `/` và `/runs/<id>` hoàn toàn không có page scroll trên desktop 1366×768.
- Các ô lệch giá trị trong run result có nền đỏ nhạt (`crit-soft`), chữ đỏ đậm (`crit`) rõ ràng.
- Các số liệu tiền căn phải, font tabular-nums monospace.
- Filter bar co giãn mượt mà khi thay đổi kích thước cửa sổ.

## Acceptance Criteria

- [ ] `/`, `/runs/<id>`, `/batch-runs/<id>/result`, `/issues`, `/reports/<id>` chuyển thành công sang pattern REPORT.
- [ ] Không có page scroll trên desktop 1366×768 (`/runs/<id>` giảm từ 2644px về <= 768px; Dashboard giảm từ 1065px về <= 768px).
- [ ] Quy chuẩn `rh-diff` và format số tiền được bảo toàn 100%.
- [ ] Report Viewer giữ nguyên khả năng hiển thị metadata-driven columns động.
- [ ] Ảnh AFTER đã lưu tại `artifacts/ui-migration/UI-02/`.
- [ ] Tất cả kiểm tra lint, typecheck, unit test và e2e đều PASS.

## Files Expected To Change

- `app/ui/pages/dashboard.py`
- `app/ui/pages/run_result.py`
- `app/ui/pages/batch_run_result.py`
- `app/ui/pages/issues.py`
- `app/ui/pages/report_viewer.py`
- `app/ui/components/report_widgets.py`

## Files Must Not Change

- `app/services/run.py`
- `app/services/report_exec.py`
- `app/services/compare.py`
- `app/engine/**`

## Completion Report Format

```markdown
## UI-02 Completed

Pages migrated to Report Pattern:
- / (Dashboard: compact KPI cards, no page scroll: 1065px -> 768px)
- /runs/<id> (Run result: DataGrid infinite, rh-diff preserved, no page scroll: 2644px -> 768px)
- /batch-runs/<id>/result (Batch run progress in DataGrid)
- /issues (Issues resolution in DataGrid)
- /reports/<id> (Report viewer: metadata-driven DataGrid preserved)

Screenshots:
- artifacts/ui-migration/UI-02/<page>-after-1366x768.png

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

