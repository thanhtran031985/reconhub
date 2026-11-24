# 101-interactive-grid — Chuyển grid danh sách sang Interactive Grid (Tabulator) phong cách Oracle APEX

- Ngày tạo: 2026-11-23
- Giai đoạn: GĐ3
- Phụ thuộc: 18
- Nhánh git: feat/101-interactive-grid

## Mục tiêu
Chuyển đổi bảng danh sách Bộ đối soát (`/batches`) sang định dạng **Interactive Grid** (phong cách Oracle APEX Interactive Grid) sử dụng thư viện Tabulator JS thuần kết hợp với Dash Mantine Components. Hệ thống hỗ trợ người dùng lọc dữ liệu ngay trên từng cột (Header Filters), kéo thả đổi thứ tự cột, tùy chỉnh co dãn độ rộng cột (Column Resizing), lưu và khôi phục các khung nhìn cá nhân hóa (Personalized Saved Views / Templates) vào `localStorage`, tự động phản hồi co dãn theo thanh sidebar menu (Responsive), và thay thế toàn bộ popup trình duyệt mặc định bằng Fluent Modal.

## Phạm vi
- **Thư viện & Giao diện tĩnh (`app/ui/assets/`)**:
  - Tích hợp Tabulator v6.2.1 (`tabulator.min.js`, `tabulator.min.css`).
  - Xây dựng theme Fluent Compact tùy chỉnh (`tabulator_fluent.css`): hỗ trợ ép tràn 100% độ rộng container, căn giữa toàn bộ tiêu đề cột, căn giữa dữ liệu các cột Trạng thái / Số mục / Song song / Thao tác, nút icon thao tác 26x26px.
- **Controller Client-side (`app/ui/assets/batches_tabulator.js`)**:
  - Khởi tạo bảng với chế độ `layout: "fitColumns"`, `movableColumns: true`, `resizableColumnFit: true`, `resizableColumnGuide: true`.
  - Bộ lọc trực tiếp trên từng header cột (Text search cho Mã/Tên, Dropdown select cho Trạng thái, Number search cho Số mục/Song song).
  - Quản lý cấu hình Views: Lưu cấu hình cột (`field`, `width`) theo từng View trong `localStorage`. Cho phép Lưu vị trí cột vào View hiện tại, Đặt làm mặc định, Khôi phục gốc.
  - Lắng nghe sự kiện thu gọn / mở rộng menu sidebar (`#app-sidebar-toggle-btn`) và `ResizeObserver` để tự động dãn bảng kín 100% không để lại khoảng trống màu trắng bên phải.
- **Trang Bộ đối soát (`app/ui/pages/batch_defs.py`)**:
  - Thay thế bảng cũ bằng container Tabulator `#reconhub_bdef_tbl`.
  - Bổ sung thanh công cụ Saved Views (Dropdown chọn View, nút Lưu vị trí, Lưu thành View mới..., Đặt mặc định, Khôi phục gốc, Xóa View).
  - Bỏ thanh tìm kiếm/lọc bên trên (`cmd_bar`) để tối ưu diện tích màn hình vì đã có header filter trên từng cột.
  - Bổ sung `dmc.Modal` Fluent cho "Lưu thành View mới..." (`bdef-save-view-modal`) và "Xóa Template / View" (`bdef-delete-view-modal`), loại bỏ hoàn toàn `prompt()` và `confirm()` native của trình duyệt.
- **Kiểm thử**:
  - Cập nhật unit test `tests/unit/test_batch_def_pages.py` kiểm tra cấu trúc render layout, modal và scripts.
  - Kiểm thử E2E và hồi quy trên trình duyệt.

## Ngoài phạm vi
- Chưa thay thế toàn bộ các bảng khác trong hệ thống (sẽ tách thành các task mở rộng tiếp theo).
- Không thay đổi bảng cơ sở dữ liệu `RECON_BATCH_DEF` hay service backend.

## Thiết kế
- `designs/components/Screen10_BatchRun.md`
- `designs/reference/preview-fluent.html`
- Phong cách: Fluent Compact + Oracle APEX Interactive Grid.

## Spec liên quan
- `docs/specs/08_production_architecture.md`
- `docs/PRD.md` (Phần Quản lý Bộ đối soát)

