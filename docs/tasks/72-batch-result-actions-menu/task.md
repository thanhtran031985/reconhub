# Task 72 — Trang kết quả chạy bộ: nút tải + cột Thao tác thành menu

## Yêu cầu (user 12/11/2026, kèm ảnh /batch-runs/17/result)

Lần chạy bộ #17 "Tháng 7/2026" (DOANH_THU_BDP, 2 mục, cả 2 ĐÃ XONG:
SMP khớp 100%, VTOS khớp 8,4% lệch -42.631.474.159):

1. Nút "Tải tất cả (.zip, 2 file riêng)" ở góc phải — kiểm tra xem đã
   có code chưa; chưa thì bổ sung.
2. Cột "Thao tác": chuyển thành bấm vào hiện ra menu (thay cho 3 nút
   xếp chồng Mở run / Tải file / Chạy lại); kiểm tra nút "Tải file" đã
   có code chưa.

## Phạm vi

- Chỉ trang kết quả chạy bộ (`app/ui/pages/batch_run_result.py`,
  service `app/services/batch_run.py` nếu cần). Không đổi logic chạy,
  không migration.
