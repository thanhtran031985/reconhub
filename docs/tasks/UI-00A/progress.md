# Tiến độ TASK UI-00A — UI Inventory & Fluent Migration Assessment

Trạng thái: ✅ ĐÃ HOÀN THÀNH

## 1. Mục tiêu và phạm vi
- [x] Đọc `AGENTS.md`, `.agents/rules/ui-dash.md`, `designs/tokens.json`, `designs/README.md`.
- [x] Đọc source code `app/ui/**`, `tests/e2e/**` và visual reference `designs/reference/preview-fluent.html`.
- [x] Khảo sát toàn bộ 26 trang đã register qua `dash.register_page` (bao gồm admin và hidden routes).
- [x] Khảo sát các component dùng chung hiện tại (AppShell, Navbar, PageHeader, CommandBar, DataGrid,...).
- [x] Đo lường hiện tượng Page Scroll (dọc) và Horizontal Overflow (ngang) ở độ phân giải baseline 1366×768.
- [x] Chụp 62 ảnh baseline giao diện ở các viewport (1366×768, 1440×900, 390×844) lưu tại `artifacts/ui-inventory/`.
- [x] Lập báo cáo kiểm kê chi tiết: [docs/ui-migration.md](../../ui-migration.md).
- [x] Lập backlog task chi tiết từ `UI-00B` đến `UI-99` và chỉ mục tra cứu tại [docs/tasks/UI-MIGRATION-INDEX.md](../UI-MIGRATION-INDEX.md).
- [x] Giữ nguyên 100% source code production, không refactor, không sửa UI trong task kiểm kê này.

## 2. Kết quả kiểm kê
- **Tổng số trang đã kiểm kê:** 26 pages
- **Số trang bị page scroll trên desktop (1366×768):** 18 pages (cần chuẩn hóa viewport-locked + scroll nội bộ)
- **Số trang bị tràn ngang (horizontal overflow):** 4 pages
- **Số trang ứng viên Master–Detail:** 9 pages
- **Số trang độ phức tạp cao (L/XL):** 11 pages
- **Tổng số ảnh baseline đã lưu:** 62 screenshots tại `artifacts/ui-inventory/`

## 3. Nghiệm thu Acceptance Criteria
- [x] Đã đọc AGENTS.md và ui-dash.md.
- [x] Đã inventory tất cả dash.register_page.
- [x] Không bỏ sót admin/hidden page.
- [x] Shared components đã được inventory.
- [x] Tất cả page đã được phân loại layout đích.
- [x] Tất cả page đã được đánh Complexity.
- [x] Tất cả page đã được đánh Callback Risk.
- [x] Page scroll được đo ở 1366×768.
- [x] Horizontal page overflow được đo.
- [x] AgGrid inventory hoàn tất.
- [x] Modal/Drawer audit hoàn tất.
- [x] 4-state audit hoàn tất.
- [x] Responsive audit hoàn tất.
- [x] Baseline screenshot hoàn tất.
- [x] `docs/ui-migration.md` đã tạo.
- [x] Đã đề xuất UI-00B và UI-01...UI-n.
- [x] Không có source code production nào bị thay đổi.

