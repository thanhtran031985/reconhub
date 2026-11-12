# Follow-up task 66 — Plan: bảng Đang chạy / Đang chờ + badge + filter

## Bối cảnh

- Trang `app/ui/pages/queue_health.py` (task 66): card có 4 con số hàng đợi +
  bảng "Mục kẹt" (service `get_queue_health` trả `stuck`).
- Service đã fetch sẵn 2 tập rows: `exp_rows` (export QUEUED/RUNNING) và
  `run_rows` (run QUEUED) — bảng mới dùng lại đúng 2 tập này, không thêm query.

## Các bước

1. **Service** (`app/services/worker_health.py`): `get_queue_health` trả thêm
   key `"active"`: mọi export QUEUED/RUNNING + mọi run QUEUED, cùng shape dict
   như item `stuck` (kind, id, run_id, report_name, created_by, created_at,
   age_minutes, status, stale_heartbeat, can_cancel — giữ nguyên quy tắc
   `can_cancel`: export chỉ chủ hủy, run ADMIN hoặc chủ hủy). Sắp xếp theo
   `created_at` tăng dần (cũ nhất trước), tối đa `ACTIVE_LIST_LIMIT = 50`.
   Không đổi key `stuck`, không đổi counts.
2. **UI** (`app/ui/pages/queue_health.py`):
   - `_health_card_body(health, note, note_tone, status_filter="all",
     kind_filter="all")`: thêm section "Đang chạy / Đang chờ (n)" TRÊN section
     "Mục kẹt" (thêm tiêu đề cho cả 2 section). Bảng mới dùng chung helper vẽ
     dòng với bảng kẹt (7 cột: Loại, Mục, Người tạo, Tạo lúc, Chờ bao lâu,
     Trạng thái, Hủy); cột Trạng thái vẽ `status_chip` (RUNNING → Đang chạy,
     QUEUED → Đang chờ); nút Hủy chỉ khi `can_cancel`. Trống thì hiện
     "Không có mục nào đang chạy hoặc chờ."
   - `render_health_card`: thêm hàng filter GIỮA header và body (vùng tĩnh,
     ngoài `queue-health-card-body` — theo mẫu task 60, để đổi filter không
     bị reset khi body vẽ lại): 2 `dmc.Select` size xs — `queue-health-filter-status`
     (Tất cả / Đang chạy / Đang chờ, value `all`/`RUNNING`/`QUEUED`) và
     `queue-health-filter-kind` (Tất cả / Export / Run, value
     `all`/`export`/`run`). Chỉ lọc bảng đang chạy/đang chờ; bảng kẹt giữ nguyên.
   - `handle_health_actions`: thêm 2 Input là 2 Select filter; khi trigger là
     filter (hoặc Làm mới / Hủy) thì vẽ lại body với filter hiện tại. Giữ nguyên
     guard chặn re-fire (skill dash_callback_safety).
3. **Tests-first**: mở rộng `tests/unit/test_queue_health66.py` (service trả
   `active` đủ cả export RUNNING/QUEUED + run QUEUED, sort cũ trước; body vẽ
   bảng active + badge Đang chạy/Đang chờ; filter theo trạng thái và loại lọc
   đúng; bảng kẹt vẫn hiện) + sửa test cũ nếu assert exact keys của
   `get_queue_health` (kiểm tra `test_worker_health62.py`).
4. **Check live mới** `~/workspace/check-66followup-queue-active.py` (port
   8114, DB/storage riêng `/run/pytest-tmp/check66followup.*`, seed như
   check-66 + 1 export RUNNING 10% + 1 run QUEUED): bảng active hiện cả 2
   mục kèm badge; filter Trạng thái = Đang chạy ẩn dòng QUEUED; filter Loại =
   Export ẩn dòng run; Hủy từ bảng active → CANCELLED + mất khỏi bảng; bảng
   kẹt vẫn hiện run kẹt; không lỗi JS (quét CẢ console error VÀ pageerror).
5. **Parent**: review diff → chạy lại targeted tests → chạy lại check live →
   typecheck + ruff → full suite → commit 1 commit
   `66-queue-health-tab-followup: thêm bảng đang chạy/đang chờ, badge trạng thái, bộ lọc`
   → export patch `~/workspace/reconhub-task66-followup.patch` → verify `git am`
   sạch trên worktree ở `374b8c5` → cập nhật MEMORY.md → giao patch (áp sau
   patch 66, KHÔNG cần db-migrate, chỉ khởi động lại app).

## Quyết định

- F1: bảng mới lấy từ cùng service (thêm key `"active"`), không thêm query mới.
- F2: badge trạng thái bằng `status_chip` (RUNNING → Đang chạy, QUEUED → Đang
  chờ); cột Loại giữ chữ Export/Run như bảng kẹt, không thêm badge loại.
- F3: 2 Select filter ở header tĩnh của card (ngoài vùng body vẽ lại); chỉ lọc
  bảng đang chạy/đang chờ, bảng kẹt giữ nguyên.
- F4: không thêm cột tiến độ % cho export đang chạy (ngoài phạm vi).
- F5: không migration; patch follow-up áp sau patch 66, chỉ khởi động lại app.
