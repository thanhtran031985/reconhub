# Task 60 — plan fix đề xuất (CHỜ USER DUYỆT, chưa làm)

## Bước 1 (nhỏ nhất, xử lý cả 3 triệu chứng)
- Tách `dmc.Pagination` ra khỏi vùng bị vẽ lại: đặt cố định trong
  `layout()` ở cả /history và 2 card dashboard; callback chỉ cập
  nhật dòng bảng + dòng "Hiển thị x–y". Pagination không bị hủy →
  giữ được focus, hết cảm giác reload.

## Bước 2 (bỏ spinner khỏi phân trang)
- /history: spinner chỉ hiện lúc tải lần đầu/lọc (hoặc bỏ
  `dcc.Loading` quanh bảng, thay bằng trạng thái tải nhỏ trong bảng).
- Dashboard: bỏ hẳn spinner cho 2 callback phân trang vì dữ liệu đã
  nằm trong store (không có server round-trip).

## Bước 3 (/history, nâng cấp nếu muốn triệt để)
- Chuyển bảng sang AG Grid như /report-runs (task 55): callback chỉ
  trả `rowData`, grid tự diff tại chỗ, kèm vân tay task 53 để
  tick/lọc không vẽ lại thừa.

## Bước 4 (dashboard, nâng cấp tương tự)
- Chỉ cập nhật `TableTbody` trong card thay vì trả cả card; hoặc gộp
  chung với bước 1.

## Kiểm chứng
- Test unit cho callback đổi trang (chỉ cập nhật dòng, Pagination
  còn nguyên); Playwright: bấm phân trang → không spinner, focus
  còn ở nút trang, dòng mới hiện, không lỗi JS. Full suite.
- Patch riêng, áp sau patch 59, không db-migrate.
