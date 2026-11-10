# Decisions — 35-report-aggrid

- **Q0 (2026-11-10):** Dùng AG Grid qua wrapper `data_grid` sẵn có. Bản
  community miễn phí đủ tính năng cần (sửa ô, kéo dòng, virtualize).
- **Q1 (2026-11-10):** Sửa ô + kéo-thả chỉ đổi local; persist duy nhất
  khi bấm "Lưu cột" (1 lần gọi `update_columns` với toàn bộ `rowData`).
  Xóa cột giữ nguyên xóa ngay qua service rồi tải lại `rowData`.
- **Q2 (2026-11-10):** Không dùng cell renderer tùy chỉnh cho nút Xóa.
  Chọn dòng (`rowSelection="single"`) + nút "Xóa cột đã chọn" trên thanh
  công cụ grid.
- **Q3 (2026-11-10):** Tìm kiếm dùng quick filter có sẵn của grid; bỏ
  đoạn JS ẩn dòng ở cột.
- **Q4 (2026-11-10):** Grid `editable=False` toàn bộ khi version không
  phải DRAFT.
- **Q6 (2026-11-10):** Cột Kiểu (data_type) chỉ hiển thị, không sửa được
  (service `update_columns` coi `data_type` là readonly; grid cũ có select
  Kiểu nhưng `handle_col_save` không hề gửi giá trị này nên đổi Kiểu chưa
  bao giờ được lưu — để sửa được là gây hiểu lầm).
- **Q7 (2026-11-10):** "Lưu cột" = `update_columns(rows)` rồi
  `reorder_columns(order)` (service có sẵn, 1 transaction riêng cho thứ tự;
  chỉ gọi reorder khi thứ tự mới khác DB để khỏi ghi audit thừa). Thứ tự
  lấy từ `virtualRowData` (đồng bộ sau kéo-thả; `rowData` không đồng bộ
  sau kéo-thả — đã kiểm chứng bằng prototype), nội dung ô lấy từ `rowData`.
  Khi đang lọc tìm kiếm (`virtualRowData` ngắn hơn), gộp thứ tự visible
  vào `rowData` theo vị trí cũ.
- **Q8 (2026-11-10):** `cellEditorParams` không nhận function (dash-ag-grid
  35.3.0 không convert `{"function": ...}` trong đó — đã kiểm chứng) nên
  options Định dạng là hợp tĩnh mọi mask + "" — service validate mask theo
  kiểu cột lúc lưu và báo lỗi tiếng Việt nếu sai.
- **Q9 (2026-11-10):** Xóa cột: chọn dòng (`rowSelection="single"`) + nút
  "Xóa cột đã chọn" (không dùng cell renderer tùy chỉnh). Xóa xong `_bump`
  state để wizard render lại grid từ DB. Nhân tiện sửa bug tiềm ẩn:
  `handle_col_del_click` cũ khai 3 Output nhưng trả 2 giá trị.
- **Q10 (2026-11-10):** "Khôi phục thứ tự DB" và "Làm mới cột" cũng `_bump`
  state để grid render lại (thay cho đoạn JS sắp xếp lại DOM).
- **Q11 (2026-11-10):** Bỏ nút ↑↓ dời cột (kéo-thả thay thế); bỏ phần cột
  trong `drag_drop_reporting.js` (giữ phần tham số); bỏ tbody ẩn
  `admin-col-tbody` và callback drag-drop nhánh `col`.
- **Q12 (2026-11-10):** Tắt sort/filter cột trong grid (`sortable: False`,
  `filter: False`) — sort sẽ làm `virtualRowData` lệch khỏi thứ tự hiển thị
  và lưu nhầm thứ tự đã sort thành thứ tự hiển thị. Chỉ còn tìm kiếm nhanh
  qua ô "Tìm trường DB".
