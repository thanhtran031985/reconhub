# Plan — Task 64: Sửa layout modal chuyển Oracle (2 card + stepper hiện item đang chạy)

## Bối cảnh
- Task 63 (commit `2219105`) đã có modal stepper: `dmc.Modal` size lg, bên trong là `dmc.ScrollArea(h=380)` ôm stepper + checklist gộp chung → modal bị scroll. File chính: `app/ui/pages/data_sources.py` (`_render_mig_stepper`, `_render_mig_report`, các callback `handle_mig_modal`, `handle_mig_run`, `handle_mig_fake_tick`, `handle_mig_real_tick`, `handle_mig_real_switch`); helper checklist: `app/services/migration_checklist.py` (không đổi).
- Branch hiện tại: `feat/58-history-cancel-filter`, HEAD `2219105` (task 63). Task 64 xếp chồng lên trên (như task 58–63).

## Bước 1 — Modal vừa trang, không scroll
- Đổi modal sang size `xl`, chiều cao cố định vừa khung nhìn (vd ~88vh), layout flex cột với `min-height: 0`: header một dòng | dòng tóm tắt + switch | vùng 2 card `flex: 1, min-height: 0` | footer cố định (Đóng / Bắt đầu).
- Bỏ `ScrollArea(h=380)` ôm toàn bộ stepper. Chỉ card detail có `ScrollArea` riêng cho checklist dài (vd bước 4 có 43 bảng).
- Nghiệm thu ui-dash: Playwright ở 1366×768 và 1440×900: trong modal không có scroll dọc trang, không scroll ngang.

## Bước 2 — Chia 2 card: stepper + detail (Master–Detail)
- Card trái "Tiến trình" rộng cố định ~320–340px: stepper dọc 6 bước (vòng tròn đánh số, đường kẻ nối, xong ✓ xanh / đang chạy nền primary / chờ vòng xám), bấm được để chọn bước.
- Card phải "Chi tiết bước" flex 1: header (tên bước + badge trạng thái + "n/m việc xong") + checklist dòng con của bước đang chọn + (bước 6 khi xong) bảng đối chiếu + 4 bước làm tay.
- Bước đang chọn lưu ở `dcc.Store` (vd `ds-mig-selected-step`, mặc định = bước đang chạy, nếu chưa chạy thì bước 1); bấm bước trong stepper → store đổi → detail vẽ lại. Các callback hiện viết `ds-mig-stepper.children` phải vẽ lại cả 2 card (hoặc tách Output detail riêng — giữ nguyên tắc một Output một callback, dùng `allow_duplicate` có lý do như task 63).
- Click bước: dùng `html.Div`/`dmc` có `n_clicks` với pattern-matching `ALL` + `triggered_id` (xem `~/workspace/custom-skills/dash_callback_safety/SKILL.md`); không dùng `MATCH` output trùng nhau.

## Bước 3 — Stepper hiện item đang chạy
- Helper thuần mới (đặt trong `app/services/migration_checklist.py` hoặc cạnh `_render_mig_stepper`): với một bước, tính `done/total` và `running_item` = dòng chờ đầu tiên khi bước đang chạy (bảng chép theo thứ tự nên dòng chờ đầu tiên chính là item đang làm).
- Dòng phụ dưới tên bước:
  - xong: "✓ n/n việc xong" (xanh);
  - đang chạy: "Đang: <label item>" (xanh dương, ellipsis) + "n/m bảng xong";
  - chờ: "Chờ • 0/m việc" (dimmed).
- Trong card detail: item đang làm tô riêng (chấm xanh + nhãn "Đang chạy", nền nhạt primary); dòng xong ✓ xanh kèm detail (vd "Đích: 393 dòng"); dòng chờ ○ dimmed.
- Không đổi data model, không thêm cột, không đổi logic tick/poll.

## Bước 4 — Kiểm chứng
- Tests-first: test unit cho helper tính running item + render stepper (dòng phụ đúng 3 trạng thái) + render detail theo bước chọn (kể cả bước 6 hiện báo cáo khi xong). Cập nhật test task 63 / check script nếu text render đổi.
- Check live Playwright `~/workspace/check-64-migration-modal-layout.py` (port 8110, DB/storage riêng `/run/pytest-tmp/check64.*`, seed + launcher như check-63): modal mở không scroll (documentElement.scrollHeight <= innerHeight trong modal, không scroll ngang) ở 1366×768; đủ 2 card; bấm bước 2 → detail hiện checklist bước 2; chạy fake → stepper bước 4 hiện "Đang: Sao chép bảng …" + số đếm tăng dần; detail tô item đang chạy; quét cả console error VÀ pageerror.
- Full suite xanh (parent chạy sau review), commit một commit `64-migration-modal-layout: ...`, export patch, verify `git am` sạch trên worktree ở `2219105`.

## Quyết định chờ ghi
- D1: running item suy ra từ dòng chờ đầu tiên, không thêm trạng thái "running" vào checklist (theo yêu cầu user đã duyệt).
- D2: báo cáo đối chiếu + next steps nằm trong detail của bước 6 khi xong (không thêm vùng thứ 3 dưới 2 card).
