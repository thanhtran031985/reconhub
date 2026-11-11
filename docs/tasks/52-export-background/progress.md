# Task 52 — progress

## Yêu cầu (11/11/2026)
- Xuất Excel chạy ngầm cho báo cáo 5 (/reports/5), giống Oracle EBS in
  báo cáo: dữ liệu lớn ~1.000.000 record, user chọn mode chạy ngầm thì
  hệ thống tự chạy, user vào Lịch sử báo cáo tải file khi xong.
- User trả lời 4 câu hỏi (11:08): tự vào lịch xem (không thông báo);
  xuất lại sinh run mới (dữ liệu mới); ADMIN setup dọn file manual
  (mặc định) hoặc scheduler xóa sau xxx ngày; xếp hàng giống EBS.

## Bước 2 — Viewer: chế độ xuất (xong, 11/11/2026)
- Select `viewer-export-mode` ("Xuất ngay"/"Chạy ngầm", mặc định "Xuất
  ngay") cạnh nút Xuất Excel; "Chạy ngầm" gọi `request_export` rồi dừng
  hẳn — không poll, không tự tải; hiện link Lịch sử báo cáo (file đã
  DONE sẵn thì hiện link tải file đó). Tests `test_export_background52`
  4/4.

## Bước 3 — Lịch sử: trạng thái export + Thử lại/Hủy + tự làm mới (xong)
- Cột File hiện export mới nhất: "Đang chờ", "Đang xuất NN%", "Lỗi" +
  nút "Thử lại", "Đã hủy", DONE giữ icon tải. Nút "Hủy" cho
  QUEUED/RUNNING. Interval tự làm mới 10s + nút "Làm mới" tay. Tests
  7/7.

## Bước 4 — "Xuất lại" (xong)
- Service `rerun_and_export`: tạo run mới (cùng report/template/tham
  số, version ACTIVE) → chạy ngay → DONE thì `request_export` (định
  dạng theo export mới nhất của run gốc, mặc định XLSX) + audit
  RERUN_AND_EXPORT. Không cần cột cờ/migration (D6 sửa lại). Nút "Xuất
  lại" trong Lịch sử (clientside loading chống bấm 2 lần). Tests 5/5.

## Bước 5 — Dọn file export (xong)
- `app/services/export_retention.py`: setting RECON_APP_SETTING
  (EXPORT_RETENTION_MODE manual|scheduler mặc định manual,
  EXPORT_RETENTION_DAYS mặc định 30, 1..365), service get/set chỉ
  ADMIN, `sweep_old_exports` (chỉ terminal, mốc FINISHED_AT, audit
  actor "worker"). `delete_export` chỉ ADMIN, chỉ terminal, xóa file +
  dòng + audit. Trang /settings mới (menu system_settings, QUẢN TRỊ,
  ADMIN-only, khai báo trong app/ui/menus.py) + nút "Xóa" (ADMIN) ở cột
  File. Worker export sweep tối đa 1 lần/giờ trong vòng lặp. Cập nhật
  count menu 17→18 ở test_menu_sync/test_menu_admin_service. Tests
  13/13.
- Lưu ý: lần đầu test retention chưa patch `get_recon_engine` của module
  mới nên đã ghi 2 key vào DB thật data/recon_app.db — đã xóa; test
  dùng fixture autouse `_patch_retention_engine` trỏ về engine test.
- Hồi quy có sẵn (không do task 52): test_app_startup_menu_sync FAIL
  khi chạy chung sau test_menu_sync (đã kiểm chứng trên base 973a431
  bằng worktree) — chạy lẻ vẫn pass.

## Bước 6 — Kiểm chứng tổng + patch (xong, 11/11/2026)
- Typecheck + ruff sạch; full suite 1511 pass, 6 skipped (chạy lại sau
  khi sửa MATCH→ALL + guard).
- Playwright check-52.py 13/13: chạy ngầm → Lịch sử "Đang chờ" → worker
  xong → tải được .xlsx thật (200); Xuất lại tạo đúng 1 run mới;
  /settings lưu scheduler/7 ngày; không lỗi JS.
- Bài học lớn (D8/D9): 4 callback MATCH riêng cùng ghi 1 output làm cả
  app không mount được; gộp thành 1 callback ALL + guard map số lần
  bấm (kẻo bảng render lại kích nhầm hủy/xóa/xuất-lại ngẫu nhiên).
- Patch ~/workspace/reconhub-task52.patch, áp sau patch 51, không cần
  db-migrate, khởi động lại app và worker. Đang chờ user áp + kiểm
  chứng trên app thật.
