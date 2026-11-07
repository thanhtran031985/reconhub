# Tiến độ TASK UI-00B — Fluent Foundation

| Bước | Nội dung | Trạng thái |
|---|---|:---:|
| Preflight | Kiểm tra lint, typecheck, test baseline | ✅ |
| Step 1 | Foundation Data Models & Constants (`grid_defaults.py`) | ✅ |
| Step 2 | DataGrid Wrapper (`data_grid.py`) | ✅ |
| Step 3 | PageHeader, CommandBar, FilterBar | ✅ |
| Step 4 | MasterDetailLayout & WizardShell | ✅ |
| Step 5 | 4-State Helpers (`skeleton_grid.py`, `error_state.py`) | ✅ |
| Step 6 | AppShell Fluent Refactoring (`shell.py`) | ✅ |
| Step 7 | Foundation Test Suite & Verification (`test_ui_foundation.py`) | ✅ |

## Nhật ký thực hiện

### 2026-11-07 — UI-00B Hoàn thành
- **Preflight**:
  - Tạo nhánh `feat/UI-00B`.
  - Kiểm tra lint baseline: 3 lỗi pre-existing ở `test_batch_def_service.py`.
  - Kiểm tra typecheck baseline: 21 lỗi pre-existing ở 5 files cũ.
- **Step 1 — Foundation Data Models & Constants**:
  - Tạo `app/ui/components/grid_defaults.py` với `ROW_HEIGHT=32`, `HEADER_HEIGHT=34`, `GRID_DEFAULTS`, `DIFF_CELL_CLASS_RULES`.
- **Step 2 — DataGrid Wrapper**:
  - Tạo `app/ui/components/data_grid.py` bọc `dag.AgGrid` tự động áp dụng `GRID_DEFAULTS`, theme Quartz Fluent `ag-theme-quartz-auto-dark`, hỗ trợ flex 1 và 2 chế độ `clientSide` & `infinite`.
- **Step 3 — PageHeader, CommandBar, FilterBar**:
  - Tạo `page_header.py`: Chuẩn 1 dòng Title 18px, subtitle 12px dimmed, breadcrumbs và nút hành động căn phải.
  - Tạo `command_bar.py`: Input tìm kiếm 28px icon lucide:search, divider và nhóm nút hành động.
  - Tạo `filter_bar.py`: Paper bg surface-2 với nhóm bộ lọc compact.
- **Step 4 — MasterDetailLayout & WizardShell**:
  - Tạo `master_detail.py`: Layout 2 cột responsive Master flex 1 + Detail 380px viền trái, cuộn độc lập.
  - Tạo `wizard_shell.py`: Stepper 1 dòng compact 34px, body flex 1 cuộn riêng, footer Back/Next cố định ở chân.
- **Step 5 — 4-State Helpers**:
  - Tạo `skeleton_grid.py`: `skeleton_grid(rows=8, cols=4)` và `skeleton_panel()`.
  - Tạo `error_state.py`: Chuẩn hóa 4-state ErrorState có nút "Thử lại", hỗ trợ cả chế độ full paper và banner_only alert.
- **Step 6 — AppShell Fluent Refactoring**:
  - Cập nhật `app/ui/layout/shell.py`:
    - Header hạ xuống 44px (`header={"height": 44}`).
    - Navbar chuẩn 200px (mở) và 48px (thu gọn rail), thêm vạch chỉ báo active 3px màu primary bên trái.
    - Bọc `dash.page_container` trong container `minHeight: 0`, `overflow: auto`, `flex: 1` để triệt tiêu scroll toàn trang desktop.
    - Cập nhật toàn bộ viền sang token `--line` (`var(--line)`).
- **Step 7 — Foundation Test Suite & Verification**:
  - Viết `tests/unit/test_ui_foundation.py` với 11 test cases bao phủ toàn bộ foundation components, backward compatibility, and shell refactor.
  - Kết quả kiểm tra: 11/11 tests PASS.
  - Ruff lint & mypy typecheck trên các file mới/sửa: PASS 100%.
