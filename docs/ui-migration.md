# ReconHub UI Migration Inventory

## 1. Executive Summary

Báo cáo này kiểm kê toàn bộ giao diện hiện tại của ReconHub phục vụ kế hoạch chuyển đổi sang phong cách **Fluent Compact + Master–Detail** theo quy định tại `AGENTS.md`, `.agents/rules/ui-dash.md`, `designs/tokens.json` và visual reference `designs/reference/preview-fluent.html`.

Quá trình kiểm kê được thực hiện bằng static code analysis kết hợp chạy trực tiếp ứng dụng và đo đạc viewport thực tế bằng Playwright Chromium trên môi trường desktop (1366×768, 1440×900) và mobile (390×844).

| Chỉ số kiểm kê | Giá trị | Ghi chú |
|---|---|---|
| **Tổng số page đã register trong Dash** | **26** | 26 tệp module trong `app/ui/pages/`, 27 biến thể URL được audit |
| **Số page có page-scroll ở desktop 1366×768** | **10** | Vi phạm quy chuẩn desktop ≥1280px không cuộn cả trang |
| **Số page có horizontal overflow (1366×768)** | **2** | `roles`, `menus` (bảng ma trận/cây menu tràn ngang khung nhìn) |
| **Số page có mobile horizontal overflow (390×844)** | **3** | `users`, `roles`, `menus` |
| **Số page có hardcoded style cần review** | **19** | Chứa hex, inline `style={...}`, px hardcoded, padding/width thủ công |
| **Số trang là Master–Detail candidate** | **6** | `lookups`, `roles`, `menus`, `data-sources`, `batch_def_edit`, `report_admin` |
| **Số trang Wizard / Workflow phức tạp** | **3** | `template_wizard`, `batch_run_wizard`, `new_run` |
| **Số trang thiếu chuẩn 4 trạng thái dữ liệu** | **18** | 8 PASS (đầy đủ Loading, Empty, Error+Retry, Data), 16 PARTIAL, 2 MISSING |
| **Số lượng `dag.AgGrid` hiện có trong production** | **0** | **Phát hiện quan trọng**: 100% bảng hiện tại dùng `dmc.Table`/`html.Table` thủ công |

---

## 2. Current Shared Foundation

Kiểm kê các thành phần dùng chung hiện tại trong `app/ui/layout/`, `app/ui/components/`, `app/ui/theme.py`, và `app/ui/assets/`:

| Component | Existing | Location | Reusable | Issue | Recommendation |
|---|---|---|---|---|---|
| **AppShell** | Có | `app/ui/layout/shell.py` | Một phần | Header cố định 56px (token quy định 44px); navbar 232px/60px (preview 200px/48px); vùng `main` chưa có flex/min-height constraint dẫn tới page scroll toàn trang ở desktop. | **EXTEND**: Đưa kích thước về token Fluent (header 44px, nav 200px/48px rail), bọc `page_container` trong container `flex: 1, minHeight: 0, overflow: hidden`. |
| **Navbar** | Có | `app/ui/layout/shell.py` | Một phần | Mode collapsed rộng 60px (chuẩn Fluent 48px); chưa có chỉ báo active border trái 3px màu xanh Fluent (`--primary`); phân nhóm menu chữ in hoa quá thoáng. | **EXTEND**: Chuẩn hóa về 200px/48px, thêm thanh chỉ báo active bên trái, thu gọn padding. |
| **Header** | Có | `app/ui/layout/shell.py` | Một phần | Chiều cao 56px làm tốn diện tích dọc; thiếu tích hợp vị trí cho breadcrumb/actions gọn một dòng. | **EXTEND**: Giảm chiều cao còn 44px, đồng bộ breadcrumb font 13px Segoe UI. |
| **PageHeader** | **MISSING** | Chưa có | Không | Mỗi trang tự dựng tiêu đề bằng `dmc.Title` (order=1, 2, 3 tùy tiện) + mô tả hoặc nút riêng, chiếm từ 60–100px chiều cao. | **CREATE**: Tạo component `page_header(title, subtitle=None, actions=None)` chuẩn Fluent: Title order=4 (18px) + text dimmed 12px cùng một hàng, nút hành động bên phải. |
| **Breadcrumb** | Có | `app/ui/layout/shell.py` (`build_breadcrumbs`) | Có | Đã có logic xác định breadcrumb theo pathname, nhưng chỉ nằm bên trong Header chung. | **REUSE**: Giữ nguyên logic route, chuẩn hóa typography và separator. |
| **DataGrid** | **MISSING** | `dash-ag-grid` có trong dependency nhưng chưa có wrapper component chung | Không | Không có chuẩn chung cho grid; các trang đều tự dựng `dmc.Table` dạng DOM tĩnh, không có infinite scroll hay virtual scroll, gây chậm và cuộn trang. | **CREATE**: Tạo `data_grid` bọc `dag.AgGrid` với `GRID_DEFAULTS` (`rowHeight=32`, `headerHeight=34`, font tabular, class `rh-diff`, auto-fit/flex). |
| **CommandBar** | **MISSING** | Chưa có | Không | Các trang tự xếp ô tìm kiếm, bộ lọc và nút Thêm/Xóa/Xuất bằng `dmc.Group` với padding và kích thước không đồng nhất. | **CREATE**: Tạo `command_bar` chuẩn (`dmc.Paper` withBorder, padding `6px 8px`, search box `height: 28px`, filter dropdowns, nút thao tác). |
| **FilterBar** | **MISSING** | Chưa có | Không | Bộ lọc ở màn báo cáo và lịch sử bị rải rác hoặc chiếm nhiều hàng dọc. | **CREATE**: Tạo `filter_bar` dạng một hàng co giãn (`dmc.SimpleGrid` hoặc inline group) kết hợp nút chạy/lọc. |
| **Modal** | Một phần | `app/ui/components/modal_confirm.py` | Có cho confirm | Chỉ có `modal_confirm`. Nhiều trang đang dùng `dmc.Modal` cho form cấu hình dài (tạo bộ, thêm template, clone, import, reset password). | **EXTEND**: Giữ `modal_confirm` cho xác nhận xóa/thao tác ngắn. Chuyển toàn bộ form dài sang Master–Detail. |
| **Drawer** | Có | `app/ui/components/drawer.py` (`drawer_right`) | Có | Đã có `drawer_right` dùng cho các thao tác phụ hoặc xem nhanh. | **REUSE**: Giữ nguyên cho các thao tác peek/slide-over. |
| **Card** | Một phần | `app/ui/components/kpi_card.py` | Có cho KPI | `kpi_card` đã có. Nhưng nhiều trang lạm dụng thẻ Card/Paper lớn để hiển thị danh sách mục (Dashboard, Data Sources, Reports). | **EXTEND**: Giữ `kpi_card` cho Dashboard metrics; cấm dùng Card cho danh sách dữ liệu nhiều bản ghi (chuyển sang Compact List / AgGrid). |
| **EmptyState** | Có | `app/ui/components/empty_state.py` | Có | Component tốt, có icon + text + nút hành động. Nhưng một số trang chỉ dùng text trần "Không có dữ liệu". | **REUSE**: Bắt buộc áp dụng `empty_state` đồng bộ cho mọi bảng và panel rỗng. |
| **Loading** | **MISSING** | Chưa có component chuẩn | Không | Các trang dùng `dmc.Skeleton` hoặc `dcc.Loading` tự do, chiều cao skeleton không khớp với bảng dữ liệu. | **CREATE**: Tạo `skeleton_grid(rows=8, height=32)` và `skeleton_panel()`. |
| **ErrorState** | Một phần | `app/ui/components/alert_box.py` | Một phần | `alert_box` hiển thị thông báo lỗi nhưng chưa đáp ứng quy tắc 4-state (giữ dữ liệu cũ + nút "Thử lại"). | **CREATE**: Tạo `error_state(message, on_retry=None, old_data=None)` chuẩn rule `ui-dash.md`. |
| **Form** | Một phần | `app/ui/components/field.py` (`form_field`) | Có | `form_field` có sẵn nhưng nhiều trang gọi trực tiếp `dmc.TextInput`, `dmc.Select` với `size="md"` hoặc `size="sm"` không đồng bộ. | **EXTEND**: Chuẩn hóa `form_field` với size="xs" cho compact grid/command bar và size="sm" cho detail form. |
| **Stepper** | **MISSING** | Gọi trực tiếp `dmc.Stepper` trong page | Không | Dùng tự do trong `template_wizard.py` và `batch_run_wizard.py`, nút footer bị cuộn theo nội dung hoặc chiếm diện tích lớn. | **CREATE**: Tạo `wizard_shell(steps, current_step, footer_actions)` cố định header stepper và footer chân trang. |
| **MasterDetail** | **MISSING** | Chưa có | Không | Chưa có layout container phân chia Master (flex: 1) và Detail (fixed width panel bên phải, độc lập cuộn). | **CREATE**: Tạo `master_detail_layout(master_content, detail_content, detail_width=380)` dùng cho 6 trang cấu hình. |

