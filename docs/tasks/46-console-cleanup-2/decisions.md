# Quyết định — Task 46

- `page_header` nhận cả chuỗi lẫn component: chuỗi bọc Title như cũ,
  component dùng thẳng — giữ `id="history-title"` để callback
  `update_history_table` vẫn ghi được số run, giao diện không đổi
  (Title của history đã có size 18, fw 600 giống Title của page_header).
- Bỏ Output preview-container khỏi `handle_drag_drop_reorder` thay vì
  thêm placeholder tĩnh: thêm placeholder sẽ trùng id với khung thật
  ở bước 4 (2 phần tử cùng id), còn callback này với kéo tham số luôn
  trả `no_update` cho Output đó nên bỏ là không đổi hành vi.
- Không động tới 4 callback cột còn lại (Lưu/Làm mới/Khôi phục/Xóa):
  nút của chúng chỉ tồn tại ở bước 4 cùng với khung xem trước.
