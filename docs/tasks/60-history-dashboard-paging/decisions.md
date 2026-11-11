# Task 60 — decisions

## D1 — Bỏ dcc.Loading thay vì "spinner chỉ lúc tải lần đầu/lọc"
Plan bước 2 cho /history đề xuất spinner chỉ hiện lúc tải lần đầu/lọc
(hoặc bỏ `dcc.Loading`, thay bằng trạng thái tải nhỏ trong bảng). Chọn
phương án trong ngoặc: bỏ hẳn `dcc.Loading` quanh bảng ở cả /history và
dashboard. Lý do: một callback phục vụ cả phân trang lẫn lọc
(`update_history_table`; `render_dashboard` + 2 callback phân trang đều
ghi vào vùng trong Loading), và Loading không phân biệt được trigger —
giữ Loading thì bấm phân trang vẫn hiện spinner. Lúc mở trang, vùng
bảng/nội dung hiện trạng thái tải nhỏ ("Đang tải lịch sử…",
"Đang tải dashboard…"); khi đổi lọc, bảng cũ giữ nguyên tới khi dữ liệu
mới về (không chớp, không spinner) — tốt hơn spinner.

## D2 — update_history_table trả thêm tổng số trang của Pagination
Phạm vi task nói callback "chỉ cập nhật dòng bảng + dòng 'Hiển thị x–y',
không trả lại Pagination". Hiểu "không trả lại" là không trả lại
component Pagination trong children (node không bị hủy/vẽ lại) — nhưng
prop `total` của Pagination vẫn phải đồng bộ khi lọc làm đổi tổng số
trang, nếu không Pagination hiện sai số trang. Đây đúng pattern
report-runs (task 55): callback trả `total` (prop) chứ không trả
component.

## D3 — handle_history_page trả cả giá trị Pagination
Khi đổi lọc, store về trang 1 nhưng Pagination (đã tách cố định) vẫn
hiện trang cũ. `handle_history_page` trả thêm `history-pagination.value`
(cùng pattern Input/Output một prop như `handle_runs_refresh` ở
report-runs, task 55) để reset control về 1. Không tạo vòng lặp: Dash
chỉ kích hoạt callback khi giá trị prop thật sự đổi.

## D4 — Callback phân trang dashboard KHÔNG trả giá trị Pagination
Giá trị Pagination ở dashboard không bao giờ lệch: store chỉ đổi qua
`render_dashboard`, mà lần đó vẽ lại toàn bộ nội dung (kèm footer
value=1). Callback phân trang chỉ cần kẹp trang qua `_page_slice` cho
dòng "Hiển thị x–y" (phòng thủ) và trả body + showing + total.

## D5 — Footer phân trang dashboard giữ TRONG Card
Bước 1 của plan nói "đặt cố định trong layout/card". Giữ footer trong
Card (chỉ tách thân bảng ra div `*-card-body` riêng) để card vẫn là
component tự chứa — `batch_run_wizard.py` cũng dùng
`render_recent_runs_card` và không phải sửa theo. Node Pagination vẫn
không bị hủy vì callback chỉ ghi vào div body.