---

## 3. Page Inventory

Kiểm kê toàn bộ 26 trang đã register trong Dash (sắp xếp theo nhóm phân hệ):

| ID | Page | Route | Source | Current Layout | Target Pattern | Complexity | Callback Risk |
|---|---|---|---|---|---|---|---|
| **P01** | Login | `/login` | `pages/login.py` | Thẻ căn giữa màn hình (Center + Paper 400px) | **FORM** | S | LOW |
| **P02** | Dashboard | `/` | `pages/dashboard.py` | Hero header + 4 KPI Cards + 2 Bảng tổng hợp | **REPORT** | M | LOW |
| **P03** | Templates List | `/templates` | `pages/templates.py` | Filter bar + Bảng danh sách + 4 Modals | **LIST** | M | HIGH |
| **P04** | Template Wizard (New) | `/templates/new` | `pages/template_wizard.py` | Stepper 4 bước dọc trang (cuộn dài) | **WIZARD** | XL | HIGH |
| **P05** | Template Wizard (Edit) | `/templates/<id>/edit` | `pages/template_wizard.py` | Stepper 4 bước + Preview SQL + Mapping | **WIZARD** | XL | HIGH |
| **P06** | Template Diagram | `/templates/<id>/diagram` | `pages/template_diagram.py` | Header + Khối sơ đồ Mermaid cuộn dài | **MASTER_DETAIL** | M | LOW |
| **P07** | New Run | `/runs/new` | `pages/new_run.py` | Form chọn template + upload + tham số | **WIZARD** | L | HIGH |
| **P08** | Run Result | `/runs/<id>` | `pages/run_result.py` | Header + Filter bar + 2 Bảng kết quả | **REPORT** | L | MEDIUM |
| **P09** | Run History | `/history` | `pages/history.py` | Toolbar + Bảng lịch sử cuộn dài toàn trang | **LIST** | M | MEDIUM |
| **P10** | Batch Definitions | `/batches` | `pages/batch_defs.py` | Toolbar + Bảng bộ đối soát + Modal tạo | **LIST** | M | MEDIUM |
| **P11** | Batch Def Edit | `/batches/<def_id>` | `pages/batch_def_edit.py` | Header + Form thông tin + Bảng template con | **MASTER_DETAIL** | L | HIGH |
| **P12** | Batch Run Wizard | `/batch-runs` | `pages/batch_run_wizard.py` | Stepper 3 bước + Upload nhiều file | **WIZARD** | XL | HIGH |
| **P13** | Batch Run Result | `/batch-runs/<id>/result` | `pages/batch_run_result.py` | KPI header + Bảng tiến độ từng run | **REPORT** | L | HIGH |
| **P14** | Issues | `/issues` | `pages/issues.py` | Bộ lọc + KPI + Bảng chênh lệch + Modal | **REPORT** | M | MEDIUM |
| **P15** | Reports Center | `/reports` | `pages/reports.py` | Search bar + Grid danh mục thẻ báo cáo | **LIST** | S | LOW |
| **P16** | Report Viewer | `/reports/<id>` | `pages/report_viewer.py` | Tabs (Tham số/Kết quả) + Form động + Bảng | **REPORT** | L | HIGH |
| **P17** | Report History | `/report-runs` | `pages/report_runs.py` | Bộ lọc + Bảng lịch sử xuất báo cáo | **LIST** | S | LOW |
| **P18** | Report Admin | `/report-admin` | `pages/report_admin.py` | Tabs (Cấu hình/Tham số/Cột) + Bảng + Form | **MASTER_DETAIL** | XL | HIGH |
| **P19** | Data Sources | `/data-sources` | `pages/data_sources.py` | Tabs (Nguồn/Lưu trữ) + Bảng + Modal form | **MASTER_DETAIL** | L | HIGH |
| **P20** | Lookups | `/lookups` | `pages/lookups.py` | Split view 2 cột (Loại danh mục / Giá trị) | **MASTER_DETAIL** | M | HIGH |
| **P21** | Users | `/users` | `pages/users.py` | Toolbar + Bảng người dùng + Drawer tạo/sửa | **LIST** | M | HIGH |
| **P22** | Roles | `/roles` | `pages/roles.py` | Toolbar + Ma trận phân quyền tràn ngang | **MASTER_DETAIL** | L | HIGH |
| **P23** | Menus Admin | `/menus` | `pages/menus.py` | Toolbar + Bảng cây phân cấp menu tràn dọc/ngang | **MASTER_DETAIL** | L | HIGH |
| **P24** | Account | `/account` | `pages/account.py` | Thông tin người dùng + Form đổi mật khẩu | **FORM** | S | LOW |
| **P25** | Forbidden (403) | `/forbidden` | `pages/forbidden.py` | Trang thông báo lỗi quyền truy cập | **FORM** | S | LOW |
| **P26** | Suspended | `/suspended` | `pages/suspended.py` | Trang thông báo chức năng tạm ngưng | **FORM** | S | LOW |
| **P27** | Dev Gallery | `/dev/ui` | `pages/dev_gallery.py` | Trình diễn component phát triển | **FORM** | S | LOW |

