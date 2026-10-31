# Kế hoạch thực hiện — Task 11: Màn Kết quả run, grid động, Đã kiểm tra xong (11-run-result-ui)

## 1. Mục tiêu và phạm vi
Xây dựng màn hình Kết quả run (`/runs/<run_id>`, `Screen06-RunResult`) theo PRD C6 và thiết kế `designs/components/Screen06-RunResult`:
- Tuyến đường `/runs/<run_id>` hiển thị chi tiết kết quả đối soát theo template, profile, tham số và khoảng ngày giờ đã chọn.
- Header: Mã run, tên template, phụ đề tóm tắt tham số; Chip trạng thái kiểm tra (`Chưa kiểm tra` / `Đã kiểm tra lúc ...`) và Chip dữ liệu tạm (`Dữ liệu tạm còn ...` / `Đã xóa lúc ...`); Nút hành động: "Đã kiểm tra xong", "Xóa dữ liệu tạm" (nếu còn), "Chạy lại" (chuyển sang `/runs/new`), "Export Excel" (tải file qua `/download/export/<run_id>`).
- 4 KpiCards: Control total file, Tổng tiền Excel trong khoảng, Tổng tiền DB, Chênh lệch.
- Thanh tỉ lệ trạng thái (stacked proportion bar) và bộ tab 7 trạng thái kết quả đối soát kèm số đếm và tiền chênh.
- Tìm kiếm theo khóa (mono) và tùy chọn checkbox "Chỉ hiện cột lệch".
- Bảng dữ liệu Grid cột động sinh từ `get_run_columns` với các nhóm cột Excel | DB | Chênh lệch, highlight ô lệch `rh-diff`.
- Drawer chi tiết dòng khi click vào một hàng kết quả: hiển thị các dòng Excel thô tương ứng (hoặc thông báo dữ liệu đã xóa) và bản ghi DB tương ứng.
- Hộp thoại Modal "Đã kiểm tra xong": Checkbox "Xóa luôn dữ liệu tạm của run này" (mặc định bật), danh sách sẽ xóa / giữ lại, gọi service `mark_checked`.

## 2. Các bước thực hiện

### Bước 1 — Header + KPI + tabs trạng thái
- Viết test trước trong `tests/unit/test_page_run_result.py`:
  - Render header với đầy đủ subtitle, chips kiểm tra và dữ liệu tạm.
  - Render 4 KpiCard từ summary của run.
  - Render thanh tỉ lệ và các tab trạng thái (đếm số lượng từng trạng thái).
- Cài đặt `render_header`, `render_kpis`, `render_ratio_bar_and_tabs` trong `app/ui/pages/run_result.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_run_result.py`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Grid động
- Viết test trước trong `tests/unit/test_page_run_result.py`:
  - Hàm `build_grid_column_defs` sinh cấu trúc cột cho các profile khác nhau.
  - Lọc và tìm kiếm khóa, lọc theo tab trạng thái, lọc "Chỉ hiện cột lệch".
- Cài đặt `render_result_grid` và `build_grid_column_defs` sử dụng bảng hoặc `dag.AgGrid` chuẩn DMC.
- Kiểm tra: `uv run pytest tests/unit/test_page_run_result.py`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Drawer chi tiết + Export Excel
- Viết test trước:
  - Click vào dòng kết quả -> Drawer hiển thị dòng Excel gốc và dòng DB.
  - Khi dữ liệu tạm đã xóa -> Drawer hiển thị alert "Dữ liệu Excel gốc đã xóa lúc ...".
  - Link nút "Export Excel" trỏ đúng route `/download/export/<run_id>`.
- Cài đặt `render_detail_drawer` và callback chọn dòng.
- Kiểm tra: `uv run pytest tests/unit/test_page_run_result.py`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 4 — Đã kiểm tra xong & Xóa dữ liệu tạm + E2E
- Viết test trước:
  - Mở Modal Đã kiểm tra xong -> xác nhận với checkbox purge=True -> gọi `mark_checked(ctx, run_id, purge=True)`.
  - Mở Modal với purge=False -> chỉ đánh dấu kiểm tra, dữ liệu tạm vẫn còn.
  - E2E test màn hình `/runs/<run_id>` trong `tests/e2e/test_e2e_screens.py`.
- Cài đặt callback cho Modal Đã kiểm tra xong và Modal Xóa dữ liệu tạm.
- Kiểm tra toàn bộ: `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe e2e`.
- Cập nhật tiến độ `progress.md`, `docs/tasks/README.md`, chạy `uv run poe tasks-dashboard`.
