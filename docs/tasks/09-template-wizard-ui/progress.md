# Tiến độ — 09-template-wizard-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Khung + state + autosave | ✅ | 2026-11-01 | 14c0002 |
| 2 | Bước 1–2 | ✅ | 2026-11-01 |  |
| 3 | Bước 3 | 🔄 | 2026-11-01 |  |
| 4 | Bước 4 | ⬜ |  |  |
| 5 | Bước 5 + kích hoạt | ⬜ |  |  |
| 6 | Tab sơ đồ | ⬜ |  |  |

## Nhật ký
### Bước 2 — 2026-11-01 02:57
- Đã làm: Cài đặt giao diện và xử lý logic cho Bước 1 (File mẫu & cấu trúc) và Bước 2 (Định nghĩa & ánh xạ trường) trong Wizard (`app/ui/pages/template_wizard.py`):
  - Bước 1 — File mẫu & Cấu trúc file (`render_step_1`):
    - Tích hợp vùng kéo thả file mẫu `file_drop` giới hạn 50MB định dạng `.xlsx`.
    - Ô cấu hình: Sheet, Dòng header (`NumberInput`), Dòng bắt đầu dữ liệu (`NumberInput`), các Badge header bắt buộc nhận diện file.
    - Khối "Hệ thống phát hiện": 4 alert thông báo theo tone màu (số cột/dòng, cảnh báo dòng cuối là dòng tổng đề xuất loại bỏ làm control total, tỷ lệ duy nhất của Số hóa đơn đề xuất mức gộp, cột Mã giao dịch đọc dạng Text tránh mất số 0 đầu) kèm Checkbox áp dụng đề xuất.
    - Khối xem trước 5 dòng: Bảng hiển thị 5 dòng dữ liệu mẫu đầu tiên từ file mẫu định dạng chuẩn (mã mono, số căn phải).
  - Bước 2 — Định nghĩa & Ánh xạ trường (`render_step_2`):
    - Tiêu đề "Cột Excel → Trường logic" kèm các nút hành động "Gợi ý lại" và "Trường dẫn xuất".
    - Bảng ánh xạ: Checkbox Dùng, Cột Excel mẫu, Trường logic (input mono có validation lỗi), Nhãn tiếng Việt, Kiểu dữ liệu (text, number, date, datetime), Danh sách chip chuẩn hóa (trim, upper, value_map, derived), Giá trị mẫu.
    - Hỗ trợ hiển thị và phân biệt các trường dẫn xuất (`derived`).
  - Kết nối callback hiển thị nội dung động `handle_render_step_content` theo bước active của Stepper.
  - Bổ sung test đơn vị `test_render_step_1_and_step_2` trong `tests/unit/test_page_template_wizard.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_template_wizard.py` (5 passed); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Khối Hệ thống phát hiện giúp người dùng nhận diện ngay cấu trúc file và dòng tổng mà không cần mở Excel kiểm tra thủ công.
- Việc cần người làm thủ công: Không có.
### Bước 1 — 2026-11-01 02:54
- Đã làm: Cài đặt khung màn hình Wizard Đăng ký & Chỉnh sửa Template (`app/ui/pages/template_wizard.py`, Screen03):
  - Phân quyền RBAC: Chỉ tài khoản có vai trò `ADMIN` hoặc `TEMPLATE_OWNER` mới được truy cập; các vai trò khác bị chặn và chuyển hướng `/forbidden`.
  - Hỗ trợ các tuyến đường `/templates/new` (tạo mới từ đầu hoặc file mẫu) và `/templates/<template_id>/edit` (nạp cấu hình bản nháp hoặc cấu hình phiên bản hiện hành).
  - Tiêu đề màn hình H1: `Đăng ký template: {template_code}`, phụ đề hiển thị bản nháp v{N}, Data Source và bảng nguồn.
  - Bộ chuyển Tab đầu trang (SegmentedControl): `Cấu hình template` và `Sơ đồ diễn giải`.
  - Thanh tiến trình Stepper 5 bước: `1. File mẫu`, `2. Định nghĩa trường`, `3. Nguồn DB`, `4. Profile so sánh`, `5. Dry-run`.
  - Quản lý trạng thái bằng các Store: `wizard-config-store` (lưu trữ cấu trúc TemplateConfig dict), `wizard-meta-store` (lưu trữ template_id, version nháp, is_dirty, bước hiện tại, thời gian lưu gần nhất).
  - Cơ chế tự động lưu nháp qua `dcc.Interval` (mỗi 15s tự động lưu nếu có thay đổi dirty) và nút "Lưu nháp" thủ công gọi service `save_draft_template`.
  - Nút điều hướng chân trang: "Quay lại" và "Tiếp" / "Lưu & kích hoạt".
  - Các hàm tiện ích: `config_to_form_state`, `form_state_to_config` (validate Pydantic và ánh xạ lỗi sang đường dẫn tương ứng qua `map_validation_errors`), `build_default_config`.
  - Viết bộ test đơn vị `tests/unit/test_page_template_wizard.py` (4 tests).
- Kiểm tra: `uv run pytest tests/unit/test_page_template_wizard.py` (4 passed); `uv run poe test` (250 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Quản lý cấu hình bằng `dcc.Store` kết hợp với validation Pydantic v2 ở mỗi lần chuyển đổi giúp phát hiện sớm sai lệch trước khi ghi DB.
- Việc cần người làm thủ công: Không có.

## Nhật ký
<!-- ### Bước N — YYYY-MM-DD HH:mm
- Đã làm:
- Kiểm tra: lệnh + kết quả (ghi rõ test Oracle bị skip hay đã chạy qua VPN)
- Suy ra (nếu có):
- Việc cần người làm thủ công:
-->
