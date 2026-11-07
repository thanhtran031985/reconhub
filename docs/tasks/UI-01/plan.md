# Implementation Plan — TASK UI-01: Compact Lists

## 1. Mục tiêu
Chuyển đổi 5 màn hình danh sách:
- `/templates` (`app/ui/pages/templates.py`)
- `/history` (`app/ui/pages/history.py`)
- `/batches` (`app/ui/pages/batch_defs.py`)
- `/report-runs` (`app/ui/pages/report_runs.py`)
- `/reports` (`app/ui/pages/reports.py`)

sang pattern **LIST** chuẩn Fluent Compact (`PageHeader` + `CommandBar` + Container bảng cuộn nội bộ `flex: 1`).
Triệt tiêu hoàn toàn page scroll ở màn hình desktop 1366×768 (đặc biệt `/history` hiện cuộn 2181px), loại bỏ lưới Card lớn tại `/reports` đưa về Compact Grouped Table.

## 2. Các bước triển khai

### Step 1 — Templates List (`app/ui/pages/templates.py`)
- Thay thế tiêu đề và các nút rời rạc bằng `page_header(title="Templates", subtitle="Danh sách cấu hình đối soát Excel và Oracle", actions=[tmpl-create-btn, tmpl-import-btn])`.
- Đưa ô tìm kiếm `tmpl-filter-search`, bộ lọc trạng thái `tmpl-filter-status` vào `command_bar()`.
- Chuẩn hóa container bảng `tmpl-table-container` thành khung flex `height: 100%`, `minHeight: 0`, cuộn nội bộ với header bảng sticky 34px, hàng compact 34px.
- Giữ nguyên 100% component ID và pattern-matching callbacks (`tmpl-action-clone`, `tmpl-action-export`, `tmpl-action-archive`, `tmpl-action-delete`, `tmpl-action-sample`).

### Step 2 — Run History (`app/ui/pages/history.py`)
- Thay thế H1 lớn bằng `page_header(title="Lịch sử đối soát", subtitle="Danh sách các lượt chạy đối soát và kết quả")`.
- Đưa các bộ lọc ngày giờ, template, trạng thái và bulk actions vào `command_bar()`.
- Đóng gói bảng run history vào container cuộn nội bộ có chiều cao cố định flex 1 (`minHeight: 0`, `overflow: auto`), triệt tiêu hoàn toàn lỗi cuộn trang 2181px.
- Giữ nguyên toàn bộ logic checkbox `history-run-cb`, `history-select-all-cb`, `history-bulk-purge-modal` và nút tải file kết quả.

### Step 3 — Batch Definitions (`app/ui/pages/batch_defs.py`)
- Thay thế tiêu đề bằng `page_header(title="Bộ đối soát", subtitle="Quản lý tập hợp các template chạy đồng thời", actions=[bdef-create-btn])`.
- Đưa tìm kiếm `bdef-filter-search` và lọc trạng thái `bdef-filter-status` vào `command_bar()`.
- Chuyển bảng sang Compact Table có header sticky và hàng 34px, bọc trong container `flex: 1`.

### Step 4 — Report Runs (`app/ui/pages/report_runs.py`)
- Tích hợp `page_header(title="Lịch sử xuất báo cáo", subtitle="Theo dõi tiến độ và tải kết quả báo cáo động")`.
- Tích hợp `command_bar` cho bộ lọc trạng thái, tìm kiếm và làm mới.
- Đưa bảng sang Compact Table gọn gàng với chip trạng thái và nút tải file.

### Step 5 — Reports Center (`app/ui/pages/reports.py`)
- Loại bỏ lưới thẻ Card (`dmc.SimpleGrid` + `report-card`) chiếm diện tích lớn.
- Chuyển thành Compact Grouped Table (`rlist`) theo mẫu `preview-fluent.html`:
  - Dòng tiêu đề phân nhóm (28px, chữ hoa `c="dimmed"`).
  - Các dòng báo cáo (36px, mã mono, tên, mô tả ngắn, tag danh mục, nút mở).
  - Giữ nguyên chức năng toggle yêu thích (`report-fav-btn`) và tìm kiếm `reports-search-input`.

### Step 6 — Regression Tests & Verification
- Viết test Playwright / unit test kiểm tra layout không cuộn toàn trang desktop 1366×768 (`document.documentElement.scrollHeight <= innerHeight`).
- Chạy kiểm tra toàn bộ suite test và lint:
  - `uv run poe lint`
  - `uv run poe typecheck`
  - `uv run pytest tests/unit/test_ui_foundation.py tests/test_ui_auth.py`
  - `uv run poe tasks-dashboard`

## 3. Rủi ro & Giải pháp
- **Rủi ro**: Làm gián đoạn các callback pattern-matching (như `tmpl-action-clone`, `history-run-cb`).
  - **Giải pháp**: Không đổi cấu trúc dictionary ID của bất kỳ button/checkbox nào. Mọi action icon/button đều được gán đúng ID và index cũ.
- **Rủi ro**: Bảng bị mất thanh cuộn hoặc bị ẩn nội dung trên màn hình nhỏ.
  - **Giải pháp**: Sử dụng flex column với `minHeight: 0`, `overflow: "auto"`, đảm bảo thanh cuộn luôn xuất hiện bên trong container bảng khi dữ liệu dài.
