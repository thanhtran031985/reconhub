# Task 67 — Sửa lỗi wizard chạy bộ + switch chạy ngay/chạy ngầm

## Yêu cầu (user 12/11/2026, kèm 3 ảnh batch #15 DOANH_THU_BDP kỳ 2026-07)

### 1. Bước "Tải và ghép file": xóa rồi upload lại báo "đã tồn tại"
Upload 1 file, xóa đi, upload lại cùng tên thì hệ thống báo lỗi đã tồn tại.

### 2. Bấm "Tiếp tục" lại hiện "Đã đặt lại tham số về mặc định"
Sau bước 2, bấm Tiếp tục thì hiện thông báo thành công "Đã đặt lại tham
số về mặc định" — dù user không hề bấm nút đặt lại nào.

### 3. "Kiểm tra trước" OK nhưng "Thực thi" lại thất bại
- Bấm Kiểm tra trước báo thành công, sang bước Thực thi bấm chạy thì mục
  "Doanh thu smartport BDP" (BILL_SMART_PORT_BDP) THẤT BẠI, mục "Doanh thu
  Vtos" ĐÃ XONG.
- Yêu cầu: **bổ sung thêm card phía bên phải câu SQL, nếu thất bại thì hiện
  lỗi gì** (vd run thất bại là Run #1033).
- Qua route /runs/1033, tab "Câu lệnh SQL đối soát" lại không có SQL
  ("-- Không có câu lệnh SQL nguồn được lưu cho run này.") — **xem lại khi
  chạy có truyền câu SQL không**.

### 4. Thêm switch chạy ngay / chạy ngầm ở bước "Thực thi" (user bổ sung 11:38)
Mặc định chạy ngay như hiện tại; chạy ngầm thì như phần in report (vào hàng
đợi, xem ở Lịch sử).

## Phạm vi đã chẩn đoán (chờ user duyệt plan)

- A: sửa trùng tên khi upload lại file đã bỏ (bước 2).
- B: sửa callback đặt lại tham số tự kích hoạt khi sang bước 3.
- C1: hiện lỗi thật của run con ở card lỗi bên cạnh câu SQL (bước 5) + trên
  trang /runs/<id>.
- C2: lưu câu SQL đã build khi chạy lỗi (trang run vẫn xem được SQL đã thử).
- C3: kiểm tra trước chạy probe SQL để bắt lỗi SQL trước khi thực thi.
- D: switch chạy ngay (mặc định) / chạy ngầm ở bước Thực thi.

## Ngoài phạm vi

- Không đổi tiêu chí precheck khác (file, control total, tham số).
- Không đổi cơ chế hàng đợi/worker (đã có sẵn cho chạy ngầm).
- Không migration mới.
