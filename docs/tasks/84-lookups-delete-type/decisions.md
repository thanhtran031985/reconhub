# Decisions — Task 84

- D1: bỏ text "Bật"/"Tắt" nhưng giữ Switch nguyên (size md, aria-label, disabled) — trạng thái nhìn Switch là đủ, không cần chữ.
- D2: xóa loại thì xóa cả mã của loại trong cùng 1 transaction (người dùng cần dọn loại test); chỉ cấm 2 trường hợp: loại hệ thống (FORBIDDEN) và mã đang dùng trong RECON_ISSUE (CONFLICT, chỉ kiểm tra với ISSUE_REASON như `delete_lookup_code` đang làm).
- D3: icon xóa là sibling của nút chọn (không nằm trong Button) để bấm xóa không kích hoạt chọn loại; Group canh giữa dọc, icon ở góc phải.
- D4: số mã sẽ bị xóa cùng loại đưa vào Tooltip của icon (biết trước khi bấm); modal xác nhận dùng mô tả tĩnh (cảnh báo xóa cả mã trong loại) vì `modal_confirm` không có mô tả động.
- D5: callback xóa loại dùng đúng id `{id}-cancel`/`{id}-confirm` của helper (KHÔNG `-btn`) — bài học trực tiếp từ bug task 83.
- D6: loại đang mở bị xóa thì `cb_master_detail_sync` tự coi như chưa chọn (kiểm tra loại còn trong `list_lookup_types` không) — tránh dùng store output trùng (Dash cấm 2 callback cùng Output nếu không allow_duplicate).
