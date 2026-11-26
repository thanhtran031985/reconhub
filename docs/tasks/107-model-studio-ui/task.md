# 107-model-studio-ui — Model Center & Semantic Model Studio UI (REPORT-STUDIO-01B)

- Ngày tạo: 2026-11-26
- Giai đoạn: GĐ3
- Phụ thuộc: 106-semantic-model-core, 31-data-model-explorer, 104-layout-cache-perf
- Nhánh git: feat/107-model-studio-ui

## Mục tiêu
1. Xây dựng màn **Mô hình báo cáo / Model Center** (`/report-models`) cho phép tìm kiếm, lọc, tạo mới, mở, nhân bản (Clone), phân tích ảnh hưởng (Impact Analysis) và lưu trữ (Archive) Semantic Model.
2. Xây dựng màn **Model Studio** (`/report-models/<model_id>` và `/report-models/<model_id>/edit`) theo bố cục 3 panel Fluent Compact (Model Explorer | Model Canvas | Properties) + Status Bar:
   - Thêm bảng/view từ Data Source Oracle/SQLite vào mô hình (tự nhận diện PK/FK gợi ý).
   - Kéo thả sắp xếp bảng trên canvas, zoom/pan/fit/auto-layout (Star Schema), kéo cột-nối-cột để tạo quan hệ (kèm nút form `+ Tạo quan hệ` hỗ trợ bàn phím).
   - Chỉnh sửa Table Properties (Role, Grain bắt buộc cho Fact), Field Properties (Visibility, Aggregation rules, Format, Virtual Date Hierarchy, RLS metadata V1), Relationship Properties (Cardinality, Join Type, Kiểm tra quan hệ 2 tầng) và Measure Studio (Simple + AST Calculated).
   - Thực hiện Validation mô hình có điều hướng lỗi trực tiếp, Lưu nháp chống ghi đè (Optimistic Concurrency) và Publish phiên bản bất biến kèm diff + Change Note.

## Phạm vi
- Pages UI: `app/ui/pages/report_models.py` (`/report-models`), `app/ui/pages/report_model_studio.py` (`/report-models/<model_id>`).
- Assets JS/CSS: `app/ui/assets/semantic_model_canvas.js` (drag entity, drag-to-connect column, pan/zoom/fit/click-outside qua `set_props`), cập nhật `app/ui/assets/custom.css` dùng CSS tokens (`tokens.css`).
- Layout / Breadcrumbs: cập nhật `build_breadcrumbs` trong `app/ui/layout/shell.py` cho `/report-models*`.
- Tests: `tests/unit/test_page_report_models.py`, `tests/unit/test_page_model_studio.py`, `tests/e2e/test_model_studio_e2e.py`.

## Ngoài phạm vi
- Không viết nghiệp vụ SQL/DB trực tiếp trong page Dash (mọi thao tác gọi service ở `app/services/semantic_model*.py`).
- Không xây dựng Report Studio UI hoặc Query Planner (nằm ở task `108` và `109`).
- Không hỗ trợ chỉnh sửa/kéo thả sơ đồ phức tạp trên màn hình Mobile (`390×844`): mobile dùng chế độ xem danh sách / thông báo mở trên desktop để chỉnh sửa.

## Thiết kế
- `designs/components/AppShell`
- `designs/components/DataGrid`
- `designs/components/Drawer`
- `designs/components/EmptyState`
- `designs/components/Button`
- `designs/components/StatusChip`
- `designs/components/Alert`
- `designs/reference/preview-fluent.html`, `.agents/rules/ui-dash.md`, `designs/tokens.json`
- Wireframe tham chiếu: `01 MODEL STUDIO` (điều chỉnh dùng `dmc.AppShell` sidebar dọc thay top-tabbar, bổ sung nút `Phát hành` tách riêng trên header).

## Spec liên quan
- `docs/tasks/106-semantic-model-core/task.md`
- `app/ui/pages/data_model.py` & `app/ui/assets/data_model_canvas.js` (mẫu ER Canvas, scroll/zoom/fit/highlight)
- `app/ui/pages/mail_template_studio.py` (mẫu Studio 3 panel Fluent Compact)

