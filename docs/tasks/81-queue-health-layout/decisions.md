# Task 81 — Decisions

- D1: bỏ hẳn hàng header của card (tiêu đề "Sức khỏe hàng đợi &
  worker" trùng tiêu đề trang); nút chính lên page_header
  (tham số `actions` đã có sẵn).
- D2: bỏ chặn 132px từng bảng, thân card cuộn chung khi tràn
  (thay vì mỗi bảng cuộn riêng) — mục kẹt là nội dung chính của
  trang, không được giấu sau 2 lớp cuộn.
- D3: độ rộng cột theo %, không dùng px (chuẩn ui-dash cấm px
  trong page).
- D4: class CSS theo tiền lệ task 79 (`.notif-*` → `.qh-*` trong
  app/ui/assets/custom.css), không style inline.
- D5: 2 Select lọc giữ `w=170`/`w=140` (prop sizing của Mantine,
  không phải style px inline) — theo đúng tiền lệ task 79
  (command bar notifications dùng `w=220/130/150`). Chỉ độ rộng
  cột bảng dùng style với % (theo plan, không px).
