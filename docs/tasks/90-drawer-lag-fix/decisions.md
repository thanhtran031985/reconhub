# Decisions — Task 90

## D1 — Nguyên nhân gốc: guard trả `0` thay vì `no_update` cho trigger Store
- `handle_save_issue_from_drawer` có 2 output: feedback + trigger Store
  (`run-res-trigger-store`, input của callback vẽ lại grid). Nhánh chặn/lỗi
  trả `(no_update, 0)` — ý đồ là "không làm gì", nhưng `0` là một giá trị
  gán thật. Dash không so sánh giá trị Store nên mọi lần gán đều kích hoạt
  callback phụ thuộc → vẽ lại grid (140KB) → renderer diff ~7,4 giây.
- Bằng chứng: response vẽ grid (`run-res-grid-container`) xuất hiện ngay sau
  response ghi trigger Store ở MỌI lần mở drawer; CPU profile cho thấy thời
  gian nằm trong `dash_renderer` (`isFirstLevelPropsChild`,
  `determineChangedProps`), không phải trong code app hay truy vấn DB.
- Các callback khác trong file trả `no_update` đúng cách; chỉ callback lưu
  này có 5 chỗ trả `0`.

## D2 — Chỉ sửa nhánh chặn/lỗi, giữ nguyên nhánh thành công
- Lưu thật thành công PHẢI vẽ lại grid để cập nhật badge trạng thái trên dòng
  → giữ `return feedback, int(n_clicks or 1)`.
- Các nhánh lỗi (chưa đăng nhập, run/row không hợp lệ, upsert lỗi) không đổi
  gì trong DB → không vẽ lại grid, chỉ hiện alert.

## D3 — Không làm nhanh bản thân việc vẽ lại grid trong task này
- Vẽ lại grid 50 dòng vẽ tay tốn ~7 giây main thread ngay cả khi thật sự cần
  (đổi filter, lưu thành công). Sửa phần đó cần đổi cấu trúc grid (AG Grid /
  ít dòng mỗi trang / cập nhật surgical) — việc lớn hơn, để task riêng nếu
  user yêu cầu.
