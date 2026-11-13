# Task 86 — /batches: cho xóa bộ đối soát đã có lần chạy (bỏ chặn "đã có N lần chạy")

## Yêu cầu (user 14:03 13/11/2026, trang /batches)
Bỏ ràng buộc: "Không thể xóa bộ đối soát 'BATCH_PW_1794045016' đã có 8 lần chạy trong hệ thống. Hãy sử dụng chức năng Lưu trữ."

## Phân tích (parent đọc code trước khi giao)
- Chặn nằm ở `delete_batch_def` (app/services/batch_def.py:424): đếm `RECON_BATCH_RUN.BATCH_DEF_ID == def_id`, nếu > 0 → CONFLICT với thông báo trên; ngược lại xóa `RECON_BATCH_DEF_ITEM` rồi `RECON_BATCH_DEF` + audit.
- Chặn này không phải rào thừa: các FK sau trỏ về bộ/lần chạy của bộ, xóa bộ khi còn lần chạy mà không dọn bảng con sẽ lỗi FK (Oracle chặn chắc; SQLite tùy PRAGMA):
  - `RECON_BATCH_RUN.BATCH_DEF_ID → RECON_BATCH_DEF.ID` (not null).
  - `RECON_BATCH_RUN_ITEM.BATCH_RUN_ID → RECON_BATCH_RUN.ID`, `BATCH_DEF_ITEM_ID → RECON_BATCH_DEF_ITEM.ID`.
  - `RECON_BATCH_RUN_FILE.BATCH_RUN_ID → RECON_BATCH_RUN.ID`, `BATCH_RUN_ITEM_ID → RECON_BATCH_RUN_ITEM.ID`.
  - `RECON_BATCH_DEF_ITEM.BATCH_DEF_ID → RECON_BATCH_DEF.ID`.
  - `RECON_RUN.BATCH_RUN_ID → RECON_BATCH_RUN.ID` (nullable), `RECON_RUN.BATCH_RUN_ITEM_ID → RECON_BATCH_RUN_ITEM.ID` (nullable) — các run đối soát con trỏ về lần chạy bộ.
- `RECON_BATCH_RUN_ITEM.CURRENT_RUN_ID` KHÔNG có FK (ghi chú trong metadata: tránh tham chiếu vòng), nên không cần xử lý riêng.
- UI: nút Xóa ở `app/ui/pages/batch_defs.py` (id `bdef-action-delete`) → modal `bdef-delete-modal` (mô tả hiện tại: "chỉ xóa được khi chưa có lần chạy nào") → callback `_run_list_action` gọi `delete_batch_def`, lỗi hiện qua `notify_error(res.message)`.
