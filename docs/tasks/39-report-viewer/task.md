# 39-report-viewer — Trung tâm báo cáo: ngày yyyy-mm-dd, Org trống, AG Grid, Excel luôn mở, nút Xem cùng dòng

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3 (fix, theo mẫu task 33/36/37/38 — không thêm dòng dashboard)
- Phụ thuộc: 38
- Nhánh git: feat/39-report-viewer (rẽ từ `b79f660`, đỉnh `feat/38-wizard-fixes`)

## Vấn đề (người dùng báo 10/11/2026, kèm ảnh /reports/5 "BC RM Updated")

1. **Ngày hiển thị "November 1, 2026".** `render_param_control` (DATE và
   DATE_RANGE) không đặt `valueFormat` nên dmc.DateInput dùng mặc định
   "MMMM D, YYYY". Các page khác đã dùng `valueFormat="YYYY-MM-DD"`
   (batch_run_wizard.py:667/691). `valueFormat` chỉ đổi cách hiển thị,
   `value` vẫn là chuỗi ISO "YYYY-MM-DD" nên luồng resolve/bind không đổi.
2. **Org để trống thì lỗi DPY-4010** dù Org không bắt buộc: "Lỗi thực thi
   truy vấn nguồn Oracle: DPY-4010: a bind variable replacement value for
   placeholder \":P_ORG\" was not provided". Gốc: `resolve_param_values`
   (report_param.py:699) cố tình bỏ tham số không bắt buộc và không có giá
   trị khỏi dict đã resolve ("param không bắt buộc và không có giá trị thì
   vắng mặt"); `build_run_query` (CUSTOM_SQL) trả binds = đúng dict đó nên
   placeholder `:P_ORG` không có bind nào cả — driver Oracle báo DPY-4010
   dù SQL có viết dạng `(:P_ORG IS NULL OR ORG = :P_ORG)` thì vẫn lỗi vì
   bind vắng mặt hoàn toàn. Sửa: CUSTOM_SQL bind đủ mọi tham số đã khai
   báo, tham số không bắt buộc vắng giá trị thì bind NULL. VIEW/TABLE
   không đổi (vắng = không lọc, đã đúng).
3. **Kết quả vẫn là bảng HTML** (`render_result_table`) + phân trang ngoài.
   Chuyển sang AG Grid (wrapper `data_grid`, như grid cột bước 4 ở task
   35), giữ phân trang server-side theo số dòng đã chọn (50/100/200).
   Sort giữ server-side qua `columnState` của grid → sort-store → refetch
   (không sort client-side trong trang vì sai với dữ liệu toàn cục).
   Giữ hàng Tổng (pinnedBottomRowData) và định dạng ô `_format_cell`.
4. **"Xuất Excel" bị disable** cho tới khi xem báo cáo xong. Mở luôn:
   bấm xuất thì dùng điều kiện tìm kiếm hiện tại (form tham số); nếu run
   hiện tại đúng điều kiện đó thì xuất lại run đó, khác thì tạo + chạy run
   mới rồi xuất. Hiện progress bar (animated, indeterminate — service
   export chỉ có trạng thái QUEUED/RUNNING/DONE/FAILED, không có % tiến
   độ số) trong lúc poll.
5. **Nút "Xem báo cáo" luôn ở dòng riêng** dưới form. Nếu tổng span tham
   số < 12 thì đặt nút cùng dòng với tham số (ô span = phần còn lại, tối
   đa 3 cột, tối thiểu 2); >= 12 thì xuống dòng mới như hiện tại.
6. **Lỗi chạy báo cáo hiện alert đỏ to** (`alert_box` trong
   `viewer-run-error`, chiếm cả dòng dưới form). Chuyển sang notification
   (`notify_error`, tự đóng sau 6s) như các toast khác trong app.
