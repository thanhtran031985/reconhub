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
