# Tiến độ — 29-reporting-fluent-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Chuẩn hóa màn danh sách Quản trị báo cáo (`/report-admin`) tương tự `/batches` | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 1 |
| 2 | Đồng bộ Trung tâm báo cáo (`/reports`) theo Fluent Compact | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 2 |
| 3 | Tái cấu trúc Wizard Bước 3 (`/report-admin`): Master–Detail & Canvas 12 cột | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 3 |
| 4 | Cải thiện Xem báo cáo (`/reports/<id>`), Wizard Bước 4, Sticky Footer & Hoàn tất | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 4 |

## Nhật ký
- 2026-11-08: Khởi tạo task 29 từ thiết kế chuẩn Screen16 preview.html và yêu cầu chuẩn hóa danh sách `/report-admin` tương tự `/batches`. Lên plan và được duyệt.
- 2026-11-08: Hoàn thành bước 1: xây dựng lại bảng danh sách `/report-admin` theo phong cách Fluent Compact của `/batches` (command bar tìm kiếm, lọc trạng thái/nhóm, bảng sticky header, status chip, menu 3 chấm, unit tests 32/32 pass).
- 2026-11-08: Hoàn thành bước 2: chuyển đổi `/reports` từ lưới card sang Bảng gom nhóm danh mục bám sát `preview.html` (.rlist), bổ sung nhãn đếm `#reports-catalog-meta` có aria-live="polite", unit tests 10/10 pass.
- 2026-11-08: Hoàn thành bước 3: tái cấu trúc Wizard bước 3 sang Master–Detail 2 cột (Cột trái: danh sách tham số, Canvas layout 12 cột trực quan có kiểm tra vượt span, form cấu hình trường; Cột phải: LOV Detail Panel cố định #lovside), unit tests 32/32 pass.
- 2026-11-08: Hoàn thành bước 4: thêm dòng Footer Total cho `/reports/<id>` khi có cột is_total=True, sinh dữ liệu mẫu giả lập ở Bước 4 Wizard để xem trước format cột, cố định thanh điều hướng chân trang Sticky Footer cho Wizard (.wfoot), unit tests 18/18 và 32/32 pass.
- 2026-11-08: Chụp màn hình Playwright tự động đối chiếu app thực tế với thiết kế `preview.html` (`scripts/capture_reporting_screens.py`), lưu trong `docs/tasks/29-reporting-fluent-ui/screenshots/`. Kiểm tra toàn diện lint, typecheck, unit tests và e2e đạt 100% xanh. Đóng task 29.
