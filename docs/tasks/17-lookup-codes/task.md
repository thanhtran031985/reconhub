# 17-lookup-codes — Quản lý danh mục Lookup Code & Lookup Type dùng chung

- Ngày tạo: 2026-11-02
- Giai đoạn: GĐ3 (Mở rộng)
- Phụ thuộc: 01, 08, 14
- Nhánh git: feat/17-lookup-codes

## Mục tiêu
Xây dựng mô hình Enterprise Lookup System (Lookup Type & Lookup Code) cho phép quản trị viên thêm, sửa, xem, vô hiệu hóa (soft-delete) các danh mục dùng chung (như trạng thái đối soát, nguyên nhân chênh lệch, loại tiền tệ...) thay vì phải hardcode trong mã nguồn hoặc phân mảnh nhiều bảng riêng biệt.

## Phạm vi
- **Database & Schema**:
  - Tạo bảng `RECON_LOOKUP_TYPE` (mã loại danh mục, tên hiển thị, mô tả, cờ hệ thống `IS_SYSTEM`, trạng thái `IS_ACTIVE`).
  - Tạo bảng `RECON_LOOKUP_CODE` (khóa chính kép `(LOOKUP_TYPE, LOOKUP_CODE)`, nhãn tiếng Việt `MEANING`, thứ tự `DISPLAY_ORDER`, mã màu `COLOR_BADGE`, icon `ICON_NAME`, cờ mặc định `IS_DEFAULT`, cờ hệ thống `IS_SYSTEM`, trạng thái `IS_ACTIVE`).
  - Migration Alembic hỗ trợ cả SQLite và Oracle.
  - Tự động nạp (seed/migrate) dữ liệu khởi tạo cho 2 nhóm: `ISSUE_STATUS` (OPEN, IN_PROGRESS, ACCEPTED, RESOLVED) và `ISSUE_REASON` (lấy từ `RECON_ISSUE_REASON` hiện có).
- **Tầng nghiệp vụ (Service layer)**:
  - `app/services/lookup.py`: Các hàm `list_lookup_types`, `create_lookup_type`, `update_lookup_type`, `list_lookup_codes`, `create_lookup_code`, `update_lookup_code`, `toggle_lookup_code_status`, `delete_lookup_code`.
  - Phân quyền: Chỉ `ADMIN` có quyền thêm/sửa/xóa/đổi trạng thái; các vai trò khác (`OPERATOR`, `TEMPLATE_OWNER`, `VIEWER`) chỉ có quyền đọc.
  - Cơ chế cache danh mục trong bộ nhớ để đọc nhanh không tốn I/O.
- **Giao diện người dùng (UI)**:
  - Màn hình Quản lý Lookups tại `/lookups` (`app/ui/pages/lookups.py`) với bố cục Master – Detail 2 cột:
    - Cột trái (35%): Danh sách Loại danh mục (Type), tìm kiếm nhanh, badge số lượng mã con, nút "+ Thêm loại".
    - Cột phải (65%): Bảng danh sách Giá trị (Code) theo Type đang chọn, tìm kiếm mã, switch bật/tắt Active trực tiếp, badge xem trước màu/icon, nút "+ Thêm giá trị mới" và nút Sửa/Xóa.
  - Modals: Thêm/Sửa Loại danh mục, Thêm/Sửa Giá trị danh mục (chọn màu sắc Badge, chọn icon, nhập thứ tự hiển thị).
  - Tích hợp đường dẫn "/lookups" vào Menu Sidebar (mục Cấu hình) trong `app/ui/layout/shell.py`.
- **Kiểm thử**:
  - Unit tests cho `lookup_service`: CRUD, phân quyền, validation chống trùng mã, bảo vệ mã hệ thống.
  - Unit tests cho `app/ui/pages/lookups.py`: render layout, mở modal, tương tác callbacks.

