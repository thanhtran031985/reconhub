# Task 83 — /lookups: sửa layout card bên phải, hàng bảng bị rớt

## Yêu cầu (user 13/11/2026, kèm ảnh /lookups)
- Chỉnh lại layout card bên phải (bảng Lookup Code) cho hợp lý, hiện tại đang rớt hàng.

## Hiện trạng (đã đọc code `app/ui/pages/lookups.py`, hàm `render_code_table`)
- Ảnh thật: mỗi hàng bảng cao ~110px, chỉ hiện ~3 hàng, bảng phải cuộn nội bộ; icon Sửa (bút chì) nằm trên, icon Xóa (thùng rác) rớt xuống dưới với khoảng trống lớn.
- Nguyên nhân gốc: 2 `dmc.ActionIcon` ở cột Thao tác đang để `size="xl"` (~44px mỗi cái) + gap 8px = 96px, trong khi cột Thao tác chỉ rộng 90px (header `width: "90px"`). `dmc.Group` mặc định `wrap="wrap"` nên icon thứ 2 rớt xuống dòng dưới, làm hàng cao gấp đôi.
- Các yếu tố khác không phải nguyên nhân: `verticalSpacing="sm"`, Switch `size="md"`, Badge 1 dòng, `TableScrollContainer minWidth=650` (card phải ở 1440px rộng ~850px nên không bị ép ngang).
- Callback các nút Sửa/Xóa bám theo id dict (`lookups-edit-code-btn`, `lookups-delete-code-btn`), không bám theo kích cỡ → đổi size không ảnh hưởng logic.
- Test sẵn có: `tests/unit/test_page_lookups.py` (fixture `lookups_env`, `test_render_code_table_shows_codes` ở dòng 105).
- Ghi chú ngoài phạm vi: tiêu đề loại ở card trái đang bị cắt chữ ("…column sang |") — thuộc card trái, không sửa trong task này.

## Bổ sung (user 10:13 13/11/2026): xóa card trái
- Bỏ hẳn cột trái "Loại danh mục" (danh sách type + ô tìm loại + nút "+ Thêm loại danh mục"). Chọn loại chuyển sang `dmc.Select` có search ở thanh trên cùng của trang, nút Thêm loại giữ lại bên cạnh Select.
- Cấu trúc callback hiện tại (đã đọc): `cb_master_detail_sync` nhận Input click từng type-item (pattern ALL) + ô tìm loại + refresh store; Output vẽ lại `lookups-type-list` + badge đếm loại. `render_type_list(ctx, selected_type, search_query)` trả (ui, total_count); `list_lookup_types` đã có số lượng giá trị mỗi loại (card trái hiện "8 giá trị · 8 đang dùng"). `cb_add_type_modal` bám nút `lookups-add-type-btn` (giữ nguyên id). Hàm thuần `handle_select_type` — kiểm tra nơi dùng trước khi đổi/xóa.
