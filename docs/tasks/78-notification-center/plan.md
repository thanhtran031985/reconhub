# Task 78 — Plan: trung tâm thông báo trong app (phương án A đầy đủ)

## Thiết kế (chờ user duyệt phương án A hoặc B)

1. **Bảng mới `RECON_NOTIFICATION`** (migration Alembic, chạy được
   SQLite + Oracle): ID, USER_ID (người nhận), TYPE (RUN_FAILED,
   RUN_DONE?, EXPORT_FAILED, EXPORT_DONE, BATCH_FAILED, BATCH_DONE?,
   WORKER_DOWN, QUEUE_STUCK, MIGRATION_DONE), TITLE, MESSAGE, LINK
   (href tới run/báo cáo/lịch sử), IS_READ, CREATED_AT. Index
   (USER_ID, IS_READ, CREATED_AT).
2. **Service mới `app/services/notification.py`** (ServiceResult,
   tiếng Việt): `create_notification(ctx/người nhận, type, title,
   message, link)`; `list_notifications(ctx, page, page_size)` (chưa
   đọc trước, phân trang); `unread_count(ctx)`; `mark_read`,
   `mark_all_read`, `delete_notification`. Chỉ thấy thông báo của
   mình; ADMIN thấy thông báo hệ thống (worker/migration).
3. **Cài đặt theo user** (bảng RECON_APP_SETTING khóa theo user hoặc
   cột trên RECON_USER — chốt lúc làm): bật/tắt từng loại sự kiện.
   Mặc định: lỗi BẬT; EXPORT_DONE/RUN_DONE/BATCH_DONE TẮT (theo
   task 52: tự vào lịch xem, không thông báo).
4. **Nối sự kiện vào các điểm chuyển trạng thái đã có** (không đổi
   luồng chạy): run_executor (run FAILED → chủ run; DONE chỉ khi user
   bật), export worker (export FAILED/DONE), sync_batch_status
   (batch FAILED/DONE), worker heartbeat (worker down/stuck → ADMIN),
   migration hoàn tất (→ ADMIN).
5. **UI**: chuông + badge số chưa đọc ở header shell (poll nhẹ hoặc
   đếm lúc mở trang — chốt lúc làm, tránh Interval nặng); bấm chuông
   mở panel danh sách mới nhất (bấm 1 mục → tới link + đánh dấu đã
   đọc); trang `/notifications` xem tất cả + đánh dấu tất cả đã đọc;
   cài đặt loại sự kiện ở trang này hoặc /settings.

## Phương án B (chỉ báo khi lỗi)

- Như trên nhưng chỉ 3 loại sự kiện: RUN/EXPORT/BATCH FAILED (chủ
  run) + WORKER_DOWN/QUEUE_STUCK (ADMIN). Không có DONE, không có
  cài đặt từng loại, không có trang cài đặt. Bảng + service + chuông
  giữ nguyên (để sau này mở rộng).

## Các bước (chung)

1. Test đỏ trước: service tạo/liệt kê/đếm/đánh dấu đã đọc (phân
   quyền: chỉ thấy của mình); handler chuông.
2. Migration + service + nối sự kiện.
3. UI chuông + panel + trang danh sách (+ cài đặt nếu phương án A).
4. Check live: tạo run lỗi → chuông tăng 1, bấm vào tới đúng run +
   đã đọc; run xong (DONE) không sinh thông báo khi tắt; ADMIN thấy
   thông báo worker; JS sạch (quét CẢ console error VÀ pageerror).
5. Typecheck/ruff + full suite → commit → patch (áp sau patch 77,
   CẦN db-migrate, khởi động lại app + worker).

## Lưu ý

- Nhánh `feat/78-notification-center` tách từ HEAD task 77 sau khi
  user duyệt phương án.