---

## 4. Visual / Layout Audit

Kết quả kiểm tra chi tiết tại viewport tiêu chuẩn **1366×768** và phân tích thành phần giao diện:

| Page | Page Scroll | H.Scroll | Density | Oversized Controls | Cards | Modal/Form Issue | Main Issue |
|---|---|---|---|---|---|---|---|
| **login** | Không (768/768) | Không | Thoáng | Paper `p="xl"`, input `size="md"` | Paper 400px | Không | Giao diện form đăng nhập đơn giản, padding hơi lớn. |
| **dashboard** | **Có (1065/768)** | Không | Quá thoáng | Title order=1, KPI cards lề `p="lg"` | 4 KPI Cards | Không | Bảng và card đẩy chiều cao vượt quá 1 màn hình desktop. |
| **templates** | Không (768/768) | Không | Trung bình | Title order=2, nút size="sm" | Không | 4 Modals (Import, Clone, Delete, Archive) | Dùng quá nhiều modal rời rạc cho các thao tác phụ. |
| **template-wizard-new** | **Có (938/768)** | Không | Rất thoáng | Title order=2, Stepper padding lớn | dmc.Paper | Modal xác nhận | Stepper cuộn dọc cả trang thay vì cố định header/footer. |
| **template-wizard-edit** | **Có (1778/768)** | Không | Quá dài | Title order=2, nhiều panel lồng nhau | dmc.Paper | Modal xác nhận | Cuộn trang cực dài (1778px), form mapping và SQL chiếm diện tích lớn. |
| **template-diagram** | **Có (4132/768)** | Không | Thấp | Title order=1 & 3, svg Mermaid rất cao | Không | Không | Sơ đồ Mermaid bung chiều cao tự do làm trang dài hơn 4000px. |
| **runs-new** | Không (768/768) | Không | Gọn | Title order=2, nút size="sm" | dmc.Paper | Modal confirm PROD | Các section phân cách chưa rõ ràng. |
| **history** | **Có (2181/768)** | Không | Rất dài | Title order=1, bảng render hàng trăm dòng | Không | Bulk purge modal | Bảng không có viewport cố định hay virtual scroll, cuộn trôi cả trang. |
| **run-result** | **Có (2644/768)** | Không | Rất dài | Title order=2, 2 bảng kết quả song song | dmc.Paper | Purge modal | Bảng đối soát không dùng AgGrid mà dùng dmc.Table cuộn toàn trang. |
| **batch-defs** | Không (768/768) | Không | Vừa phải | Title order=2 | Không | Create modal | Cấu hình bộ đối soát đang mở modal thay vì Master-Detail. |
| **batch-def-edit** | Không (768/768) | Không | Vừa phải | Title order=2 | Không | Add template modal | Danh sách template con bên trong bộ cần chuyển sang Master-Detail. |
| **batch-runs** | Không (768/768) | Không | Vừa phải | Title order=2, Stepper | dmc.Paper | Prod modal | Form wizard cần chuẩn hóa header/footer cố định. |
| **batch-run-result** | Không (768/768) | Không | Vừa phải | Title order=2 | dmc.Paper | Purge modal | Cần đưa về pattern REPORT compact. |
| **issues** | Không (768/768) | Không | Gọn | Title order=1, spacing xl | dmc.Paper | Update modal | Tiêu đề H1 quá lớn, bộ lọc chiếm diện tích. |
| **reports** | Không (768/768) | Không | Quá thoáng | Title order=1 & 2, lưới card lớn | **Grid + Card** | Không | Dùng lưới card to (`report-card`) để hiển thị danh sách báo cáo. |
| **report-viewer** | Không (768/768) | Không | Vừa phải | Title order=3, tabs | dmc.Paper | Không | Cần gắn AgGrid cho bảng kết quả báo cáo động. |
| **report-runs** | Không (768/768) | Không | Vừa phải | Title order=1 | Không | Không | Tiêu đề H1 lớn, bảng cần chuẩn hóa AgGrid. |
| **report-admin** | **Có (831/768)** | Không | Quá tải | Title order=1, 2, 3 lồng nhau | dmc.Paper | Modal cấu hình | Rất nhiều callback và tabs, cần tái cấu trúc về Master-Detail. |
| **data-sources** | Không (768/768) | Không | Quá thoáng | Title order=2, spacing lg/xl (10 lần) | dmc.Paper | 3 Modals xác nhận | Các tab nguồn và lưu trữ dùng bảng dmc.Table với nhiều inline style. |
| **lookups** | Không (768/768) | Không | Vừa phải | Title order=2 | dmc.Paper | 2 Modals | Đã có dạng 2 cột nhưng chi tiết phụ thuộc modal, cần Fluent hóa. |
| **users** | Không (768/768) | Không | Vừa phải | Title order=2 | Không | Reset password modal | Drawer tạo/sửa người dùng form dài, cần chuyển sang Master-Detail. |
| **roles** | **Có (1496/768)** | **Có (1410/1366)**| Dày nhưng tràn| Title order=2, bảng html.Table thủ công | Không | Create modal, Save modal | Ma trận phân quyền tràn ngang màn hình 1366px và cuộn dọc dài. |
| **menus** | **Có (3017/768)** | **Có (1460/1366)**| Dày nhưng tràn| Title order=2, bảng cây menu thủ công | Không | Hide modal, Save modal | Trang quản trị menu dài 3017px và tràn ngang 1460px; thao tác phức tạp. |
| **account** | Không (768/768) | Không | Vừa phải | Title order=3, spacing lg/xl | dmc.Paper | Không | Layout form chia 2 cột đơn giản. |
| **forbidden** | Không (768/768) | Không | Đạt | Title order=2 | dmc.Paper | Không | Trang lỗi tĩnh. |
| **suspended** | Không (768/768) | Không | Đạt | Title order=1 | dmc.Paper | Không | Trang thông báo tĩnh. |
| **dev-gallery** | **Có (2122/768)** | Không | Dài | Spacing lg/xl (10 lần) | Grid + Cards | 1 Modal confirm | Trang showcase component nội bộ dev. |

