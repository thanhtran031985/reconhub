# Quyết định — 29-reporting-fluent-ui

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-08 | Dùng `preview.html` tại `designs/components/Screen16-DynamicReporting/` làm nguồn sự thật UI/UX | Đồng bộ với thiết kế Fluent Compact + Master-Detail của hệ thống | Chuẩn hóa toàn bộ 4 trang reporting theo `preview.html` |
| 2026-11-08 | Chuyển `/reports` từ Card Grid sang Bảng gom nhóm danh mục | Tuân thủ quy tắc `ui-dash.md` mục 34 và thiết kế `.rlist` | Tiết kiệm diện tích màn hình 1366×768 |
| 2026-11-08 | Bố cục Bước 3 Wizard thành Master-Detail (Canvas trái, LOV phải) | Bám sát thiết kế `preview.html` | Tăng trực quan khi thiết kế layout 12 cột |
| 2026-11-08 | Tách biệt tuyến đường `/report-admin` (danh sách) và `/report-admin/new` / `/report-admin/<id>` (wizard); cố định footer điều hướng chuẩn `/batch-runs/11` | Khắc phục tiêu đề danh sách đè lên wizard, nút Quay lại/Tiếp theo bị ẩn ở zoom 100%, chuẩn hóa Menu 3 chấm và phân trang giống `/batches` | Giao diện chuẩn mực, tương thích zoom 100% không bị cuộn mất footer |

## Câu hỏi còn mở
- Không.
