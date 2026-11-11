# Task 56 — decisions

- D1: Font 12px theo pattern task 40 (class CSS + biến AG Grid
  `--ag-font-size`), không set font-size trực tiếp từng cell. Class
  `.rh-runs-grid` chỉ áp cho grid Lịch sử (viewer giữ 13px).
- D2: Nút/link trong cell style bằng class CSS trong custom.css
  (`.rh-grid-btn`, `.rh-grid-btn.danger`, `.rh-grid-link`), không style
  inline trong JS — giống cách repo đã làm cho các nút native
  (`.rh-btn-arrow`, `.rh-btn-del`). Màu lấy theo token Mantine
  (blue-6/red-6, fallback hex) để khớp nút subtle xs của bảng cũ.
  Icon play-circle của nút "Chạy lại" cũ không khôi phục (renderer JS
  không dùng được DashIconify) — chỉ giữ chữ, giống các nút còn lại.
- D3: Tham số về cuối để nút hành động (Hủy/Xuất lại/Chạy lại) nằm
  trước cột dài, thấy được mà không cần cuộn ngang.
- D4: Bắt đầu/Kết thúc 140px (đủ "11/11/2026 13:09:56" ở font 12);
  Nhóm 80 ("Tài chính"), Trạng thái 90 ("Đang chờ"); Báo cáo flex
  min 130, Tham số flex min 140.
- D5: Tổng các cột trước Tham số ~1160px để vừa khung nội dung ~1208px
  ở viewport 1440 (đo live) — nút cuối (Chạy lại) thấy được mà không
  cần cuộn ngang; Tham số (flex, cuối) nhận phần còn lại và cuộn ngang
  khi khung hẹp hơn.
