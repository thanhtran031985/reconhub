# Task 46 — Dọn 2 lỗi console (tiếp task 45)

## Yêu cầu (10/11/2026, người dùng)

1. `validateDOMNesting(...): <h4> cannot appear as a child of <h4>` —
   React cảnh báo lồng thẻ h4 sai.
2. `ReferenceError: A nonexistent object was used in an Output` —
   Output `admin-col-preview-container` không tồn tại trong layout.

## Nguyên nhân (đã đọc code + tái hiện)

1. **h4 trong h4 (trang Lịch sử):** `history.py render_header` truyền
   `dmc.Title(..., order=4, id="history-title")` vào `page_header`,
   mà `page_header` lại bọc mọi tiêu đề trong một `dmc.Title(order=4)`
   nữa. Chỉ history.py truyền component làm title; các trang khác đều
   truyền chuỗi. `id="history-title"` phải giữ vì callback
   `update_history_table` ghi `children` vào đó (số run đổi theo lọc).
2. **Output admin-col-preview-container (/report-admin):** callback
   `handle_drag_drop_reorder` (kéo-thả tham số) có Output tới khung xem
   trước cột bước 4, nhưng khung đó chỉ tồn tại khi wizard mở. Input
   của callback là `admin-drag-drop-store` (Store tĩnh trong layout)
   nên Dash chạy callback ngay lúc tải trang danh sách — tái hiện được
   chỉ bằng cách mở /report-admin, đúng hash `aa9233f4...` như người
   dùng báo. 4 callback còn lại cùng Output (Lưu/Làm mới/Khôi phục/Xóa
   cột) an toàn vì nút của chúng chỉ có ở bước 4, nơi khung xem trước
   cũng tồn tại.

## Phạm vi

- `page_header.py`: nhận cả chuỗi lẫn component làm title.
- `report_admin.py`: bỏ Output preview-container khỏi
  `handle_drag_drop_reorder` (kéo-thả tham số luôn trả `no_update` cho
  Output này nên bỏ đi không đổi hành vi).
- Không migration.
