# Implementation Plan — 27-reporting-ui (UI Report Center, Viewer và Wizard)

## Bối cảnh
- Phụ thuộc task 26 — đã xong, nhánh `feat/26-reporting-export` ở `8ade114`.
- Người dùng duyệt plan task 26 ngày 06/11/2026 17:41 và giao luôn task 27 + 28 với **toàn quyền duyệt plan** — plan này tự duyệt theo ủy quyền đó, không chờ duyệt lại. Làm xong cả task rồi gửi xem (full-task mode, như task 19–26).
- Tài liệu đã có trên nhánh `docs/dynamic-reporting`: spec 12 (§3 màn hình, §4 Wizard, §5 thực thi, §6 Export), 12a, 12b, `designs/Screen16-DynamicReporting-preview.html` (prototype v2 — source of truth cho UI).
- Code hiện có tái dùng được:
  - Services tasks 21–26: `report.list_reports/get_report/set_report_favorite`, `report_template.list_templates/get_template/create_template/update_template/archive_template/get_version/clone_version/activate_version/archive_version`, `report_param` (CRUD/resolve/LOV/layout/preview/auto_layout), `report_column` (list/refresh/update/move/reorder/restore/get_result_layout/preview), `report_source` (validate_version_sql/list_report_objects/list_report_columns/analyze_version_source/apply_source_diff), `report_run` (create/execute/get_page/dry_run/cancel/metrics/list/get/preset), `report_export` (request/execute/list/get/download/retry/cancel), `data_source.list_data_sources`.
  - UI: `app/ui/pages/history.py` (mẫu layout + page_gate + stores + pagination), `template_wizard.py` (mẫu dmc.Stepper 5 bước + step content callback), `roles.py` (mẫu stores/callbacks/guards), `run_result.py` (mẫu render grid), components (`alert_box`, `empty_state`, `button_*`, `status_chip`, `field`), `app/ui/layout/shell.py` (`_SIDEBAR_SKIP_CODES` còn giữ 3 code report — task 21 dặn task 27 gỡ), `app/routes/file_routes.py` (mẫu `/download/file/<id>` + `/download/export/<run_id>`).
  - Registry test `tests/unit/test_perm_registry.py`: mọi page phải khai báo `MENU_CODE`; mọi `@service` có `ctx` đầu tiên phải khai báo `requires_menu` hợp lệ.
- Lưu ý: Playwright trên máy ảo không có Oracle — các flow cần Oracle (chạy report, phân trang dữ liệu thật, dry-run, export) kiểm tra ở mức service (đã có từ task 25/26) + kiểm tra trạng thái lỗi trên trình duyệt; Playwright tập trung vào render/form/layout/wizard/states/a11y/responsive (Q6).

## Nhánh và tài liệu
- Nhánh mới `feat/27-reporting-ui` từ `8ade114` (đầu nhánh task 26).
- Chép `docs/tasks/27-reporting-ui/` từ nhánh docs vào nhánh mới (task/progress/decisions/test-checklist; plan.md chép nguyên văn plan này).
- Spec 12/12a/12b + Screen16 ở lại nhánh `docs/dynamic-reporting` làm tham chiếu, không đưa vào patch task 27.

## Các bước (theo progress.md)