## Quyết định kiến trúc
- **Dùng Tabulator JS thuần client-side**: Không phụ thuộc vào các wrapper Dash chưa hoàn thiện; nạp qua `assets/` và khởi tạo trực tiếp qua clientside script để tối ưu hiệu năng và kiểm soát DOM.
- **Quản lý Saved Views qua `localStorage`**: Lưu danh sách View và cấu hình cột (`field`, `width`) trực tiếp ở trình duyệt người dùng với khóa tiền tố `reconhub_bdef_views_*`.
- **Bỏ `persistence: { columns: true }`**: Tránh lỗi Tabulator serialize các function `headerFilter` thành `undefined`. Thay vào đó, áp dụng layout thủ công bằng cách điều chỉnh thứ tự và `width` của mảng `columns`.
- **Responsive đàn hồi (`resizableColumnFit` + `widthGrow`)**: Đặt `resizableColumnFit: true`, bỏ gán cứng `minWidth = it.width`, cột tên sử dụng `widthGrow: 3` để cho phép thu nhỏ cột tùy ý và tự động co dãn khi sidebar đóng/mở.
- **Fluent Modal thay thế Popup Native**: Sử dụng `dmc.Modal` của Dash Mantine Components kết hợp Store để thay thế hoàn toàn `prompt()` và `confirm()`.

## Các bước
### Bước 1 — Tích hợp Tabulator JS và theme CSS Fluent Compact
- Làm: Thêm thư viện `tabulator.min.js`, `tabulator.min.css` vào `app/ui/assets/`. Viết file `tabulator_fluent.css` chuẩn Fluent Compact (chiều cao dòng, typography, borders, căn giữa header và cell dữ liệu, nút thao tác).
- Kiểm tra: File asset được Dash tự động nạp mà không có xung đột CSS.

### Bước 2 — Xây dựng Tabulator Controller (`batches_tabulator.js`)
- Làm: Viết controller `window.ReconBatchesTabulator` với cấu hình cột, bộ lọc header trên từng cột, kéo thả đổi vị trí và thay đổi độ rộng cột.
- Kiểm tra: Mở `/batches`, dữ liệu hiển thị đúng, các bộ lọc header hoạt động mượt mà.

### Bước 3 — Quản lý Saved Views và lưu vị trí/độ rộng cột vào localStorage
- Làm: Hiện thực các phương thức `initViews()`, `switchView()`, `saveCurrentView()`, `saveNewView()`, `resetDefaultView()`, `setDefaultView()`, `deleteCurrentView()`.
- Kiểm tra: Kéo đổi thứ tự và độ rộng cột, bấm Lưu vị trí cột, tải lại trang vẫn giữ nguyên cấu hình.

### Bước 4 — Thay thế native browser popup bằng Dash Mantine Modal
- Làm: Thêm `dmc.Modal` trong `app/ui/pages/batch_defs.py` (`bdef-save-view-modal` và `bdef-delete-view-modal`). Kết nối qua clientside callback để mở modal và xử lý hành động.
- Kiểm tra: Không còn xuất hiện bất kỳ hộp thoại `127.0.0.1:8050 says...` nào trên trình duyệt.

### Bước 5 — Tối ưu hóa UI trang Bộ đối soát và kiểm thử toàn diện
- Làm: Loại bỏ thanh `cmd_bar` cũ; tinh chỉnh co dãn khi toggle sidebar; cập nhật `tests/unit/test_batch_def_pages.py`.
- Kiểm tra: `uv run poe lint`, `uv run poe typecheck`, `uv run poe test` đều xanh.

## Chấp nhận khi
- [x] Giao diện bảng danh sách Bộ đối soát hiển thị đúng chuẩn phong cách Oracle APEX Interactive Grid.
- [x] Hỗ trợ lọc trực tiếp trên từng header cột (Text, Select, Number).
- [x] Cho phép kéo thả thay đổi vị trí cột và điều chỉnh độ rộng cột (không bị cứng minWidth).
- [x] Lưu và khôi phục View cá nhân hóa trong `localStorage` hoạt động chính xác.
- [x] Khi thu nhỏ/mở rộng menu bên trái, bảng tự động dãn tràn 100% không bị hở khoảng trống bên phải.
- [x] Toàn bộ thao tác Lưu view mới, Xóa view sử dụng `dmc.Modal`, không dùng native popup.
- [x] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh.

### Data Model Impact
- [x] Task không thay đổi database schema.

## Câu hỏi mở
- Không còn câu hỏi mở. Tính năng đã được kiểm thử thực tế và nghiệm thu thành công.
