# Task 56 — progress

## Bước 1 — Docs + nhánh (xong, 11/11/2026)
- Nhánh `feat/56-history-aggrid-ui` từ `db93556` (task 55).
- Mẫu đã rà: font grid theo pattern task 40 (class + --ag-font-size);
  nút cũ là dmc.Button size xs variant subtle (Xóa color red), link
  Chạy lại là Button subtle + icon play-circle trong dcc.Link.

## Bước 2 — Code (xong)
- custom.css: `.rh-runs-grid { --ag-font-size: 12px; }` +
  `.rh-grid-btn` / `.danger` / `.rh-grid-link` (subtle xs: nền trong
  suốt, không viền, chữ xanh Mantine, hover nền nhạt; Xóa chữ đỏ).
- report_runs.py: className grid thêm rh-runs-grid; Tham số về cuối;
  width đã rà (Nhóm 80, Trạng thái 90, Bắt đầu/Kết thúc 140, File 110,
  nút 60–70) — các cột trước Tham số ~1160px, vừa khung ~1208px ở
  viewport 1440 nên nút cuối thấy được không cần cuộn ngang.
- dashAgGridFunctions.js: renderer nút/link dùng class CSS trên.
  (Icon play-circle của nút Chạy lại cũ không khôi phục — renderer JS
  không dùng được DashIconify.)

## Bước 3 — Kiểm chứng (xong)
- Unit test_history_aggrid55.py: 17 pass (5 test mới TestUi56).
- Playwright check-56.py 8/8: font cell 12px; Tham số là cột cuối;
  ô Bắt đầu hiện đủ "11/11/2026 09:13:54"; nút Hủy nền trong suốt +
  chữ xanh Mantine; link Chạy lại xanh; link Chạy lại nằm trong khung
  (1262 < 1424, không cần cuộn ngang); tick vẫn cập nhật dòng tại chỗ
  (không regression task 55); không lỗi JS.
- Bài học: màu xanh thực tế là #228be6 (blue-6 mặc định của theme
  Mantine), không phải #1971c2 — var --mantine-color-blue-6 đã có giá
  trị nên fallback không áp dụng; check phải assert đúng màu theme.
  Thanh cuộn ngang của AG Grid nằm ở .ag-body-horizontal-scroll-viewport,
  set scrollLeft trên .ag-body-viewport không có tác dụng.

## Bước 4 — Full suite + patch (xong)
- Full suite 1548 pass, 6 skipped (1543 + 5 test mới).
- Patch ~/workspace/reconhub-task56.patch, áp sau patch 55, không cần
  db-migrate, chỉ khởi động lại app. Đang chờ user áp + kiểm chứng
  trên app thật.
