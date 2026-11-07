# TEST CHECKLIST — TASK UI-99: Global UI Review & Cleanup

## 1. Phase A Audit Verification (Audit Only)
- [x] Quét toàn bộ 26 trang bằng Playwright tại 1366×768:
  - [x] Kiểm tra `document.documentElement.scrollHeight <= innerHeight`.
  - [x] Kiểm tra `document.documentElement.scrollWidth <= innerWidth`.
- [x] Quét toàn bộ 26 trang tại 1440×900:
  - [x] Kiểm tra `scrollHeight <= innerHeight` và `scrollWidth <= innerWidth`.
- [x] Quét toàn bộ 26 trang tại 390×844:
  - [x] Kiểm tra `scrollWidth <= clientWidth` (không tràn ngang).
- [x] Quét tĩnh toàn bộ `app/ui/**`:
  - [x] Liệt kê mọi màu hex / rgb / rgba còn sót lại (0 bare hex colors).
  - [x] Liệt kê mọi inline style thừa.
  - [x] Liệt kê mọi control size không đúng chuẩn (md/lg/xl).
  - [x] Liệt kê CSS selector không còn dùng trong `app/ui/assets/custom.css` (0 selector chết).
- [x] Quét Console browser:
  - [x] Không có unhandled exception hoặc React key warning nghiêm trọng.
- [x] **Trình nộp bảng Issue List và hoàn thành Phase A**.

## 2. Phase B Fix & Regression
- [x] Tất cả lỗi layout trong danh sách được phê duyệt đã khắc phục.
- [x] Các class CSS chết trong `app/ui/assets/custom.css` đã được loại bỏ an toàn.
- [x] Bộ ảnh so sánh Before/After cuối cùng được lưu trữ và kiểm tra đạt chuẩn thiết kế `preview-fluent.html`.

## 3. Full CI Suite
- [x] `uv run poe lint` PASS 100% không warning.
- [x] `uv run poe typecheck` PASS 100% không lỗi mypy.
- [x] `uv run poe test` PASS 100% unit & integration test.
- [x] `uv run poe e2e` PASS 100% end-to-end test.
- [x] Cập nhật trạng thái tất cả task thành DONE trong `docs/tasks/UI-MIGRATION-INDEX.md`.
