# Task 65 — Sửa modal migration (idle, bước 7 manual) + layout tab Lưu trữ

## Yêu cầu gốc (user, 12/11/2026 08:26, kèm ảnh chụp modal đã áp patch 62–64)
1. "mới bấm chuyển sang oracle, chưa bấm bắt đầu mà bước 1 đang để đang chạy?" — lỗi hiển thị: modal mới mở (chưa chạy) nhưng bước 1 tô xanh + ghi "Đang chạy…".
2. "xong 6 bước là Migration thành công?" — câu hỏi, đã trả lời: fake xong 6 bước chỉ là mô phỏng xong (không ghi gì sang Oracle); thật xong 6 bước không lỗi = chép dữ liệu thành công, nhưng app vẫn chạy SQLite cho tới khi làm xong 4 bước tay.
3. "sau bước 6, thêm bước 5 với card bước manual" — user ghi "bước 5" nhưng đã có 6 bước, parent hiểu là **bước 7** (gõ nhầm). Thêm bước 7 "Các bước làm tay" sau bước 6, card chi tiết liệt kê 4 bước làm tay:
   1. Dừng ứng dụng web ReconHub và background worker.
   2. Cập nhật biến môi trường RECON_DB_URL trong file .env sang Oracle đích.
   3. Chạy lệnh kiểm tra schema: uv run poe db-migrate
   4. Khởi động lại dịch vụ web và worker để chạy hoàn toàn trên Oracle.

## Yêu cầu bổ sung (user, 12/11/2026 08:31, gộp vào task 65)
4. Card "Chuyển dữ liệu sang Oracle" và card "Script khởi tạo schema đích Oracle" để cùng nhau, chia làm 2 card cạnh nhau cho dễ nhìn, không phải kéo lên xuống.
5. Card "Xóa dữ liệu tạm theo điều kiện": nút "Xem trước" cùng hàng với điều kiện tìm kiếm (hiện tại đang rớt dòng).

## Phạm vi đã duyệt (user "sửa thêm phần này luôn")
- (1) Sửa lỗi idle: lúc chưa chạy, cả 6 bước đều hiện "Chờ", không tô bước nào là đang chạy.
- (3) Bước 7 "Các bước làm tay": có trong stepper (7 bước), card chi tiết liệt kê 4 bước tay, mỗi bước có ô tick để đánh dấu khi làm xong; tick được lưu lại (thật: lưu vào CHECKLIST_JSON; fake: chỉ lưu tạm trên trang); cả 4 tick xong thì bước 7 hiện ✓. Bước 7 chỉ mở được sau khi bước 6 xong — trước đó hiện "Chờ" + ghi chú. Chạy xong 6 bước thì tự chọn bước 7 để thấy ngay 4 bước tay (báo cáo đối chiếu vẫn ở detail bước 6).
- (4) Hai card migration + script nằm cùng một hàng, mỗi card flex 1; dưới 900px xếp dọc (theo ui-dash).
- (5) Nút "Xem trước" cùng hàng với 4 ô lọc, căn thẳng hàng với ô nhập (không căn theo label), không rớt dòng ở 1440×900 và 1366×768.

## Ngoài phạm vi
- Không đổi logic chạy fake/real, switch, precheck, checklist, migration 0008. Chỉ sửa cách vẽ + thêm bước 7 manual.
