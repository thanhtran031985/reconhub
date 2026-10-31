# Tiến độ — 10-new-run-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Upload + nhận diện | ✅ | 2026-11-01 | c9b8701 |
| 2 | Tham số + precheck | ✅ | 2026-11-01 | c9b8701 |
| 3 | Chạy + tiến độ | ✅ | 2026-11-01 | c9b8701 |

## Nhật ký
### Bước 3 — 2026-11-01 03:22
- Đã làm: Cài đặt khối thực thi đối soát, hộp thoại xác nhận an toàn PROD, theo dõi tiến độ n/5 giai đoạn và kiểm thử E2E:
  - Khối 3. Thực thi: Nút "Chạy đối soát" kèm text hiển thị lý do khóa nút trực quan khi chưa chọn file hoặc khoảng thời gian chưa hợp lệ.
  - Hộp thoại Modal xác nhận môi trường PROD (`modal_confirm`): Tự động phát hiện Data Source có `ENV == 'PROD'` để cảnh báo và yêu cầu xác nhận trước khi gửi truy vấn sang Oracle PROD.
  - Theo dõi tiến độ chạy trực quan qua `dmc.Progress` và `dcc.Interval` theo 5 giai đoạn:
    1. Đọc và chuẩn hóa file
    2. Lọc thời gian, control total, lưu dữ liệu tạm
    3. Truy vấn Oracle (qua VPN)
    4. So sánh 190 nhóm
    5. Ghi kết quả
  - Tự động chuyển hướng URL về trang kết quả `/runs/<id>` khi hoàn tất.
  - Bổ sung test E2E `test_e2e_new_run_page_accessible` trong `tests/e2e/test_e2e_screens.py`.
- Kiểm tra: `uv run pytest tests/e2e/test_e2e_screens.py` (5 passed); `uv run poe lint` (pass); `uv run poe typecheck` (pass); `uv run poe test` (264 passed, 4 skipped).
- Suy ra (nếu có): Cơ chế cảnh báo PROD giúp bảo vệ dữ liệu sản xuất, đồng thời thanh tiến độ 5 giai đoạn đem lại trải nghiệm tương tác trực quan cho Operator.
- Việc cần người làm thủ công: Không có.
### Bước 2 — 2026-11-01 03:20
- Đã làm: Cài đặt khối 2. Profile và tham số tìm kiếm (`render_params_section`):
  - Lựa chọn Profile đối soát và Data Source kết nối Oracle.
  - Bộ tham số thời gian: `Từ ngày giờ (p_from)` và `Đến ngày giờ (p_to)` bắt buộc theo chuẩn `datetime-local` có giây (`step="1"`), tham số đơn vị `p_org` (mono).
  - Hàm kiểm tra hợp lệ `validate_run_params`: Bắt buộc nhập cả hai đầu, `p_from <= p_to`, tối đa 93 ngày; hiển thị thông báo lỗi `rmsg` trực tiếp dưới hai ô input.
  - Nút chọn nhanh: "Hôm qua" và "Tháng trước" tính toán chính xác mốc thời gian ISO đầu và cuối ngày.
  - Checkbox "Áp dụng cùng khoảng thời gian cho dữ liệu Excel" (mặc định bật).
  - Khối Precheck: Hiển thị thông báo bind parameter và ước tính số dòng Excel ngoài khoảng.
  - Cảnh báo trùng run: Kiểm tra nếu đã có run hoàn thành với cùng template và khoảng thời gian.
  - Viết test đơn vị `test_quick_range_calculation`, `test_validate_run_params`, `test_render_params_and_execution_section` trong `tests/unit/test_page_new_run.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_new_run.py` (7 passed); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Chọn nhanh thời gian giúp Operator thao tác nhanh gọn đối soát định kỳ hàng ngày và hàng tháng mà không phải chọn thủ công từng mốc giờ.
- Việc cần người làm thủ công: Không có.
### Bước 1 — 2026-11-01 03:16
- Đã làm: Cài đặt màn hình Chạy đối soát (`app/ui/pages/new_run.py`, Screen05) và khối Upload + nhận diện template:
  - Tuyến đường `/runs/new`, kiểm tra quyền hạn RBAC cho `OPERATOR`, `TEMPLATE_OWNER`, `ADMIN` (chuyển hướng `/forbidden` nếu không có quyền).
  - Hiển thị Empty state nếu hệ thống chưa có template nào ở trạng thái ACTIVE kèm nút "Đăng ký template".
  - Vùng kéo thả file `file_drop` (hỗ trợ .xlsx, .xls, .csv tối đa 50MB).
  - Hàm xử lý upload `process_uploaded_file`: Gọi `upload_file` lưu kho lưu trữ an toàn, tự động nhận diện template qua `detect_template`, áp dụng bộ lọc dòng `apply_row_filters` để loại dòng tổng footer và tính toán Control Total.
  - Khối thông báo file: Tên file, dung lượng, nút "Đổi file", alert nhận diện template (khớp 3/3 header), alert số dòng hợp lệ (200 dòng), số dòng tổng loại bỏ (1 dòng) và alert Control Total khớp.
  - Viết test đơn vị `test_render_file_section_empty`, `test_process_uploaded_file_and_render` trong `tests/unit/test_page_new_run.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_new_run.py` (passed); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Tự động nhận diện template từ header giúp người dùng chỉ cần kéo thả file mà không cần nhớ mã template.
- Việc cần người làm thủ công: Không có.
