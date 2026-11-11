# Task 61 — grid Lịch sử báo cáo báo lỗi console overlayNoRowsTemplate

## Yêu cầu
Mở trang Lịch sử báo cáo (/report-runs), console báo:
`{prop: overlayNoRowsTemplate} Blocked a string that AG Grid would evaluate, to prevent XSS attacks. If you really want this, use dangerously_allow_code`
(kèm Error Component Stack do React DevTools gắn thêm — thực chất chỉ là
console.error, không throw, không crash trang).

Lỗi này xuất hiện cả khi user đang ở /reports/5 vì console giữ lại log
khi chuyển trang SPA trong cùng tab — viewer tự nó sạch.

## Nguyên nhân gốc
- Grid `report-runs-grid` truyền `overlayNoRowsTemplate` là chuỗi tĩnh
  ("Chưa có run nào. Chạy một báo cáo ở Trung tâm báo cáo để xem lịch
  sử tại đây.") qua `dashGridOptions`.
- dash-ag-grid 35.3.1 chặn mọi chuỗi ở vị trí hàm (`overlayNoRowsTemplate`
  nằm trong tập guarded `_e`) khi grid thiếu `dangerously_allow_code=True`.
- Đây là grid duy nhất trong app thiếu cờ này (viewer và admin grid đã có
  từ task 39). Lỗi có từ task 55, lọt qua vì các check trước chỉ quét
  `pageerror` còn lỗi này chỉ là `console.error`.
- Hậu quả: khi grid trống, dòng chữ thân thiện không hiện (rơi về chữ mặc
  định của AG Grid); console đỏ mỗi lần mở trang.

## Cách fix
Thêm `dangerously_allow_code=True` cho grid `report-runs-grid`
(`app/ui/pages/report_runs.py`), giữ nguyên chuỗi overlay.
