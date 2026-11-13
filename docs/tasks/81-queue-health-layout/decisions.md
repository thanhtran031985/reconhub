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
- D6 (follow-up 13/11/2026, user yêu cầu sau khi áp 80+81): kết
  quả bấm Hủy hiện bằng toast notification (`notify_success` /
  `notify_error` vào `html.Div#queue-health-alert`, mẫu
  report_runs "Đã hủy export.") thay cho banner alert_box trong
  body. Banner xanh chiếm chỗ + đẩy nội dung xuống; toast tự ẩn
  sau 4s/6s, không chiếm chỗ. Alert_box vẫn giữ cho trạng thái
  lỗi tải dữ liệu (không tải được trạng thái hàng đợi) và cho
  màn login/không quyền — chỉ đổi phản hồi hành động Hủy.
- D7 (follow-up 81, lỗi thật tìm ra khi check live): 2 nút Hủy trùng
  id dict khi cùng 1 mục hiện ở cả 2 bảng → Dash trả n_clicks=None
  khi bấm nút ở bảng Đang chạy / Đang chờ và guard chặn hủy (đã chứng
  minh live: bấm nút thứ 2 thì hủy được, nút thứ 1 thì không). Fix:
  id nút mang thêm `section` ("active"/"stuck") để luôn duy nhất;
  Input pattern-matching thêm `"section": ALL` (pattern thiếu key thì
  không khớp id có key đó). Lỗi này có sẵn từ task 66 (chỉ lộ khi mục
  vừa ở bảng active vừa ở bảng kẹt); user từng hủy được run #51 vì
  run đó (hoặc nút bấm) không rơi vào trường hợp trùng.
- D8 (follow-up 81): toast phải đi qua `dmc.NotificationContainer`
  + prop `sendNotifications` (list dict, DMC 2.8.1) — `dmc.Notification`
  trần trong html.Div KHÔNG render (đã chứng minh live: response có
  đủ Notification nhưng div vẫn trống 6s); đổi sang Container +
  children cũng không hiện (container 2.x không render children
  thành toast). Container toàn cục ở shell.py:839 đã có sẵn
  (top-right, zIndex 9999) nhưng KHÔNG có id nên không callback nào
  nhắm tới được — giữ nguyên (sửa toàn app là việc riêng, ngoài
  phạm vi follow-up này); trang này dùng container riêng theo id.
  `notify_success`/`notify_error` (trả component) giữ nguyên cho
  178 chỗ dùng cũ; follow-up này thêm helper trả dict cho
  sendNotifications.
