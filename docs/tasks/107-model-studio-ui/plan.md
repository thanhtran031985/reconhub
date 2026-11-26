# Implementation Plan — 107-model-studio-ui

## Bước 1 — Model Center (`/report-models`) & Create / Clone / Impact / Archive
- **File tạo/sửa:**
  - Sửa `app/services/data_source.py`: bổ sung `"report_model"` vào `@requires_menu(..., any_of=True)` của `options_data_sources` để `TEMPLATE_OWNER` (hoặc vai trò chỉ được cấp menu `report_model`) lấy được danh sách Data Source an toàn (không chứa mật khẩu).
  - Sửa `app/ui/layout/shell.py`: bổ sung `build_breadcrumbs` cho `/report-models` và `/report-models/<id>`.
  - Tạo `app/ui/pages/report_models.py` (`MENU_CODE = "report_model"`, `path="/report-models"`): `page_header` (`+ Tạo mô hình`), `command_bar` (tìm kiếm, lọc Data Source, lọc Trạng thái, Làm mới), `dag.AgGrid` (dùng `GRID_DEFAULTS`), 4 trạng thái dữ liệu (`dmc.Skeleton`, `empty_state`, `dmc.Alert` giữ dữ liệu + Thử lại, có dữ liệu), Modal tạo mới (`Code`/`Name`/`Data Source`), Modal Clone, Drawer `Impact Analysis` (read-only), Modal xác nhận Archive.
- **Test viết trước:** `tests/unit/test_page_report_models.py` (gate `/login` & `/forbidden`, 4 trạng thái, filter/search, nút hành động đủ `aria-label`, Modal tạo/Clone/Archive & Drawer Impact).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_page_report_models.py tests/unit/test_ui_foundation.py -v`
- **Rủi ro:** Quyền đọc Data Source cho `TEMPLATE_OWNER`; dùng sai prop DMC 2.x hoặc lẫn hex cứng vi phạm `test_dark_mode73.py`.

## Bước 2 — Khung Model Studio 3 panel, Model Explorer & Drawer `+ Thêm bảng`
- **File tạo/sửa:**
  - Sửa `app/services/semantic_model.py`: bổ sung `@service @requires_menu("report_model") discover_source_objects(ctx, data_source_id, schema=None, q=None, object_type=None)` gọi `catalog.list_tables`, `list_table_constraints` (đếm PK/FK), `estimate_table_rows` nhằm giữ đúng quy tắc callback UI không gọi trực tiếp `app/engine/`.
  - Tạo `app/ui/pages/report_model_studio.py` (`MENU_CODE = "report_model"`, `path_template="/report-models/<model_id>"`): bố cục Fluent Compact 3 panel không cuộn cả trang (`flex: 1, minHeight: 0`), `page_header` (tên model, chip trạng thái, nút `Kiểm tra model`, `Lưu nháp`, `Phát hành`, menu `...`), `Status Bar` đáy, `Model Explorer` trái (ô tìm bảng/cột tự expand & highlight, nhóm `Fact` / `Dimension` / `Bridge` / `Unclassified` + `Quan hệ (N)`), Drawer `+ Thêm bảng` (lọc Schema, `TABLE`/`VIEW`, search, ước lượng dòng, PK/FK, khóa chọn bảng đã thêm vào model).
  - Sửa `app/ui/assets/custom.css`: thêm class `.rm-*` theo 100% CSS token từ `app/ui/assets/tokens.css` (kèm responsive `<900px` xếp dọc chỉ đọc).
- **Test viết trước:** `tests/unit/test_page_model_studio.py` (layout 3 panel, search explorer expand/highlight, picker `+ Thêm bảng` lọc và loại trừ bảng đã có, gate phân quyền).
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_page_model_studio.py tests/unit/test_dark_mode73.py -k "not undefined" -v`
- **Rủi ro:** Bọc thêm wrapper `flex: 1` bên trong block parent gây hỏng `clientHeight` khi cuộn canvas (áp đúng cấu trúc 1 container scroller ngoài như `data_model.py`).

