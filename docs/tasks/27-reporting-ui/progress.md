# Tiến độ – 27-reporting-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Report Center cards/search/favorite | ✅ | |
| 2 | Viewer tabs/dynamic form/grid | ⬜ | |
| 3 | Wizard 6 bước theo prototype v5 | ⬜ | |
| 4 | Loading/empty/error/accessibility/responsive | ⬜ | |

## Ghi chú bước 1
- Trang `/reports` mới (MENU_CODE report_center): search + lọc nhóm + chỉ yêu thích, cards nhóm theo category, sao yêu thích toggle (set_report_favorite, cập nhật store không reload), nút "+ Đăng ký báo cáo" chỉ khi có menu report_admin.
- `shell.py`: gỡ 3 code report khỏi `_SIDEBAR_SKIP_CODES` (Q8) — thanh bên hiện Trung tâm/Lịch sử/Quản trị báo cáo.
- Test: 10 pass (unit + e2e HTTP /reports 200). Playwright `/tmp/rpt27/center.py`: T27-01 (search/category/favorite bền sau reload), T27-02 (operator không thấy report ẩn/nút tạo; admin thấy) — PASS, ảnh `shots/center-*.png`.
- Bẫy: dmc.Checkbox dùng prop `checked` (không phải `value`); dmc.Select render thành input + dropdown (Playwright click `[role="option"]`, không dùng select_option). Lint sạch, typecheck 21 lỗi = baseline.
