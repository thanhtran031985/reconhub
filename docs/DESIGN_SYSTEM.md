# ReconHub — Design System

Nguồn duy nhất cho màu, chữ, khoảng cách, bo góc, bóng, kích thước. **Không viết cứng hex, px trong page/component**: dùng biến CSS (`designs/tokens.css`, nạp vào `app/ui/assets/`) hoặc theme Dash Mantine (`app/ui/theme.py`, sinh bởi `scripts/gen_dmc_theme.py`). Thiếu token: thêm vào `designs/tokens.json` rồi chạy lại script.

Tệp này SINH RA bởi `python scripts/design_system.py`; không sửa tay. Phiên bản token: 3. Dày dữ liệu, không cuộn cả trang ở ≥1366×768. Mặt sáng, viền mảnh, thanh bên sáng, xanh Fluent. Mẫu: designs/reference/preview-fluent.html.

---

## 1. Nguyên tắc (từ designs/README.md)


Hệ thống giao diện cho ứng dụng đối soát dữ liệu Excel với Oracle. Người dùng là chuyên viên dữ liệu, kế toán, vận hành làm việc trên màn 1366–1440px với bảng dày dữ liệu. Hướng thiết kế: bảng điều khiển dày dữ liệu, xanh dương chủ đạo, mặt trắng, viền mảnh, thanh bên tối, không bóng (trừ lớp nổi).

### Nguyên tắc nội dung
- Tiếng Việt có dấu, viết hoa kiểu câu. Giữ thuật ngữ: Template, Profile, Measure, Group by, Data Source, Run, Dry-run, Control total.
- H1 nói rõ đối tượng ("Run #1042 · DTP – HĐ tác nghiệp"); dòng phụ nói phạm vi.
- Thời gian `dd/MM/yyyy HH:mm:ss` giờ Việt Nam; khoảng thời gian "01/02/2026 00:00:00 → 05/02/2026 23:59:59".
- Số tiền `24.114.547.250`, cột số căn phải, `tabular-nums`. Chưa có dữ liệu: "—", không hiện 0.
- Lỗi nói chuyện gì xảy ra và làm gì tiếp. Không emoji, không dấu chấm than. Nút là động từ.
- Thao tác xóa: hộp thoại nêu "Sẽ xóa" và "Giữ lại"; xóa hàng loạt yêu cầu gõ XOA; xóa file yêu cầu gõ đúng tên file.
- Số hóa đơn, mã template, username, tên trường logic, cột DB, SQL dùng `--font-mono`.

### Màu
- Nền `bg`; thẻ/bảng/ô nhập `surface`; tiêu đề bảng, hover `surface-2`; viền `line`; viền điều khiển `line-strong`.
- `primary` cho nút chính, tab/bước đang chọn; mỗi vùng một nút chính. Nút xóa dùng biến thể danger (`crit`).
- Bảy trạng thái kết quả (tokens.json `status`), chip luôn có icon + chữ. Ô lệch: nền `crit-soft`, chữ `crit`, đậm.
- Nhãn môi trường: DEV `info`, UAT `warn`, PROD `crit`. Trạng thái người dùng: Hoạt động `ok`, Tạm khóa `warn`, Đã tắt `off`.

### Chữ, khoảng cách, bo góc
- Inter (dự phòng Segoe UI), thân 14px; không chữ dưới 11px.
- Thang 4/6/8/10/12/14/16/18/20/24/28/32; giữa khối 18px; đệm nội dung 24px × 28px.
- Bo: chip viên, nút/ô nhập 8px, khối 12px. Bóng chỉ cho popover và ngăn kéo.

### Bố cục
- Thanh bên 232px nền `nav-bg` (dưới 1000px thu 64px). Thanh trên 56px: breadcrumb, nhãn ENV, menu người dùng (Tài khoản, Đăng xuất).
- Trang đăng nhập: nền `nav-bg`, thẻ trắng 400px ở giữa, logo, ô nhập, nút chính rộng hết thẻ.
- Banner (dưới thanh trên): bảo trì (`warn`), cảnh báo dữ liệu tạm cho Admin (`warn`, có link "Xem và xóa").

