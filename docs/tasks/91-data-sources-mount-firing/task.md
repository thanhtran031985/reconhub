# Task 91 — /data-sources mount firing: audit giả + tải danh sách 2 lần

## Vấn đề
Mở trang `/data-sources` phát sinh 13 request `_dash-update-component`
(từ trang chủ), nội dung hiện sau ~2,7s trên máy ảo, cảm giác lag và
load nhiều lần (user báo 11:50 14/11/2026; đã đo bằng probe
`probe-datasources-load.py`, port 8146, DB check88f).

## Nguyên nhân gốc (đã đo, không đoán)
Các nút/switch trong bảng và tab Lưu trữ được vẽ bởi callback nên khi
bảng/tab vẽ xong chúng mount mới → callback của chúng bắn theo
(`prevent_initial_call=True` chỉ chặn lần load đầu của app, không chặn
lần mount sau — bài học D25/task 65 đã biết).

1. **BUG GHI AUDIT GIẢ (nặng nhất):** `handle_ds_active_toggle` bắn khi
   Switch mount → guard `triggered` vẫn có giá trị nên không chặn được →
   gọi `activate_data_source`/`deactivate_data_source` với đúng trạng
   thái hiện tại → service KHÔNG idempotent: luôn tắt các nguồn SOURCE
   khác, bật lại nguồn này, đổi `UPDATED_AT`, và **ghi audit
   `ACTIVATE_DATA_SOURCE` với `OLD_JSON` hardcode `"N"`**. Đã chứng minh
   bằng DB: mở trang xong có bản ghi audit ID 11 (nguồn #2, 11:51
   14/11/2026) dù không ai bấm gì.
2. **Tải danh sách 2 lần:** toggle trả `time.time()` vào
   `ds-active-trigger` (Input của `load_sources_data`) → danh sách tải
   lại lần 2 → bảng vẽ lại.
3. **Tab Lưu trữ tải dù chưa mở:** `load_storage_data` bắn khi load trang
   (không có `prevent_initial_call`, không xét tab đang mở) → kéo theo
   các callback purge/migration trong tab bắn theo (purge preview,
   mig modal, purge confirm).
4. **`handle_purge_preview` không có guard n_clicks:** khi nút Xem trước
   mount, nó chạy luôn query preview (đếm run sẽ xóa) và hiện alert
   "Tìm thấy N run" dù user chưa bấm.
5. **`handle_drawer_open` trả tuple reset khi mount:** nút Sửa mount lại
   (bảng vẽ lại) → trả "đóng drawer + xóa form" — vô tình đóng drawer
   nếu bảng vẽ lại trong lúc drawer đang mở.

## Phạm vi
Chỉ sửa `app/ui/pages/data_sources.py` (không đụng service, không
db-migrate). `/templates` để sau (user chốt 11:52 14/11/2026).

## Tiêu chí nghiệm thu
- Mở `/data-sources`: danh sách chỉ tải 1 lần; không còn request
  `ds-active-trigger`/`ds-store-list` lần 2.
- Mở trang KHÔNG ghi thêm bản ghi audit nào; `UPDATED_AT` của nguồn
  không đổi.
- Tab Lưu trữ không tải khi chưa mở tab; bấm tab Lưu trữ thì tải.
- Bấm Switch thật vẫn kích hoạt/vô hiệu hóa + ghi audit + badge header
  đổi như cũ.
- Bấm "Xem trước" xóa dữ liệu vẫn chạy preview; mở tab Lưu trữ không
  tự chạy preview.
- Lưu trong drawer xong drawer đóng như cũ; bảng vẽ lại không đóng
  drawer đang mở.
- Full suite xanh; live check pass.