### Bước 1 — Report Center cards/search/favorite
- `app/ui/pages/reports.py` mới, route `/reports`, `MENU_CODE = "report_center"`, title "Trung tâm báo cáo – ReconHub".
- `app/ui/layout/shell.py`: gỡ `report_center`, `report_history`, `report_admin` khỏi `_SIDEBAR_SKIP_CODES` (Q8) — 3 menu hiện ở thanh bên (report_center/report_history nhóm DOI_SOAT sau issue; report_admin nhóm QUAN_TRI sau menu_admin).
- Layout theo prototype v2 (`v-center`): hero + nút "+ Đăng ký báo cáo" (chỉ hiện khi user có menu `report_admin`), toolbar tìm kiếm (tên/mã/mô tả) + lọc nhóm (Q7) + lọc "Chỉ yêu thích", cards nhóm theo category (FINANCE → "Tài chính", ACCOUNTING → "Kế toán", OPERATIONS → "Vận hành"), mỗi card: tag mã, tên, mô tả, số template, sao yêu thích (toggle `set_report_favorite`, cập nhật ngay không reload), nút "Xem báo cáo" → `/reports/<id>`.
- Chỉ hiện report ACTIVE + IS_VISIBLE='Y' với user thường (service `list_reports` đã lọc); ADMIN thấy tất cả.
- Trạng thái: loading (dcc.Loading), trống (empty_state "Không có báo cáo phù hợp."), lỗi (alert_box + Thử lại).
- Test trước: e2e HTTP (`tests/e2e/test_e2e_screens.py`: GET /reports 200 + title) + Playwright script `/tmp/rpt27/center.py` (T27-01 search/category/favorite, T27-02 active only) trên DB tạm seed report mẫu.
- Kiểm tra: `uv run poe test` (phạm vi unit+e2e), `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Viewer tabs/dynamic form/grid (+ Lịch sử)
- `app/ui/pages/report_viewer.py` mới, route `/reports/<report_id>`, `MENU_CODE = "report_center"`, title "Xem báo cáo – ReconHub".
- Tabs template (`list_templates`): mỗi tab là một template, hiện version ACTIVE của template đó (`get_version`); tab không có ACTIVE → thông báo "Chưa có version ACTIVE".
- Form tham số động theo prototype (`v-report`): `build_param_layout` (grid 12 cột, mobile 1 cột) + `preview_layout` (giá trị mặc định); control theo DATA_TYPE/CONTROL_TYPE — DATE/DATETIME → dmc.DateInput, NUMBER → dmc.NumberInput, TEXT → dmc.TextInput, SELECT → dmc.Select, MULTI_SELECT → dmc.MultiSelect, DATE_RANGE → 2 DateInput (Q2: LOV options nạp lúc mở trang cho STATIC/LOOKUP và SQL không dep; SQL LOV có dep bind thì refresh khi dep đổi qua callback `resolve_lov`).
- "Xem báo cáo" → `create_report_run` + `execute_report_run` (đồng bộ, như task 25 Q2) rồi `get_report_page` (page_size 50 mặc định, dmc.Pagination); bảng kết quả dmc.Table theo `get_result_layout` (web): header = LABEL, canh theo ALIGNMENT, format theo FORMAT_MASK, số canh phải, total row khi IS_TOTAL; sort theo cột (click header → `get_report_page` với sorts); lỗi chạy → alert_box với ERROR_CODE + nút Thử lại (T27-13).
- "Xuất Excel" → `request_export` (XLSX) rồi poll `list_exports` mỗi 2s tới DONE → link tải `/download/report-export/<id>`; trạng thái export hiện trong card kết quả.
- `app/ui/pages/report_runs.py` mới, route `/report-runs`, `MENU_CODE = "report_history"`, title "Lịch sử báo cáo – ReconHub": bảng `list_report_runs` (Run, Báo cáo, Người chạy, Dòng, Trạng thái, Thời gian) theo mẫu history.py; hành động: "Xem" (mở Viewer với run đó), "Chạy lại" (Q4: `create_report_run` với PARAMS_JSON của run gốc → redirect sang Viewer với run mới), "Tải file" (danh sách export của run → link `/download/report-export/<id>`).
- `app/routes/file_routes.py`: route mới `/download/report-export/<export_id>` (Q5): `download_export` (owner scope + ADMIN bypass), 401 chưa đăng nhập, 404 không tìm thấy/file mất, `send_file` với tên `export-<id>.<ext>` (zip giữ nguyên tên).
- Test trước: e2e HTTP cho `/reports/1` và `/report-runs` + Playwright script `/tmp/rpt27/viewer.py` (T27-03 tabs, T27-04 controls/LOV, T27-05 layout 12 cột, T27-06 pagination control + sort, T25-09 kiểm tra lại bằng Playwright — xem lịch sử chỉ thấy run của mình) trên DB tạm; flow chạy thật kiểm tra ở mức service (task 25) + trạng thái lỗi Oracle trên trình duyệt.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Wizard 6 bước theo prototype v5
- `app/ui/pages/report_admin.py` mới, route `/report-admin`, `MENU_CODE = "report_admin"`, title "Quản trị báo cáo – ReconHub".
- Danh sách: Report Master (`list_reports` bản ADMIN) + template/version của report đã chọn (`get_template`); hành động: "+ Báo cáo mới" (wizard mới), "Sửa" (mở wizard ở version DRAFT), "Clone version" (`clone_version` → mở wizard ở bản clone), "Lưu trữ" (`archive_version`/`archive_template`), "Kích hoạt" chỉ ở bước 6.
- Wizard dùng `dmc.Stepper` (mẫu template_wizard.py), 6 bước theo prototype v5: 1. Thông tin, 2. Nguồn dữ liệu, 3. Tham số & LOV, 4. Cấu hình cột, 5. Xem trước, 6. Hoàn tất. Stepper bấm được để quay lại bước đã qua (khác với lỗi stepper ở `/templates/.../edit` — callback đổi `active` có guard `n_clicks`).
  - Bước 1: `create_report` + `create_template` (DRAFT v1) khi mới; khi sửa DRAFT thì `update_report`/`update_template`. Fields theo prototype: mã/tên báo cáo, nhóm (Q7), mã/tên template, thứ tự, chủ sở hữu, mô tả, mặc định yêu thích, hiển thị.
  - Bước 2: Data Source (`list_data_sources`), SOURCE_TYPE, timeout 1..600, preview/export max. CUSTOM_SQL: textarea + "Phân tích SQL" → `validate_version_sql` (binds + columns) rồi `apply_source_diff` (cột mới/tắt cột mất). VIEW/TABLE: owner/object select (`list_report_objects`) → `list_report_columns` → `apply_source_diff`; cảnh báo TABLE trực tiếp (spec §4). Chưa phân tích thì không qua bước 3 (như prototype).
  - Bước 3: grid tham số (`create/update/delete_param`: code/label/type/required/default/row/span/visible) + panel LOV bên phải (STATIC grid Value/Label + ALL; SQL: textarea + "Kiểm tra LOV SQL" qua `resolve_lov`; LOOKUP: chọn type) + layout canvas (`move_param` bằng nút ↑↓/chuyển hàng + nhập row/span, `auto_layout` nút "Tự sắp xếp", `preview_layout` — Q3: không dùng HTML5 drag trong Dash, dùng nút + nhập số, đủ chức năng prototype). Vượt 12 → cảnh báo đỏ, chặn qua bước (validate_layout).
  - Bước 4: grid cột (`update_column`/`update_columns`/`move_column` bằng nút ↑↓/`restore_column_order`/`refresh_columns`): DB field readonly, label, type, format select theo type, alignment, web/excel/total checkbox, width; preview table cập nhật ngay (`preview_result_layout`).
  - Bước 5: form tham số thử (`preview_layout`) → "Chạy dry-run" (`dry_run_version`): hiện tổng dòng, thời gian, sample 100 dòng, cảnh báo timeout/type/format; lỗi thì không cho kích hoạt.
  - Bước 6: "Kích hoạt template" (`activate_version`) → màn hoàn tất (tag ACTIVE, snapshot đã ghi); "Về Trung tâm báo cáo".
- Test trước: e2e HTTP `/report-admin` + Playwright script `/tmp/rpt27/wizard.py` (T27-07..T27-12) trên DB tạm: bước 1 tạo report+template, bước 2 CUSTOM_SQL (phân tích — cần Oracle nên kiểm tra thông báo lỗi rõ ràng khi không có Oracle + đường thành công ở mức service), bước 3 LOV + layout, bước 4 grid, bước 5/6 kiểm tra ở mức service + UI chặn khi chưa dry-run.
- Kiểm tra: `uv run poe test`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Loading/empty/error/accessibility/responsive
- Rà soát cả 4 trang: loading (dcc.Loading + skeleton), empty (empty_state), error (alert_box + giữ dữ liệu cũ + Thử lại), access (403 → `/forbidden` qua page_gate; menu ẩn → `/suspended`).
- Accessibility (T27-14): `aria-label` cho nút icon (sao, ↑↓, xóa), `aria-live="polite"` cho vùng thông báo/kết quả, focus vào tiêu đề trang khi đổi trang, tab order tự nhiên (dmc mặc định), lỗi form gắn với field.
- Responsive + theme (T27-15): Playwright script `/tmp/rpt27/states.py` chụp 1440×900, 1366×768, 768, 375, 320 + light/dark cho Center/Viewer/Wizard; grid 12 cột → 1 cột ở mobile (build_param_layout columns=1); bảng kết quả scroll ngang ở màn hẹp.
- Test trước: Playwright script states.py (T27-13 4 states, T27-14 keyboard/focus/aria-live, T27-15 viewports + theme).
- Kiểm tra: `uv run poe test`, `uv run poe e2e`, `uv run poe lint`, `uv run poe typecheck`.

## Kiểm tra cuối
- `uv run poe test` đầy đủ, `uv run poe e2e`, `uv run poe typecheck` (21 lỗi baseline, 0 mới), `uv run poe lint`.
- Playwright 4 script (`center.py`, `viewer.py`, `wizard.py`, `states.py`) trên DB tạm — lưu ảnh vào `/tmp/rpt27/shots/`.
- Không phá golden/reconcile/batch/permission hiện có; không dùng dữ liệu giả trong production path.

## Câu hỏi chốt (Q0–Q8) — tự duyệt theo ủy quyền 06/11/2026 17:41
- Q0: Nhánh `feat/27-reporting-ui` từ `8ade114` (đầu nhánh task 26). Đồng ý (tự duyệt).
- Q1: Làm xong cả task rồi gửi xem (full-task mode, như task 19–26). Đồng ý (tự duyệt).
- Q2: LOV options nạp lúc mở Viewer cho STATIC/LOOKUP và SQL không dep; SQL LOV có dep bind refresh khi dep đổi qua callback. Đồng ý (tự duyệt).
- Q3: Wizard layout/column drag → nút ↑↓ + nhập row/span + "Tự sắp xếp" (không HTML5 drag trong Dash). Đồng ý (tự duyệt).
- Q4: History "Chạy lại" → tạo run mới với PARAMS_JSON gốc, redirect sang Viewer với run mới. Đồng ý (tự duyệt).
- Q5: Tải export qua Flask route `/download/report-export/<id>` (mẫu `/download/file`). Đồng ý (tự duyệt).
- Q6: E2E = test HTTP trong repo + Playwright script ở /tmp (mẫu roles); flow cần Oracle kiểm tra ở mức service + trạng thái lỗi trên trình duyệt. Đồng ý (tự duyệt).
- Q7: Nhóm báo cáo: FINANCE (Tài chính), ACCOUNTING (Kế toán), OPERATIONS (Vận hành). Đồng ý (tự duyệt).
- Q8: Gỡ 3 code report khỏi `_SIDEBAR_SKIP_CODES` (task 21 dặn). Đồng ý (tự duyệt).