### Bốn trạng thái dữ liệu
1. Bình thường. 2. Đang tải: skeleton đúng kích thước. 3. Trống: lý do + một hành động. 4. Lỗi: giữ dữ liệu cũ, Alert nói phần nào lỗi, thời điểm dữ liệu cũ, nút "Thử lại".
Mỗi `preview.html` có thanh chuyển 4 trạng thái và công tắc Sáng/Tối.

### Biểu tượng, chuyển động, bàn phím
Icon nét lucide 16px, `currentColor` (code dùng `dash-iconify` bộ `lucide:`); nút chỉ có icon phải có `aria-label`. Chuyển động 150ms, ngăn kéo 250ms, tôn trọng `prefers-reduced-motion`. Tab theo thứ tự đọc; Enter/Space mở vùng upload; Esc đóng ngăn kéo/hộp thoại; viền focus 2px.

### Ánh xạ sang Dash Mantine

Code bằng Dash 3 + dash-mantine-components 2.x (Mantine v8) + dash-ag-grid. Tài liệu DMC cho AI: https://www.dash-mantine-components.com/llms. Theme sinh bằng `scripts/gen_dmc_theme.py`; biến CSS tokens.css nạp qua `app/ui/assets/`.

| Thiết kế | Dash | Ghi chú |
|---|---|---|
| AppShell | `dmc.AppShell` + Navbar/Header/Main; menu `dmc.NavLink`; menu người dùng `dmc.Menu` | icon `DashIconify(icon="lucide:…")` |
| Button | `dmc.Button` (filled/default/subtle; `color="crit"` cho xóa), `loading` | |
| Field | `dmc.TextInput`, `dmc.PasswordInput`, `dmc.Select` (searchable), `dmc.MultiSelect` (vai trò), `dmc.Textarea`, `dmc.NumberInput`, `dmc.Checkbox`, `dmc.Switch` | `label`, `description`, `error`, `withAsterisk` |
| DateTimeField | `dmc.DateTimePicker(withSeconds=True, valueFormat="DD/MM/YYYY HH:mm:ss")` | |
| StatusChip | `dmc.Badge(variant="light", color=tone, leftSection=icon)` | |
| Alert | `dmc.Alert(color=tone, icon=…)` | |
| Tabs | `dmc.Tabs`, `dmc.SegmentedControl` | |
| Stepper | `dmc.Stepper` + `StepperStep` | |
| KpiCard | `dmc.Paper(withBorder=True, p="md", radius="lg")` | |
| DataGrid | `dag.AgGrid` (ag-theme-quartz ánh xạ token), nhóm cột Excel/DB/Chênh, `cellClassRules` → `rh-diff`, `rowSelection` cho chọn nhiều | infinite row model |
| Drawer | `dmc.Drawer(position="right", size=540)` | |
| Modal xác nhận | `dmc.Modal` + ô gõ xác nhận | xóa dữ liệu, khóa người dùng |
| FileDrop | `dcc.Upload` bọc `dmc.Paper` | `max_size` 50MB |
| EmptyState | `dmc.Stack(align="center")` | |
| CodeBlock | `dmc.CodeHighlight` | |
| Skeleton | `dmc.Skeleton` | |
| Mermaid | `html.Pre(className="mermaid")` + clientside callback | `assets/mermaid.min.js` |

Chỗ kiểu mặc định Mantine khác preview thì chỉnh bằng theme/`styles`; không chỉnh được thì ghi decisions.md.

### Thư mục
- `tokens.json` nguồn token; `tokens.css` sinh bởi `scripts/design_system.py`.
- `components/bundle.css` kiểu dáng chung tiền tố `rh-`; `components/_shared/preview.js` thanh trạng thái + icon cho preview.
- `components/<Thành phần>/README.md`; `components/Gallery/preview.html` mọi thành phần.
- `components/Screen01…Screen11` màn hoàn chỉnh (README.md + preview.html).


