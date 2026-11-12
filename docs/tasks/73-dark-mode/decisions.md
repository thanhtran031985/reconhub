# Task 73 — Decisions

- D1: gốc lỗi là 2 hệ thống theme không đồng bộ — Mantine scheme
  (`data-mantine-color-scheme`, do ColorSchemeToggle bật) vs token
  custom (`[data-theme="dark"]` trong tokens.css, không code nào set
  `data-theme`). Nền trang dùng `var(--bg)` nên kẹt ở light.
- D2: `kpi_card.py` dùng `c="dark"` cố định → số tối trên nền thẻ tối
  ở dark mode; "207" thấy được vì tone `warn` cho màu cam.
- D3: tokens.css + theme.py là file sinh ra (design-system /
  gen_dmc_theme) — sửa ở bộ sinh, không sửa tay.
- D4: phạm vi sửa chờ user chốt (A: gốc + dashboard + component dùng
  chung / B: rà toàn bộ các trang).
- D5: user chọn "Để dark mode sau" (12/11/2026) — hoãn task 73, làm
  sau khi xong task 71/72. Chẩn đoán D1–D3 giữ nguyên để dùng lại.
  15:36 12/11/2026 user quay lại: "tạo nhánh mới rồi chỉnh darkmode
  tất cả các page" → làm lại task 73, phạm vi B (toàn bộ các trang),
  nhánh mới `feat/73-dark-mode` từ ce782d1.
- D6: nút filled primary ở dark mode dùng shade 4 (#65A1D5, do
  `primaryShade.dark: 4` trong gen_dmc_theme.py) → chữ trắng chỉ đạt
  tương phản 2.76. Đổi `primaryShade.dark` 4 → 5 (#3A86C9, ~3.9) ở
  bộ sinh theme, sinh lại theme.py. Các màu khác (ok/crit/warn...)
  vẫn shade 4 theo mặc định Mantine — chỉ sửa primary vì đó là màu
  nút/pagination; không ghi đè `-filled` bằng CSS để tránh đổi toàn
  bộ filled element.
- D7: `ag-theme-quartz-auto-dark` chỉ đổi theo prefers-color-scheme
  của OS, không theo toggle của app. Khi OS sáng + app tối, grid giữ
  nền trắng nhưng nút subtle trong cell dùng màu chữ sáng của dark
  mode → "Xuất lại"/"Chạy lại" trên /report-runs chìm (1.12). Ghi đè
  biến --ag-* (nền/chữ/header/viền) dưới selector dark của Mantine
  trong custom.css để grid tối theo app, bất kể OS.
- D8: renderer trạng thái grid Lịch sử báo cáo
  (dashAgGridFunctions.js `reconRunsStatusCell`) dùng tên màu CSS cố
  định 'green'/'red'/'blue'/'gray' → 'green' (#008000) chìm trên nền
  tối (2.83). Đổi sang token --ok/--crit/--info/--ink-soft (đọc được
  cả 2 mode, >= 5.3). Lưu ý: 'red' ở `mk('delete', ...)` là prop
  color của DMC Button (Mantine tự thích ứng) — không động.
