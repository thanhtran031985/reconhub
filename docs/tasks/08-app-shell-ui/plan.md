# Kế hoạch thực hiện — 08-app-shell-ui

## Mục tiêu
Xây dựng bộ component Dash Mantine theo thiết kế `designs/`, khung ứng dụng AppShell phân quyền theo 4 vai trò, kèm banner bảo trì và banner cảnh báo dung lượng tạm; hoàn thiện 3 màn hình cốt lõi: Templates (Screen02), Data Sources (Screen08 - 2 tab với khối xóa dữ liệu tạm an toàn), và Người dùng (Screen11) kết nối trực tiếp với các dịch vụ nghiệp vụ đã hoàn thành ở các task trước, đáp ứng đủ 4 trạng thái giao diện (Loading, Empty, Error, Data).

---

## Chi tiết các bước thực hiện

### Bước 1 — Bộ component chuẩn hóa & Dev Gallery
- **Tập tin tạo/sửa**:
  - `app/ui/components/__init__.py`
  - `app/ui/components/status_chip.py`: Chip trạng thái luôn kèm icon nét lucide + chữ (7 trạng thái so sánh, trạng thái run, trạng thái người dùng, trạng thái template, trạng thái dữ liệu tạm, nhãn môi trường).
  - `app/ui/components/field.py`: Wrapper các loại input (text, password, select, multiselect, textarea mono, datetime, checkbox, switch, number) chuẩn hóa label, hint/description, error, withAsterisk và thuộc tính `aria-describedby`.
  - `app/ui/components/kpi_card.py`: Thẻ chỉ số hiển thị label, value đã format, tone màu, meta text và icon.
  - `app/ui/components/alert_box.py`: Thông báo Alert với tone (ok, crit, warn, info), icon, tiêu đề và action.
  - `app/ui/components/empty_state.py`: Trạng thái trống gồm icon, tiêu đề, mô tả và nút hành động.
  - `app/ui/components/button.py`: Các wrapper chuẩn hóa button primary, danger, subtle kèm trạng thái loading.
  - `app/ui/components/modal_confirm.py`: Hộp thoại modal xác nhận thao tác quan trọng/xóa dữ liệu kèm ô gõ từ khóa xác nhận.
  - `app/ui/components/drawer.py`: Drawer chuẩn trượt từ cạnh phải (size 540px).
  - `app/ui/components/file_drop.py`: Vùng kéo thả upload bọc `dcc.Upload` với styling Paper.
  - `app/ui/components/code_block.py`: Khối hiển thị mã/SQL chuẩn định dạng với nút copy.
  - `app/ui/formatters.py`: Các hàm định dạng hiển thị chuẩn: `format_currency` (phân cách hàng ngàn bằng dấu chấm, "—" khi None), `format_datetime` (dd/MM/yyyy HH:mm:ss giờ VN), `format_bytes` (B, KB, MB, GB theo chuẩn Việt Nam).
  - `app/ui/pages/dev_gallery.py`: Trang `/dev/ui` tổng hợp trưng bày mọi component ở các trạng thái.
- **Test viết trước**:
  - `tests/unit/test_ui_components.py`: Kiểm tra `status_chip` luôn có icon + chữ cho mọi trạng thái; `form_field` sinh `aria-describedby` khi có lỗi; các hàm `formatters` xuất kết quả chính xác theo chuẩn thiết kế.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_ui_components.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 2 — AppShell hoàn chỉnh & Banner thông báo
