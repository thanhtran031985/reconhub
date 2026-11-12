# Task 73 — Progress

- 12/11/2026: user gửi ảnh dashboard dark mode (tiêu đề chìm, số KPI chìm, nền lẫn lộn). Parent chẩn đoán xong bằng code (2 hệ thống theme không đồng bộ; kpi_card c="dark"; tokens.css sinh ra, không sửa tay), viết task.md + plan.md + decisions.md (D1–D4), trình phạm vi sửa chờ user chốt (A gốc + dashboard / B toàn bộ).
- 12/11/2026: user chọn "Để dark mode sau" — hoãn task 73 (decisions D5), làm sau khi xong task 71/72.
- 12/11/2026: user quay lại (15:36): "tạo nhánh mới rồi chỉnh darkmode tất cả các page" → phạm vi B (toàn bộ các trang), nhánh mới `feat/73-dark-mode` từ ce782d1. Parent cập nhật decisions D5, giao subagent triển khai theo plan (gốc token + kpi_card + rà toàn bộ trang, check live dark mode port 8124).
- 12/11/2026: triển khai xong (chưa commit, chưa chạy full suite — parent chạy sau).
  - Gốc (D1/D3): scripts/design_system.py đổi selector dark sang `[data-mantine-color-scheme="dark"]` (light giữ `:root`); chạy `uv run poe design-system` sinh lại designs/tokens.css; chạy `uv run poe theme` đồng bộ app/ui/assets/tokens.css + sinh lại theme.py.
  - kpi_card: bỏ `c="dark"` → `c="var(--ink)"` cho tone mặc định (crit/warn giữ màu tone); đã chứng minh live: số KPI dark rgb(240,240,240) trên nền tối, light rgb(36,36,36) trở lại.
  - Rà toàn app/ui: 7 chỗ `c="dark"` còn lại → `var(--ink)` (empty_state, file_drop, modal_confirm, page_header breadcrumb, shell x2); 99 lần dùng biến CSS không tồn tại → remap về token thật (`--p`→`--surface`, `--p2`/`--bg-subtle`→`--surface-2`, `--border(-subtle)`→`--line`, `--danger`→`--crit`, `--success`→`--ok`, `--surface-1`→`--surface`, `--text-*`→`--ink(-soft)`, `--mono`→`--font-mono`, `--crimson-7`→`--crit`, `--radius-sm`→`--radius-card`, `--sh`→`--shadow-card`); hex cứng → token (`bg="gray.1"`→`var(--surface-2)`, `"#FFFFFF"` nền pill/footer→`var(--surface)`, `"#fff"/"#FFFFFF"` chữ trên primary→`var(--on-primary)`, `.rh-btn-del`→`--crit`/`--crit-soft`); `bg="surface-2"` (không phải tên màu Mantine) → `var(--surface-2)`. Giữ nguyên: ô SQL tối cố ý ở report_admin.py, `c="gray"` (xám trung tính, đọc được cả 2 mode — check live không flag).
  - D6 (tìm bởi check live): `primaryShade.dark` 4→5 ở scripts/gen_dmc_theme.py, sinh lại theme.py — nút filled primary chữ trắng 2.76→~3.9.
  - D7 (tìm bởi check live): custom.css thêm block `--ag-*` dưới `[data-mantine-color-scheme="dark"] .ag-theme-quartz-auto-dark` — grid tối theo toggle app, không theo OS.
  - D8 (tìm bởi check live): dashAgGridFunctions.js `reconRunsStatusCell` dùng token --ok/--crit/--info/--ink-soft thay tên màu CSS 'green' (2.83→~5.3).
  - Test mới tests/unit/test_dark_mode73.py: 16 test (selector Mantine, đồng bộ tokens.css, kpi_card, không c="dark", không biến CSS lạ, không hex cứng, primaryShade dark=5, biến --ag-*, màu trạng thái grid dùng token) — 16/16 pass. Targeted suite 252 pass. ruff check sạch; typecheck sạch (147 file). `ruff format --check` trên file đổi: chỉ còn drift có sẵn (page_header.py:21, menus.py, report_admin.py, batch_run_wizard.py, template_wizard.py, data_sources.py — không phải dòng task 73); 2 dòng của task đã chỉnh tay theo format (design_system.py:18, page_header.py:66).
  - Check live ~/workspace/check-73-dark-mode.py (port 8124, DB/storage riêng /run/pytest-tmp/check73.*): **19/19 PASS** — toggle dark đổi scheme + token --bg #1F1F1F/--ink #F0F0F0; nền trang tối; tiêu đề dashboard tương phản 9.95; 4 số KPI sáng (lum 0.87, warn 0.34); quét tương phản < 3.0 trên dashboard, batch-runs, report viewer (đã Xem, 55 dòng), settings, report-runs, history, queue-health: không còn chữ chìm; về light mode --bg #F5F5F5, KPI tối trở lại; không lỗi JS (console error + pageerror). Lưu ý check: dashboard chỉ hiện đủ KPI khi DB có run (đã seed 2 run DONE/FAILED theo mẫu test_page_dashboard.py); KPI to đo ở 18px (không phải 20px); `wait_for_function` nhận `arg=` làm tham số đầu của hàm.
  - Chưa kiểm chứng: sơ đồ Mermaid (template_diagram) — container đã đổi sang --surface-2 nhưng bản thân sơ đồ giữ theme sáng của Mermaid ở dark mode (giới hạn đã biết); các màu filled không phải primary (ok/crit/warn shade 4, tương phản chữ trắng 2.76–3.6) — check không flag chỗ nào dùng chúng với chữ, để nguyên theo mặc định Mantine.
  - Đã chạy `uv run poe tasks-dashboard` và revert dashboard.html. Chưa commit, chưa chạy full suite.
  - Parent review (12/11/2026): diff 37 file chỉ đổi màu/token, không
    đổi logic; test_dark_mode73.py 16/16 pass (chạy lại độc lập);
    check live 19/19 PASS (chạy lại độc lập); ruff check sạch;
    format: dòng task 73 sạch, drift còn lại ở page_header.py:21 là
    có sẵn trước task; typecheck + full suite đang chạy.
  - Lưu ý: tổ hợp 9 file test (dashboard_service, console_cleanup45/46,
    menu_display, menus_page, migration_modal64, batch_wizard_fixes67,
    batch_run_pages, batch_recent_paging68) làm
    `test_failed_run_summary_keeps_source_sql` fail — ĐÃ CHỨNG MINH
    CÓ SẴN TRƯỚC TASK 73 (fail y hệt trên worktree ở ce782d1, không
    có test_dark_mode73.py; test pass khi chạy riêng). Lỗi tương tác
    thứ tự test, không liên quan dark mode; không chặn task.
  - Parent review, tiếp: full suite lần 1: 1772 pass + 1 fail
    `test_page_users.py::test_login_history_table_looks_like_a_table`
    (assert "var(--bg-subtle" — biến cũ không tồn tại, task 73 remap
    đúng sang --surface-2, token "Tiêu đề bảng" light #FAFAFA /
    dark #2E2E2E). Parent sửa test sang assert --surface-2
    (đổi theo hành vi có chủ đích, mẫu task 70). Targeted 22 pass
    (test_page_users + test_dark_mode73). Typecheck sạch (147 file).
    Full suite lần 2: **1773 passed, 6 skipped** (1757 cũ + 16 mới).
