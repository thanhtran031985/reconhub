# Task 81 — Plan

## Nhánh

`feat/81-queue-health-layout` từ `443b26c` (task 80). Patch áp sau
patch 80, không cần db-migrate, chỉ khởi động lại app.

## Thay đổi

1. `app/ui/pages/queue_health.py`:
   - `layout()`: page_header(title, subtitle, actions=[nút Làm mới
     (giữ id `queue-health-refresh-btn`), Anchor "Xem lịch sử"
     href /report-runs]) + command bar (dmc.Paper withBorder chứa
     2 Select lọc, giữ nguyên id) + Card chính (flex 1) chứa
     `#queue-health-card-body`. Bỏ `render_health_card` dạng cũ
     (header card + filter trong card) — hoặc rút gọn nó thành
     Card chỉ bọc body.
   - Bỏ `maxHeight: 220` ở body div; body `flex: 1, minHeight: 0,
     overflow: auto` (cuộn chung khi tràn). Bỏ chặn 132px của từng
     bảng trong `_health_items_table` (giữ TableScrollContainer
     minWidth 520 cho màn hẹp). Bỏ style px inline (padding/gap
     Box, height 32px từng TableTd, fontSize 13px) → class CSS.
   - Tiêu đề section thành `dmc.Title(..., order=5)`.
   - Độ rộng cột theo % ở TableTh (vd Loại 8 / Mục 30 / Người tạo
     12 / Tạo lúc 17 / Chờ bao lâu 12 / Trạng thái 13 / Hủy 8 —
     chỉnh sao cho "Tạo lúc" vừa đủ ở 1366, không vỡ nowrap).
   - Gợi ý mẫu: xem `app/ui/pages/notifications.py` + class
     `.notif-*` trong `app/ui/assets/custom.css` (task 79) để theo
     cùng cách làm (class trong assets, không style inline).
2. `app/ui/assets/custom.css`: thêm class `.qh-*` (padding/gap
   trang, cao hàng, cỡ chữ bảng).
3. `tests/unit/test_queue_health66.py`: thêm test — nút Làm mới
   nằm trong page header (tìm theo id trong layout), 2 Select nằm
   ngoài body, tiêu đề section là Title order=5, body không còn
   maxHeight 220, TableTh có độ rộng %. Test cũ (tìm Select theo
   id) phải tiếp tục pass.
4. Check live: mở rộng `~/workspace/probe-queue-health-layout.py`
   (seed 1 run QUEUED 10h, đã có): ở 1366x768 và 1440x900 —
   scrollHeight == innerHeight, không cuộn ngang, dòng kẹt hiện
   hết mà không cần cuộn body (body scrollHeight == clientHeight
   với 1+1 dòng), "Tạo lúc" vẫn dạng đầy đủ, quét CẢ console
   error VÀ pageerror (bỏ qua ERR_TUNNEL_CONNECTION_FAILED).
   Chụp 2 ảnh đính vào progress.
5. Ruff + typecheck (file đổi) → full suite → parent review,
   commit, patch, verify `git am` trên worktree ở 443b26c.

## Lưu ý

- Giữ nguyên id `queue-health-refresh-btn`,
  `queue-health-filter-status`, `queue-health-filter-kind`,
  `queue-health-card-body` và callback `handle_health_actions`
  (chỉ đổi layout, không đổi luồng).
- Không chạy `uv run poe format` (drift có sẵn). Không commit
  `docs/tasks/dashboard.html` (file tự sinh).
