# Decisions — 40-report-viewer-fixes

- "Nút in báo cáo" được hiểu là nút "Xem báo cáo" (viewer không có nút In
  nào); chờ người dùng xác nhận nếu ý khác.
- DMC Button Loading State (đã đọc docs
  dash-mantine-components.com/components/button.txt): clientside_callback
  đặt `loading=True` ngay khi bấm (nút tự disable khi loading), callback
  chính trả `loading=False` — mẫu này đã có sẵn trong repo ở trang
  Data Model (nút Đồng bộ, 2 pha click → trigger → chạy).
- % export thật bắt buộc phải lưu tiến độ xuống DB (poll đọc qua
  `get_export`); không bịa % theo thời gian. Đổi lại cần migration 0007
  + `db-migrate` khi áp patch — chờ chốt Q0.
- Không sửa SQL_TEXT của báo cáo bằng code: nếu tab SQL cho thấy thiếu
  điều kiện NULL thì sửa ở /report-admin (dữ liệu của người dùng).
- Font grid: chỉ giảm `--ag-font-size` 14px → 13px trên grid viewer, giữ
  nguyên chiều cao dòng/header.
- Cảnh báo NULL ở tab SQL chỉ xét tham số KHÔNG bắt buộc (mới có thể vắng
  giá trị): bản đầu xét cả p_from/p_to bắt buộc nên báo cáo có guard vẫn
  hiện cảnh báo oan — phát hiện khi kiểm chứng live, đã sửa + hồi quy
  bằng check 2c.
