# Tiến độ — 08-app-shell-ui

Trạng thái: 🔄

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Component + gallery | ✅ | 2026-11-01 | 784f80b |
| 2 | AppShell + banner | ✅ | 2026-11-01 | 5d39b0a |
| 3 | Màn Templates | ✅ | 2026-11-01 |  |
| 4 | Màn Data Sources | 🔄 | 2026-11-01 |  |
| 5 | Màn Người dùng | ⬜ |  |  |

## Nhật ký
### Bước 3 — 2026-11-01 02:02
- Đã làm: Cài đặt trọn vẹn màn hình Quản lý Template tại `app/ui/pages/templates.py` (Screen02). Thiết kế chuẩn giao diện: tiêu đề và mô tả, nút "Đăng ký template" (dẫn tới Wizard), nút "Import JSON" (kèm modal kéo thả file và switch ghi đè), nút làm mới danh sách; thanh tìm kiếm và lọc trạng thái (ACTIVE / DRAFT / ARCHIVED). Bảng template hiển thị đầy đủ thông tin: Mã template (font mono), Tên & mẫu file, Số trường logic, Danh sách profiles (kèm profile mặc định đánh dấu bằng key icon), Phiên bản, Chủ sở hữu (@username), Trạng thái (`status_chip`), và Menu thao tác (Sửa, Sơ đồ, Nhân bản, Export JSON tải file JSON, Lưu trữ). Đáp ứng đủ 4 trạng thái giao diện: Đang tải (Skeleton), Trống (EmptyState), Lỗi (Alert + nút Thử lại), và Có dữ liệu. Cài đặt các callbacks xử lý tải danh sách, lọc, Import JSON, Nhân bản template (`clone_template`), Lưu trữ template (`archive_template`) và Export JSON (`dcc.Download`). Viết bộ test `tests/unit/test_page_templates.py` và test e2e `tests/e2e/test_e2e_screens.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_templates.py` (4 passed); `uv run poe e2e` (1 passed); `uv run poe test` (236 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Tích hợp tải file trực tiếp qua `dcc.Download` kết hợp dịch vụ `export_template` giúp xuất cấu hình JSON mượt mà ngay trên giao diện mà không cần reload trang.
- Việc cần người làm thủ công: Không có.
### Bước 2 — 2026-11-01 01:55
- Đã làm: Tái cấu trúc package layout `app/ui/layout/` với module `shell.py`. Xây dựng khung ứng dụng AppShell gồm thanh bên Navbar 232px (nền nav-bg, logo ReconHub, danh mục menu phân quyền chặt chẽ theo 4 vai trò Admin, Template Owner, Operator, Viewer); thanh trên Header 56px tích hợp Breadcrumbs định hướng động, nhãn môi trường (DEV/UAT/PROD) và menu người dùng góc phải (Tài khoản, Đăng xuất). Cài đặt cơ chế hiển thị Banner thông báo: Banner bảo trì (khi setting `MAINTENANCE_MODE == 'Y'`) và Banner cảnh báo dung lượng dữ liệu tạm (chỉ hiển thị cho vai trò Admin khi vượt ngưỡng dung lượng, kèm liên kết dẫn tới tab Lưu trữ). Viết bộ test `tests/unit/test_ui_shell.py` kiểm chứng quyền xem menu, điều kiện bật banner và sinh breadcrumb.
- Kiểm tra: `uv run pytest tests/unit/test_ui_shell.py` (3 passed); `uv run poe test` (231 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Tách cấu trúc layout dạng package giúp mở rộng các layout phụ mà vẫn duy trì tính tương thích ngược cho `app.py`.
- Việc cần người làm thủ công: Không có.
### Bước 1 — 2026-11-01 01:51
- Đã làm: Cài đặt trọn vẹn bộ component Dash Mantine tại `app/ui/components/`: `status_chip` (đủ 7 trạng thái kết quả, trạng thái run, trạng thái người dùng, trạng thái template, dữ liệu tạm, môi trường, vai trò — luôn đảm bảo icon lucide và nhãn chữ); `form_field` (hỗ trợ label, description/hint, required asterisk, tự động gán `aria-describedby` trỏ tới thông báo lỗi khi có lỗi); `kpi_card` (thẻ chỉ số chuẩn hoá màu sắc tone ok/crit/warn); `alert_box` (thông báo theo tone kèm icon và nút action); `empty_state` (trạng thái trống với icon, mô tả và nút hành động); `button_primary`, `button_danger`, `button_subtle`; `modal_confirm` (hộp thoại xác nhận thao tác nhạy cảm, hỗ trợ ô gõ từ khóa xác nhận ví dụ XOA); `drawer_right` (ngăn kéo 540px chuẩn); `file_drop` (vùng kéo thả 50MB); `code_block` (hiển thị mã SQL có nút sao chép). Cài đặt các hàm định dạng `app/ui/formatters.py` (`format_currency`, `format_number`, `format_datetime`, `format_bytes`). Tạo trang thư viện `app/ui/pages/dev_gallery.py` tại đường dẫn `/dev/ui`. Viết bộ test `tests/unit/test_ui_components.py`.
- Kiểm tra: `uv run pytest tests/unit/test_ui_components.py` (3 passed); `uv run poe test` (228 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Toàn bộ component UI tuân thủ triệt để design token từ theme DMC và không hardcode mã màu hex trong các trang.
- Việc cần người làm thủ công: Không có.
