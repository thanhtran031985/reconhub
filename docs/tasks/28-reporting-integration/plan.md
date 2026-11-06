# Kế hoạch – 28-reporting-integration (đã tự duyệt theo ủy quyền 06/11/2026)

Người dùng giao full-task mode ngày 06/11/2026 17:41 ("bạn toàn quyền duyệt plan,
làm xong cả 3 task thì export"): plan này tự duyệt theo đề xuất, làm trọn 4 bước,
không dừng chờ continue sau mỗi bước. Nhánh `feat/28-reporting-integration`
từ tip task 27 (`94eabf1`).

## Hiện trạng đã rà (06/11/2026, trước khi code)
- Menu: 3 menu report khai báo ở `app/ui/menus.py` (MENUS + ROLE_MENUS_SEED):
  report_center + report_history cho cả 4 vai trò, report_admin chỉ ADMIN;
  4 page report đều có MENU_CODE + `page_gate`; services report có
  `requires_menu` (28 report_admin, 30 report_center, 7 data_source);
  `requires_menu` gắn `menu_codes` lên hàm nên registry quét được.
- Owner scope: list/get run/export/download đã có owner scope + ADMIN bypass
  (task 25/26/27); cần test bao phủ lại tất cả endpoint + route HTTP.
- Audit: report.py/report_template.py/report_param.py/report_column.py/
  report_source.py đã ghi audit cho create/update/version/activate/clone/
  archive/source; **thiếu: report_run.py (0) và report_export.py (0)** —
  create/execute/dry-run/cancel run, preset, request/retry/cancel/download
  export chưa có audit. Spec 12 §7 yêu cầu audit cho
  create/update/version/dry-run/activate/run/export/download/cancel.
- Migration: `RECON_TABLES_ORDER` đã có đủ 11 bảng report (task 21 bước 4);
  `CONFIG_ONLY_TABLES` chưa có bảng report nào; precheck/start_migration đã
  hỗ trợ 3 mode (NO_TEMP/FULL/CONFIG_ONLY, spec 08).
- Concurrency: activate có `_acquire_activate_lock` (REPORT_ACTIVATE_LOCK);
  execute chỉ chạy run QUEUED (state machine); export có claim + tối đa
  2 RUNNING/user (task 26).
- PROD: spec 12 §7 — activate/source SQL chỉ report_admin; "Data Source PROD
  vẫn ADMIN-only nếu task 19 quy định" — bước 1 kiểm chứng quy định task 19
  hiện tại rồi ghi quyết định, không tự bịa quy tắc mới.

## Bước 1 — Task19 menu + owner_filter tất cả endpoints (T28-01..T28-04)
- Test registry (mới, `tests/unit/test_reporting_integration.py`):
  mọi hàm @service trong `app/services/report*.py` có `menu_codes`;
  3 menu report tồn tại trong MENU_BY_CODE, `sync_from_code` đồng bộ đủ,
  ROLE_MENUS_SEED gán đúng (center/history 4 vai trò, admin chỉ ADMIN);
  4 page report có MENU_CODE + gọi `page_gate`.
- Test owner scope: operator `list/get_report_run`, `list/get/download_export`
  chỉ thấy của mình (run/export người khác → NOT_FOUND/403); ADMIN thấy tất cả;
  e2e HTTP download run người khác → 403/404.
- Kiểm chứng PROD: rà quy định task 19 về DS PROD + hành vi hiện tại của
  report run/dry-run trên DS PROD; ghi decisions.md (chỉ sửa code nếu phát
  hiện thiếu rào chắn so với quy định đã chốt).
- Cập nhật progress.md + tasks-dashboard; commit bước 1.

## Bước 2 — Audit hoàn chỉnh (T28-05)
- Thêm `write_audit_log` cùng transaction vào:
  - `report_run.py`: CREATE_REPORT_RUN, EXECUTE_REPORT_RUN (DONE + FAILED),
    DRY_RUN_VERSION, CANCEL_REPORT_RUN, CREATE_PRESET, DELETE_PRESET.
  - `report_export.py`: REQUEST_EXPORT, EXECUTE_EXPORT (worker, DONE/FAILED),
    RETRY_EXPORT, CANCEL_EXPORT, DOWNLOAD_EXPORT.
  - Không audit `set_report_favorite` (tùy chọn cá nhân, ngoài danh sách
    spec 12 §7) và `get/list` (chỉ đọc).
- Test đỏ trước: sau mỗi thao tác, đọc RECON_AUDIT_LOG thấy đúng
  entity/action/actor; audit cùng transaction (lỗi thao tác → không có audit).
- Cập nhật progress.md + tasks-dashboard; commit bước 2.

## Bước 3 — Metadata migration SQLite→Oracle (T28-06, T28-07)
- `CONFIG_ONLY_TABLES` thêm bảng cấu hình báo cáo (theo thứ tự FK):
  RECON_REPORT, RECON_REPORT_TEMPLATE, RECON_RPT_TPL_VER, RECON_RPT_PARAM,
  RECON_RPT_PARAM_LOV, RECON_RPT_COLUMN, RECON_RPT_PRESET, RECON_RPT_FAVORITE
  (preset/favorite là cấu hình của người dùng, nhỏ, cần để UX chạy được sau
  chuyển). Lịch sử + dữ liệu phái sinh (RECON_REPORT_RUN, RECON_RPT_EXPORT,
  RECON_RPT_LOV_CACHE) chỉ đi theo NO_TEMP/FULL, không vào CONFIG_ONLY.
- Test (mở rộng `tests/unit/test_metadata_migration.py`, mock target engine
  SQLite): precheck CONFIG_ONLY liệt kê đúng tập bảng (có report config,
  không có run/export/cache); NO_TEMP có run/export; FULL có đủ; số dòng
  khớp sau `start_migration` mock.
- Kiểm chứng Oracle thật cần VPN nên để phía người dùng (ghi rõ trong báo cáo
  cuối, như T21-01/T22-07/T26-12).
- Cập nhật progress.md + tasks-dashboard; commit bước 3.

## Bước 4 — Performance/security/E2E/regression (T28-08..T28-12)
- T28-08 SQL injection suite (mới): `check_report_sql` từ chối `; DROP`,
  UNION, comment `--`/`/*`, stacked query, bind lạ; whitelist query builder
  từ chối identifier ngoài metadata; sorts từ chối field lạ; LIKE prefix
  escape `%`/`_`.
- T28-09 concurrency: giữ lock activate → activate thứ hai CONFLICT;
  execute run đã RUNNING/DONE → VALIDATION_ERROR; export vượt 2 RUNNING/user
  → QUEUED (đã có ở task 26, kiểm lại).
- T28-11 E2E flow (pytest, Oracle mock): admin tạo report+template, analyze,
  dry-run, activate → operator chạy run + phân trang + export XLSX + tải file;
  assert đủ audit + owner scope trên cùng flow.
- T28-12 performance: test đo thời gian list_reports / create+execute run
  (mock) / get_report_page / request_export trên SQLite+mock Oracle, assert
  dưới ngưỡng (list < 1s, execute 5 dòng < 2s, page < 1s, request < 1s);
  ghi số đo + ngưỡng vào decisions.md.
- T28-10: full `poe test` + `poe e2e` + lint + typecheck (21 lỗi baseline);
  cập nhật checklist T28-01..T28-12, progress.md, README task → ✅,
  tasks-dashboard; commit bước 4 (đóng task 28).

## Rủi ro / lưu ý
- Không sửa ngoài phạm vi task 28; không dùng dữ liệu giả trong production path
  (mock chỉ trong test).
- Không chạy 2 bộ pytest đồng thời; worktree test dùng `.venv` của clone.
- Audit trong worker export chạy ở tiến trình worker hiện có — không đổi kiến trúc.
