# Task 84 — /lookups: bỏ chữ Bật ở cột Trạng thái + thêm xóa loại danh mục

## Yêu cầu (user 11:23 13/11/2026, kèm ảnh /lookups sau patch 83-followup)
1. Cột Trạng thái: bỏ chữ "Bật" (cạnh Switch) đi.
2. Card "Loại danh mục" (cột trái): thêm icon xóa canh giữa, nằm góc phải mỗi thẻ loại, để xóa loại — dùng khi nhập test (vd loại "22222 / TEST" 0 giá trị).

## Hiện trạng (đã đọc code)
- Cột Trạng thái (`render_code_table`): `dmc.Group[dmc.Switch(size="md"), dmc.Text("Bật"/"Tắt", size="xs", c="dimmed")]`. Switch đã có aria-label "Bật hoặc tắt mã …" nên bỏ text không mất thông tin.
- Chưa có chức năng xóa LOẠI: service `app/services/lookup.py` có `delete_lookup_code` (xóa cứng mã nếu không phải hệ thống và chưa dùng trong RECON_ISSUE) nhưng không có `delete_lookup_type`. Bảng `RECON_LOOKUP_CODE.LOOKUP_TYPE` có FK tới `RECON_LOOKUP_TYPE.LOOKUP_TYPE` nên xóa loại còn mã sẽ lỗi FK nếu không xóa mã trước.
- Thẻ loại (`render_type_list`): `dmc.Paper(dmc.Button(fullWidth, id={"type": "lookups-type-item", ...}))` — nút chọn chiếm toàn bộ thẻ. Icon xóa phải nằm NGOÀI nút chọn (sibling trong Group) để bấm xóa không chọn nhầm loại.
- Tiền lệ modal xác nhận: `modal_confirm` + store target + callback như `cb_delete_code_modal` (đã sửa id ở task 83: nút modal là `{id}-cancel`/`{id}-confirm`, KHÔNG có `-btn` — sai id này từng làm nút Xóa mã chết hoàn toàn).
