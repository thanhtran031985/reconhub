# Task 61 — decisions

## D1 — Thêm cờ thay vì đổi template sang dạng function
Thêm `dangerously_allow_code=True` cho grid (khớp pattern viewer/admin
grid từ task 39) thay vì đổi `overlayNoRowsTemplate` sang dạng
`{"function": ...}` hay bỏ dòng chữ. Chuỗi này là text tĩnh của mình,
không phải dữ liệu người dùng nên không có rủi ro XSS; giữ được dòng chữ
thân thiện khi grid trống.

## D2 — Không sửa gì thêm ở grid này
`getRowId` dạng chuỗi và `cellRenderer` dạng tên hàm không bị chặn
(chúng nằm trong tập không guarded của dash-ag-grid) — check live
55–58 đã chứng minh nút bấm render đúng. Chỉ thiếu cờ cho overlay.
