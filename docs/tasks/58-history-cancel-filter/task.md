# Task 58 — history-cancel-filter

## Yêu cầu (user, 17:34 11/11/2026, kèm ảnh /report-runs)
1. "những job đang chạy mà hủy thì chuyển sang đã hủy để không tính
   vào trong 10 worker đang chạy" — hủy export đang RUNNING phải thành
   CANCELLED ngay và giải phóng slot worker.
2. "dòng bấm xoa, thì button xuất lại và chạy lại đang đẩy về phía
   trước" — bấm Xóa xong nút Xuất lại/Chạy lại bị đẩy sang trái; giữ
   nguyên vị trí các nút.
3. "bố sung thêm tìm theo trạng thái" — thêm lọc theo trạng thái run ở
   Lịch sử báo cáo.

## Phạm vi
- Fix 1: `execute_export` kiểm tra hủy mỗi batch (thay vì mỗi 10
  batch); chốt DONE chỉ khi export còn RUNNING (UPDATE có điều kiện);
  kiểm tra lại hủy ngay trước khi chốt.
- Fix 2: cột Hành động giữ cố định 4 vị trí nút; nút không phù hợp vẽ
  ẩn cùng kích thước (không bấm được).
- Fix 3: ô Select lọc trạng thái run (service đã hỗ trợ `status`).
- Không đổi cơ chế tick/vân tay, không migration. User chưa trả lời
  câu hỏi run #32/#33 kẹt QUEUED không có export (ảnh 17:34) — để
  riêng, không mở rộng phạm vi task này.
