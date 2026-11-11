# Task 60 — history-dashboard-paging (điều tra, CHƯA fix)

## Yêu cầu (user, 17:52 11/11/2026)
http://127.0.0.1:8050/history và trang dashboard — "xem trang này,
bấm qua phân trang có load lại layout không? đang thấy reload".

## Kết luận điều tra (live, seed 25 run DONE, app cổng 8102)
**KHÔNG có full page load** ở cả 2 trang: URL không đổi, không có
navigation event, shell/header/sidebar không render lại. Cái user
thấy là "reload giả" do 3 thứ cộng lại mỗi lần bấm phân trang:
(1) spinner `dcc.Loading` phủ kín vùng bảng/card,
(2) toàn bộ dòng bảng bị gỡ và vẽ lại từ đầu,
(3) focus rớt về BODY (nút phân trang bị hủy/vẽ lại).

Bằng chứng: /history sang trang 2 — spinner hiện ~95ms sau khi bấm,
20 node gỡ / 5 node thêm, dòng mới hiện sau ~511ms (về trang 1:
~724ms), focus rớt về BODY. Dashboard card Run gần đây — spinner
hiện ~47ms, tắt ~216ms, 15 node gỡ, dòng mới sau ~210ms, focus rớt
về BODY. Card "Tỉ lệ lệch theo template" chưa kiểm chứng live được
(seed không có template nào có summary nên card trống, không hiện
phân trang) — code cùng pattern nên cùng lỗi.

## Nguyên nhân gốc
- /history (`app/ui/pages/history.py`): `update_history_table`
  Output là `history-table-container.children` +
  `history-title.children`; mỗi lần đổi trang gọi lại `list_runs`
  rồi dựng lại toàn bộ `render_runs_table(...)` — bảng 20 dòng +
  thanh phân trang (chính `dmc.Pagination` nằm trong đó, dòng 553)
  — rồi thay thế toàn bộ children. Container nằm trong
  `dcc.Loading(id="history-loading")` (dòng 733).
- Dashboard (`app/ui/pages/dashboard.py`):
  `_update_recent_card` / `_update_diff_card` (dòng 658–671) Output
  là `dashboard-recent-card.children` /
  `dashboard-diff-card.children`, trả về toàn bộ card dựng lại từ
  store. Phân trang chỉ cắt slice client-side từ store (không query
  server) mà vẫn vẽ lại cả card. Cả 2 card nằm trong
  `dcc.Loading(id="dashboard-loading")` bao quanh
  `dashboard-content-container` (dòng 516).

## Cách fix đề xuất (xem plan.md) — CHỜ USER DUYỆT
1. Tách Pagination ra khỏi vùng bị vẽ lại (đặt cố định trong
   layout, callback chỉ cập nhật dòng bảng + dòng "Hiển thị x–y").
2. Bỏ spinner khỏi thao tác phân trang.
3. /history (nâng cấp): chuyển sang AG Grid như /report-runs.
4. Dashboard (nâng cấp): chỉ cập nhật `TableTbody` trong card.

## Lưu ý điều tra
- Điều tra trên worktree tạm ở commit `4cdafb3` (task 57) vì lúc đó
  cây chính đang dở dang (lỗi cú pháp tạm thời ở report_runs.py
  dòng 378 do task 58 đang sửa). `history.py` và `dashboard.py` ở
  đó giống hệt nhánh hiện tại nên kết quả vẫn đúng. Không sửa bất
  cứ file nào trong repo. Script kiểm chứng:
  `~/workspace/check-history-paging.py`,
  `check-history-paging2.py`, `check-history-paging3.py`.
- Quan sát phụ chưa kết luận: 1 lần khởi động lạnh, bảng /history
  lần đầu không hiện trong 20s (retry thì được) — có thể chỉ là
  warm-up, cần theo dõi thêm.
