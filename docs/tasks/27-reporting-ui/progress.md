# Tiến độ – 27-reporting-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Report Center cards/search/favorite | ✅ | |
| 2 | Viewer tabs/dynamic form/grid | ✅ | |
| 3 | Wizard 6 bước theo prototype v5 | ✅ | |
| 4 | Loading/empty/error/accessibility/responsive | ✅ | |

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

## Ghi chú bước 3
- `app/ui/pages/report_admin.py` mới (`/report-admin`, MENU_CODE report_admin, chỉ ADMIN): danh sách report kèm template/version + Sửa/Clone/Lưu trữ; wizard 6 bước (Stepper + state store `{mode, report_id, template_id, version_id, version_status, step, max_step, analyzed, dry_run_ok, editing_param_id, rev}`; mở bằng `?new=1` / `?template=<id>` / `?clone=<version_id>`).
- Bước 1: tạo/sửa report+template (handle_save_step1; trùng mã báo "đã tồn tại"). Bước 2: nguồn CUSTOM_SQL/VIEW/TABLE — lưu bằng service mới `update_version_source` rồi `validate_version_sql` → analyze → apply (xem decisions.md); chưa chọn DS báo lỗi rõ. Bước 3: CRUD tham số + LOV (STATIC text `value|label`, SQL, LOOKUP) + nút ↑↓ thay kéo-thả (Q3) + Tự sắp xếp + cảnh báo layout violations. Bước 4: grid cột (bulk save, ↑↓, Khôi phục thứ tự, refresh = analyze+apply) — chỉ DRAFT. Bước 5: form thử qua `render_param_form` chung Viewer + dry-run (mock Oracle ở unit test). Bước 6: tóm tắt + Kích hoạt (chặn khi chưa dry-run) + Clone/Lưu trữ version.
- Sửa Viewer: STATIC LOV nhận cả `static_json` (dạng thật) và `static_values` (dạng test cũ).
- Test: 26 unit mới `test_page_report_admin.py` pass; viewer/runs/center 58 pass; e2e 18 pass (+`/report-admin` 200). Lint sạch, typecheck 21 lỗi = baseline. Hồi quy full suite sau bước 3: **977 passed, 5 skipped** (tăng 27 so với 950 sau bước 2: 26 test admin + 1 e2e). Playwright `/tmp/rpt27/wizard.py` PASS: T27-07 (list admin + operator bị chặn 403), T27-08 (tạo mới bước 1 → bước 2), T27-09 (bước 2 báo lỗi chưa chọn DS khi không có Oracle/DS), T27-10 (guard kẹt bước 2 khi chưa phân tích), T27-12 (Clone mở wizard với template đã nạp). T27-11 dry-run/activate happy-path chỉ kiểm ở unit test với mock Oracle (không Oracle trên máy ảo); bước 5/6 render + guard đã kiểm bằng Playwright ở mức có thể.
- Bẫy đã sửa trong bước 3 (xem decisions.md): import chéo page gây lỗi duplicate paths khi chạy server; layout() phải nhận **kwargs vì query string; dmc.Select chỉ nhận value chuỗi (DS select); build_param_layout là hàm thuần nhận version detail, service là preview_layout.

## Ghi chú bước 4 (đóng task)
- Rà `handle_result_render`: phát hiện và sửa hoán đổi tham số page_size/sorts trong wiring Dash thật (xem decisions.md) + test hồi quy sort DESC kiểm tra ORDER BY; `viewer-page-size` đổi sang value chuỗi.
- 4 trạng thái: Loading đã có sẵn ở Center/Viewer/Lịch sử (dcc.Loading), thêm `admin-wizard-loading` cho wizard; empty state Viewer/Lịch sử/Wizard đã có; lỗi Viewer giữ dữ liệu cũ + "Thử lại"; lỗi tải Center trước đây render div trống đã sửa thành alert thật.
- Accessibility T27-14: aria-live="polite" trên vùng thông báo/kết quả cả 4 trang; nút icon (sao yêu thích, Chạy lại, Sửa/Clone/Lưu trữ) đã có aria-label từ trước.
- Responsive T27-15: bọc ScrollArea cho 3 bảng trang Quản trị (tràn 49px ở 375 trước sửa). Playwright `/tmp/rpt27/states.py` PASS: aria-live đủ 4 trang, lỗi giữ empty state cũ + Thử lại, không tràn ngang ở 1440/1366/768/375/320, dark mode light→dark qua toggle, không lỗi JS. Ảnh `shots/states-*.png`, `states-dark.png`.
- Hồi quy sau bước 4: viewer.py + center.py Playwright PASS lại; full suite **979 passed, 5 skipped** (tăng 2 test mới: sort wiring + lỗi giữ dữ liệu cũ); e2e 18 pass.
