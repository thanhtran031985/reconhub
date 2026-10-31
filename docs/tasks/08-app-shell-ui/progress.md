# Tiến độ — 08-app-shell-ui

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Component + gallery | ✅ | 2026-11-01 | 784f80b |
| 2 | AppShell + banner | ✅ | 2026-11-01 | 5d39b0a |
| 3 | Màn Templates | ✅ | 2026-11-01 | 28eb315 |
| 4 | Màn Data Sources | ✅ | 2026-11-01 | 6457186 |
| 5 | Màn Người dùng | ✅ | 2026-11-01 | 5d653f6 |

## Nhật ký
### Bước 5 — 2026-11-01 02:46
- Đã làm: Cài đặt màn hình Quản lý Người dùng (`app/ui/pages/users.py`, Screen11):
  - Phân quyền RBAC: Chỉ người dùng có vai trò `ADMIN` mới được truy cập, người dùng vai trò khác bị chuyển hướng tới `/forbidden`.
  - Tiêu đề màn hình đếm động tổng số tài khoản và số tài khoản đang tạm khóa; nút "Thêm người dùng" (icon `lucide:plus`) và nút làm mới dữ liệu.
  - Bộ lọc: Ô tìm kiếm (username, họ tên, email) kèm debounce; Chọn vai trò (Tất cả, Admin, Template Owner, Operator, Viewer); Chọn trạng thái (Tất cả, Hoạt động, Tạm khóa, Đã tắt).
  - Bảng dữ liệu: Username (font mono đậm), Họ tên, Email, Vai trò (`status_chip` hoặc Badge nhiều vai trò), Trạng thái (Hoạt động `status_chip` tone ok, Tạm khóa đến HH:mm tone warn, Đã tắt tone off, Chờ đổi mật khẩu tone info), Lần đăng nhập cuối; Cột thao tác: Sửa, Đặt lại mật khẩu, Mở khóa (hiển thị khi tài khoản đang bị tạm khóa).
  - Ngăn kéo Thêm / Sửa người dùng (Drawer 540px): Tên đăng nhập (chỉ nhập khi tạo, vô hiệu hóa khi sửa), Họ tên, Email, Nhóm checkbox vai trò (bắt buộc ≥ 1); Khi tạo mới: Mật khẩu ban đầu và tùy chọn bắt đổi mật khẩu lần đầu; Khi sửa: Khối chuyển đổi trạng thái Bật / Tắt tài khoản (chặn tắt quản trị viên cuối cùng `LAST_ADMIN`), bảng lịch sử đăng nhập gần nhất hiển thị thời gian, kết quả và địa chỉ IP.
  - Hộp thoại Đặt lại mật khẩu (Modal): Nhập mật khẩu mới, tùy chọn bắt đổi mật khẩu lần tới, cảnh báo đăng xuất các phiên đang mở và tự động mở khóa tài khoản.
  - Đáp ứng 4 trạng thái giao diện: Đang tải, Trống, Lỗi (có nút Thử lại) và Có dữ liệu.
  - Viết bộ test `tests/unit/test_page_users.py` (4 passed) và bổ sung test e2e `tests/e2e/test_e2e_screens.py` (3 passed).
- Kiểm tra: `uv run pytest tests/unit/test_page_users.py` (4 passed); `uv run poe e2e` (3 passed); `uv run poe test` (246 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Thao tác mở khóa nhanh trên bảng giúp quản trị viên xử lý ngay khi nhân viên bị khóa tài khoản do gõ sai mật khẩu nhiều lần mà không cần mở drawer.
- Việc cần người làm thủ công: Không có.
### Bước 4 — 2026-11-01 02:18
- Đã làm: Cài đặt màn hình Data Sources và Quản lý Lưu trữ (`app/ui/pages/data_sources.py`, Screen08) với 2 tab:
  - Tab 1 "Nguồn đối soát": Bảng danh sách nguồn Oracle (mã nguồn font mono, tên hiển thị, host:port/service, người dùng, ngày cập nhật, trạng thái kiểm tra kết nối `status_chip`, thao tác Kiểm tra kết nối và Sửa); Ngăn kéo thêm/sửa nguồn đối soát (Drawer) với validation đầy đủ, lưu mật khẩu mã hóa Fernet.
  - Tab 2 "Lưu trữ RECON_APP": 3 thẻ KpiCard chỉ số dung lượng (Dung lượng dữ liệu tạm / Dung lượng tối đa cảnh báo, Dòng dữ liệu tạm, Dòng đã đối soát xong); Form bộ lọc dọn dẹp (chọn template, trước ngày, chỉ xóa dòng đã đối soát); Hộp thoại Modal xác nhận xóa nhạy cảm yêu cầu gõ chính xác từ khóa "XOA" trước khi thực hiện; Bảng nhật ký xóa (`RECON_PURGE_LOG`) gồm thời gian, người thực hiện, điều kiện lọc, số dòng xóa, dung lượng giải phóng; Khung code hiển thị kịch bản SQL tạo người dùng chỉ đọc trên Oracle đích (`generate_target_user_sql` tại `app/services/oracle_admin.py`) tích hợp nút sao chép.
  - Phân quyền nghiêm ngặt: Màn hình chỉ dành riêng cho vai trò Admin, người dùng không có quyền Admin bị chặn và chuyển hướng thông báo không có quyền truy cập.
  - Xử lý vấn đề trùng lặp định danh trang Dash (`PAGE_REGISTRY`) khi import trang trong môi trường kiểm thử.
  - Viết bộ test đơn vị `tests/unit/test_page_data_sources.py` (4 tests) và test e2e truy cập màn hình.
- Kiểm tra: `uv run pytest tests/unit/test_page_data_sources.py` (4 passed); `uv run poe test` (241 passed, 4 skipped); `uv run poe lint` (pass); `uv run poe typecheck` (pass).
- Suy ra (nếu có): Tách tiện ích sinh script SQL tạo user Oracle sang module `app/services/oracle_admin.py` giúp quản lý mã nguồn sạch và tái sử dụng khi cần.
- Việc cần người làm thủ công: Không có.
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