## Quyết định kiến trúc
1. **Tuân thủ `dmc.AppShell`:** Không dùng thanh tab ngang thay thế shell như ảnh wireframe; điều hướng qua sidebar nhóm `Cấu hình → Mô hình báo cáo` (`/report-models`), kèm link chuyển ngữ cảnh trong `page_header` (nút mở Report Studio khi task `109` có mặt).
2. **Canvas 60fps không reload server khi kéo chuột:** Dùng **Entity Cards HTML + lớp SVG nối dây vừa đúng kích thước `canvas_w × canvas_h` (không dùng full-page SVG gây page-scroll)** kết hợp JS clientside (`app/ui/assets/semantic_model_canvas.js` + `window.dash_clientside.set_props`). Khi người dùng kéo thả card hoặc kéo dây từ cột nguồn sang cột đích, JS cập nhật DOM tức thì rồi mới đẩy kết quả cuối về `dcc.Store`. Có thể đánh giá nạp thêm thư viện JS nhẹ (vd `interactjs`) vào `app/ui/assets/lazy/` nếu cần tối ưu cảm giác kéo thả đa trình duyệt (ghi rõ vào `decisions.md`).
3. **Fallback Accessibility cho Drag-to-Connect:** Ngoài kéo cột-sang-cột bằng chuột, luôn có nút `+ Tạo quan hệ` mở form nhanh trong Explorer/Toolbar để người dùng bàn phím hoặc bảng nhiều cột thao tác chính xác.
4. **4 trạng thái đầy đủ:** Áp dụng `dmc.Skeleton` (Loading), `empty_state` (Empty Model / Empty Search), `dmc.Alert` giữ dữ liệu cũ + nút `Thử lại` (Error metadata), và Data.
5. **Quyết định Mobile (`390×844`):** Model Center (`/report-models`) hiển thị đầy đủ trên mobile không tràn ngang; tại Model Studio (`/report-models/<id>`), nếu viewport `< 900px` hiển thị panel thông tin mô hình dạng xếp dọc chỉ đọc kèm thông báo rõ *"Thiết kế sơ đồ quan hệ và thuộc tính mô hình yêu cầu màn hình máy tính (≥ 1280px)"*, không render editor gãy vỡ.

## Các bước
### Bước 1 — Model Center (`/report-models`) & Luồng Create / Clone / Impact / Archive
- Làm: Tạo `app/ui/pages/report_models.py` (`MENU_CODE = "report_model"`). Gồm `page_header` (`+ Tạo mô hình`), `command_bar` (search, lọc Data Source, lọc Status, Refresh), `dag.AgGrid` (Mã model, Tên, Data Source, Số Fact/Dimension/Relationship, Active Version, Status, Updated At, Actions), Modal/Form tạo mô hình (nhập Code/Name/Data Source), Modal Clone, Drawer `Impact Analysis` (read-only), Modal Archive (xác nhận hiển thị số report bị ảnh hưởng). Cập nhật `build_breadcrumbs` trong `app/ui/layout/shell.py`.
- Test viết trước: `tests/unit/test_page_report_models.py` kiểm tra gate phân quyền (`/login`, `/forbidden`), 4 trạng thái, filter, render action buttons đủ `aria-label`.
- Kiểm tra: `uv run pytest tests/unit/test_page_report_models.py -v`.

### Bước 2 — Khung Model Studio 3 panel, Model Explorer & Drawer `+ Thêm bảng`
- Làm: Tạo `app/ui/pages/report_model_studio.py` với `path_template="/report-models/<model_id>"` (và alias `/report-models/<model_id>/edit`). Bố cục Fluent Compact không cuộn cả trang (`flex: 1, minHeight: 0`), có `page_header` (tên model, status badge `Draft`/`Valid`/`Warning`/`Invalid`/`Published`, nút `Kiểm tra model`, `Lưu nháp`, `Phát hành`, menu `...`), `Status Bar` dưới đáy. Dựng `Model Explorer` bên trái: ô `Tìm bảng/cột...` (match cột tự mở bảng & highlight), nhóm `Fact`/`Dimension`/`Bridge`/`Unclassified` + `Quan hệ (N)`, và Drawer/Modal `+ Thêm bảng` (lọc Data Source, Schema, `TABLE`/`VIEW`, Search, ước lượng dòng, PK/FK count, khóa chọn bảng đã thêm).
- Test viết trước: `tests/unit/test_page_model_studio.py` kiểm tra layout 3 panel, search explorer expand & highlight, picker thêm bảng loại trừ bảng đã tồn tại.
- Kiểm tra: `uv run pytest tests/unit/test_page_model_studio.py -v`.

### Bước 3 — Model Canvas HTML+SVG & Clientside JS (`semantic_model_canvas.js`)
- Làm: Viết `app/ui/assets/semantic_model_canvas.js` (nạp lazy hoặc theo page) và phần render Canvas ở giữa `report_model_studio.py`: hiển thị card bảng (Role badge, PK/FK/Hidden/Measure markers, datatype compact font mono), đường nối SVG kèm nhãn `*:1` / `1:1` (tô màu active/selected/dimmed), thanh công cụ `Zoom In`, `Zoom Out`, `Fit`, `Auto Layout` Star Schema (có Undo vị trí), click chọn bảng/quan hệ, double-click center & zoom, kéo card cập nhật tọa độ Draft, kéo cột sang cột tạo quan hệ nháp tạm.
- Test viết trước: mở rộng `tests/unit/test_page_model_studio.py` kiểm tra hàm tính Star Schema `Auto Layout` deterministic, bounding box `Fit`, và sinh connector SVG không hardcode bảng/quan hệ.
- Kiểm tra: `uv run pytest tests/unit/test_page_model_studio.py -v`.