- **Tập tin tạo/sửa**:
  - `app/ui/layout/shell.py`:
    - Thanh bên Navbar 232px (nền nav-bg, thu gọn 64px): Cụm menu "Đối soát" (Dashboard, Chạy đối soát, Lịch sử); Cụm menu "Cấu hình" lọc theo vai trò (Templates cho Admin/TemplateOwner/Operator; Đăng ký template cho Admin/TemplateOwner; Data Sources & Người dùng CHỈ CHO Admin).
    - Thanh trên Header 56px: Breadcrumbs định hướng động, nhãn môi trường (DEV/UAT/PROD), Menu người dùng góc phải (Tài khoản, Đăng xuất).
    - Cụm Banner cảnh báo dưới Header:
      - Banner Bảo trì: khi hệ thống ở chế độ bảo trì (`MAINTENANCE_MODE == 'Y'`).
      - Banner Dữ liệu tạm: khi dung lượng dữ liệu tạm vượt ngưỡng cảnh báo (`usage.is_warning == True`), chỉ hiển thị cho Admin kèm liên kết "Xem và xóa".
  - Cập nhật `app/ui/app.py` và `app/ui/layout.py` đồng bộ cấu trúc AppShell mới.
- **Test viết trước**:
  - `tests/unit/test_ui_shell.py`: Kiểm tra danh sách menu xuất hiện chính xác theo 4 vai trò (Admin, Template Owner, Operator, Viewer); kiểm tra điều kiện xuất hiện của Banner bảo trì và Banner dữ liệu tạm.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_ui_shell.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 3 — Màn hình Quản lý Template (Screen02-Templates)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/templates.py`:
    - Tiêu đề "Danh sách template", nút "Đăng ký template" (mở Wizard), nút "Import JSON" (modal upload), ô tìm kiếm/lọc trạng thái.
    - Bảng Template: Mã template (mono), Tên template, Cấu hình nhận diện file, Số trường logic, Profiles (chip), Phiên bản, Người tạo / Chủ sở hữu, Trạng thái (ACTIVE / DRAFT / ARCHIVED), Thao tác (Sửa, Nhân bản, Export JSON, Lưu trữ).
    - Đủ 4 trạng thái: Loading (Skeleton), Empty ("Chưa có template nào"), Error ("Không thể tải danh sách template" + nút Thử lại), Data.
    - Callbacks xử lý: Tìm kiếm/lọc, Modal Import JSON (gọi `template.import_template`), Export JSON (`template.export_template`), Modal Nhân bản (`template.clone_template`), Modal Lưu trữ (`template.archive_template`).
- **Test viết trước**:
  - `tests/unit/test_page_templates.py`: Kiểm tra render 4 trạng thái, xử lý callback clone, archive, export JSON.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_templates.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 4 — Màn hình Data Sources & Lưu trữ RECON_APP (Screen08-DataSources)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/data_sources.py`:
    - Kiểm quyền truy cập: Chỉ tài khoản có vai trò `ADMIN` mới được truy cập; người dùng khác chuyển hướng tới `/forbidden`.
    - Tab 1 — "Nguồn đối soát": Danh sách nguồn DB từ `data_source.list_data_sources(purpose="SOURCE")`; nút "Thêm nguồn đối soát" mở Drawer; Drawer thêm/sửa kết nối; nút "Kiểm tra kết nối" (gọi `data_source.test_data_source_connection`).
    - Tab 2 — "Lưu trữ RECON_APP":
      - DB đang dùng: Loại DB (SQLite/Oracle), File/Host, Phiên bản schema, Dung lượng.
      - Dữ liệu tạm: 3 KpiCard (Dung lượng tạm, Run chưa kiểm tra, Run cũ quá hạn); ô nhập cấu hình ngưỡng cảnh báo GB và số ngày giữ; nút "Lưu ngưỡng".
      - Xóa dữ liệu tạm theo điều kiện: Form lọc (Template, Đã kiểm tra, Thời gian chạy, Người chạy), nút "Xem trước" gọi `temp_data.preview` -> Alert thông báo kết quả xem trước + nút "Xóa n run" (danger) -> Modal xác nhận gõ đúng từ khóa `XOA` -> gọi `temp_data.purge_filter`.
      - Nhật ký xóa dữ liệu tạm: Bảng hiển thị từ `RECON_PURGE_LOG`.
      - Đích Oracle đã đăng ký & Script tạo user: Hiển thị CodeBlock script SQL `oracle_admin.generate_target_user_sql`.
      - Khối chuẩn bị cho Chuyển dữ liệu sang Oracle & Bản lưu SQLite cũ (Task 13).
