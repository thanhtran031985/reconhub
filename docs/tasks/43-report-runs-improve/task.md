# Task 43 — Cải tiến trang Lịch sử báo cáo (/report-runs)

## Yêu cầu (10/11/2026, người dùng, kèm ảnh màn hình)

- Thêm phân trang (đã có sẵn 50/trang nhưng chưa có chọn cỡ trang, chưa
  hiện tổng số).
- Cột Báo cáo hiện tên báo cáo (hiện đang lấy mã — thực tế là `report_id`
  vì service không trả tên).
- Thêm cột nhóm báo cáo.
- Thêm thời gian bắt đầu, thời gian kết thúc, tổng thời gian chạy theo giây.
- Dòng format phần ngàn: 14585 → 14,585.
- Tải file: biểu tượng Excel + dấu mũi tên xuống (thay chữ "Tải file").
- Bỏ nút Xem; thêm cột lưu tham số user đã chạy; khi chạy lại thì lấy
  tham số đó truyền qua trang trung tâm báo cáo.
- Thêm tìm kiếm: từ ngày đến ngày (ngày chạy), nhóm báo cáo, tên báo cáo,
  người chạy.

## Quyết định đã chốt với người dùng (10/11/2026)

1. Dòng format dấu phẩy: `14,585` (không theo chuẩn chấm của app).
2. Tổng thời gian = cả thời gian chờ + chạy (`FINISHED_AT − CREATED_AT`).
3. Chạy lại: truyền tham số qua trang trung tâm, người dùng tự bấm chạy.

## Phạm vi

- Service `list_report_runs` + page `/report-runs` + viewer `?rerun_from=`.
- Không migration (run đã lưu `PARAMS_JSON`, `CREATED_AT`, `FINISHED_AT`).
- Không đổi hành vi export/tải file (chỉ đổi hiển thị nút tải).
