# TEST CHECKLIST — TASK UI-99: Global UI Review & Cleanup

## 1. Phase A Audit Verification (Audit Only)
- [ ] Quét toàn bộ 26 trang bằng Playwright tại 1366×768:
  - [ ] Kiểm tra `document.documentElement.scrollHeight <= innerHeight`.
  - [ ] Kiểm tra `document.documentElement.scrollWidth <= innerWidth`.
- [ ] Quét toàn bộ 26 trang tại 1440×900:
  - [ ] Kiểm tra `scrollHeight <= innerHeight` và `scrollWidth <= innerWidth`.
- [ ] Quét toàn bộ 26 trang tại 390×844:
  - [ ] Kiểm tra `scrollWidth <= clientWidth` (không tràn ngang).
- [ ] Quét tĩnh toàn bộ `app/ui/**`:
  - [ ] Liệt kê mọi màu hex / rgb / rgba còn sót lại.
  - [ ] Liệt kê mọi inline style thừa.
  - [ ] Liệt kê mọi control size không đúng chuẩn (md/lg/xl).
  - [ ] Liệt kê CSS selector không còn dùng trong `app/ui/assets/custom.css`.
- [ ] Quét Console browser:
  - [ ] Không có unhandled exception hoặc React key warning nghiêm trọng.
- [ ] **DỪNG LẠI (STOP) và trình nộp bảng Issue List cho người dùng**.

## 2. Phase B Fix & Regression (Sau khi có lệnh "Tiếp tục UI-99 Fix")
- [ ] Tất cả lỗi layout trong danh sách được phê duyệt đã khắc phục.
- [ ] Các class CSS chết trong `app/ui/assets/custom.css` đã được loại bỏ an toàn.
- [ ] Bộ ảnh so sánh Before/After cuối cùng được lưu trữ và kiểm tra đạt chuẩn thiết kế `preview-fluent.html`.

## 3. Full CI Suite
- [ ] `uv run poe lint` PASS 100% không warning.
- [ ] `uv run poe typecheck` PASS 100% không lỗi mypy.
- [ ] `uv run poe test` PASS 100% unit & integration test.
- [ ] `uv run poe e2e` PASS 100% end-to-end test.
- [ ] Cập nhật trạng thái tất cả task thành DONE trong `docs/tasks/UI-MIGRATION-INDEX.md`.

