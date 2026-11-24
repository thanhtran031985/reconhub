# Checklist kiểm thử — 101-interactive-grid

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Hiển thị dữ liệu danh sách Bộ đối soát trên Interactive Grid | Bảng nạp đầy đủ các dòng bộ đối soát từ backend, hiển thị đúng các cột: Tên bộ đối soát, Mã bộ, Trạng thái, Số mục, Song song/DS, Thao tác. | ✅ |
| **TC-FN-02** | Bộ lọc trên từng Header cột (Text, Select, Number) | Nhập từ khóa vào ô lọc Tên/Mã, chọn Trạng thái từ dropdown, nhập số vào Số mục/Song song: bảng lọc tức thì dữ liệu tương ứng. | ✅ |
| **TC-FN-03** | Kéo thả thay đổi thứ tự các cột (Column Reordering) | Người dùng kéo thả header cột để đổi vị trí (trừ cột Thao tác cố định ở cuối), cột chuyển đến vị trí mới mượt mà. | ✅ |
| **TC-FN-04** | Kéo điều chỉnh độ rộng cột (Column Resizing) | Người dùng kéo đường phân cách header để tăng/giảm độ rộng cột; cột tên không bị khóa cứng minWidth lớn. | ✅ |
| **TC-FN-05** | Lưu cấu hình vị trí/độ rộng cột vào View hiện tại | Bấm nút "Lưu vị trí cột", tải lại trang (F5): thứ tự và kích thước các cột giữ nguyên như đã lưu. | ✅ |
| **TC-FN-06** | Lưu thành View mới và Chuyển đổi giữa các View | Bấm "Lưu thành View mới...", modal Fluent hiển thị; nhập tên và lưu thành công; chuyển đổi qua lại giữa các View khôi phục đúng cấu hình tương ứng. | ✅ |
| **TC-FN-07** | Đặt mặc định và Khôi phục cấu hình gốc | Bấm "Đặt mặc định" lưu View active khi mở trang; bấm "Khôi phục gốc" hoàn trả cấu hình ban đầu của hệ thống. | ✅ |
| **TC-FN-08** | Xóa View tùy biến bằng Fluent Modal | Bấm "Xóa View", modal xác nhận mở ra; bấm Xóa: View bị xóa khỏi dropdown và quay về View mặc định; chặn xóa View mặc định hệ thống. | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Căn giữa tiêu đề và dữ liệu các cột định dạng | 100% tiêu đề các cột căn giữa; dữ liệu các cột Trạng thái, Số mục, Song song, Thao tác căn giữa chuẩn xác. | ✅ |
| **TC-UI-02** | Nút icon Thao tác chuẩn Fluent Compact | Cột Thao tác hiển thị icon mở chi tiết kích thước 26x26px, hover đổi màu xanh `#2563EB`, căn giữa ô. | ✅ |
| **TC-UI-03** | Co dãn bảng khi thu gọn / mở rộng menu bên trái | Bấm nút ẩn/hiện sidebar (`#app-sidebar-toggle-btn`): bảng tự động dãn tràn 100% khung hiển thị, không bị hở khoảng trống trắng bên phải. | ✅ |
| **TC-UI-04** | Không còn xuất hiện hộp thoại native browser | Toàn bộ popup `prompt()` và `confirm()` được thay thế bằng Mantine Modal giao diện Fluent Compact. | ✅ |
| **TC-UI-05** | Loại bỏ thanh tìm kiếm cũ trùng lặp | Bỏ thanh `cmd_bar` phía trên, mở rộng không gian trực quan cho Interactive Grid. | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff (`ruff check app/ui/pages/batch_defs.py`) | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy (`mypy app/ui/pages/batch_defs.py`) | ✅ |
| **TC-REG-03** | `uv run poe test` | Toàn bộ unit tests trang batch defs pass (`tests/unit/test_batch_def_pages.py`) | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | Bảo vệ dữ liệu trong `localStorage` | Dữ liệu lưu trong localStorage chỉ chứa cấu hình giao diện UI (`field`, `width`, `name`), không lưu dữ liệu nhạy cảm hay mật khẩu. | ✅ |
| **TC-SEC-02** | Kiểm tra quyền truy cập (RBAC) | Truy cập màn hình Bộ đối soát và dữ liệu tuân thủ phân quyền người dùng theo quy định. | ✅ |
| **TC-SEC-03** | Xử lý an toàn DOM & XSS | Không sử dụng `eval` hoặc chèn HTML không an toàn trong các formatter của Tabulator. | ✅ |
