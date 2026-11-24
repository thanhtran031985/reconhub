# Kế hoạch — 101-interactive-grid

## 1. Mục tiêu kiến trúc & Nghiệp vụ
Chuyển đổi bảng danh sách Bộ đối soát (`/batches`) từ giao diện bảng tĩnh sang **Interactive Grid** phong cách Oracle APEX Interactive Grid, mang lại trải nghiệm tương tác dữ liệu linh hoạt, hiện đại và chuẩn mực theo phong cách Fluent Compact.

---

## 2. Các bước triển khai chi tiết

### Bước 1 — Nạp thư viện Tabulator JS và thiết lập theme Fluent Compact
- **Mục tiêu**: Tích hợp Tabulator 6.2.1 và xây dựng giao diện Fluent Compact đồng bộ với hệ thống.
- **Thực hiện**:
  1. Thêm `tabulator.min.js` và `tabulator.min.css` vào thư mục `app/ui/assets/`.
  2. Tạo `app/ui/assets/tabulator_fluent.css` với các quy tắc CSS:
     - Khung bao `.tabulator` tràn 100% độ rộng container.
     - Header nền xám nhạt `#f8fafc`, viền dưới `#e2e8f0`, chữ đậm vừa, căn giữa toàn bộ tiêu đề cột (`.tabulator-col-title-holder`).
     - Dòng dữ liệu độ cao compact, hover đổi màu nhẹ `#f1f5f9`.
     - Căn giữa 100% dữ liệu các cột Trạng thái, Số mục, Song song/DS, Thao tác.
     - Nút icon thao tác `.tab-icon-btn` kích thước 26x26px, hover đổi màu xanh thương hiệu `#2563EB`.

### Bước 2 — Xây dựng Tabulator Controller (`batches_tabulator.js`)
- **Mục tiêu**: Xây dựng controller quản lý bảng dữ liệu với các tính năng Interactive Grid.
- **Thực hiện**:
  1. Định nghĩa cấu hình cột với header filter tích hợp:
     - `name`: Tên bộ đối soát, input text filter, `widthGrow: 3`, `minWidth: 80`.
     - `code`: Mã bộ, input text filter, `width: 170`, `minWidth: 80`.
     - `status`: Trạng thái, dropdown select filter ("Tất cả", "Hoạt động", "Tạm dừng"), `width: 140`.
     - `cnt_items`: Số mục, number filter, `width: 110`.
     - `max_parallel_per_ds`: Song song/DS, number filter, `width: 130`.
     - `actions`: Thao tác (icon Chi tiết), không filter, `width: 100`, không di chuyển cột.
  2. Bật `movableColumns: true`, `resizableColumnFit: true`, `resizableColumnGuide: true`.
  3. Lắng nghe sự kiện click nút toggle sidebar `#app-sidebar-toggle-btn` và `ResizeObserver` trên container để tự động gọi `redraw(true)`.

### Bước 3 — Quản lý Saved Views và lưu vị trí/độ rộng cột
- **Mục tiêu**: Cho phép người dùng tùy biến và lưu lại các khung nhìn cá nhân hóa.
- **Thực hiện**:
  1. Quản lý trạng thái Views trong `localStorage` với tiền tố `reconhub_bdef_views_v1`.
  2. Xây dựng logic:
     - `saveCurrentView()`: Lưu thứ tự và độ rộng pixel của từng cột hiện tại vào View đang chọn.
     - `saveNewView(name)`: Tạo View mới với cấu hình hiện tại và chọn làm View active.
     - `resetDefaultView()`: Trả View về cấu hình mặc định ban đầu.
     - `setDefaultView()`: Lưu View hiện tại thành mặc định khi mở trang.
     - `deleteCurrentView()`: Xóa View tùy biến (chặn xóa View mặc định hệ thống).
  3. Áp dụng layout: Sắp xếp lại mảng `columns` theo thứ tự và gán `width` trước khi gọi `setColumns()`.

### Bước 4 — Thay thế native browser popup bằng Dash Mantine Modal
- **Mục tiêu**: Loại bỏ hoàn toàn `alert()`, `confirm()`, `prompt()` mặc định của trình duyệt để đảm bảo trải nghiệm Fluent mượt mà, chuyên nghiệp.
- **Thực hiện**:
  1. Thêm `dmc.Modal` `bdef-save-view-modal` trong `batch_defs.py` chứa:
     - Input `dmc.TextInput` nhập tên View.
     - Nút Hủy và nút Lưu (`dmc.Button`).
     - Xử lý xác thực: báo lỗi nếu để trống hoặc trùng tên.
  2. Thêm `dmc.Modal` `bdef-delete-view-modal` trong `batch_defs.py` chứa:
     - Nội dung xác nhận xóa View.
     - Nút Hủy và nút Xóa (`dmc.Button` màu đỏ).
     - Kiểm tra nếu là View mặc định thì hiển thị thông báo không cho phép xóa.
  3. Kết nối trigger qua clientside callbacks và custom events.

### Bước 5 — Tối ưu hóa UI trang Bộ đối soát và kiểm thử toàn diện
- **Mục tiêu**: Tối ưu diện tích hiển thị và đảm bảo không có lỗi hồi quy.
- **Thực hiện**:
  1. Loại bỏ thanh tìm kiếm `cmd_bar` cũ trong `batch_defs.py`.
  2. Cập nhật unit test `tests/unit/test_batch_def_pages.py` kiểm tra render trang `/batches`, container `#reconhub_bdef_tbl`, các modal và components.
  3. Chạy `uv run poe lint`, `uv run poe typecheck`, `uv run poe test`.
  4. Kiểm thử giao diện trên trình duyệt thực tế (Playwright) xác nhận không có lỗi JavaScript console.