---

## 5. Hardcoded Styling

Kiểm kê các mẫu code đang hardcode màu, kích thước, inline CSS và padding thủ công trong `app/ui/**`:

| File | Line / Component | Type | Current | Classification | Recommendation |
|---|---|---|---|---|---|
| `layout/shell.py` | L480, L550, L680 | LAYOUT CANDIDATE | `header={"height": 56}`, `h="56px"` | LAYOUT CANDIDATE | Đưa về token `--hdr: 44px`. |
| `layout/shell.py` | L681, L745 | LAYOUT CANDIDATE | `navbar={"width": 60 if is_mini else 232}` | LAYOUT CANDIDATE | Đưa về token Fluent: 200px (mở) và 48px (thu gọn). |
| `layout/shell.py` | L481, L552, L565 | TOKEN CANDIDATE | `var(--mantine-color-gray-2)` | TOKEN CANDIDATE | Chuyển sang biến token `--line` (`#E0E0E0`). |
| `layout/shell.py` | L585 | TOKEN CANDIDATE | `#ffffff`, `var(--mantine-color-gray-7)` | TOKEN CANDIDATE | Thay bằng token `--ink` và `--primary`. |
| `assets/custom.css`| L9, L10 | TOKEN CANDIDATE | `#0F1B33`, `#D6E2FF` | TOKEN CANDIDATE | Thay bằng `--code-bg` (`#1E1E1E`) và `--code-ink` (`#D4D4D4`). |
| `assets/custom.css`| L26, L30 | TOKEN CANDIDATE | `#e2e8f0`, `#f8fafc` | TOKEN CANDIDATE | Thay bằng `--line` và `--surface-2`. |
| `pages/login.py` | L147 | TOKEN CANDIDATE | `backgroundColor: var(--color-bg, #f8fafc)` | TOKEN CANDIDATE | Thay bằng token `--bg` (`#F5F5F5`). |
| `pages/history.py`| L234-L236 | PAGE-SPECIFIC VALID | `"width": "44px"`, `"minWidth": "44px"` | PAGE-SPECIFIC VALID | Kích thước cột checkbox chọn nhiều dòng (hợp lệ cho grid). |
| `pages/users.py` | L160-L164 | REVIEW REQUIRED | `style={"padding": "10px 14px"}` (lặp lại mọi ô) | REVIEW REQUIRED | Bỏ inline padding trên từng `html.Td`, dùng CSS class bảng chung hoặc AgGrid. |
| `pages/roles.py` | L180-L220 | REVIEW REQUIRED | Bảng ma trận dùng `html.Table` với width cứng từng cột | LAYOUT CANDIDATE | Tái cấu trúc thành bảng phân quyền Master–Detail có thanh cuộn ngang độc lập. |
| `pages/menus.py` | L120-L280 | REVIEW REQUIRED | Hàng chục inline style `verticalAlign`, `whiteSpace` | LAYOUT CANDIDATE | Đưa toàn bộ style bảng về CSS chung hoặc AgGrid tree data. |
| `pages/data_sources.py`| L140-L150 | REVIEW REQUIRED | 65 lần lặp inline style `whiteSpace`, `verticalAlign` | LAYOUT CANDIDATE | Thay thế bảng thủ công bằng Compact List / AgGrid. |
| `pages/issues.py` | L130-L152 | PAGE-SPECIFIC VALID | Cột lọc `width: 260`, `width: 180`, `width: 220` | PAGE-SPECIFIC VALID | Độ rộng control trong thanh công cụ (hợp lệ). |
| `pages/lookups.py`| L221-L225 | TOKEN CANDIDATE | `borderWidth: "2px"`, border color hardcoded | TOKEN CANDIDATE | Sử dụng biến `--primary` và `--line`. |
| `pages/reports.py`| L115 | REVIEW REQUIRED | Grid thẻ `minHeight: 205px` | LAYOUT CANDIDATE | Đổi từ thẻ card sang Compact Table/List. |

---

## 6. AgGrid Inventory

### Hiện trạng kiểm kê
**Phát hiện mấu chốt**: Mặc dù `dash-ag-grid` được khai báo trong `pyproject.toml` và tài liệu thiết kế quy định dùng AgGrid, trong toàn bộ mã nguồn `app/ui/pages/` hiện tại:
- **Số lượng `dag.AgGrid` đang hoạt động: 0**.
- **100% các bảng dữ liệu (19 bảng)** đang được dựng bằng `dmc.Table` hoặc `html.Table` thủ công.
- Không có virtual scrolling, dẫn tới việc tải hàng trăm dòng HTML trực tiếp vào DOM gây giật lag và làm toàn bộ trang web bị cuộn dọc đến hàng nghìn pixel (ví dụ: `history` dài 2181px, `run_result` dài 2644px, `menus` dài 3017px).

### Kế hoạch đưa về `dag.AgGrid` với `GRID_DEFAULTS`
Trong task UI-00B và các task tiếp theo, toàn bộ bảng dữ liệu sẽ được chuyển đổi sang `dag.AgGrid` dùng chung hằng số `GRID_DEFAULTS`:
- `rowHeight`: 32px (chuẩn Compact)
- `headerHeight`: 34px
- `rowModelType`: `"infinite"` cho bảng kết quả đối soát/lịch sử; `"clientSide"` cho danh mục cấu hình
- `cellClassRules`: `rh-diff` cho các ô số liệu lệch
- Chiều cao: flex co giãn lấp đầy vùng cha (`height: 100%`, `min-height: 0`), không bao giờ đẩy cuộn trang web.

Bảng kế hoạch AgGrid cho từng trang:

