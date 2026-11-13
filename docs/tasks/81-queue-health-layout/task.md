# Task 81 — Sửa layout /queue-health theo chuẩn ui-dash

## Bối cảnh

Review layout 13/11/2026 (kèm patch 80): đo ở clone với 1 run QUEUED
10h — 1366x768 và 1440x900 đều KHÔNG cuộn trang, không cuộn ngang,
không lỗi JS. Nhưng trang vẫn lệch chuẩn ui-dash và có 1 lỗi thật:
thân card bị chặn cứng 220px nên bảng "Mục kẹt" phải cuộn *trong
card* mới thấy (ảnh user gửi + ảnh probe 1440x900 đều cắt nửa dòng
kẹt). User duyệt "Sửa layout luôn" 08:33 13/11/2026.

## Phạm vi (đúng 5 mục đã chốt với user)

1. Bỏ chặn 220px ở thân card: card lấp đầy chiều cao còn lại của
   trang (flex 1, min-height 0); thân card chỉ cuộn khi nội dung
   thật sự tràn viewport. Với 1 mục đang chờ + 1 mục kẹt, cả 2 bảng
   phải hiện hết ở 1440x900 mà không cần cuộn trong card.
2. Nút "Làm mới" / "Xem lịch sử" lên page header (page_header
   đã có tham số `actions`); bỏ hàng header của card (tiêu đề
   "Sức khỏe hàng đợi & worker" trùng với tiêu đề trang nên bỏ).
3. 2 Select lọc ra command bar riêng: dmc.Paper withBorder đặt
   trên vùng chính, NGOÀI `#queue-health-card-body` (mẫu task 60:
   đổi filter không reset khi body vẽ lại).
4. Thay style px viết thẳng trong page bằng class trong
   `app/ui/assets/custom.css` (tiền lệ task 79: class `.notif-*`):
   padding/gap của Box layout, cao hàng 32px, fontSize 13px,
   maxHeight 220/132. Không còn hex/px trong page.
5. Tiêu đề section "Đang chạy / Đang chờ (N)", "Mục kẹt (N)"
   thành dmc.Title order=5; bảng đặt độ rộng cột theo % (không
   dùng px) để cột "Mục" không chiếm hết — cột "Tạo lúc" phải
   chứa vừa "12/11/2026 14:22:05" (task 80) ở 1366.

## Không làm

- Không đổi hành vi/callback (handle_health_actions, Hủy, lọc,
  làm mới giữ nguyên id và luồng); không thêm modal xác nhận Hủy
  (ngoài phạm vi đã chốt); không đụng cột "Tạo lúc" dạng đầy đủ
  của task 80; không đụng các trang khác.
