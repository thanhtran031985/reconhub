# Follow-up task 65 — Modal migration: bỏ next-steps ở bước 6, click bước đổi indicator, progress bar

## Yêu cầu gốc (user, 12/11/2026 ~09:38, kèm ảnh chụp modal sau khi fake chạy xong)
1. "bước 6 bỏ thông tin này vì đã làm bước 7 rồi" + 4 dòng "Các bước tiếp theo cần thực hiện" (dừng app+worker, sửa RECON_DB_URL, db-migrate, khởi động lại) — bỏ khối này khỏi detail bước 6, vì bước 7 "Các bước làm tay" đã có đủ 4 việc đó. Bảng đối chiếu số dòng các bảng ở bước 6 giữ nguyên.
2. "click vào các bước khi đã chạy xong, indicator không đổi, vd mình click bước 6 nhưng không đổi indicator vẫn đang bước 7" — sau khi chạy xong (đang chọn bước 7), bấm bước 6 thì detail đổi sang "Hoàn tất" nhưng highlight bên stepper vẫn đứng ở bước 7.
3. "thêm process bar khi bấm bắt đầu để xem chạy từng bước" — thêm thanh tiến độ trong modal, hiện từ lúc bấm Bắt đầu, xem được từng bước đang chạy tới đâu.

## Phạm vi đã duyệt (user 12/11/2026: gộp vào task 65, không tách task mới)
- (1) Bỏ khối "Các bước tiếp theo cần thực hiện" khỏi detail bước 6; chỉ bỏ phần vẽ, không xóa nguồn dữ liệu `next_steps` (vẫn dùng để tạo item bước 7).
- (2) Bấm bước nào thì highlight stepper chuyển sang bước đó (cả lúc đang chạy và sau khi chạy xong); detail vẫn đổi như hiện tại.
- (3) Thanh tiến độ nằm ngay trên 2 card trong modal, hiện từ lúc bấm Bắt đầu: % theo số việc xong/tổng số việc của 6 bước tự động (không tính bước 7), kèm tên bước đang chạy; cập nhật mỗi tick (fake 0,4s, thật 1,5s); xong thì 100%. Lúc chưa chạy (idle) không hiện bar.

## Ngoài phạm vi
- Không đổi logic chạy fake/real, switch, precheck, checklist, bước 7 manual, migration 0008. Chỉ sửa cách vẽ + thêm progress bar.
