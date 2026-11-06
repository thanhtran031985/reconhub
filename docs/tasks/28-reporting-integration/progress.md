# Tiến độ – 28-reporting-integration

Trạng thái: ⬜

| Bước | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| 1 | Task19 menu + owner_filter tất cả endpoints | ✅ | |
| 2 | Audit hoàn chỉnh | ⬜ | |
| 3 | Metadata migration SQLite→Oracle | ⬜ | |
| 4 | Performance/security/E2E/regression | ⬜ | |

## Ghi chú bước 1
- Registry: 3 menu report trong MENU_BY_CODE (center/history nhóm DOI_SOAT 70/80, admin nhóm QUAN_TRI 40); ROLE_MENUS_SEED center/history cho 3 vai trò còn lại, admin chỉ ADMIN; `sync_from_code` tạo đủ menu; 4 page khai MENU_CODE + page_gate; 57 hàm @service báo cáo đều có menu_codes (mapping kỳ vọng bổ sung vào test_perm_registry.py).
- Owner scope: test lại list/get run + download export — operator chỉ thấy của mình (run người khác → NOT_FOUND, download → NOT_FOUND/FORBIDDEN), ADMIN thấy tất cả.
- PROD (mới): `_check_prod_admin` trong report_run.py — operator tạo/chạy/xem trang trên DS PROD → FORBIDDEN "Chỉ ADMIN được chạy trên Data Source PROD."; ADMIN chạy bình thường. Test T28-03 đỏ trước rồi xanh sau khi thêm rào chắn.
- Test: 7 test mới test_reporting_integration.py + 4 test registry pass; hồi quy report run/page/history/cancel/viewer/runs/admin pass.
