# Kế hoạch thực hiện — Task 10: Màn Chạy đối soát (10-new-run-ui)

## 1. Mục tiêu và phạm vi
Xây dựng màn hình Chạy đối soát (`/runs/new`, `Screen05-NewRun`) theo PRD C5 và thiết kế `designs/components/Screen05-NewRun`:
- Cho phép Operator, Template Owner và Admin upload file dữ liệu Excel/CSV (tối đa 50MB).
- Tự động nhận diện Template dựa trên cấu trúc header (`detect_by_headers`) hoặc cho phép chọn thủ công nếu không tự nhận diện được.
- Đọc và thẩm định file: đếm số dòng hợp lệ, dòng tổng đã loại, tính và hiển thị trạng thái Control Total.
- Cấu hình Profile đối soát, Data Source (DEV/PROD), tham số lọc bắt buộc: `Từ ngày giờ` (`p_from`, datetime-local có giây), `Đến ngày giờ` (`p_to`, datetime-local có giây), nút chọn nhanh ("Hôm qua", "Tháng trước"), và các tham số khác theo template (như `p_org`).
- Kiểm tra tính hợp lệ của khoảng thời gian (Từ <= Đến, tối đa 93 ngày) và precheck số dòng ngoài khoảng.
- Cảnh báo trùng run nếu đã có run cùng template và khoảng thời gian.
- Hộp thoại xác nhận an toàn khi chạy trên môi trường PROD.
- Tiến độ thực thi trực quan n/5 giai đoạn (`dcc.Interval`) và chuyển hướng sang màn kết quả `/runs/<id>` khi hoàn tất.

## 2. Kiến trúc & Components
- Tuyến đường: `/runs/new` đăng ký qua `dash.register_page` trong `app/ui/pages/new_run.py`.
- Quyền truy cập RBAC: `OPERATOR`, `TEMPLATE_OWNER`, `ADMIN`.
- Các Store quản lý trạng thái:
  - `new-run-file-store`: Lưu thông tin file đã upload (`file_id`, `filename`, `size_bytes`, `storage_path`).
  - `new-run-template-store`: Lưu thông tin template được chọn (`template_id`, `version`, `config`).
  - `new-run-state-store`: Lưu trạng thái form, validation, precheck, và run_id khi chạy.
- Giao diện:
  - `file_drop` cho vùng upload.
  - `alert_box` cho các thông báo file, nhận diện template, precheck và cảnh báo trùng run.
  - `kpi_card` và các trường nhập liệu DMC `TextInput`, `Select`, `Checkbox`, `Progress`.
  - `modal_confirm` cho xác nhận chạy trên nguồn dữ liệu PROD.

## 3. Các bước thực hiện

### Bước 1 — Upload + nhận diện template
- Viết test trước trong `tests/unit/test_page_new_run.py`:
  - Upload file mẫu `dtp_sample_200.xlsx` -> nhận diện đúng `DTP_HOA_DON_TAC_NGHIEP v1`.
  - Hiển thị đầy đủ thông tin: tên file, kích thước, số dòng hợp lệ (200), số dòng tổng loại (1), control total khớp.
- Cài đặt `render_file_section` và callbacks upload file, lưu trữ file qua `upload_file`, và tự động nhận diện template qua `detect_template`.
- Kiểm tra: `uv run pytest tests/unit/test_page_new_run.py`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 2 — Tham số + precheck
- Viết test trước trong `tests/unit/test_page_new_run.py`:
  - Chọn nhanh 'Hôm qua', 'Tháng trước' tính toán chính xác ngày giờ ISO đầu và cuối.
  - Bắt lỗi khi thiếu `p_from` hoặc `p_to`, khi `p_from > p_to`, hoặc khi khoảng > 93 ngày -> nút Chạy bị vô hiệu hóa kèm thông báo lỗi `rmsg`.
  - Kiểm tra precheck gọi service `precheck` thành công.
- Cài đặt `render_params_section`, hàm `validate_run_params`, hàm `compute_quick_range`, và callback precheck debounced.
- Cảnh báo trùng run nếu tìm thấy run đã hoàn thành trước đó.
- Kiểm tra: `uv run pytest tests/unit/test_page_new_run.py`, `uv run poe lint`, `uv run poe typecheck`.

### Bước 3 — Chạy đối soát + tiến độ + Modal PROD & E2E
- Viết test trước:
  - Chọn Data Source PROD -> mở Modal xác nhận PROD trước khi gọi run.
  - Chạy run thành công -> tạo run trong `RECON_RUN`, mô phỏng hoặc theo dõi tiến độ n/5 giai đoạn, chuyển hướng sang `/runs/<id>`.
  - E2E test truy cập trang `/runs/new` trong `tests/e2e/test_e2e_screens.py`.
- Cài đặt `render_execution_section`, modal PROD `modal_confirm`, callback kích hoạt run gọi `create_run`, interval theo dõi tiến độ và điều hướng URL.
- Kiểm tra toàn bộ: `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`, `uv run poe e2e`.
- Cập nhật tài liệu tiến độ `progress.md`, `docs/tasks/README.md`, chạy `uv run poe tasks-dashboard`.