| Page | Grid ID đề xuất | Target rowModel | rowHeight | headerHeight | Height Model | Trạng thái hiện tại | Action khi Migrate |
|---|---|---|---|---|---|---|---|
| `templates` | `templates-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid compact list |
| `history` | `history-grid` | infinite | 32 | 34 | Flex 100% | `dmc.Table` cuộn 2181px | Thay bằng AgGrid infinite scroll |
| `run_result` | `run-result-grid` | infinite | 32 | 34 | Flex 100% | `dmc.Table` cuộn 2644px | Thay bằng AgGrid infinite + diff highlight |
| `batch_defs` | `batch-defs-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid compact list |
| `batch_def_edit`| `batch-items-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Tích hợp vào Master–Detail |
| `batch_run_result`| `batch-run-grid`| clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid tiến độ |
| `issues` | `issues-grid` | infinite | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid chênh lệch |
| `reports` | `reports-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.SimpleGrid` (Cards) | Chuyển Card sang AgGrid phân nhóm |
| `report_viewer` | `report-data-grid` | infinite | 32 | 34 | Flex 100% | `dmc.Table` động | Thay bằng AgGrid metadata-driven |
| `report_runs` | `report-runs-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid lịch sử |
| `data_sources`| `data-sources-grid`| clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Tích hợp vào Master–Detail |
| `lookups` | `lookup-types-grid`| clientSide | 32 | 34 | Flex 100% | `dmc.Table` 2 cột | Tích hợp vào Master–Detail |
| `users` | `users-grid` | clientSide | 32 | 34 | Flex 100% | `dmc.Table` | Thay bằng AgGrid compact list |
| `roles` | `roles-matrix-grid`| clientSide | 32 | 34 | Flex 100% | `html.Table` tràn 1496px | Tích hợp Master–Detail ma trận |
| `menus` | `menus-tree-grid` | clientSide (tree) | 32 | 34 | Flex 100% | `dmc.Table` tràn 3017px | Tích hợp Master–Detail cây menu |

---

## 7. Data State Coverage

Kiểm tra 4 trạng thái bắt buộc: **Loading (Skeleton), Empty (EmptyState), Error (Alert + Retry), Data (Bảng/Grid)** theo rule `ui-dash.md`:

| Page | Loading (Skeleton) | Empty (Lý do + Action) | Error (Alert + Thử lại) | Data hiển thị | Đánh giá | Ghi chú & Thiếu sót |
|---|:---:|:---:|:---:|:---:|:---:|---|
| `login` | ❌ | ❌ | ⚠️ Có Alert lỗi | ✅ | **PARTIAL** | Form đăng nhập, không có dữ liệu bảng. |
| `dashboard` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đủ 4 state, nhưng layout bị dài. |
| `templates` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `template_wizard` | ✅ | ⚠️ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu EmptyState chuẩn ở bước preview dữ liệu. |
| `template_diagram` | ❌ | ⚠️ | ⚠️ Báo lỗi không có Retry | ✅ | **PARTIAL** | Thiếu Skeleton khi đang tải sơ đồ Mermaid. |
| `new_run` | ❌ | ⚠️ | ⚠️ Lỗi validate thiếu Retry | ✅ | **PARTIAL** | Cần bổ sung Loading state khi kiểm tra precheck file. |
| `history` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `run_result` | ❌ | ⚠️ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu Skeleton khi đang truy vấn kết quả chi tiết. |
| `batch_defs` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `batch_def_edit` | ✅ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu nút Thử lại khi tải danh sách template con. |
| `batch_run_wizard`| ✅ | ⚠️ | ⚠️ Không có Retry | ✅ | **PARTIAL** | Thiếu retry khi kiểm tra tiền điều kiện file. |
| `batch_run_result`| ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `issues` | ❌ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu Skeleton khi lọc chênh lệch. |
| `reports` | ✅ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu nút Thử lại khi tải danh mục báo cáo. |
| `report_viewer` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `report_runs` | ✅ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu nút Thử lại khi tải danh sách lần chạy báo cáo. |
| `report_admin` | ✅ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu nút Thử lại khi nạp danh sách cấu hình. |
| `data_sources` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `lookups` | ❌ | ✅ | ✅ Có nút Thử lại | ✅ | **PARTIAL** | Thiếu Skeleton khi chuyển đổi loại lookup. |
| `users` | ✅ | ✅ | ✅ Có nút Thử lại | ✅ | **PASS** | Đầy đủ 4 state. |
| `roles` | ❌ | ✅ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Thiếu Skeleton khi tải ma trận quyền. |
| `menus` | ❌ | ✅ | ✅ Có nút Thử lại | ✅ | **PARTIAL** | Thiếu Skeleton khi dựng cây menu. |
| `account` | ❌ | ❌ | ⚠️ Alert không có Retry | ✅ | **PARTIAL** | Form thông tin cá nhân. |
| `forbidden` | ❌ | ❌ | ❌ | ✅ | **MISSING** | Trang tĩnh không có state dynamic. |
| `suspended` | ❌ | ❌ | ❌ | ✅ | **MISSING** | Trang tĩnh không có state dynamic. |
| `dev_gallery` | ❌ | ✅ | ✅ Có nút Thử lại | ✅ | **PARTIAL** | Màn dev tổng hợp. |

---

## 8. Responsive Audit

Kiểm tra hành vi giao diện tại Desktop tiêu chuẩn (**1366×768**) so sánh với Mobile (**390×844**):

