# Task 79 — Plan: trung tâm thông báo theo thiết kế

Ảnh thiết kế: `~/workspace/user/media_library/image/Designer__1.png`.
Đọc thêm: `.agents/rules/ui-dash.md`, `designs/tokens.json`,
`app/services/notification.py`, `app/ui/pages/notifications.py`,
`app/ui/layout/shell.py` (chuông).

## Thiết kế đã chốt

1. **Migration 0011** (mới, sau 0010): thêm 2 cột nullable vào
   RECON_NOTIFICATION: RELATED_TYPE String(40) (RUN / REPORT_RUN /
   EXPORT / BATCH / SYSTEM), RELATED_ID BigInteger. Emit hiện tại
   (`notify_for_run/report_run/export/batch`) đã biết entity → ghi
   luôn 2 cột này lúc tạo (không đổi chữ ký hàm ngoài việc thêm
   tham số nội bộ). `notify_admins` ghi SYSTEM/NULL.
   Menu: đổi MenuDef "notifications" sang nhóm QUẢN TRỊ, order 30;
   kiểm tra `sync_menus` có tự cập nhật SOURCE_GROUP/SOURCE_ORDER
   từ code không — nếu không, migration 0011 cập nhật dòng
   RECON_MENU (idempotent) + test `test_perm_migration` cập nhật
   theo (số menu không đổi, chỉ đổi nhóm).
2. **Service `notification.py`**: mở rộng `list_notifications` thêm
   `q` (tìm trong TITLE/MESSAGE), `event_type` (mã loại hoặc rỗng
   = tất cả), `time_range` ("7d" | "30d" | "all"; lọc CREATED_AT).
   Giữ `unread_only`. Thêm `get_notification_detail(ctx, id)`:
   trả notification + `entity` resolve theo RELATED_TYPE:
   - RUN → RECON_RUN: mã `RUN_{id:05d}`, tên bộ (qua batch nếu có),
     tên template, thời gian chạy (FINISHED_AT − STARTED_AT),
     nguyên nhân = ERROR_MSG/ERROR_CODE.
   - REPORT_RUN → RECON_REPORT_RUN: tên báo cáo, tên template, thời
     gian chạy, lỗi.
   - EXPORT → RECON_RPT_EXPORT: tên báo cáo, tên file, thời gian
     chạy, lỗi.
   - BATCH → RECON_BATCH_RUN: tên bộ, số mục xong/lỗi, thời gian
     chạy, lỗi.
   - SYSTEM/không có entity → chỉ title/message/link.
   `is_enabled` kiểm tra thêm công tắc tổng (xem mục 5): tắt thì
   mọi loại đều không tạo thông báo.
3. **Trang /notifications → Master–Detail, không cuộn trang**
   (≥1366×768; dưới 900px xếp dọc, trang được cuộn — theo quy tắc
   ui-dash): header 1 dòng (Title order=4 + subtitle, nút "Đánh
   dấu tất cả đã đọc" + "Cài đặt" bên phải) | command bar trong
   Paper (search + 3 Select + Làm mới) | vùng chính flex 1
   min-height 0: list trái (ScrollArea, nhóm HÔM NAY/HÔM QUA/ngày
   cũ, giờ tương đối, icon trạng thái, chấm chưa đọc, dòng chọn
   highlight) + panel phải rộng 320 (token `size-detail-panel`,
   nền surface-2, viền trái, ScrollArea riêng) | footer cố định:
   "N thông báo · M chưa đọc · Cập nhật HH:MM:SS" + Pagination.
   Phân trang server-side giữ nguyên (20/trang). Bỏ style inline
   px → token. Bấm 1 dòng → chọn (không điều hướng ngay); nút
   "Mở kết quả Run" trong panel mới điều hướng (đánh dấu đã đọc
   trước, như D18 task 78). Nút "Sao chép mã run" copy mã vào
   clipboard (dcc.Clipboard hoặc clientside).
4. **Popover chuông (shell.py)**: thêm tab Tất cả / Chưa đọc
   (lọc panel theo tab) + footer "Đánh dấu tất cả đã đọc" và
   "Xem tất cả →". Giữ 5 mục mới nhất mỗi tab; bấm mục vẫn đánh
   dấu đọc rồi điều hướng (D18).
5. **Cài đặt → Modal** (theo thiết kế; form ngắn: 1 toggle tổng +
   12 switch theo nhóm nên dùng Modal được — xem decisions D2):
   nút "Cài đặt" mở `dmc.Modal` ("Cài đặt thông báo", "Chỉ áp dụng
   cho tài khoản của bạn."): công tắc tổng "Nhận thông báo trong
   ứng dụng" + đủ 12 loại theo EVENT_GROUPS (thiết kế chỉ vẽ 6
   mẫu, hiển thị đủ 12 để không mất chức năng) + Hủy/Lưu thay đổi.
   Công tắc tổng lưu dạng pref đặc biệt EVENT_TYPE='ALL' trong
   RECON_NOTIFICATION_PREF (thiếu dòng = BẬT); `get_prefs` /
   `set_prefs` xử lý 'ALL' riêng (không thêm vào EVENT_TYPES).
   Bỏ khối cài đặt inline cũ khỏi trang.
6. **Giờ tương đối**: hàm dùng chung trong page ("2 phút",
   "1 giờ", "Hôm qua 16:20", ngày cũ "12/11/2026 16:20").

## Các bước

1. Preflight: nhánh đúng `feat/79-notification-center-design`
   từ 4758088; cây sạch trừ `docs/tasks/71-.../progress.md`
   (của parent); DB dev đã ở 0010; port check live tiếp theo 8130.
2. Tests đỏ trước: service (lọc q/type/time; detail từng loại
   entity + SYSTEM fallback; công tắc tổng tắt → không tạo;
   RELATED_* ghi đúng); handler chọn dòng/panel, tab popover.
3. Migration 0011 + service + detail resolver.
4. UI: trang Master–Detail + command bar + footer; popover tabs;
   modal cài đặt; bỏ prefs inline + px.
5. Check live `~/workspace/check-79-notification-design.py`
   (port 8130, DB riêng): seed run lỗi + export lỗi + batch +
   worker-down → lọc/tìm/nhóm ngày/giờ tương đối; chọn dòng →
   panel đủ trường + nút Mở kết quả + copy mã; popover tab Chưa
   đọc + đánh dấu tất cả; tắt công tắc tổng → run lỗi mới không
   sinh thông báo; bật lại → sinh; footer tổng/chưa đọc/giờ cập
   nhật; JS sạch (CẢ console error VÀ pageerror).
   **Screenshot nghiệm thu 1366×768, 1440×900, 390×844** đính
   vào báo cáo bước; kiểm tra không cuộn trang ở 2 cỡ desktop
   (`scrollHeight <= innerHeight`, không cuộn ngang).
6. Typecheck/ruff + full suite → commit → patch (áp sau patch 78,
   CẦN db-migrate 0011, khởi động lại app + worker).

## Lưu ý

- Không thêm loại sự kiện mới, không email, không sửa bug ngoài
  scope trừ khi là blocker + có regression test.
- Trang Dash KHÔNG import lẫn nhau; callback mới: Output dùng ở
  >1 callback phải có allow_duplicate=True ở tất cả trừ một.
