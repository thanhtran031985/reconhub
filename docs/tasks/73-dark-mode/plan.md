# Task 73 — Plan: dark mode chữ chìm, nền lẫn lộn

## Chẩn đoán (đã đọc code)

App có **2 hệ thống theme không đồng bộ**:

1. **Mantine color scheme** — nút mặt trăng là `dmc.ColorSchemeToggle`
   (`app/ui/layout/shell.py:504`), nó bật/tắt scheme của Mantine
   (`data-mantine-color-scheme` trên `<html>`). Các component Mantine
   (Paper, Text mặc định...) theo scheme này: dark mode thì nền thẻ
   tối, chữ mặc định sáng.
2. **Token tự chế** — `app/ui/assets/tokens.css` định nghĩa biến
   `--bg/--surface/--ink/...` cho dark mode dưới selector
   `[data-theme="dark"]`, nhưng **không có code nào set `data-theme`**
   (grep toàn `app/ui/` không thấy). Nên các biến custom mãi ở giá trị
   light (`--bg: #F5F5F5`, `--ink: #242424`), nền trang (dùng
   `var(--bg)`) không tối theo.

Hệ quả đúng như ảnh: chỗ nào dùng Mantine mặc định thì tối đúng
(thẻ "Tỉ lệ lệch" nền tối chữ sáng), chỗ nào dùng màu cố định thì
chìm:

- `kpi_card.py`: số liệu `c="dark"` — màu `dark` của Mantine là màu
  cố định, tối cả ở dark mode → số tối trên nền thẻ tối. ("207" thấy
  được vì tone `warn` → `c="warn"` là màu cam.)
- Tiêu đề trang: chữ Mantine (sáng ở dark mode) trên nền trang vẫn
  sáng (do `var(--bg)` kẹt ở light) → chữ sáng trên nền sáng.

`tokens.css` có chú thích "SINH TỪ tokens.json – không sửa tay"
(lệnh `uv run poe design-system`), `theme.py` sinh từ
`scripts/gen_dmc_theme.py` — nên sửa ở bộ sinh, không sửa tay file
sinh ra. Quy tắc repo: chỉ dùng design token, không viết hex trong
page.

## Thiết kế

1. **Gốc**: cho token custom đi theo scheme của Mantine — đổi selector
   trong bộ sinh token (`designs/tokens.json` /
   `scripts/design_system.py`, xác nhận đúng file khi làm) từ
   `[data-theme="dark"]` sang `[data-mantine-color-scheme="dark"]`
   (light giữ `:root`), rồi chạy lại `uv run poe design-system` để
   sinh lại `tokens.css`. Không thêm JS đồng bộ theme.
2. **Màu cố định**: `kpi_card.py` bỏ `c="dark"` → dùng màu chữ theo
   token (màu ink thích ứng); rà toàn app các `c="dark"`, hex hardcode
   trong page/component và sửa những chỗ chìm ở dark mode.
3. Kiểm chứng bằng Playwright ở dark mode: bật toggle, chụp dashboard
   + vài trang chính, assert tiêu đề/số KPI đọc được (nền trang tối,
   chữ sáng) + quét console error + pageerror.

## Phạm vi chờ user chốt

- **A. Gốc + dashboard + component dùng chung** (kpi_card,
  page_header, shell): sửa xong trang dashboard, các trang khác hưởng
  phần gốc (token) nhưng chưa rà từng trang.
- **B. Toàn bộ**: thêm rà từng trang chính (batch, report, settings,
  history...) và sửa hết chỗ chìm.

## Các bước (khi user chốt phạm vi)

1. Test đỏ trước: unit test token CSS sinh ra chứa selector Mantine
   dark (hoặc test tương đương ở bộ sinh); test render kpi_card ở
   dark mode không dùng màu cố định.
2. Sửa bộ sinh token + sinh lại tokens.css + sửa kpi_card + rà màu cố
   định (theo phạm vi đã chốt).
3. Check live dark mode (port 8123) + typecheck/ruff + full suite →
   commit → patch (áp sau patch 72, không db-migrate, chỉ khởi động
   lại app).
