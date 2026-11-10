# Task 41 — Padding 5 trang giống /report-admin, /account padding + canh giữa

## Yêu cầu (10/11/2026, người dùng)

- 5 trang `/data-sources`, `/lookups`, `/users`, `/roles`, `/menus`: chỉnh
  padding giống trang `/report-admin`.
- Trang `/account`: padding và canh giữa.

## Chẩn đoán

- `/report-admin` (danh sách): container `#admin-list-container` có
  `padding: "8px 12px"`, `gap: "6px"`, `height: 100%`, flex column.
- Cả 5 trang kia: root `html.Div` `height: calc(100vh - 48px)`, flex
  column, `overflow: hidden`, **không có padding** — nội dung (header,
  bảng, tab) dính sát mép trái/phải/trên của khung trang.
- `/account`: root `html.Div` cùng khung `calc(100vh - 48px)` nhưng
  **không padding** (header dính mép); cột nội dung `dmc.Stack`
  `maw=640` nhưng không có `mx="auto"` nên lệch trái thay vì canh giữa;
  nhánh chưa đăng nhập đã có `padding: 24px` (giữ nguyên).

## Phạm vi

- Chỉ sửa padding/căn giữa ở root layout 6 trang trên. Không đổi spacing
  nội bộ (header `mb`, gap trong bảng/tab giữ nguyên), không đổi nội dung,
  không migration.
- `/menus`: cả nhánh lỗi (root không có style) cũng thêm cùng padding để
  nhất quán.
