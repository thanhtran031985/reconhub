# Task 53 — progress

## Bước 1 — Docs + nhánh (xong, 11/11/2026)
- Nhánh `feat/53-history-refresh` từ `0e8a9ec` (task 52).

## Bước 2–3 — Code + test unit (xong)
- Helper `_runs_fingerprint`, store `report-runs-fingerprint`,
  `handle_runs_refresh` gate khi trigger là tick 10s; mọi trigger khác
  luôn vẽ lại. Test mới 14 pass (fingerprint + gate + Làm mới ép vẽ
  lại); test cũ test_console_cleanup45 vẫn pass.
- Lưu ý: tham số State `report-runs-page-store` trước đây bị gắn nhầm
  vào `_refresh_store` (hàm không dùng tới nên không gây lỗi) — nay đã
  gắn đúng thành `_page_store`.

## Bước 4 — Kiểm chứng live (xong)
- Playwright check-53.py 5/5: tick 10s không đổi thì bảng không vẽ lại
  (dòng giữ nguyên trong DOM); export chạy ngầm tự hiện "Đang chờ" rồi
  icon tải khi worker xong (tick vẫn vẽ lại khi dữ liệu đổi); bấm "Làm
  mới" hiện run mới ngay; không lỗi JS.
- Bài học: React giữ lại DOM node khi vẽ lại cùng cấu trúc (không có
  key) nên không assert "dòng bị thay thế" được — check 53c đổi sang
  chèn run mới vào DB rồi bấm "Làm mới" và assert tổng tăng ngay.
