# Tiến độ — 29-reporting-fluent-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Chuẩn hóa màn danh sách Quản trị báo cáo (`/report-admin`) tương tự `/batches` | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 1 |
| 2 | Đồng bộ Trung tâm báo cáo (`/reports`) theo Fluent Compact | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 2 |
| 3 | Tái cấu trúc Wizard Bước 3 (`/report-admin`): Master–Detail & Canvas 12 cột | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 3 |
| 4 | Cải thiện Xem báo cáo (`/reports/<id>`), Wizard Bước 4, Sticky Footer & Hoàn tất | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 4 |
| 5 | Tái cấu trúc toàn bộ 6 bước Wizard `/report-admin` bám sát `preview.html`, tự sinh SQL từ Table/View, tương thích SQLite/Oracle dry-run | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 5 |
| 6 | Tách route `/report-admin/new` & `/<id>`, menu thao tác 3 chấm, phân trang và cố định footer giống `/batch-runs/11` | ✅ | 2026-11-08 | 29-reporting-fluent-ui: step 6 |

## Nhật ký
- 2026-11-08: Khởi tạo task 29 từ thiết kế chuẩn Screen16 preview.html và yêu cầu chuẩn hóa danh sách `/report-admin` tương tự `/batches`. Lên plan và được duyệt.
- 2026-11-08: Hoàn thành bước 1: xây dựng lại bảng danh sách `/report-admin` theo phong cách Fluent Compact của `/batches` (command bar tìm kiếm, lọc trạng thái/nhóm, bảng sticky header, status chip, menu 3 chấm, unit tests 32/32 pass).
- 2026-11-08: Hoàn thành bước 2: chuyển đổi `/reports` từ lưới card sang Bảng gom nhóm danh mục bám sát `preview.html` (.rlist), bổ sung nhãn đếm `#reports-catalog-meta` có aria-live="polite", unit tests 10/10 pass.
- 2026-11-08: Hoàn thành bước 3: tái cấu trúc Wizard bước 3 sang Master–Detail 2 cột (Cột trái: danh sách tham số, Canvas layout 12 cột trực quan có kiểm tra vượt span, form cấu hình trường; Cột phải: LOV Detail Panel cố định #lovside), unit tests 32/32 pass.
- 2026-11-08: Hoàn thành bước 4: thêm dòng Footer Total cho `/reports/<id>` khi có cột is_total=True, sinh dữ liệu mẫu giả lập ở Bước 4 Wizard để xem trước format cột, cố định thanh điều hướng chân trang Sticky Footer cho Wizard (.wfoot), unit tests 18/18 và 32/32 pass.
- 2026-11-08: Chụp màn hình Playwright tự động đối chiếu app thực tế với thiết kế `preview.html` (`scripts/capture_reporting_screens.py`), lưu trong `docs/tasks/29-reporting-fluent-ui/screenshots/`.
- 2026-11-08: Nhận phản hồi rà soát UI từ người dùng: tái cấu trúc lại toàn bộ các bước của Wizard `/report-admin` theo pixel-perfect Fluent Ribbon và bố cục của `preview.html`:
  - Ribbon 6 bước dạng segmented bar chuẩn Fluent với icon tick xanh cho các bước đã qua, highlight xanh dương cho bước hiện tại.
  - Bước 1: Chuyển sang form lưới 4 cột `.info-grid` đồng bộ thiết kế `preview.html`, tích hợp lưu trực tiếp vào nút Tiếp theo.
  - Bước 2: Thiết kế lại với 4 cột config, dropdown chọn Table/View tự nạp danh sách từ catalog; khi chọn bảng/view, hệ thống truy vấn các cột và **tự động sinh câu lệnh SQL** có thụt lề định dạng chuẩn vào khung soạn thảo SQL nền tối `#0a1427`.
  - Bước 3: Canvas Master-Detail 12 cột trực quan và LOV side panel.
  - Bước 4: Bảng mapping cột trực tiếp, format mask, alignment, độ rộng và checkboxes hiển thị.
  - Bước 5 & 6: Sửa `open_checked_connection` (dùng `raw_connection` cho SQLite) và `build_report_query` / `build_paged_query` tương thích cả SQLite và Oracle, cho phép dry-run và kích hoạt template thành công 100%.
  - Tự động hóa kiểm thử và chụp toàn bộ 10 ảnh màn hình chạy thực tế qua Playwright (`scripts/test_and_capture_wizard.py`).
  - Kiểm tra 387/387 unit test báo cáo xanh 100%, lint và typecheck sạch sẽ.
- 2026-11-08: Hoàn thành bước 6: Tối ưu UI/UX `/report-admin` và Wizard bám sát phản hồi thực tế:
  - Cột "Thao tác" đồng bộ `/batches`: ActionIcon sửa nhanh (`lucide:edit-3`) + Dropdown menu 3 chấm (`lucide:more-vertical`) gồm Sửa, Clone, Lưu trữ, Xóa.
  - Bổ sung phân trang `dmc.Pagination` và nhãn `Hiển thị X - Y trong tổng số Z mục`.
  - Padding và Header: Chuẩn hóa padding `padding: "8px 12px"`, `gap: "6px"`; bọc header danh sách và nút "+ Báo cáo mới" vào container riêng biệt để ẩn hoàn toàn khi chuyển sang Wizard.
  - Cố định Sticky Footer chuẩn kiến trúc `/batch-runs/11`: Top bar cố định (Breadcrumb, tiêu đề, nút Đóng về danh sách, Ribbon 6 bước), thân cuộn riêng biệt, Footer cố định chân trang (`height: "48px"`), nút "Quay lại" và "Tiếp theo" luôn hiển thị rõ ràng tại zoom 100%.
  - Định tuyến phân tách: Hỗ trợ URL sạch `/report-admin` (danh sách), `/report-admin/new` (tạo mới) và `/report-admin/<id>` (chỉnh sửa), có fallback query string.
