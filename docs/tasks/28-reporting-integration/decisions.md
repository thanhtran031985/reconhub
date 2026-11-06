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

## Bước 3 (06/11/2026)
- CONFIG_ONLY (T28-06): thêm 8 bảng cấu hình báo cáo vào CONFIG_ONLY_TABLES
  (RECON_REPORT, RECON_REPORT_TEMPLATE, RECON_RPT_TPL_VER, RECON_RPT_PARAM,
  RECON_RPT_PARAM_LOV, RECON_RPT_COLUMN, RECON_RPT_PRESET, RECON_RPT_FAVORITE).
  Preset/favorite tính là cấu hình người dùng (nhỏ, cần để UX chạy được sau
  chuyển). Thứ tự FK giữ nguyên cha-trước-con-sau.
- Lịch sử (T28-07): RECON_REPORT_RUN, RECON_RPT_EXPORT và cache phái sinh
  RECON_RPT_LOV_CACHE không vào CONFIG_ONLY — chỉ đi theo NO_TEMP/FULL.
  NO_TEMP đã có sẵn 11 bảng report trong RECON_TABLES_ORDER từ task 21.
- Kiểm chứng Oracle thật cần VPN nên để phía người dùng (như T21-01/T22-07/
  T26-12); trên máy ảo chỉ kiểm bằng mock target engine SQLite.

## Bước 4 (06/11/2026)
- SQL injection (T28-08): guard `_check_core` chặn thêm toán tử tập hợp
  UNION/INTERSECT/MINUS (một SELECT duy nhất — UNION có thể đọc trộm bảng
  khác mà tài khoản read-only vẫn thấy). Đổi ở lõi dùng chung (cả template
  đối soát): đã rà — không sample/test nào dùng UNION trong SQL người dùng
  (UNION ALL duy nhất ở `app/engine/catalog.py` là discovery nội bộ, không
  qua guard). LIKE_PREFIX escape `\`/`%`/`_` + `ESCAPE '\'` (trước đây giá trị
  "%" khớp mọi dòng); test cũ `test_filter_like_prefix_appends_percent_in_bind`
  vẫn xanh (chuỗi "BD" không đổi).
- Concurrency (T28-09): activate lock (REPORT_ACTIVATE_LOCK, TTL 60s) giữ
  → activate thứ hai CONFLICT; execute run không QUEUED → VALIDATION_ERROR;
  export >2 RUNNING/user → QUEUED (đã có task 26, kiểm lại bằng test cũ).
- E2E (T28-11): mock Oracle phải giả đúng kiểu context manager của
  `open_checked_connection` (`@contextmanager` + yield) — `patch` với
  return_value là MagicMock thường làm `with` nhận nhầm `__enter__()` trống
  khiến describe trả 0 cột (bẫy đã gặp, ghi lại để tránh lặp).
- Hiệu năng (T28-12, đo trên máy ảo, SQLite + mock Oracle, 5 dòng):
  list_reports 5ms, create+execute run 19ms, get_report_page 3ms,
  request_export 5ms. Ngưỡng test: list < 1s, chạy run < 2s, page < 1s,
  request export < 1s. Số đo Oracle thật (VPN) chưa có — ngưỡng trên là
  sàn cho SQLite/mock, cần đo lại khi có Oracle.
