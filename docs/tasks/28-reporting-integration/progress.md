# Tiến độ – 28-reporting-integration

Trạng thái: ⬜

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Task19 menu + owner_filter tất cả endpoints | ✅ | |
| 2 | Audit hoàn chỉnh | ✅ | |
| 3 | Metadata migration SQLite→Oracle | ✅ | |
| 4 | Performance/security/E2E/regression | ✅ | |

## Ghi chú bước 1
- Registry: 3 menu report trong MENU_BY_CODE (center/history nhóm DOI_SOAT 70/80, admin nhóm QUAN_TRI 40); ROLE_MENUS_SEED center/history cho 3 vai trò còn lại, admin chỉ ADMIN; `sync_from_code` tạo đủ menu; 4 page khai MENU_CODE + page_gate; 57 hàm @service báo cáo đều có menu_codes (mapping kỳ vọng bổ sung vào test_perm_registry.py).
- Owner scope: test lại list/get run + download export — operator chỉ thấy của mình (run người khác → NOT_FOUND, download → NOT_FOUND/FORBIDDEN), ADMIN thấy tất cả.
- PROD (mới): `_check_prod_admin` trong report_run.py — operator tạo/chạy/xem trang trên DS PROD → FORBIDDEN "Chỉ ADMIN được chạy trên Data Source PROD."; ADMIN chạy bình thường. Test T28-03 đỏ trước rồi xanh sau khi thêm rào chắn.
- Test: 7 test mới test_reporting_integration.py + 4 test registry pass; hồi quy report run/page/history/cancel/viewer/runs/admin pass.

## Ghi chú bước 2
- Audit bổ sung (cùng transaction với đổi trạng thái): run — CREATE/EXECUTE (DONE+FAILED)/DRY_RUN/CANCEL + preset CREATE/DELETE; export — REQUEST/EXECUTE (worker DONE+FAILED)/RETRY/CANCEL/DOWNLOAD. Actor = người gọi; EXECUTE_EXPORT lấy CREATED_BY (worker không có ctx).
- Test: 4 test TestAudit mới (run trail, failed run, preset, export trail) — đỏ trước, xanh sau khi thêm audit. Hồi quy run/export/page/viewer/runs: 87 pass. Lint sạch, typecheck 21 lỗi = baseline.

## Ghi chú bước 3
- CONFIG_ONLY thêm 8 bảng cấu hình báo cáo (report/template/version/param/LOV/column/preset/favorite); run/export/lov_cache chỉ NO_TEMP/FULL.
- Test: 3 test mới (precheck CONFIG_ONLY/NO_TEMP + start_migration CONFIG_ONLY mock) — đỏ trước, xanh sau. 12 test migration pass. Lint sạch, typecheck 21 lỗi = baseline.
- Chưa kiểm chứng trên Oracle thật (không VPN) — để phía người dùng.

## Ghi chú bước 4 (đóng task)
- T28-08: guard chặn UNION/INTERSECT/MINUS (lõi dùng chung, đã rà không sample/test nào dùng); LIKE_PREFIX escape wildcard + ESCAPE; builder từ chối identifier/toán tử/sort ngoài whitelist; sort field lạ bị chặn ở get_report_page.
- T28-09: activate lock → CONFLICT; execute run không QUEUED → VALIDATION_ERROR; export >2 RUNNING → QUEUED (test cũ task 26).
- T28-11: E2E admin đăng ký (report+template+source+analyze+param+dry-run+activate) → operator chạy run + phân trang sort DESC + export CSV + tải file; audit đủ dọc flow.
- T28-12: số đo máy ảo (SQLite + mock, 5 dòng): list 5ms, chạy run 19ms, page 3ms, request export 5ms; ngưỡng test list < 1s / run < 2s / page < 1s / request < 1s.
- Hồi quy sau bước 4: full suite **1009 passed, 5 skipped** (tăng 30 so với 979 sau task 27); e2e 18 pass; lint sạch; typecheck 21 lỗi = baseline.
