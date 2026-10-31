# Kế hoạch thực hiện — 15-dashboard-compare

## Mục tiêu
Dashboard đầy đủ theo PRD C1 (thẻ chỉ số, tỉ lệ lệch theo template, việc cần làm, run gần đây); chức năng so sánh hai run cùng template/profile phân loại theo 3 nhóm (chỉ có trong run A, chỉ có trong run B, có trong cả hai - đổi trạng thái/giữ nguyên).

## Các bước triển khai

### Bước 1 — Service (`app/services/dashboard.py`)
- Xây dựng `app/services/dashboard.py`:
  - `get_dashboard_summary(ctx: Ctx, month: str | None = None) -> dict[str, Any]`:
    - Thống kê run trong kỳ: tổng số, hoàn thành, lỗi, đang chạy, chưa kiểm tra, việc của tôi.
    - Tỉ lệ khớp trung bình toàn hệ thống.
    - Dung lượng dữ liệu tạm và thời điểm run gần nhất.
    - Danh sách 10 run gần đây nhất kèm phần trăm khớp và trạng thái kiểm tra.
    - Thống kê "Tỉ lệ lệch theo template" (`diff_rate_by_template`): số run, số nhóm so sánh, số nhóm lệch, tỉ lệ %.
  - `compare_runs(ctx: Ctx, run_id_a: int, run_id_b: int) -> dict[str, Any]`:
    - Kiểm tra điều kiện 2 run: tồn tại, trạng thái DONE, cùng template/profile.
    - Đối chiếu các dòng kết quả theo `KEY_HASH`:
      1. Nhóm chỉ có trong run A (`ONLY_IN_A`)
      2. Nhóm chỉ có trong run B (`ONLY_IN_B`)
      3. Nhóm có trong cả hai (`IN_BOTH`): phân loại `STATUS_CHANGED` hoặc `SAME_STATUS`, so sánh giá trị chênh lệch.
    - Trả về KPI tổng quan và danh sách dòng chi tiết.
  - `get_previous_run(ctx: Ctx, run_id: int) -> dict[str, Any] | None`:
    - Tìm run DONE trước đó gần nhất cùng `TEMPLATE_ID` và `PROFILE_CODE`.
- Viết bộ unit test `tests/unit/test_dashboard_service.py` kiểm thử đầy đủ các hàm service, đặc biệt test 2 run khác dữ liệu đếm đúng 3 nhóm.
- Chạy `uv run poe test` xác nhận xanh.

### Bước 2 — UI Dashboard (`app/ui/pages/dashboard.py`)
- Cập nhật `app/ui/pages/dashboard.py` (Screen01):
  - Gọi service `get_dashboard_summary(ctx)`.
  - Hiển thị 4 thẻ KPI chuẩn: Run trong kỳ, Tỉ lệ khớp trung bình, Chưa kiểm tra (kèm meta dung lượng dữ liệu tạm), Việc của tôi.
  - Khối "Tỉ lệ lệch theo template" với bảng hiển thị số lượng và thanh tỉ lệ lệch trực quan.
  - Bảng "Run gần đây" với 7 cột chuẩn, dòng có thể bấm để chuyển hướng xem kết quả run.
  - Banner cảnh báo dữ liệu tạm khi vượt ngưỡng (dành cho Admin).
  - 4 trạng thái giao diện: Đang tải, Trống (chưa có run), Lỗi (thông báo + nút Thử lại), Dữ liệu bình thường.
- Cập nhật và bổ sung unit test `tests/unit/test_page_dashboard.py`.
- Chạy `uv run poe test` và `uv run poe e2e`.

### Bước 3 — So sánh run (`app/ui/pages/run_result.py`)
- Bổ sung nút "So với run trước" trên thanh Header của `Screen06-RunResult`.
- Tạo Drawer/Modal "So sánh với run trước" (`run-res-compare-drawer`):
  - Hiển thị thông tin 2 run được so sánh (mặc định run hiện tại và run trước đó, hoặc cho phép chọn run từ danh sách).
  - 4 thẻ KPI chỉ số chênh lệch: Chỉ có ở Run A, Chỉ có ở Run B, Đổi trạng thái, Giữ nguyên.
  - Bảng so sánh chi tiết hỗ trợ lọc theo 3 nhóm, tìm kiếm theo khóa.
- Thêm callbacks mở drawer, tải dữ liệu so sánh và lọc bảng.
- Viết test trong `tests/unit/test_page_run_result.py`.
- Kiểm tra toàn bộ tiêu chuẩn nghiệm thu: `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe e2e`.
