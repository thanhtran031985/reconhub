# Task 66 — Tách card sức khỏe thành tab riêng + sửa link run kẹt

## Yêu cầu gốc (user, 12/11/2026 ~10:02, kèm 3 ảnh)
1. "tách card Sức khỏe hàng đợi & worker thành 1 tab nha bạn" — card hiện đang nằm trên dashboard (http://127.0.0.1:8050), tách ra thành tab riêng.
2. "bấm vào run 37, lỗi như sau trong khi vào page http://127.0.0.1:8050/report-runs lại có" — bấm link #37 · BC RM Updated trong danh sách kẹt của card → sang /runs/37 → "Không tìm thấy dữ liệu lần chạy #37.", trong khi /report-runs vẫn liệt kê #37 (Đang chờ, tạo 11/11/2026 14:24:48).

## Bối cảnh thêm (từ ảnh user)
- Danh sách kẹt lúc chụp: #37 và #38, cùng báo cáo "BC RM Updated", admin, tạo 11/11 14:24, kẹt 12 giờ 36 phút, trạng thái CHỜ CHẠY; Run đang chờ: 2; cả 2 worker Đang chạy (thấy lần cuối 12/11 03:01); Song song tối đa: 2.
- /report-runs: #37/#38 đều "Đang chờ", cột File "Đã hủy" (export đã bị hủy), có nút Xóa / Xuất lại / Chạy lại.
- Đây là cùng mẫu với run #32/#33 kẹt QUEUED không có export (17:34 11/11/2026, user chưa trả lời tạo bằng cách nào — vẫn là câu hỏi mở).

## Phạm vi đã duyệt (user 12/11/2026: duyệt, đặt tên task 66)
- (1) Trang mới "Hàng đợi & worker" (route /queue-health), là 1 mục menu riêng trong sidebar nhóm Đối soát, ai cũng xem được (ADMIN + cả 3 vai trò còn lại, như card hiện tại); card rời khỏi dashboard hẳn (cả nhánh dashboard có dữ liệu và nhánh dashboard trống).
- (2) Sửa link run kẹt: run báo cáo trong danh sách kẹt link sang /report-runs (nơi run đó tồn tại), không sang /runs/<id> nữa.
- Không đổi luật hiển thị/hủy trong card (Hủy export chỉ chủ, Hủy run ADMIN hoặc chủ), không đổi cách tính kẹt, không đổi nút Làm mới bằng tay.

## Ngoài phạm vi
- Không điều tra thêm vì sao #37/#38 kẹt (xem phân tích ở plan: run QUEUED trơ trọi khi export đã hủy thì không worker nào nhận — bấm Hủy trên card là dọn được).
- Không đổi /runs/<id> (trang kết quả run đối soát) hay /report-runs.