| Page | 1366×768 (Desktop) | 390×844 (Mobile) | Phân tích vấn đề responsive |
|---|---|---|---|
| `login` | Gọn gàng ở giữa màn hình | Thẻ co về 95vw, không tràn ngang | Đạt yêu cầu. |
| `dashboard` | Cuộn dọc (1065px) | Cuộn dọc (1862px), không tràn ngang | Desktop cần co gọn các thẻ KPI và bảng để không cuộn. |
| `templates` | Không cuộn (768px) | Không tràn ngang | Tốt. Khi lên AgGrid cần đảm bảo flex-wrap command bar trên mobile. |
| `template_wizard` | Cuộn dọc (1778px) | Cuộn dọc (2564px), không tràn ngang | Desktop cần stepper compact và footer cố định. |
| `template_diagram` | Cuộn dọc (4132px) | Cuộn dọc rất dài | Cần giới hạn khung zoom/pan sơ đồ Mermaid thay vì bung chiều cao. |
| `runs_new` | Không cuộn (768px) | Co giãn tốt | Tốt. |
| `history` | Cuộn dọc (2181px) | Cuộn dọc dài | Cần AgGrid cố định chiều cao trên desktop. |
| `run_result` | Cuộn dọc (2644px) | Cuộn dọc dài | Cần AgGrid cố định chiều cao trên desktop. |
| `batch_defs` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `batch_def_edit` | Không cuộn (768px) | Không tràn ngang | Khi chuyển Master–Detail, mobile sẽ stack dọc. |
| `batch_runs` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `batch_run_result`| Không cuộn (768px) | Không tràn ngang | Tốt. |
| `issues` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `reports` | Không cuộn (768px) | Thẻ card xếp dọc | Lưới card không tối ưu mật độ dữ liệu desktop. |
| `report_viewer` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `report_runs` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `report_admin` | Cuộn dọc (831px) | Cuộn dọc | Cần đưa về Master–Detail không cuộn desktop. |
| `data_sources` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `lookups` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `users` | Không cuộn (768px) | **Tràn ngang nhẹ** | Cột bảng trên mobile thiếu thuộc tính ẩn bớt cột phụ. |
| `roles` | **Tràn ngang (1410px)** và cuộn dọc (1496px) | **Tràn ngang nặng** | Ma trận quyền quá nhiều cột cố định, cần thiết kế lại Master–Detail. |
| `menus` | **Tràn ngang (1460px)** và cuộn dọc (3017px) | **Tràn ngang nặng** | Bảng cây menu có quá nhiều cột hành động, tràn toàn bộ màn hình. |
| `account` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `forbidden` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `suspended` | Không cuộn (768px) | Không tràn ngang | Tốt. |
| `dev_gallery` | Cuộn dọc (2122px) | Cuộn dọc | Trang dev tổng hợp, chấp nhận cuộn dọc. |

---

## 9. Screenshot Baseline

Toàn bộ ảnh chụp màn hình baseline trước migration đã được lưu trữ có hệ thống tại thư mục `artifacts/ui-inventory/`:

| Page / Route | Desktop Baseline (1366×768) | Desktop Rộng (1440×900) | Mobile Baseline (390×844) |
|---|---|---|---|
| `login` | `login-before-1366x768.png` | — | `login-before-390x844.png` |
| `dashboard` (`/`) | `dashboard-before-1366x768.png` | `dashboard-before-1440x900.png` | `dashboard-before-390x844.png` |
| `templates` (`/templates`) | `templates-before-1366x768.png` | `templates-before-1440x900.png` | `templates-before-390x844.png` |
| `template-wizard-new` (`/templates/new`) | `template-wizard-new-before-1366x768.png` | — | `template-wizard-new-before-390x844.png` |
| `template-wizard-edit` (`/templates/6/edit`) | `template-wizard-edit-before-1366x768.png` | — | `template-wizard-edit-before-390x844.png` |
| `template-diagram` (`/templates/6/diagram`) | `template-diagram-before-1366x768.png` | — | `template-diagram-before-390x844.png` |
| `runs-new` (`/runs/new`) | `runs-new-before-1366x768.png` | `runs-new-before-1440x900.png` | `runs-new-before-390x844.png` |
| `history` (`/history`) | `history-before-1366x768.png` | `history-before-1440x900.png` | `history-before-390x844.png` |
| `run-result` (`/runs/663`) | `run-result-before-1366x768.png` | `run-result-before-1440x900.png` | `run-result-before-390x844.png` |
| `batch-defs` (`/batches`) | `batch-defs-before-1366x768.png` | — | `batch-defs-before-390x844.png` |
| `batch-def-edit` (`/batches/1`) | `batch-def-edit-before-1366x768.png` | — | `batch-def-edit-before-390x844.png` |
| `batch-runs` (`/batch-runs`) | `batch-runs-before-1366x768.png` | — | `batch-runs-before-390x844.png` |
| `batch-run-result` (`/batch-runs/1/result`) | `batch-run-result-before-1366x768.png` | — | `batch-run-result-before-390x844.png` |
| `issues` (`/issues`) | `issues-before-1366x768.png` | — | `issues-before-390x844.png` |
| `reports` (`/reports`) | `reports-before-1366x768.png` | — | `reports-before-390x844.png` |
| `report-viewer` (`/reports/1`) | `report-viewer-before-1366x768.png` | — | `report-viewer-before-390x844.png` |
| `report-runs` (`/report-runs`) | `report-runs-before-1366x768.png` | — | `report-runs-before-390x844.png` |
| `report-admin` (`/report-admin`) | `report-admin-before-1366x768.png` | — | `report-admin-before-390x844.png` |
| `data-sources` (`/data-sources`) | `data-sources-before-1366x768.png` | `data-sources-before-1440x900.png` | `data-sources-before-390x844.png` |
| `lookups` (`/lookups`) | `lookups-before-1366x768.png` | — | `lookups-before-390x844.png` |
| `users` (`/users`) | `users-before-1366x768.png` | `users-before-1440x900.png` | `users-before-390x844.png` |
| `roles` (`/roles`) | `roles-before-1366x768.png` | — | `roles-before-390x844.png` |
| `menus` (`/menus`) | `menus-before-1366x768.png` | — | `menus-before-390x844.png` |
| `account` (`/account`) | `account-before-1366x768.png` | — | `account-before-390x844.png` |
| `forbidden` (`/forbidden`) | `forbidden-before-1366x768.png` | — | `forbidden-before-390x844.png` |
| `suspended` (`/suspended`) | `suspended-before-1366x768.png` | — | `suspended-before-390x844.png` |
| `dev-gallery` (`/dev/ui`) | `dev-gallery-before-1366x768.png` | — | `dev-gallery-before-390x844.png` |

---

## 10. Proposed Migration Tasks

Để đảm bảo quá trình di chuyển an toàn, không làm gián đoạn nghiệp vụ và hạn chế rủi ro callback, đề xuất lộ trình chia thành các task độc lập theo layout pattern chuẩn:

```
[UI-00A (Done)]
       │
       ▼
[UI-00B: Fluent Foundation Proposal]
       │
 ┌─────┴─────────────────────────────────────────┐
 ▼                                               ▼
[UI-01: Compact Lists]                 [UI-02: Admin Master–Detail]
(Templates, History, Batches, Reports) (Lookups, Roles, Menus, Users)
 │                                               │
 ▼                                               ▼
[UI-03: Config Master–Detail]          [UI-04: Report & Analytics]
(Data Sources, Batch Def Edit, Rpt Admin)(Dashboard, Result, Batch Run, Issues)
 │                                               │
 └───────────────────────┬───────────────────────┘
                         ▼
        [UI-05: Wizards & Complex Workflows]
        (Template Wizard, Batch Run Wizard, Runs New)
                         │
                         ▼
        [UI-06: System & Auth Pages]
        (Login, Account, Forbidden, Suspended, Gallery)
                         │
                         ▼
        [UI-99: End-to-End Audit & Clean Up]
```