## Bước 3 — Model Canvas HTML+SVG & Clientside JS (`semantic_model_canvas.js`)
- **File tạo/sửa:**
  - Tạo `app/ui/assets/semantic_model_canvas.js`: Pointer Events thuần (không thêm dependency ngoài) dùng `window.dash_clientside.set_props` để kéo thả Entity Card 60fps, kéo dây từ anchor cột nguồn sang cột đích (kèm nút `+ Tạo quan hệ` bàn phím), Zoom In/Out/wheel, Fit, pan nền trống, click-outside bỏ chọn, double-click center & zoom.
  - Cập nhật `app/ui/pages/report_model_studio.py`: helper thuần tính Star Schema Auto Layout deterministic (kèm Undo vị trí), bounding box `Fit`, render Entity Card (Role badge, PK/FK/Hidden/Measure markers, datatype mono) + đường nối SVG vừa khít `canvas_w × canvas_h` kèm nhãn `*:1` / `1:1`.
- **Test viết trước:** mở rộng `tests/unit/test_page_model_studio.py` kiểm tra `auto_layout_star_schema` deterministic, `compute_canvas_fit`, và sinh connector SVG từ metadata model.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_page_model_studio.py -v`
- **Rủi ro:** Sai lệch tọa độ anchor khi Canvas đang zoom `scale(z)` — chia delta `clientX/clientY` theo zoom hiện tại.

## Bước 4 — Panel Properties (Table/Grain, Relationship, Field/RLS V1, Measure Studio)
- **File sửa:**
  - `app/ui/pages/report_model_studio.py`: panel Properties bên phải chuyển ngữ cảnh theo selection (Table/Grain, Relationship + Validation Tầng 1/2 + Modal xác nhận xóa, Field + `allowed_aggregations_for` + Virtual Date Hierarchy + RLS metadata V1, Measure Studio Simple + Structured AST Calculated Measure).
- **Test viết trước:** mở rộng `tests/unit/test_page_model_studio.py` kiểm tra render/mapping từng tab Properties, rule khóa `SUM` theo datatype, và build/submit AST Measure + RLS metadata.
- **Lệnh kiểm tra:** `uv run pytest tests/unit/test_page_model_studio.py -v`
- **Rủi ro:** Số lượng callback/component ID lớn trong cùng page — đặt ID thống nhất `<page>-<block>-<name>`.

## Bước 5 — Validation Navigation, Save Concurrency, Publish Modal & E2E Visual Validation
- **File tạo/sửa:**
  - Hoàn thiện `app/ui/pages/report_model_studio.py`: Drawer/Panel `Kiểm tra model` (`aria-live="polite"`) click issue focus đúng đối tượng trên Canvas; xử lý `STALE_DATA` khi `Lưu nháp`; Modal `Phát hành` (Diff + Impact Analysis + Change Note); chế độ chỉ đọc trên `<900px`.
  - Rà soát `tests/unit/test_perm_registry.py` (`test_every_page_declares_menu_code`).
- **Test viết trước:** `tests/e2e/test_model_studio_e2e.py` (tạo model -> thêm Fact & Dim -> kéo/tạo quan hệ -> đặt Grain & Measure -> Validate & Publish; kiểm tra `1366×768` & `1440×900` Light/Dark mode `scrollHeight <= innerHeight`, `390×844` không tràn ngang, zero lỗi console, chụp ảnh kiểm chứng).
- **Lệnh kiểm tra:** `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run pytest tests/unit/test_page_report_models.py tests/unit/test_page_model_studio.py tests/unit/test_perm_registry.py -v`, `uv run pytest tests/e2e/test_model_studio_e2e.py -v`.

## Chỗ tự suy ra & Package ngoài
- Route `/report-models/<model_id>` là đường dẫn chính; `/report-models/<model_id>/edit` (nếu mở) chuyển hướng về `/report-models/<model_id>` để không trùng 2 page Dash.
- Không cài thêm package ngoài (`interactjs`); dùng vanilla Pointer Events JS thuần.
- Nút mở Report Studio trên header Model Studio để disabled kèm tooltip tới khi Task 109 hoàn thành.