### Bước 4 — Panel Properties (Table/Grain, Relationship, Field/RLS, Measure Studio)
- Làm: Xây dựng panel Properties bên phải trong `report_model_studio.py` tự chuyển ngữ cảnh theo selection:
  - **Table Properties:** Source Object, Alias, Display Name, Table Role (`FACT`/`DIMENSION`/`BRIDGE`), Grain Description & Grain Keys (bắt buộc cho Fact), Default Date Field, Hidden.
  - **Relationship Properties:** Name, From/To Table & Column, Cardinality (`*:1`/`1:1`), Join Type (`LEFT OUTER`/`INNER`), Cross-filter (`Single`), Active toggle, nút `Kiểm tra quan hệ` (Tầng 1) + `Kiểm tra dữ liệu mẫu` (Tầng 2) hiển thị kết quả PASS/WARNING/ERROR, `Áp dụng thay đổi`, `Xóa quan hệ` (confirmation + cảnh báo report ảnh hưởng).
  - **Field Properties:** Display Name, Role (`DIMENSION`/`MEASURE_CANDIDATE`/`KEY`/`HIDDEN`), Default Aggregation (ẩn/khóa `SUM` với non-numeric), Format String, Visible, Filterable, Sort By Field, Folder, Virtual Date Hierarchy, Sensitivity, khung RLS Metadata V1.
  - **Measure Studio:** Editor tạo/sửa Simple Measure & Structured AST Calculated Measure (preview công thức an toàn).
- Test viết trước: mở rộng `tests/unit/test_page_model_studio.py` kiểm tra render/validate từng tab Properties, khóa `SUM` trên text/date, và flow Measure Editor.
- Kiểm tra: `uv run pytest tests/unit/test_page_model_studio.py -v`.

### Bước 5 — Validation Navigation, Save Draft Concurrency, Publish Modal & E2E Visual Validation
- Làm: Hoàn thiện thanh/drawer kết quả `Kiểm tra model` (click vào từng issue tự chọn & cuộn/focus đúng Table/Relationship/Field trên Canvas + `aria-live="polite"`), nút `Lưu nháp` xử lý xung đột `STALE_DATA` (hiển thị lựa chọn Reload/So sánh, không ghi đè), nút `Phát hành (Publish)` mở modal xem Diff + Impact Analysis + nhập Change Note. Kiểm tra toàn bộ với Playwright E2E ở `1366×768`, `1440×900` (cả Light/Dark mode) và `390×844` (chụp ảnh kiểm chứng, zero console/callback errors, `scrollHeight <= innerHeight`).
- Test viết trước: `tests/e2e/test_model_studio_e2e.py`.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run pytest tests/unit/test_page_report_models.py tests/unit/test_page_model_studio.py -v`, `uv run pytest tests/e2e/test_model_studio_e2e.py -v`.

## Chấp nhận khi
- [ ] Model Center (`/report-models`) đủ Create / Open / Clone / Impact Analysis / Archive và 4 trạng thái dữ liệu.
- [ ] Model Studio (`/report-models/<id>`) đủ Explorer, Canvas (pan/zoom/fit/auto-layout/drag-card/drag-relationship), Properties (Table/Grain, Relationship + Validation 2 tầng, Field/Virtual Date/RLS V1, Measure Studio).
- [ ] Desktop `1366×768` và `1440×900`: không cuộn cả trang (`scrollHeight <= innerHeight`, `scrollWidth <= innerWidth`); Mobile `390×844`: không tràn ngang, thông báo giới hạn rõ ràng.
- [ ] Không hex/px hardcoded trong page; không lộ secret; `uv run poe typecheck`, `uv run poe lint`, `uv run poe test-engine`, `uv run pytest tests/e2e/test_model_studio_e2e.py` xanh.

### Data Model Impact
- [ ] Task không thay đổi database schema (tái sử dụng toàn bộ schema tạo ở Task 106).

## Câu hỏi mở
- Đánh giá ở Bước 3: giữ vanilla JS + SVG thuần (nhẹ, không dependency ngoài) hay nạp `interactjs` vào `app/ui/assets/lazy/` để hỗ trợ drag/snap nâng cao.