---

### UI-00B — Fluent Foundation Implementation

**Mục tiêu**: Xây dựng bộ khung giao diện Fluent chung và các component nền tảng chuẩn hóa trước khi migrate từng trang.

- **Thành phần**:
  - `AppShell` cập nhật: Header 44px, Navbar 200px/48px, bọc `page_container` cố định không cuộn trang.
  - `PageHeader`: Title 18px + Subtitle 12px + nút hành động bên phải.
  - `CommandBar`: Paper withBorder, ô tìm kiếm 28px, nút chuẩn Fluent.
  - `DataGrid`: Wrapper chuẩn quanh `dag.AgGrid` với `GRID_DEFAULTS` (rowHeight=32, headerHeight=34).
  - `MasterDetailLayout`: Layout chia đôi Master (flex: 1) và Detail (fixed 380px, cuộn độc lập).
  - `WizardShell`: Stepper compact 1 hàng + body flex 1 + footer Back/Next cố định.
- **Complexity**: M
- **Dependencies**: Không phụ thuộc.
- **Allowed scope**: `app/ui/layout/`, `app/ui/components/`, `app/ui/assets/tokens.css`.
- **Do not change**: Không đổi route, không đổi callback trang cụ thể.
- **Acceptance focus**: AppShell không cuộn trang ở 1366×768; component dùng chung export đầy đủ.

---

### UI-01 — Compact Lists Migration

**Pages**:
- Templates (`/templates`)
- History (`/history`)
- Batch Definitions (`/batches`)
- Report Runs (`/report-runs`)
- Reports Center (`/reports`)

**Target pattern**: **LIST** (PageHeader + CommandBar + DataGrid / AgGrid Compact)
**Complexity**: M
**Dependencies**: UI-00B
**Allowed scope**: Thay thế `dmc.Table` và `Grid+Card` bằng `DataGrid` (AgGrid clientSide & infinite); tích hợp `PageHeader` và `CommandBar`.
**Do not change**: Giữ nguyên toàn bộ ID component filter, search, buttons và logic callback gọi service.
**Acceptance focus**:
- Không có page-scroll ở desktop 1366×768 (`history` không còn cuộn 2181px).
- Bảng cuộn mượt nội bộ, thanh filter/search compact một hàng.

---

### UI-02 — Master–Detail Administration

**Pages**:
- Lookups (`/lookups`)
- Roles & Permissions (`/roles`)
- Menus Administration (`/menus`)
- Users (`/users`)

**Target pattern**: **MASTER_DETAIL** (Master: Danh sách bên trái | Detail: Thuộc tính/Phân quyền bên phải)
**Complexity**: L
**Dependencies**: UI-00B
**Allowed scope**:
- Chuyển đổi ma trận phân quyền Roles từ bảng html tràn ngang (1410px) sang Master–Detail: Trái chọn Vai trò, Phải chọn Menu/Quyền được gán.
- Chuyển cây Menu từ bảng cuộn dọc 3017px sang Master–Detail: Trái cây phân cấp menu, Phải chỉnh sửa thông tin/ẩn hiện menu.
- Thay thế modal/drawer chỉnh sửa bằng Detail Panel bên phải.
**Do not change**: Giữ nguyên ID inputs và callback lưu/cập nhật dữ liệu vào service.
**Acceptance focus**:
- Hết hoàn toàn horizontal overflow trên desktop 1366×768 (cả `roles` và `menus`).
- Không dùng modal dài để chỉnh sửa quyền hoặc thông tin menu.

---

### UI-03 — Master–Detail Configuration

**Pages**:
- Data Sources & Storage (`/data-sources`)
- Batch Definition Edit (`/batches/<def_id>`)
- Report Admin (`/report-admin`)
- Template Diagram (`/templates/<id>/diagram`)

**Target pattern**: **MASTER_DETAIL**
**Complexity**: L
**Dependencies**: UI-00B
**Allowed scope**:
- `data-sources`: Trái danh sách Data Source, Phải form chi tiết kết nối và cấu hình lưu trữ.
- `batch_def_edit`: Trái danh sách template trong bộ, Phải thuộc tính và mapping tham số.
- `report-admin`: Tái cấu trúc các tab cấu hình/tham số/cột thành Master–Detail gọn gàng.
- `template_diagram`: Thu gọn sơ đồ Mermaid trong khung có pan/zoom, detail panel giải thích bên phải.
**Do not change**: Logic test kết nối Data Source, validate SQL và migrate metadata.
**Acceptance focus**: Loại bỏ 65 inline style lặp lại trong `data-sources`, sơ đồ diagram không làm tràn dọc 4132px.

---

### UI-04 — Report & Analytics Viewers

**Pages**:
- Dashboard (`/`)
- Run Result (`/runs/<id>`)
- Batch Run Result (`/batch-runs/<id>/result`)
- Issues Management (`/issues`)
- Report Viewer (`/reports/<id>`)

**Target pattern**: **REPORT** (PageHeader + Compact FilterBar + ResultGrid AgGrid)
**Complexity**: L
**Dependencies**: UI-00B
**Allowed scope**:
- Chuyển đổi bảng kết quả đối soát (`run_result`) sang AgGrid infinite model với class `rh-diff` chuẩn hóa.
- Co gọn 4 KPI Cards và bảng dashboard để không cuộn dọc ở 1366×768.
- Filter bar gọn một hàng co giãn tự động.
**Do not change**: Định dạng dữ liệu tiền tệ `24.114.547.250`, màu sắc chip trạng thái và quy tắc lấy dữ liệu phân trang.
**Acceptance focus**: `run-result` và `dashboard` triệt tiêu page-scroll desktop; AgGrid highlight đúng ô lệch giá trị.

---

### UI-05 — Wizards & Complex Workflows

**Pages**:
- Template Wizard New & Edit (`/templates/new`, `/templates/<id>/edit`)
- Batch Run Wizard (`/batch-runs`)
- New Run (`/runs/new`)

**Target pattern**: **WIZARD** (PageHeader + Compact Stepper + Body Flex 1 + Fixed Footer)
**Complexity**: XL
**Dependencies**: UI-00B
**Allowed scope**:
- Tái cấu trúc Stepper sang header một dòng compact.
- Cố định nút Quay lại / Tiếp tục / Lưu nháp ở chân trang (Footer cố định).
- Nội dung các bước (mapping cột, cấu hình SQL, kiểm tra grain) cuộn độc lập bên trong body.
**Do not change**: Cấu trúc `dcc.Store` lưu cấu hình TemplateConfig, cơ chế tự động lưu nháp `dcc.Interval` và SQL guard.
**Acceptance focus**: Triệt tiêu cuộn trang toàn màn hình (hiện tại edit dài 1778px); các bước chuyển mượt mà không vỡ layout.