## Ngoài phạm vi
- Chưa thay đổi Drawer trong `run_result.py` và màn hình `issues.py` (để dành thực hiện ở bước sau theo yêu cầu người dùng).
- Chưa áp dụng Lookup code vào các module khác ngoài danh mục chung.

## Thiết kế
- Bố cục Master – Detail 2 cột card chuẩn Dash Mantine Components 2.x theo nguyên mẫu UI/UX: `designs/components/Screen12-Lookups/` (`preview.html` và `README.md`).
- Master (35%): Ô tìm kiếm Loại danh mục, badge đếm số lượng loại, danh sách loại kèm badge số lượng mã con.
- Detail (65%): Tiêu đề loại + mã loại, nút Sửa loại, Alert thông báo policy (nhóm đóng/mở), Toolbar tìm kiếm mã/nhãn + lọc trạng thái active, bảng mã, chú thích footer.
- Tuân thủ tokens và màu sắc trong `designs/tokens.json`.

## Spec liên quan
- `docs/specs/00-tong-quan-kien-truc.md` (chuẩn schema và SQLAlchemy Core).
- `docs/specs/06-xu-ly-chenh-lech.md` (danh mục chênh lệch).

## Quyết định kiến trúc
- **Enterprise Lookup Pattern**: Dùng cặp bảng `RECON_LOOKUP_TYPE` (1) và `RECON_LOOKUP_CODE` (N) với khóa chính kép `(LOOKUP_TYPE, LOOKUP_CODE)`.
- **Bảo vệ toàn vẹn dữ liệu**: Các mã đã được dùng trong nghiệp vụ hoặc có cờ `IS_SYSTEM = 'Y'` sẽ bị chặn xóa cứng (`DELETE`), thay vào đó chuyển sang trạng thái vô hiệu hóa (`IS_ACTIVE = 'N'`).
- **Tương thích màu sắc UI**: Cột `COLOR_BADGE` lưu tên token màu của Mantine (`teal`, `red`, `blue`, `yellow`, `gray`, `purple`) để các component Badge tự động hiển thị trực quan.

## Các bước
### Bước 1 — Schema & Alembic Migration
- Làm: Thêm bảng `recon_lookup_type` và `recon_lookup_code` trong `app/db/metadata.py`, viết migration Alembic cho SQLite và Oracle, nạp dữ liệu ban đầu cho `ISSUE_STATUS` và `ISSUE_REASON`.
- Test viết trước: Kiểm tra metadata bảng và query seed.
- Kiểm tra: `uv run poe db-migrate` và `uv run pytest tests/unit/test_lookup_service.py`

### Bước 2 — Service Quản lý Lookup
- Làm: Viết `app/services/lookup.py` với đầy đủ các hàm nghiệp vụ, kiểm tra quyền `ADMIN`, kiểm tra trùng mã, cơ chế soft-delete, cache dữ liệu.
- Test viết trước: `tests/unit/test_lookup_service.py` kiểm thử đủ các hàm CRUD và phân quyền.
- Kiểm tra: `uv run pytest tests/unit/test_lookup_service.py` → 100% PASS.

### Bước 3 — Giao diện Quản trị Lookups (/lookups) & Menu Sidebar
- Làm:
  - Tạo `app/ui/pages/lookups.py` với giao diện Master – Detail 2 cột, hỗ trợ Light & Dark Mode.
  - Các modal Thêm/Sửa Loại và Giá trị.
  - Thêm mục "Danh mục Lookups" vào menu Sidebar `app/ui/layout/shell.py`.
- Test viết trước: `tests/unit/test_page_lookups.py`.
- Kiểm tra: `uv run pytest tests/unit/test_page_lookups.py` → PASS.

## Chấp nhận khi
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.
- [ ] Màn hình `/lookups` hoạt động đầy đủ, quản trị viên có thể thêm, sửa, bật/tắt các mã lookup.
- [ ] Dữ liệu mặc định `ISSUE_STATUS` và `ISSUE_REASON` sẵn sàng trong DB.
