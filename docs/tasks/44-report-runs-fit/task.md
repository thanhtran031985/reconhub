# Task 44 — Trang Lịch sử báo cáo vừa trong 1 màn hình + icon nút Chạy lại

## Yêu cầu (10/11/2026, người dùng)

- Phân trang không thấy ở zoom 100% — phải zoom 30% mới thấy. Trước giờ
  code có rule vừa trong cùng 1 trang: sửa để toàn bộ trang (tiêu đề,
  thanh lọc, bảng, phân trang) vừa trong 1 màn hình, bảng cuộn nội bộ.
- Nút "Chạy lại": thêm icon của menu "Chạy đối soát" vào trước chữ.

## Nguyên nhân (đã đọc code)

- Root `dmc.Box` của `/report-runs` dùng `height: "100%"` — chiều cao phần
  trăm phụ thuộc khối cha, khối cha không giới hạn nên trang dài theo nội
  dung, phân trang bị đẩy xuống dưới màn hình. Các trang khác trong app
  dùng rule `height: "calc(100vh - 48px)"` (48px là chiều cao header).
- Icon menu "Chạy đối soát" (`/runs/new`) là `lucide:play-circle`
  (`app/ui/layout/shell.py:171`); nút "Chạy đối soát" ở Dashboard/Lịch
  sử dùng `lucide:play`, nhưng menu dùng `play-circle` nên lấy theo menu.

## Phạm vi

- Chỉ `app/ui/pages/report_runs.py` + test.
- Không migration, không đổi logic lọc/phân trang.