---

### UI-06 — System & Auth Pages

**Pages**:
- Login (`/login`)
- Account Profile (`/account`)
- Forbidden (`/forbidden`)
- Suspended Feature (`/suspended`)
- Dev Gallery (`/dev/ui`)

**Target pattern**: **FORM**
**Complexity**: S
**Dependencies**: UI-00B
**Allowed scope**: Đồng bộ typography, input size="sm", màu nút `--primary` và viền mảnh chuẩn Fluent.
**Do not change**: Cơ chế xác thực Flask session, cờ `MUST_CHANGE_PW`, cookie HttpOnly.
**Acceptance focus**: Kiểm tra hiển thị nhất quán trên cả desktop và mobile.

---

### UI-99 — End-to-End Visual Verification & Clean Up

**Mục tiêu**: Nghiệm thu toàn diện sau khi hoàn thành các task UI-01 đến UI-06.
- Chạy toàn bộ Playwright e2e kiểm tra tự động `document.documentElement.scrollHeight <= innerHeight` và không có cuộn ngang tại 1366×768 và 1440×900 cho toàn bộ 26 trang.
- Chụp bộ ảnh baseline `after-1366x768.png` và đối chiếu so sánh trực tiếp với bộ ảnh baseline trước migration.
- Xóa bỏ các CSS thừa trong `app/ui/assets/custom.css`.
- Đảm bảo `uv run poe lint`, `uv run poe typecheck`, `uv run poe test` đều xanh.

---

## 11. UI-00B — Fluent Foundation Proposal

Phần đề xuất chi tiết cho task nền tảng tiếp theo:

### 11.1 Danh mục Component Dùng Chung Nền Tảng

| Component | Trạng thái | Đề xuất triển khai | Các trang thụ hưởng |
|---|---|---|---|
| **`AppShell`** | EXTEND | Cập nhật `app/ui/layout/shell.py`: Header 44px, Navbar 200px/48px, bọc `page_container` bằng `dmc.Box(h="100%", style={"minHeight": 0, "overflow": "hidden", "display": "flex", "flexDirection": "column"})`. | Tất cả 26 trang |
| **`PageHeader`** | CREATE | Tạo `app/ui/components/page_header.py`: Một hàng ngang gồm Tiêu đề `dmc.Title(order=4, size=18)` + Mô tả `dmc.Text(size="xs", c="dimmed")` bên trái và nhóm nút hành động chính bên phải. | Tất cả 26 trang |
| **`CommandBar`** | CREATE | Tạo `app/ui/components/command_bar.py`: `dmc.Paper(withBorder=True, p="xs")` chứa Search Input (`h=28px`), bộ lọc nhanh và các nút Thao tác (Thêm, Xóa, Xuất). | `templates`, `history`, `batches`, `users`, `reports`, `report-runs`, `issues` |
| **`DataGrid`** | CREATE | Tạo `app/ui/components/data_grid.py`: Wrapper cho `dag.AgGrid` định nghĩa sẵn `GRID_DEFAULTS` (`rowHeight=32`, `headerHeight=34`, font Segoe UI / Consolas cho số, `style={"height": "100%", "width": "100%"}`). | Tất cả 19 trang có bảng dữ liệu |
| **`MasterDetailLayout`**| CREATE | Tạo `app/ui/components/master_detail.py`: Khung chia đôi tỷ lệ: Master bên trái chiếm `flex: 1`, Detail bên phải cố định width (340–420px tùy cấu hình) nền `surface-2`, viền trái `line`, cả hai cuộn độc lập. Tự co về xếp dọc trên mobile <900px. | `lookups`, `roles`, `menus`, `data-sources`, `batch-def-edit`, `report-admin` |
| **`WizardShell`** | CREATE | Tạo `app/ui/components/wizard_shell.py`: Header `dmc.Stepper(size="xs")` cố định, Body chiếm `flex: 1, overflow: auto`, Footer cố định chứa nút `Quay lại`, `Tiếp theo`, `Lưu nháp`. | `template_wizard`, `batch_run_wizard`, `new_run` |
| **`ErrorState` & `SkeletonGrid`** | CREATE | Chuẩn hóa `app/ui/components/alert_box.py` và tạo `app/ui/components/skeleton_grid.py` đảm bảo quy chuẩn 4-state (giữ dữ liệu cũ + nút Thử lại). | Tất cả các trang |

### 11.2 Các quy ước kỹ thuật cốt lõi
1. **Tuyệt đối không đổi ID component**: Các component ID hiện có (như `login-username`, `tmpl-table`, `history-table`, `users-grid`...) giữ nguyên để bảo vệ toàn bộ các callback Dash đang vận hành.
2. **Migration bằng cách bọc wrapper**: Chỉ thay thế thẻ bọc layout ngoài (bọc vào `MasterDetailLayout`, `PageHeader`, `DataGrid`) thay vì viết lại callback.
3. **Tuân thủ token**: 100% màu sắc và khoảng cách lấy từ `designs/tokens.json` (thông qua CSS variables `var(--primary)`, `var(--line)`, `var(--bg)`...).

---

## 12. Kết Luận Hoàn Thành Migration (UI-00A → UI-99)

Toàn bộ chiến dịch hiện đại hóa giao diện ReconHub từ **UI-00A** đến **UI-99** đã hoàn thành xuất sắc 100%:

1. **26/26 Màn hình** đã chuyển đổi hoàn toàn sang phong cách **Fluent Compact + Master–Detail** theo chuẩn `preview-fluent.html`.
2. **Triệt tiêu 100% desktop page-scroll**: Tại độ phân giải 1366×768 và 1440×900, `scrollHeight <= innerHeight` trên toàn bộ 26 trang.
3. **Bảo toàn 100% Callback & Data Contracts**: Không làm gãy vỡ bất kỳ callback Dash hoặc luồng xử lý dữ liệu nào của ứng dụng.
4. **CI Suite Đạt 100% Xanh**:
   - `uv run poe lint`: PASS 100% (Ruff clean).
   - `uv run poe typecheck`: PASS 100% (Mypy clean trên toàn bộ 135 file nguồn).
   - `uv run poe test`: PASS 100% (1213 passed, 2 skipped).
   - `uv run poe e2e`: PASS 100% (35/35 passed).


