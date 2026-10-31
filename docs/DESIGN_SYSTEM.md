# ReconHub — Design System

Nguồn duy nhất cho màu, chữ, khoảng cách, bo góc, bóng, kích thước. **Không viết cứng hex, px trong page/component**: dùng biến CSS (`designs/tokens.css`, nạp vào `app/ui/assets/`) hoặc theme Dash Mantine (`app/ui/theme.py`, sinh bởi `scripts/gen_dmc_theme.py`). Thiếu token: thêm vào `designs/tokens.json` rồi chạy lại script.

Tệp này SINH RA bởi `python scripts/design_system.py`; không sửa tay. Phiên bản token: 2. Bảng điều khiển dày dữ liệu, xanh dương, mặt trắng, viền mảnh, thanh bên tối.

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
| `bg` | Sáng `#F5F7FB` · Tối `#0B1220` | Nền vùng nội dung. |
| `surface` | Sáng `#FFFFFF` · Tối `#111A2E` | Mặt thẻ, bảng, ô nhập, thanh trên, ngăn kéo. |
| `surface-2` | Sáng `#F8FAFC` · Tối `#18233A` | Tiêu đề bảng, hover dòng, vùng thả file. |
| `line` | Sáng `#E3E8F0` · Tối `#26334D` | Viền thẻ, chia dòng bảng. |
| `line-strong` | Sáng `#667085` · Tối `#7C8AA5` | Viền ô nhập, nút phụ (≥ 4,5:1). |
| `ink` | Sáng `#1D2939` · Tối `#E2E8F0` | Chữ chính. |
| `ink-soft` | Sáng `#667085` · Tối `#A3B1C6` | Chữ phụ, nhãn cột. |
| `primary` | Sáng `#2563EB` · Tối `#60A5FA` | Nút chính, link, bước/tab đang chọn. |
| `primary-hover` | Sáng `#1D4ED8` · Tối `#93C5FD` | Hover nút chính. |
| `on-primary` | Sáng `#FFFFFF` · Tối `#0B1220` | Chữ trên primary. |
| `primary-soft` | Sáng `#EAF1FF` · Tối `#14223F` | Nền bước đang chọn, chip khóa. |
| `focus` | Sáng `#2563EB` · Tối `#93C5FD` | Viền focus. |
| `nav-bg` | Sáng `#0F1B33` · Tối `#0A1324` | Nền thanh bên, nền trang đăng nhập. |
| `nav-ink` | Sáng `#CFD8EA` · Tối `#CFD8EA` | Chữ menu. |
| `nav-active` | Sáng `#1B2F57` · Tối `#1B2F57` | Mục menu đang chọn. |
| `nav-accent` | Sáng `#5B8CFF` · Tối `#5B8CFF` | Vạch mục đang chọn. |
| `ok` | Sáng `#027A48` · Tối `#4ADE80` | Khớp, thành công. |
| `ok-soft` | Sáng `#E8F8F0` · Tối `#0F2E1C` | Nền chip ok. |
| `crit` | Sáng `#B42318` · Tối `#F87171` | Lệch, lỗi, PROD, xóa. |
| `crit-soft` | Sáng `#FDECEC` · Tối `#3B1418` | Nền lỗi, ô lệch. |
| `warn` | Sáng `#B54708` · Tối `#FB923C` | Thiếu trong DB, cảnh báo, UAT. |
| `warn-soft` | Sáng `#FFF4E5` · Tối `#3A2210` | Nền cảnh báo. |
| `purple` | Sáng `#5925DC` · Tối `#C4B5FD` | Thiếu trong Excel, measure. |
| `purple-soft` | Sáng `#F1EDFF` · Tối `#2A1F4D` | Nền chip purple. |
| `off` | Sáng `#475467` · Tối `#A3B1C6` | Không nhất quán, Draft, đã tắt. |
| `off-soft` | Sáng `#F2F4F7` · Tối `#1E293B` | Nền chip off. |
| `info` | Sáng `#1D4ED8` · Tối `#93C5FD` | Đang chạy, thông tin. |
| `info-soft` | Sáng `#EAF1FF` · Tối `#14223F` | Nền thông tin. |
| `code-bg` | Sáng `#0F1B33` · Tối `#060B16` | Nền khối mã. |
| `code-ink` | Sáng `#D6E2FF` · Tối `#D6E2FF` | Chữ khối mã. |

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

- `--font-ui`: "Inter", "Segoe UI", Roboto, Arial, sans-serif
- `--font-mono`: "JetBrains Mono", Consolas, ui-monospace, monospace

| Kiểu | Cỡ | Dòng | Đậm | Dùng cho |
|---|---|---|---|---|
| `screen-title` | 22px | 1.3 | 700 | H1 màn. |
| `section-title` | 15px | 1.4 | 600 | Tiêu đề khối. |
| `kpi-figure` | 24px | 1.2 | 700 | Số KpiCard. |
| `body` | 14px | 1.5 | 400 | Chữ mặc định. |
| `body-sm` | 13px | 1.45 | 400 | Gợi ý, ô phụ. |
| `label` | 12px | 1.4 | 600 | Nhãn ô nhập, tiêu đề cột. |
| `button` | 14px | 1.2 | 600 | Chữ nút. |
| `chip` | 12px | 1.4 | 600 | Chip. |
| `caption` | 11px | 1.4 | 700 | Nhãn nhóm menu. |
| `code` | 12px | 1.45 | 500 | Mã, SQL. |

## 4. Khoảng cách

| Token | Giá trị |
|---|---|
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
| `radius-chip` | `20px` |
| `radius-control` | `8px` |
| `radius-card` | `12px` |
| `radius-step` | `12px` |
| `radius-pill` | `999px` |

## 6. Kích thước

| Token | Giá trị |
|---|---|
| `size-nav` | `232px` |
| `size-nav-collapsed` | `64px` |
| `size-header` | `56px` |
| `size-control` | `36px` |
| `size-control-sm` | `28px` |
| `size-drawer` | `540px` |
| `size-login` | `400px` |

## 7. Bóng

| Token | Giá trị |
|---|---|
| `shadow-popover` | Sáng `0 6px 18px rgba(15,23,42,.12)` · Tối `0 6px 18px rgba(0,0,0,.45)` |
| `shadow-drawer` | Sáng `-8px 0 30px rgba(15,23,42,.12)` · Tối `-8px 0 30px rgba(0,0,0,.55)` |

## 8. Dùng trong mã

- Biến CSS: `var(--primary)`, `var(--space-12)`, `var(--radius-card)`.
- Dash Mantine: `color="primary"`, `p="md"`, `radius="md"`; dải màu ok/crit/warn/purple/off/info có trong theme.
- Cách chuyển thiết kế: rule `.agents/rules/ui-dash.md` và bảng ánh xạ ở `designs/README.md`.