- **Test viết trước**:
  - `tests/unit/test_page_data_sources.py`: Kiểm tra chặn quyền Viewer/Operator; kiểm tra nạp danh sách nguồn; kiểm tra callback xem trước và xóa dữ liệu tạm với từ khóa `XOA`.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_data_sources.py`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

### Bước 5 — Màn hình Quản lý Người dùng (Screen11-Users)
- **Tập tin tạo/sửa**:
  - `app/ui/pages/users.py`:
    - Kiểm quyền truy cập: Chỉ tài khoản có vai trò `ADMIN` mới được truy cập; người dùng khác chuyển hướng tới `/forbidden`.
    - Tiêu đề "Quản lý người dùng", đếm tổng số tài khoản và số tài khoản đang tạm khóa; nút "Thêm người dùng".
    - Thanh lọc: Tìm kiếm theo username, họ tên, email; lọc theo vai trò (Admin, Template Owner, Operator, Viewer); lọc theo trạng thái tài khoản.
    - Bảng Người dùng từ `user_service.list_users`: Username (mono), Họ tên, Email, Vai trò (chip nhiều), Trạng thái (Hoạt động, Tạm khóa đến HH:mm, Đã tắt, Chờ đổi mật khẩu), Lần đăng nhập cuối.
    - Drawer "Thêm người dùng": Username (mono, bất biến sau tạo), Họ tên, Email, Chọn vai trò (checkbox nhiều, bắt buộc >= 1), Mật khẩu ban đầu, Switch "Bắt đổi mật khẩu lần đầu".
    - Drawer "Sửa thông tin": Cập nhật họ tên, email, vai trò; nút "Tắt/Bật tài khoản" (bảo vệ last admin); xem danh sách "Lịch sử đăng nhập" gần nhất.
    - Modal "Đặt lại mật khẩu": Mật khẩu mới, switch bắt buộc đổi lần đầu, thông báo đăng xuất các phiên cũ và tự động mở khóa nếu đang bị khóa.
    - Nút "Mở khóa nhanh": Hiện trực tiếp khi tài khoản đang bị tạm khóa.
    - Bảo vệ an toàn: Chặn tắt tài khoản hoặc xóa vai trò Admin của Admin cuối cùng (`LAST_ADMIN_CANNOT_BE_DISABLED`).
    - 4 trạng thái: Loading, Empty, Error, Data.
  - `tests/e2e/test_e2e_screens.py`: Bộ test E2E kiểm tra luồng tương tác trên các màn hình Templates, Data Sources và Users.
- **Test viết trước**:
  - `tests/unit/test_page_users.py`: Kiểm tra phân quyền truy cập, danh sách người dùng, quy tắc cấm tắt Admin cuối cùng, thao tác đặt lại mật khẩu và mở khóa.
- **Kiểm tra**:
  - `uv run pytest tests/unit/test_page_users.py`
  - `uv run poe e2e`
  - `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`

---

## Rủi ro & Giải pháp
1. **DMC 2.x Callback Pattern Matching**: Các component sinh động trong bảng hoặc drawer sử dụng ID dạng dictionary pattern-matching (ví dụ `{"type": "user-edit-btn", "index": user_id}`). Cần dùng `MATCH` / `ALL` đúng chuẩn Dash và kiểm soát `prevent_initial_call=True`.
2. **Phiên làm việc & Context**: Mọi callback truy cập service phải gọi `get_current_ctx()` để lấy context người dùng và truyền vào service để kiểm tra phân quyền RBAC chặt chẽ.
3. **Cơ chế tải trạng thái (4 trạng thái)**: Sử dụng cấu trúc container đồng nhất hỗ trợ Skeleton khi khởi tạo, Alert khi lỗi có nút Thử lại, EmptyState khi trống, và giao diện dữ liệu khi sẵn sàng.
