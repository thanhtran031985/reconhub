# Task 78 — Progress

- 12/11/2026: user yêu cầu tạo task mới, thêm tính năng notification.
  Parent rà code: app hiện chỉ có toast thoáng qua (178 chỗ dùng),
  không có chuông/danh sách/bảng notification/SMTP. Trình task.md +
  plan.md (phương án A đầy đủ vs B chỉ báo khi lỗi) kèm ràng buộc
  task 52 (xuất-xong mặc định tắt); user chọn phương án A 20:20.
  Parent tách nhánh feat/78-notification-center từ d0a96eb (HEAD
  task 77), giao subagent triển khai theo plan.

- 12/11/2026 (triển khai): test đỏ đã viết (test_notifications78.py, 23
  test) — đỏ ở collection do chưa có service. Làm theo thứ tự:
  metadata (2 bảng) -> migration 0010 (schema + menu/grants idempotent)
  -> menus.py (MenuDef + ROLE_MENUS_SEED) -> service notification.py
  -> chuông header (shell.py: bell + Indicator + Interval 60s + 3
  callback) -> trang /notifications (danh sách phân trang + đánh dấu/
  xóa + cài đặt Switch theo loại) -> hook sự kiện (run_executor DONE/
  FAILED, report_export DONE/FAILED, report_run DONE/FAILED,
  sync_batch_status DONE/PARTIAL, reset_stale_jobs/exports,
  start_migration DONE/FAILED).
- Migration 0010 kiểm chứng: upgrade 0001 -> head trên DB tươi OK
  (2 bảng + index + menu + 3 grants), downgrade về 0009 OK, upgrade
  lại OK. Chạy `uv run poe schema-introspect`: manifest 45 bảng,
  history 63 event; cập nhật test schema cứng số (43->45, 53->55,
  19->21, 61->63, version 0010). Schema tests + notification tests:
  121 pass.
- Sửa vòng tròn import: notification.py lazy-import worker_health
  (D13). Targeted tests (notification + report_run + export 52/54 +
  worker_health 62 + batch pages/wizard 67): 146 pass.
- 12/11/2026: parent review — rà diff sạch: ADMIN có mọi menu
  không bị gỡ (effective_menus) nên đọc được notifications dù không
  có grant riêng; emit không bao giờ raise (try/except trong
  notification.py) nên không hỏng run/export; _fail_export return
  sớm khi rowcount==0 nên export bị hủy không báo lỗi; D18
  (MenuItem/html.A không href, callback điều hướng sau khi đánh dấu
  đọc) đã có test hồi quy. Chạy lại: targeted 298 pass, check-78
  21/21, ruff + typecheck sạch (149 file), git diff --check sạch.
  Full suite đang chạy.
- 12/11/2026: full suite lần 1: 11 failed, 1830 passed, 6 skipped.
  Nguyên nhân: menu mới "notifications" làm lệch 9 test khẳng định
  tập menu chính xác (test_role_service 3, test_perm_effective 4,
  test_page_roles 2: số menu 19→20, OPERATOR 9→10, danh sách dirty-bar
  thiếu menu mới). Parent sửa 9 test (thêm "notifications" vào tập
  menu kỳ vọng); 3 file đó chạy lại 61 pass. Full suite đang chạy
  lại để xác nhận 0 lỗi + tìm 2 lỗi còn lại (chưa xác định).
- 12/11/2026: full suite lần 2: 2 failed, 1839 passed, 6 skipped —
  đều ở tests/integration/test_perm_migration.py: RECON_MENU 14→15
  và RECON_ROLE_MENU (8+6+5+3)=22→25 (migration 0010 thêm menu
  notifications + cấp cho 3 vai trò). Parent sửa 3 assertion; 4
  file liên quan chạy lại 65 pass. Full suite đang chạy lần 3.
- 12/11/2026: full suite lần 3: 1841 passed, 6 skipped, 0 failed.
  (Cây gốc d0a96eb gom 1822 test; +25 test mới task 78 = 1847.
  Con số 1831 trong bản tóm tắt cũ là của cây gộp 76+77, không phải
  của nhánh 78 — không có test nào mất.) 11 lỗi ở 2 lần chạy đầu
  đều là assertion số cứng theo menu mới: 9 ở test_role_service /
  test_perm_effective / test_page_roles + 2 ở
  test_perm_migration (RECON_MENU 14→15, RECON_ROLE_MENU 22→25).
