# Quyết định – 28-reporting-integration

Tham chiếu spec 12 và data flow. Ghi mọi khác biệt đã duyệt tại đây.

## Bước 1 (06/11/2026)
- PROD ADMIN-only (T28-03, spec 11 D4 "chạy trên Data Source PROD chỉ ADMIN"):
  rào chắn đặt trong `report_run.py` (`_check_prod_admin`) tại 3 điểm thực thi
  mà operator gọi được: `create_report_run`, `execute_report_run`,
  `get_report_page` (paging = chạy lại truy vấn). Dry-run/activate đã
  report_admin-only nên không rào thêm. Khác với recon run (modal xác nhận
  PROD cho mọi vai trò có menu run): Viewer báo cáo chưa có modal PROD nên
  chọn chặn ADMIN-only cho an toàn; nếu người dùng muốn operator chạy PROD
  kèm xác nhận thì Viewer cần thêm modal như `/runs/new` — chưa làm.
- Owner scope (T28-04): đã có từ task 25/26/27 (list/get/download, ADMIN
  bypass); bước 1 chỉ bổ sung test bao phủ, không đổi code.
- Registry (T28-02): bổ sung mapping kỳ vọng cho 4 page + 57 hàm service
  báo cáo vào `test_perm_registry.py`; mọi hàm @service có ctx đều có
  menu_codes (quét generic đã có từ task 19).

## Bước 2 (06/11/2026)
- Audit thêm vào `report_run.py`/`report_export.py` (T28-05), cùng transaction
  với đổi trạng thái: CREATE_REPORT_RUN, EXECUTE_REPORT_RUN (DONE + FAILED),
  DRY_RUN_VERSION, CANCEL_REPORT_RUN, CREATE_PRESET, DELETE_PRESET,
  REQUEST_EXPORT, EXECUTE_EXPORT (worker, DONE + FAILED), RETRY_EXPORT,
  CANCEL_EXPORT, DOWNLOAD_EXPORT. Entity theo tên bảng (RECON_REPORT_RUN,
  RECON_RPT_TPL_VER, RECON_RPT_PRESET, RECON_RPT_EXPORT); actor = người gọi,
  riêng EXECUTE_EXPORT (worker, không có ctx) lấy CREATED_BY của export.
- Không audit `set_report_favorite` (tùy chọn cá nhân, ngoài danh sách spec 12
  §7) và các hàm chỉ đọc (get/list/apply_preset, get_report_page).
- REQUEST_EXPORT cache hit không ghi audit (không có thao tác mới).
- DOWNLOAD_EXPORT ghi audit sau khi qua kiểm tra owner + file tồn tại, trong
  transaction riêng (hàm vốn chỉ đọc).
