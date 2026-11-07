# Implementation Plan — TASK UI-00B: Fluent Foundation

## 1. Mục tiêu
Xây dựng bộ khung giao diện Fluent Foundation và các component layout dùng chung chuẩn hóa (`AppShell`, `PageHeader`, `CommandBar`, `FilterBar`, `DataGrid`, `MasterDetailLayout`, `WizardShell`, `SkeletonGrid`, `ErrorState`). Chuẩn bị hạ tầng component cho UI-01 đến UI-07 mà không làm xáo trộn callback hay business logic của các trang hiện hữu.

## 2. Các bước triển khai

### Step 1 — Foundation Data Models & Constants (`app/ui/components/grid_defaults.py`)
- Định nghĩa:
  - `ROW_HEIGHT = 32` (chuẩn Compact)
  - `HEADER_HEIGHT = 34`
  - `GRID_DEFAULTS`: `defaultColDef` (sortable, filter, resizable), `suppressCellFocus`, `animateRows=False`, `domLayout="normal"`, `rowHeight=32`, `headerHeight=34`.
  - CSS rule `DIFF_CELL_CLASS_RULES`: highlight các ô chênh lệch số liệu (`rh-diff`).
  - Hỗ trợ mapping theme: `ag-theme-quartz-auto-dark` kết hợp CSS tokens.

### Step 2 — DataGrid Wrapper (`app/ui/components/data_grid.py`)
- Tạo hàm `data_grid(id, columnDefs, rowData=None, rowModelType="clientSide", height="100%", ...)`:
  - Bọc component `dag.AgGrid`.
  - Tự động tích hợp `GRID_DEFAULTS`.
  - Đóng gói container flex `dmc.Box(..., style={"height": height, "minHeight": 0, "flex": 1, "width": "100%"})`.
  - Tương thích cả 2 chế độ `clientSide` và `infinite`.

### Step 3 — PageHeader, CommandBar, FilterBar
- `app/ui/components/page_header.py`:
  - Hàm `page_header(title, subtitle=None, actions=None, breadcrumbs=None)`:
  - Render 1 dòng (Title order=4, size 18px, fw=600 + text dimmed 12px + nút hành động căn phải).
  - Breadcrumbs tinh gọn phía trên hoặc cùng dòng theo chuẩn preview-fluent.
- `app/ui/components/command_bar.py`:
  - Hàm `command_bar(search_id=None, search_placeholder="Tìm kiếm...", filters=None, actions=None, id=None)`:
  - Render `dmc.Paper(..., withBorder=True)` chiều cao gọn gàng, input tìm kiếm 28px/30px icon `lucide:search`, ngăn cách `dmc.Divider(orientation="vertical")`.
- `app/ui/components/filter_bar.py`:
  - Hàm `filter_bar(children, actions=None, id=None)`:
  - Container co giãn tự động cho các bộ lọc ngày giờ, trạng thái.

### Step 4 — MasterDetailLayout & WizardShell
- `app/ui/components/master_detail.py`:
  - Hàm `master_detail_layout(master_content, detail_content, detail_width=380, id=None, ...)`:
  - Layout chia 2 cột: Master (`flex: 1`, `minWidth: 0`), Detail cố định `width=detail_width` (mặc định 380px) có viền trái.
  - Responsive: Trên desktop (≥900px) nằm ngang, mobile (<900px) tự động stack dọc.
- `app/ui/components/wizard_shell.py`:
  - Hàm `wizard_shell(steps, current_step, content, footer_actions, id=None, ...)`:
  - Header Stepper compact 1 hàng ở đỉnh (34px), body chiếm `flex: 1` cuộn độc lập, footer Back/Next cố định ở chân trang (bg surface-2).

### Step 5 — 4-State Helpers
- `app/ui/components/skeleton_grid.py`:
  - Hàm `skeleton_grid(rows=8, cols=4)` tạo khung loading giả lập bảng AgGrid (hàng cao 32px).
  - Hàm `skeleton_panel()` tạo khung loading cho detail panel.
- `app/ui/components/error_state.py`:
  - Hoàn thiện `error_state(title=None, message=None, retry_id=None, action=None, ...)`:
  - Hiển thị Alert hoặc EmptyState lỗi kèm nút "Thử lại", cho phép hiển thị đè hoặc dưới dạng banner giữ nguyên dữ liệu cũ.

### Step 6 — AppShell Fluent Refactoring (`app/ui/layout/shell.py`)
- Cập nhật header:
  - Chiều cao 44px (`header={"height": 44}`).
  - Logo và topbar align chiều cao 44px.
  - Border color sử dụng token `--line` (`var(--line)`).
- Cập nhật navbar:
  - Chiều rộng 200px khi mở, 48px khi thu gọn rail.
  - Thêm vạch chỉ báo active 3px màu primary bên trái (token `--nav-accent: #0F6CBD`).
  - Cập nhật callback toggle và sync sidebar width.
- Bọc vùng `dash.page_container`:
  - `dmc.Box(dash.page_container, h="100%", style={"minHeight": 0, "overflow": "hidden", "display": "flex", "flexDirection": "column", "flex": 1})`.
  - Đảm bảo `AppShellMain` không phát sinh page-scroll toàn trang ở màn hình desktop (1366×768 / 1440×900).

### Step 7 — Foundation Test Suite & Verification
- Viết `tests/unit/test_ui_foundation.py`:
  - Kiểm tra import tất cả component mới từ `app.ui.components`.
  - Kiểm tra props và cấu trúc trả về của `data_grid`, `page_header`, `command_bar`, `filter_bar`, `master_detail_layout`, `wizard_shell`, `skeleton_grid`, `error_state`.
  - Kiểm tra cấu hình `GRID_DEFAULTS` (rowHeight=32, headerHeight=34).
  - Kiểm tra layout `shell.py` (header height 44px, navbar width 200/48px).
- Chạy verification:
  - `pytest tests/unit/test_ui_foundation.py`
  - `uv run poe lint`
  - `uv run poe typecheck`
  - `uv run poe tasks-dashboard`

## 3. Rủi ro & Giải pháp
- **Rủi ro**: Can thiệp vào `shell.py` làm ảnh hưởng callback điều hướng hoặc kiểm tra quyền `PERM_REVISION`.
  - **Giải pháp**: Giữ nguyên 100% ID các component (`app-sidebar-toggle-btn`, `app-color-scheme-toggle`, `app-location`, `app-perm-revision`, `app-perm-revision-check`), chỉ điều chỉnh giá trị cấu hình layout pixel (56px -> 44px, 232/60px -> 200/48px) và style container.
- **Rủi ro**: Trang hiện hữu bị vỡ layout khi bọc `dash.page_container` trong container `overflow: hidden`.
  - **Giải pháp**: Vùng container có `minHeight: 0`, `flex: 1`, các trang hiện hữu chưa đổi vẫn cuộn bên trong vùng `dash.page_container` bình thường bằng cách đặt `overflowY: "auto"` cho container bao bọc.

