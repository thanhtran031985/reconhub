# Tiến độ — 101-interactive-grid

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Tích hợp Tabulator JS và theme CSS Fluent Compact (`tabulator_fluent.css`) | ✅ | 2026-11-23 | feat/101-interactive-grid: step 1 |
| 2 | Xây dựng Tabulator Controller (`batches_tabulator.js`) phong cách Oracle APEX | ✅ | 2026-11-23 | feat/101-interactive-grid: step 2 |
| 3 | Quản lý Saved Views và lưu vị trí/độ rộng cột vào localStorage | ✅ | 2026-11-23 | feat/101-interactive-grid: step 3 |
| 4 | Thay thế native browser popup bằng Dash Mantine Modal chuẩn Fluent | ✅ | 2026-11-23 | feat/101-interactive-grid: step 4 |
| 5 | Tối ưu hóa UI trang Bộ đối soát, loại bỏ filter cũ và kiểm thử hồi quy | ✅ | 2026-11-23 | feat/101-interactive-grid: step 5 |

## Nhật ký

### 2026-11-23
- **Bước 1 & 2**: Tích hợp `tabulator.min.js`, `tabulator.min.css` và viết file `tabulator_fluent.css`. Xây dựng controller `batches_tabulator.js` khởi tạo bảng với các header filter trên từng cột.
  - *Sự cố phát sinh 1*: Gặp lỗi `Filter Error - Cannot build header filter, No such editor found: undefined` do bật `persistence: { columns: true }` khiến Tabulator serialize các hàm headerFilter. Khắc phục bằng cách tắt persistence mặc định và tự quản lý layout.
  - *Sự cố phát sinh 2*: Gặp lỗi `toCol.getField is not a function` khi kéo thả cột. Khắc phục bằng cách cập nhật selector và kiểm tra phần tử DOM trong hàm move column.
- **Bước 3**: Hoàn thiện tính năng lưu View cá nhân hóa vào `localStorage`.
  - *Sự cố phát sinh 3*: Kéo thay đổi độ rộng cột nhưng reload không lưu pixel. Khắc phục bằng cách lưu mảng cấu hình `{ field, width }` và áp dụng lại kích thước pixel khi khôi phục View.
  - *Sự cố phát sinh 4*: Cột Tên bộ đối soát bị cứng kích thước không thể thu nhỏ do gán `col.minWidth = it.width` và `minWidth: 260`. Khắc phục bằng cách đặt `minWidth: 80`, kích hoạt `resizableColumnFit: true`, cột tên co dãn đàn hồi `widthGrow: 3`.
  - *Sự cố phát sinh 5*: Thu nhỏ menu sidebar thì bảng bị hở khoảng trống bên phải. Khắc phục bằng cách bắt sự kiện click `#app-sidebar-toggle-btn` kết hợp `ResizeObserver` để tự động dãn bảng kín 100% (`table.redraw(true)`).
- **Bước 4**: Tiếp thu phản hồi của người dùng về việc không dùng popup `prompt()` / `confirm()` mặc định của trình duyệt:
  - Thêm `dmc.Modal` cho "Lưu thành View mới..." (`bdef-save-view-modal`) và "Xóa Template / View" (`bdef-delete-view-modal`).
  - Toàn bộ tương tác hiển thị modal Mantine mượt mà, thân thiện, chuẩn Fluent Compact.
- **Bước 5**:
  - Loại bỏ hoàn toàn thanh `cmd_bar` cũ (tìm kiếm và chọn trạng thái) phía trên bảng, tối ưu không gian hiển thị vì đã có header filters ngay trên bảng.
  - Cập nhật test case trong `tests/unit/test_batch_def_pages.py`. Toàn bộ 8/8 tests passed.
  - Kiểm thử `poe lint`, `poe typecheck`, `poe test` toàn bộ đều xanh. Người dùng đã kiểm thử thực tế và xác nhận hoàn tất.
