# Task 62 — decisions

## D1 — Ghi nhịp tim mỗi vòng poll (không phải mỗi N vòng)
Mỗi vòng poll (~2s) mỗi luồng ghi 1 UPDATE nhỏ vào RECON_APP_SETTING.
Lý do: vòng poll vốn đã query DB mỗi vòng (claim + reset_stale) nên
thêm 1 upsert không đáng kể; nhịp tim càng tươi thì ngưỡng stale 30s
càng có ý nghĩa (15 vòng). Lỗi ghi được bọc try/except, không làm
chết worker.

## D2 — Nhịp tim lưu VALUE = timestamp ISO, UPDATED_BY = worker_id
Không thêm key riêng cho worker_id: RECON_APP_SETTING đã có cột
UPDATED_BY (pattern set_export_retention), ghi worker_id vào đó là
vừa. VALUE là ISO naive UTC, đọc lại bằng datetime.fromisoformat.

## D3 — Trạng thái worker có 3 mức: running / partial / down
2 luồng trong 1 tiến trình có thể chết riêng lẻ (exception ở
reset_stale/sweep không được bọc sẽ giết 1 thread). Badge tổng:
"Đang chạy" khi cả 2 mới, "Chạy một phần" khi 1 mới, "Không phản hồi"
khi không luồng nào mới (gồm cả chưa từng chạy). Thẻ hiện thêm từng
dòng trạng thái + thời gian thấy lần cuối của mỗi luồng.

## D4 — can_cancel theo đúng luật service hủy (không đồng nhất)
- Export: chỉ chủ mới hủy được — `cancel_export` dùng
  `_load_export_row_own` (kể cả ADMIN cũng chỉ hủy export của mình).
- Run: ADMIN hoặc chủ mới hủy được — `cancel_report_run` dùng
  `_load_run_row` với admin=True. Danh sách kẹt tính can_cancel theo
  đúng 2 luật này (không tự nới quyền ở tầng UI).

## D5 — Run RUNNING không liệt kê kẹt
RECON_REPORT_RUN không có cột heartbeat nên không đánh giá được run
RUNNING có treo hay không. Chỉ liệt kê QUEUED quá 30 phút (run) và
QUEUED quá 30 phút + RUNNING quá hạn heartbeat 300s (export, cùng
điều kiện reset_stale_exports).

## D6 — Thẻ chỉ làm mới bằng tay (nút "Làm mới"), không dùng Interval
`dashboard-refresh-trigger` hiện không có gì tăng sau lần tải đầu nên
"trigger refresh sẵn có" thực chất chỉ là tải trang. Không thêm
dcc.Interval: tick 10s sẽ vẽ lại body liên tục, vừa tái tạo nút Hủy
đúng lúc user sắp bấm, vừa cần thêm vân tay chống vẽ lại thừa (pattern
task 53). Thẻ hiện nội dung mới nhất lúc mở trang; nút "Làm mới" ở
header thẻ + callback Hủy dùng chung 1 callback duy nhất (tránh 2
callback cùng ghi 1 Output — bài học task 52).

## D7 — Thẻ sức khỏe hiện cả ở nhánh trống (total == 0)
Lệch plan bước 3 (plan chỉ đặt thẻ ở nhánh bình thường). Phát hiện ở
check live: `get_dashboard_summary` đếm run đối soát (RECON_RUN),
không đếm run báo cáo — mở dashboard sau khi chỉ chạy Xem báo cáo thì
total == 0, nhánh trống return sớm, thẻ không hiện. Thẻ vẫn hiện ở
nhánh trống (dưới empty_state) vì đúng lúc chưa có run mới cần biết
worker có chạy không.
