# Task 79 — Decisions

- D1: theo ảnh thiết kế user gửi (NOTIFICATION-01); menu "Thông
  báo" chuyển sang nhóm QUẢN TRỊ, order 30.
- D2: cài đặt dạng Modal theo thiết kế. Quy tắc ui-dash cấm Modal
  làm form dài — form này ngắn (1 toggle tổng + 12 switch theo
  nhóm, chỉ bật/tắt) nên dùng Modal được; bỏ khối cài đặt inline
  cũ khỏi trang.
- D3: hiển thị đủ 12 loại sự kiện trong modal (thiết kế chỉ vẽ 6
  mẫu); ẩn 6 loại còn lại sẽ mất chức năng đã có ở task 78.
- D4: công tắc tổng "Nhận thông báo trong ứng dụng" lưu dạng pref
  đặc biệt EVENT_TYPE='ALL' trong RECON_NOTIFICATION_PREF (thiếu
  dòng = BẬT); `is_enabled` kiểm tra tổng trước rồi mới tới từng
  loại; `get_prefs`/`set_prefs` xử lý 'ALL' riêng, không thêm vào
  EVENT_TYPES.
- D5: panel chi tiết cần tham chiếu entity: migration 0011 thêm
  RELATED_TYPE/RELATED_ID (nullable) vào RECON_NOTIFICATION; emit
  ghi luôn lúc tạo; detail resolver đọc theo từng loại entity,
  SYSTEM thì chỉ title/message/link.
- D6: không thêm loại sự kiện mới (đồng bộ dữ liệu/bảo trì
  deferred), không email.
- D7: không cuộn trang ở ≥1366×768 (chỉ list/panel cuộn trong);
  dưới 900px xếp dọc, trang được cuộn (theo quy tắc ui-dash).
- D8: chuyển menu không cần migration — `sync_from_code`
  (menu_sync.py:188-204) tự cập nhật SOURCE_GROUP/SOURCE_ORDER từ
  code lúc app khởi động (xác minh ở preflight).
- D9: mã hiển thị ở panel chi tiết suy từ id: RUN `RUN_{id:05d}`,
  REPORT_RUN `RPT_{id:05d}`, EXPORT `EXP_{id:05d}`, BATCH
  `BATCH_{id:05d}`; SYSTEM không có mã.
- D10: mọi giờ hiển thị là naive UTC như DB đang lưu (nhất quán
  task 78); giờ tương đối tính theo UTC hiện tại.
- D11: bỏ nút xóa từng dòng khỏi list UI (thiết kế không có);
  service `delete_notification` giữ nguyên để tương thích API.
- D12: thứ tự list đổi sang CREATED_AT desc (bỏ chưa-đọc-trước)
  để nhóm theo ngày mạch lạc; trạng thái chưa đọc thể hiện bằng
  chấm xanh ở UI. Đổi contract task 78 — test
  `test_list_unread_first_and_paging` viết lại thành
  `test_list_newest_first_and_paging`.
- D13: sao chép mã dùng clientside callback ghi clipboard (mẫu
  data_model.py: ActionIcon `notif-detail-copy-btn` -> server ghi
  `notif-copy-store` -> clientside `navigator.clipboard.writeText`
  + toast xác nhận). Ban đầu dùng `dcc.Clipboard` nhưng check live
  thấy nó log cảnh báo React defaultProps của FontAwesomeIcon vào
  console (J0 không sạch) nên đổi; nút icon có tooltip, không phải
  nút có nhãn như thiết kế vẽ.
- D14: dòng được chọn phải giữ class gốc `notif-row` và thêm
  `notif-row-selected` (trước đây class bị thay hẳn nên dòng chọn
  mất padding/cursor/hover); phát hiện khi probe live: đếm
  `.notif-row` chỉ ra 1/2 dòng.
- D15: `dmc.Button` (DMC 2.8.1) KHÔNG nhận prop `href` — nút
  "Xem tất cả →" ở footer popover dùng `dmc.Anchor` thay thế.
  `dmc.Box` cũng KHÔNG nhận prop `gap` — gap của `.notif-page`
  đưa vào CSS class.
- D16: `test_sidebar_empty_group_hidden` đổi thành
  `test_sidebar_quan_tri_visible_for_viewer_via_notifications` —
  từ task 79 VIEWER thấy nhóm QUẢN TRỊ (chỉ 1 mục Thông báo) nên
  không còn nhóm trống nào để ẩn với VIEWER.
- D17: kỳ vọng S0 của check-79 là footer "1 thông báo · 1 chưa
  đọc" (B WORKER_DOWN hôm qua đã seed trước S0, trong cửa sổ 7d),
  không phải trang trống hoàn toàn.
- D18: nút Mở/Sao chép trong panel chi tiết LUÔN render (ẩn bằng
  display:none khi dòng không có link/mã) vì Dash yêu cầu Input
  của callback phải tồn tại trong layout — panel SYSTEM không
  render nút làm callback list/copy chết, mọi bộ lọc sau đó kẹt
  (lỗi renderer "A nonexistent object was used in an Input ...
  notif-detail-open-btn"). Nút ẩn không bấm được; nhánh mở/copy
  vẫn guard link/mã rỗng. Áp dụng cho cả 3 đường return của
  `_detail_panel` (trống / lỗi / thường) qua helper
  `_action_buttons` — lọc ra 0 dòng cũng từng làm chết callback.
- D19: callback list ở /notifications đồng bộ luôn badge chuông
  header (`app-notif-indicator` label/disabled,
  allow_duplicate=True) theo số chưa đọc mới — như bấm mục trong
  popover đã làm; nếu không, badge kẹt tới tick Interval 60s hoặc
  reload sau khi đánh dấu đọc/mở kết quả trên trang.
- D20: test `test_failed_run_summary_keeps_source_sql` (task 67) FAIL
  khi chạy cùng bộ targeted lớn (notification+menu+schema+report-run
  +export+worker-health+batch+reporting) nhưng PASS khi chạy riêng
  và PASS cùng các file notification — đã xác minh cùng bộ đó cũng
  FAIL ở commit gốc 4758088 (worktree, trước task 79): nhiễu chéo
  có sẵn giữa các file test, không do task 79. Full suite là cổng
  kiểm chứng cuối.
- D21: icon trạng thái dùng variant="filled" (vòng tròn đặc như ảnh
  thiết kế) thay vì "light" nhạt; glyph iconify vẫn cần mạng để tải
  (máy user có mạng thì hiện).
- D22: nút sao chép là Button có nhãn "Sao chép mã run" (như thiết
  kế), giữ aria-label cũ để check live cũ vẫn đúng.
- D23: menu Thông báo order 70 trong QUẢN TRỊ (order 30 trùng
  menu_admin; nav sort theo order nên trùng là mơ hồ).
- D24: khôi phục nút Xóa (task 78 có, D11 bỏ nhầm): nút Xóa trong
  panel + modal xác nhận (modal_confirm) + nhánh xóa trong callback
  danh sách; xóa xong dòng còn lại tự chọn (hành vi _list_body).
- D25: callback modal xóa guard n_clicks (hồi quy live): nút Xóa
  nằm trong panel bị vẽ lại, remount bắn callback với n_clicks=None
  làm modal tự mở sau mỗi lần lọc/phân trang.
