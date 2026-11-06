# Tiến độ – 27-reporting-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Report Center cards/search/favorite | ✅ | |
| 2 | Viewer tabs/dynamic form/grid | ✅ | |
| 3 | Wizard 6 bước theo prototype v5 | ⬜ | |
| 4 | Loading/empty/error/accessibility/responsive | ⬜ | |

## Ghi chú bước 1
- Trang `/reports` mới (MENU_CODE report_center): search + lọc nhóm + chỉ yêu thích, cards nhóm theo category, sao yêu thích toggle (set_report_favorite, cập nhật store không reload), nút "+ Đăng ký báo cáo" chỉ khi có menu report_admin.
- `shell.py`: gỡ 3 code report khỏi `_SIDEBAR_SKIP_CODES` (Q8) — thanh bên hiện Trung tâm/Lịch sử/Quản trị báo cáo.
- Test: 10 pass (unit + e2e HTTP /reports 200). Playwright `/tmp/rpt27/center.py`: T27-01 (search/category/favorite bền sau reload), T27-02 (operator không thấy report ẩn/nút tạo; admin thấy) — PASS, ảnh `shots/center-*.png`.
- Bẫy: dmc.Checkbox dùng prop `checked` (không phải `value`); dmc.Select render thành input + dropdown (Playwright click `[role="option"]`, không dùng select_option). Lint sạch, typecheck 21 lỗi = baseline.

## Ghi chú bước 2
- `app/ui/pages/report_viewer.py` mới (`/reports/<report_id>`, MENU_CODE report_center): tabs template ACTIVE, form tham số động qua `build_param_layout`/`preview_layout` (grid 12 cột, control theo DATA_TYPE/CONTROL_TYPE, LOV STATIC/LOOKUP/SQL không dep nạp lúc mở; DATE_RANGE = 2 DateInput), nút Xem báo cáo tạo + chạy run đồng bộ, bảng kết quả server-side (sort header ASC→DESC→bỏ, Pagination, page-size 50/100/200), export XLSX poll 2s → link `/download/report-export/<id>`, mở bằng `?run=<id>`.
- `app/ui/pages/report_runs.py` mới (`/report-runs`, MENU_CODE report_history): bảng `list_report_runs` (owner scope), cột File = link export DONE mới nhất, Xem → Viewer `?run=`, Chạy lại (Q4) tạo run mới từ PARAMS_JSON gốc rồi báo link.
- `app/routes/file_routes.py`: route `/download/report-export/<export_id>` (Q5) dùng service `download_export` (owner scope + ADMIN bypass); app guard chuyển chưa đăng nhập về /login (302).
- Sửa nhỏ (ghi decisions.md): Viewer kiểm tra run status FAILED sau execute; `get_report_page` chặn sớm FAILED/CANCELLED (QUEUED/RUNNING giữ hợp đồng task 25).
- Test: 13 viewer + 8 history pass; e2e HTTP 14 pass (`/reports/1`, `/report-runs` 200; download chưa đăng nhập 302, không tồn tại 403/404). Playwright `/tmp/rpt27/viewer.py` PASS: form/tabs/empty state, lỗi tham số bắt buộc, lỗi "Version chưa gắn Data Source" (không Oracle), lịch sử owner scope (operator chỉ thấy run mình, admin thấy đủ), export request hiện "Đang xuất file…", tải file `fin_revenue.xlsx` từ export DONE đã seed — kiểm lại T25-09 bằng trình duyệt ở mức UI có thể (happy-path dữ liệu cần Oracle, đã kiểm ở unit test với mock). Lint sạch, typecheck 21 lỗi = baseline.
- Hồi quy sau bước 2: full suite 948 pass, 5 skip, 2 fail → cập nhật 2 test kỳ vọng cũ theo Q8 (menu report hiện thanh bên): `test_sidebar_menu_reorder` (+`/reports`, `/report-runs` cuối nhóm ĐỐI SOÁT), `test_report_menus_skipped_from_sidebar` → `test_report_menus_shown_in_sidebar` (assert ngược). Sau sửa: full suite xanh; e2e 17 pass.