## 2. Màu

| Token | Giá trị | Dùng cho |
|---|---|---|
| `bg` | Sáng `#F5F5F5` · Tối `#1F1F1F` | Nền vùng nội dung. |
| `surface` | Sáng `#FFFFFF` · Tối `#292929` | Mặt panel, bảng, ô nhập, thanh trên, ngăn kéo. |
| `surface-2` | Sáng `#FAFAFA` · Tối `#2E2E2E` | Tiêu đề bảng, hover dòng, panel chi tiết, footer wizard. |
| `line` | Sáng `#E0E0E0` · Tối `#3D3D3D` | Viền panel, chia dòng bảng. |
| `line-strong` | Sáng `#707070` · Tối `#959595` | Viền dưới ô nhập, nút phụ (≥ 4,5:1). |
| `ink` | Sáng `#242424` · Tối `#F0F0F0` | Chữ chính. |
| `ink-soft` | Sáng `#616161` · Tối `#ADADAD` | Chữ phụ, nhãn cột. |
| `primary` | Sáng `#0F6CBD` · Tối `#479EF5` | Nút chính, link, bước/tab đang chọn. |
| `primary-hover` | Sáng `#115EA3` · Tối `#62ABF5` | Hover nút chính. |
| `on-primary` | Sáng `#FFFFFF` · Tối `#0A0A0A` | Chữ trên primary. |
| `primary-soft` | Sáng `#EBF3FC` · Tối `#0F2C48` | Nền mục/bước/dòng đang chọn, chip khóa. |
| `focus` | Sáng `#0F6CBD` · Tối `#62ABF5` | Viền focus. |
| `nav-bg` | Sáng `#FFFFFF` · Tối `#292929` | Nền thanh bên (Fluent: sáng, viền phải). |
| `nav-ink` | Sáng `#242424` · Tối `#F0F0F0` | Chữ menu. |
| `nav-active` | Sáng `#EBF3FC` · Tối `#0F2C48` | Mục menu đang chọn. |
| `nav-accent` | Sáng `#0F6CBD` · Tối `#479EF5` | Vạch trái mục đang chọn. |
| `ok` | Sáng `#107C10` · Tối `#54B054` | Khớp, thành công. |
| `ok-soft` | Sáng `#F1FAF1` · Tối `#0D2E0D` | Nền chip ok. |
| `crit` | Sáng `#C50F1F` · Tối `#F1707B` | Lệch, lỗi, PROD, xóa. |
| `crit-soft` | Sáng `#FDF3F4` · Tối `#3B1418` | Nền lỗi, ô lệch. |
| `warn` | Sáng `#BC4B09` · Tối `#F7A46B` | Thiếu trong DB, cảnh báo, UAT. |
| `warn-soft` | Sáng `#FFF9F5` · Tối `#3A2210` | Nền cảnh báo. |
| `purple` | Sáng `#5C2E91` · Tối `#C4B5FD` | Thiếu trong Excel, measure. |
| `purple-soft` | Sáng `#F7F4FB` · Tối `#2A1F4D` | Nền chip purple. |
| `off` | Sáng `#616161` · Tối `#ADADAD` | Không nhất quán, Draft, đã tắt. |
| `off-soft` | Sáng `#F0F0F0` · Tối `#333333` | Nền chip off. |
| `info` | Sáng `#0F6CBD` · Tối `#62ABF5` | Đang chạy, thông tin. |
| `info-soft` | Sáng `#EBF3FC` · Tối `#0F2C48` | Nền thông tin. |
| `code-bg` | Sáng `#1E1E1E` · Tối `#141414` | Nền khối mã. |
| `code-ink` | Sáng `#D4D4D4` · Tối `#D4D4D4` | Chữ khối mã. |

### Trạng thái kết quả

