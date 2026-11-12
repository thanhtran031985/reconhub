# Follow-up task 66 — Bảng Đang chạy / Đang chờ + badge + filter

## Yêu cầu (user 12/11/2026, sau khi áp patch 66 và xem tab mới)

User thấy run #39 đang chạy (export RUNNING 10%, run QUEUED) không hiện trong
danh sách trên tab "Hàng đợi & worker" — danh sách đó chỉ hiện mục KẸT
(QUEUED quá 30 phút hoặc export RUNNING mất nhịp tim quá 5 phút). #39 lúc
chụp ảnh mới tạo được ~1 phút nên không kẹt — hành vi đúng, nhưng trang
"Hàng đợi & worker" thiếu khả năng nhìn thấy hàng đợi đang hoạt động.

User yêu cầu (nguyên văn): "thêm bảng đang chạy/ đang chờ luôn bạn, và thêm
badge để phân biệt, bổ sung thêm filter luôn bạn".

## Phạm vi đã duyệt (user nói "làm luôn")

1. Thêm bảng "Đang chạy / Đang chờ" trên tab /queue-health, đặt TRÊN bảng
   "Mục kẹt": liệt kê export đang QUEUED/RUNNING + run đang QUEUED (cũ nhất
   trước, tối đa 50), cùng nút Hủy theo đúng quyền từng mục.
2. Badge trạng thái trên mỗi dòng bảng mới để phân biệt Đang chạy / Đang chờ
   (dùng `status_chip` có sẵn).
3. Bộ lọc cho bảng mới: 2 Select — Trạng thái (Tất cả / Đang chạy / Đang chờ)
   và Loại (Tất cả / Export / Run).

## Ngoài phạm vi

- Không thêm cột tiến độ % cho export đang chạy.
- Không đổi tiêu chí kẹt (30 phút / 300s) và không đổi bảng "Mục kẹt".
- Không migration, không đổi service khác.
