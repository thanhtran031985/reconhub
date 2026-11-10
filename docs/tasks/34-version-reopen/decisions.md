# Decisions — 34-version-reopen

- **Q0 (2026-11-10):** Mở lại từ ACTIVE và DRY_RUN_OK → DRAFT. DRAFT đã là
  DRAFT (báo lỗi, không làm gì), ARCHIVED không mở lại.
- **Q1 (2026-11-10):** Khi mở lại version ACTIVE, gỡ `ACTIVE_VERSION_ID`
  của template về NULL. Template tạm không có version ACTIVE cho tới khi
  kích hoạt lại; Viewer/tạo run/batch báo "chưa kích hoạt" đúng trạng thái.
- **Q2 (2026-11-10):** Dry-run ACTIVE là preview thuần túy: chạy query, trả
  rows, ghi audit `DRY_RUN_VERSION`, không đổi trạng thái. DRAFT/DRY_RUN_OK
  giữ hành vi cũ (thành công → DRY_RUN_OK).
- **Q3 (2026-11-10):** Chỉ ADMIN được mở lại version (như `delete_report`).
- **Q4 (2026-11-10):** Nút "Mở lại để sửa" đặt ở bước 6 trong wizard (cả màn
  hình ACTIVE và màn hình DRY_RUN_OK), kèm modal xác nhận nêu rõ báo cáo tạm
  ngưng phục vụ. Sau khi mở lại thành công, wizard nhảy sang bước 4
  (Cấu hình cột) vì đó là nhu cầu sửa bảng cũ. Không thêm vào menu 3 chấm
  ở danh sách trong task này.
