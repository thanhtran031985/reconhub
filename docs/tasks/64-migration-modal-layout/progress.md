# Tiến độ — Task 64: Sửa layout modal chuyển Oracle (2 card + stepper hiện item đang chạy)

## Bước 1 — Modal vừa trang, không scroll
- [x] Modal size `1100px`, cao 88vh (styles content/body flex cột, min-height 0), footer cố định
- [x] Bỏ `ScrollArea(h=380)` ôm toàn bộ; chỉ card detail có ScrollArea riêng
- [ ] Nghiệm thu Playwright 1366×768 (xem bước 4)

## Bước 2 — Chia 2 card: stepper + detail (Master–Detail)
- [x] Card trái "Tiến trình" 330px: stepper dọc 6 bước, bấm được (pattern-matching `mig-step` + ALL + triggered_id)
- [x] Card phải "Chi tiết bước" flex 1: header (tên bước + badge + n/m việc xong) + checklist bước chọn + báo cáo ở bước 6 khi xong
- [x] Store mới `ds-mig-state` (nguồn sự thật duy nhất cho việc vẽ, D3) + `ds-mig-selected-step` (sticky, D4)
- [x] Xóa `ds-mig-fake-store` khỏi layout; `ds-mig-modal-result` bỏ, alert chuyển vào detail (D5)

## Bước 3 — Stepper hiện item đang chạy
- [x] Helper thuần mới: `step_counts`, `running_item`, `running_step_index`, `error_step_index`
- [x] Dòng phụ: xong "✓ n/n việc xong", đang chạy "Đang: <item>" + "n/m bảng xong", chờ "Chờ • 0/m việc", lỗi hiện message
- [x] Detail: item đang làm tô riêng (chấm xanh + badge "Đang chạy", nền nhạt primary)
- [x] Vòng tròn 28px theo mockup đã duyệt
- [x] D6: `running_step_index` bỏ qua bước 0 item khi tìm bước chờ

## Bước 4 — Kiểm chứng
- [x] Tests-first: `tests/unit/test_migration_modal_layout64.py` (16 test mới, đỏ trước rồi xanh)
- [x] Cập nhật test task 63 (output count 12→13, 7→8, stepper không còn chứa checklist gộp)
- [x] Targeted: 55 pass (64 + 63 + page data-sources + metadata_migration); typecheck sạch; ruff check sạch trên file đổi (format tay dòng mới; drift cũ để nguyên)
- [x] Check live `~/workspace/check-64-migration-modal-layout.py` (port 8110): **24/24 PASS** — modal không scroll ở 1366×768 và 1440×900; đủ 2 card; bấm bước 2 → detail bước 2; fake chạy → stepper hiện "Đang: Sao chép bảng …" + số đếm tăng 4→40; detail tô item đang chạy; fake xong tự chọn bước 6 hiện báo cáo; real SQLite→SQLite DONE, CHECKLIST_JSON 6 bước done, MAINTENANCE=Y; 0 console error/pageerror. Lưu ý: lần chạy đầu 23/24 do assertion 3c so khớp "Đang chạy" phân biệt hoa/thường trong khi Mantine Badge render uppercase qua CSS (innerText trả "ĐANG CHẠY") — đã sửa check, không phải lỗi code.
- [ ] Full suite (parent chạy sau review)

## Trạng thái
- ✅ code + test + check live xong, chờ parent review (KHÔNG commit, KHÔNG xuất patch)
