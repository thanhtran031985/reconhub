# Task 80 — Decisions

- D1: chỉ đổi cột "Tạo lúc" ở /queue-health; "thấy lần cuối"
  của worker giữ dạng ngắn (không nằm trong yêu cầu).
- D2: thêm `format_full_dt` riêng, không sửa `format_short_dt`
  (hàm này còn dùng cho worker + là bản sao dùng chung kiểu ở
  dashboard/history — sửa nó sẽ đổi cả chỗ không yêu cầu).
