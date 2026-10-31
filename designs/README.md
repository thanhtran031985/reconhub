# ReconHub — Hệ thống giao diện

Hệ thống giao diện cho ứng dụng đối soát dữ liệu Excel với Oracle. Người dùng là chuyên viên dữ liệu, kế toán, vận hành làm việc trên màn 1366–1440px với bảng dày dữ liệu. Hướng thiết kế: bảng điều khiển dày dữ liệu, xanh dương chủ đạo, mặt trắng, viền mảnh, thanh bên tối, không bóng (trừ lớp nổi).

## Nguyên tắc nội dung
- Tiếng Việt có dấu, viết hoa kiểu câu. Giữ thuật ngữ: Template, Profile, Measure, Group by, Data Source, Run, Dry-run, Control total.
- H1 nói rõ đối tượng ("Run #1042 · DTP – HĐ tác nghiệp"); dòng phụ nói phạm vi.
- Thời gian `dd/MM/yyyy HH:mm:ss` giờ Việt Nam; khoảng thời gian "01/02/2026 00:00:00 → 05/02/2026 23:59:59".
- Số tiền `24.114.547.250`, cột số căn phải, `tabular-nums`. Chưa có dữ liệu: "—", không hiện 0.
- Lỗi nói chuyện gì xảy ra và làm gì tiếp. Không emoji, không dấu chấm than. Nút là động từ.
- Thao tác xóa: hộp thoại nêu "Sẽ xóa" và "Giữ lại"; xóa hàng loạt yêu cầu gõ XOA; xóa file yêu cầu gõ đúng tên file.
- Số hóa đơn, mã template, username, tên trường logic, cột DB, SQL dùng `--font-mono`.

## Màu
- Nền `bg`; thẻ/bảng/ô nhập `surface`; tiêu đề bảng, hover `surface-2`; viền `line`; viền điều khiển `line-strong`.
- `primary` cho nút chính, tab/bước đang chọn; mỗi vùng một nút chính. Nút xóa dùng biến thể danger (`crit`).
- Bảy trạng thái kết quả (tokens.json `status`), chip luôn có icon + chữ. Ô lệch: nền `crit-soft`, chữ `crit`, đậm.
- Nhãn môi trường: DEV `info`, UAT `warn`, PROD `crit`. Trạng thái người dùng: Hoạt động `ok`, Tạm khóa `warn`, Đã tắt `off`.

## Chữ, khoảng cách, bo góc
- Inter (dự phòng Segoe UI), thân 14px; không chữ dưới 11px.
- Thang 4/6/8/10/12/14/16/18/20/24/28/32; giữa khối 18px; đệm nội dung 24px × 28px.
- Bo: chip viên, nút/ô nhập 8px, khối 12px. Bóng chỉ cho popover và ngăn kéo.

## Bố cục
- Thanh bên 232px nền `nav-bg` (dưới 1000px thu 64px). Thanh trên 56px: breadcrumb, nhãn ENV, menu người dùng (Tài khoản, Đăng xuất).
- Trang đăng nhập: nền `nav-bg`, thẻ trắng 400px ở giữa, logo, ô nhập, nút chính rộng hết thẻ.
- Banner (dưới thanh trên): bảo trì (`warn`), cảnh báo dữ liệu tạm cho Admin (`warn`, có link "Xem và xóa").

## Bốn trạng thái dữ liệu
1. Bình thường. 2. Đang tải: skeleton đúng kích thước. 3. Trống: lý do + một hành động. 4. Lỗi: giữ dữ liệu cũ, Alert nói phần nào lỗi, thời điểm dữ liệu cũ, nút "Thử lại".
Mỗi `preview.html` có thanh chuyển 4 trạng thái và công tắc Sáng/Tối.

## Biểu tượng, chuyển động, bàn phím
Icon nét lucide 16px, `currentColor` (code dùng `dash-iconify` bộ `lucide:`); nút chỉ có icon phải có `aria-label`. Chuyển động 150ms, ngăn kéo 250ms, tôn trọng `prefers-reduced-motion`. Tab theo thứ tự đọc; Enter/Space mở vùng upload; Esc đóng ngăn kéo/hộp thoại; viền focus 2px.

## Ánh xạ sang Dash Mantine

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

## Thư mục
- `tokens.json` nguồn token; `tokens.css` sinh bởi `scripts/design_system.py`.
- `components/bundle.css` kiểu dáng chung tiền tố `rh-`; `components/_shared/preview.js` thanh trạng thái + icon cho preview.
- `components/<Thành phần>/README.md`; `components/Gallery/preview.html` mọi thành phần.
- `components/Screen01…Screen11` màn hoàn chỉnh (README.md + preview.html).
