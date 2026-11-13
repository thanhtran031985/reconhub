# Decisions — Task 83

- D1: nguyên nhân rớt hàng là 2 icon `size="xl"` (96px) vượt cột Thao tác 90px + Group mặc định wrap — không phải do verticalSpacing hay Switch.
- D2: icon về `size="sm"` theo chuẩn task 82 (ActionIcon subtle sm + Tooltip), không giữ xl rồi nới cột: nới cột lấy chỗ của cột Badge, còn icon xl là quá to cho bảng compact.
- D3: thêm `wrap="nowrap"` cho Group nút thao tác (phòng vệ) dù sau khi thu icon đã đủ chỗ.
- D4: Tooltip label tái dùng đúng text aria-label sẵn có (kể cả trường hợp mã hệ thống) — không bịa label mới.
- D5: không đổi `verticalSpacing` (sm → 8px mỗi phía, hàng sau fix ~44px là hợp lý) và không sửa tiêu đề card trái bị cắt chữ — ngoài phạm vi yêu cầu.
- D6: xóa card trái thì chọn loại phải có chỗ mới: `dmc.Select` searchable ở command bar là cách gọn nhất (tìm loại bằng search sẵn có của Select, không cần ô tìm riêng); không dùng Tabs (kém khi nhiều loại).
- D7: giữ `lookups-selected-type-store` làm nguồn sự thật duy nhất; Select chỉ là Input/Output của `cb_master_detail_sync` (value vào, data ra) — không tạo store mới.
- D8: nút "+ Thêm loại danh mục" giữ nguyên id `lookups-add-type-btn` để `cb_add_type_modal` không đổi; sau khi thêm/sửa loại, Select options làm mới qua Output data của callback đồng bộ.
- D9: số lượng giá trị mỗi loại đưa vào label của option ("Tên loại (CODE) — N giá trị · M đang dùng") để không mất thông tin card trái từng hiện; tổng "N loại" hiện bằng text dimmed cạnh Select.
- D10: bug nút Xóa gộp vào task 83 (cùng trang, cùng cột Thao tác đang sửa) thay vì tách task mới; sửa theo nguyên nhân gốc tìm được khi tái hiện live, không đoán mò từ code tĩnh (code bề mặt đã đủ luồng).
- D11: lỗi thật tìm ra khi check live — `cb_delete_code_modal` tham chiếu `lookups-delete-code-modal-cancel-btn` / `-confirm-btn` nhưng `modal_confirm` render `{id}-cancel` / `{id}-confirm` → Dash văng `ReferenceError`, modal xóa không bao giờ mở (có sẵn trên base `b35ed7f`, không do task 83). Sửa 2 id trong callback (không đụng helper/modal); thêm test regression qua registry callback Dash (mọi string input id phải có trong layout) + gọi trực tiếp callback.
- D12: giả thuyết race (modal mở rồi tự đóng do `cb_trigger_refresh` làm refresh-store về None → bảng vẽ lại → nút remount) BỊ BÁC BỎ bằng dữ liệu live (`~/workspace/repro-83-delete.py`): trên base, modal KHÔNG BAO GIỜ mở (ReferenceError trước cả request callback, không có response `/_dash-update-component` nào); trên code đã sửa, modal mở ở t=0,19s và giữ nguyên suốt 3s poll, callback refresh khi modal mở trả `dash.no_update` (không có refresh-store trong response), không có callback vẽ lại bảng nào sau đó. Nguyên nhân duy nhất là sai id (D11).