| Mã | Tone | Nhãn | Icon (lucide) |
|---|---|---|---|
| `MATCHED` | `ok` | Khớp | check |
| `MISMATCH` | `crit` | Lệch giá trị | not-equal |
| `MISSING_IN_DB` | `warn` | Thiếu trong DB | database-x |
| `MISSING_IN_EXCEL` | `purple` | Thiếu trong Excel | file-x |
| `INCONSISTENT` | `off` | Không nhất quán | shuffle |
| `DUPLICATE` | `warn` | Trùng khóa | copy |
| `INVALID` | `crit` | Không hợp lệ | alert-triangle |

## 3. Chữ

- `--font-ui`: "Segoe UI", "Segoe UI Web", Roboto, Arial, sans-serif
- `--font-mono`: Consolas, "Cascadia Mono", ui-monospace, monospace

| Kiểu | Cỡ | Dòng | Đậm | Dùng cho |
|---|---|---|---|---|
| `screen-title` | 18px | 1.3 | 600 | Tiêu đề màn (một dòng, cùng hàng mô tả). |
| `section-title` | 14px | 1.4 | 600 | Tiêu đề khối/panel. |
| `kpi-figure` | 20px | 1.2 | 600 | Số KpiCard. |
| `body` | 13px | 1.45 | 400 | Chữ mặc định. |
| `body-sm` | 12px | 1.4 | 400 | Gợi ý, mô tả, ô phụ. |
| `label` | 12px | 1.4 | 600 | Nhãn ô nhập, tiêu đề cột. |
| `button` | 13px | 1.2 | 600 | Chữ nút. |
| `chip` | 11px | 1.4 | 600 | Chip. |
| `caption` | 11px | 1.4 | 600 | Nhãn nhóm menu. |
| `code` | 12px | 1.5 | 400 | Mã, SQL. |

## 4. Khoảng cách

| Token | Giá trị |
|---|---|
| `space-2` | `2px` |
| `space-4` | `4px` |
| `space-6` | `6px` |
| `space-8` | `8px` |
| `space-10` | `10px` |
| `space-12` | `12px` |
| `space-14` | `14px` |
| `space-16` | `16px` |
| `space-18` | `18px` |
| `space-20` | `20px` |
| `space-24` | `24px` |
| `space-28` | `28px` |
| `space-32` | `32px` |

## 5. Bo góc

| Token | Giá trị |
|---|---|
| `radius-chip` | `4px` |
| `radius-control` | `4px` |
| `radius-card` | `6px` |
| `radius-step` | `4px` |
| `radius-pill` | `999px` |

## 6. Kích thước

| Token | Giá trị |
|---|---|
| `size-nav` | `200px` |
| `size-nav-collapsed` | `48px` |
| `size-header` | `44px` |
| `size-control` | `30px` |
| `size-control-sm` | `26px` |
| `size-drawer` | `480px` |
| `size-login` | `400px` |
| `size-detail-panel` | `320px` |
| `size-commandbar` | `40px` |
| `size-stepper` | `34px` |
| `size-grid-row` | `32px` |
| `size-grid-header` | `30px` |
| `size-list-row` | `40px` |

## 7. Bóng

| Token | Giá trị |
|---|---|
| `shadow-card` | Sáng `0 1px 2px rgba(0,0,0,.12)` · Tối `0 1px 2px rgba(0,0,0,.4)` |
| `shadow-popover` | Sáng `0 4px 16px rgba(0,0,0,.14)` · Tối `0 4px 16px rgba(0,0,0,.5)` |
| `shadow-drawer` | Sáng `-4px 0 24px rgba(0,0,0,.14)` · Tối `-4px 0 24px rgba(0,0,0,.55)` |

## 8. Dùng trong mã

- Biến CSS: `var(--primary)`, `var(--space-12)`, `var(--radius-card)`.
- Dash Mantine: `color="primary"`, `p="md"`, `radius="md"`; dải màu ok/crit/warn/purple/off/info có trong theme.
- Cách chuyển thiết kế: rule `.agents/rules/ui-dash.md` và bảng ánh xạ ở `designs/README.md`.
