# Task 47 — Wizard UI fixes (footer, bảng tham số bước 3, canvas)

## Bối cảnh
Người dùng gửi 2 ảnh chụp `/report-admin/1` (22:03 10/11/2026) với 3 yêu cầu, rồi đi ngủ, mai check sau.

## Yêu cầu
1. **Nút Quay lại / Tiếp theo to lên** — footer wizard hiện tại nút chỉ cao 18px, chữ 10px (thu nhỏ ở task 37/38 theo yêu cầu cũ). Giờ người dùng muốn to lên.
2. **Bước 3, card "3. Tham số và cấu hình LOV"**:
   - Các column cách nhau 8px.
   - STT canh giữa nhưng KHÔNG làm mất nút tăng/giảm (spinner của NumberInput).
   - Click vào Mã thì indicator (dòng được chọn) phải chuyển tới dòng click, hiện vẫn ở dòng đầu.
3. **Card "Thiết kế layout tham số tìm kiếm (Canvas 12 cột)"**: thiết kế lại card parameter cho cân đối — chia tổng chiều rộng card thiết kế thành 12 phần, card parameter chiếm N ô thì rộng N/12 (cộng thêm padding).

## Phân tích nguyên nhân gốc (đã đọc code trước khi sửa)
1. Footer (`_render_wizard_footer`, report_admin.py ~2668): nút `size="xs"` + style ép `height 18px / fontSize 10px / padding 0 10px`; thanh footer cao 20px. Muốn nút to thì phải tăng cả chiều cao footer.
2. Bảng tham số (`render_step3` ~1575):
   - Header Th đều `padding 6px 4px`, nhưng body Td phần lớn KHÔNG có padding (mặc định Mantine) — chỉ ô Nhãn có `4px 4px` → các cột cách nhau không đều.
   - Cột STT (NumberInput `admin-p-table-order`, w=46): ô Td không có `textAlign: center` nên input lệch trái trong ô 50px; header đã center. Input có sẵn `textAlign: center` cho chữ, spinner vẫn hiện (không dùng `hideControls` — bài học task 37/38: ẩn spinner để căn giữa đã phải sửa lại ở task 38).
   - Indicator: `handle_p_select_click` (~5156) khi click Mã chỉ cập nhật panel LOV (title/type/body) + `admin-state-store.editing_param_id`, KHÔNG re-render bảng. Highlight dòng (`is_selected` → nền xanh + viền trái) chỉ tính lúc `render_step3` chạy → vẫn ở dòng đầu. LOV panel đổi nhưng bảng không đổi — đúng như người dùng mô tả.
3. Canvas (`_render_param_canvas` ~1269):
   - Lưới hàng là `repeat(12, 1fr)` — track `1fr` không co dưới min-content của card. Card span 2 chứa 2 NumberInput 46px + nhãn Hàng/Cột (~141px tối thiểu) trong khi track span 2 chỉ ~135px ở 1440px → grid bị đội track, card lệch nhau, ô Cột bị cắt ở mép (thấy trong ảnh 2).
   - Sửa: track `repeat(12, minmax(0, 1fr))` + box `minWidth: 0` → card đúng N/12 chiều rộng khả dụng; nhóm Hàng/Cột cho phép wrap để card hẹp xếp 2 dòng thay vì bị cắt.

## Quyết định thiết kế
- Nút footer: `size="sm"`, cao 36px (chuẩn app — nút Xem sau task 42 cũng 36px), padding `0 18px`, chữ 13px, icon 16. Thanh footer 20px → 48px để chứa nút. Áp cho cả 3 biến thể nút Tiếp theo (bước 1, bước 2–5, bước 6) + nút Quay lại.
- Bảng: mọi Td body về padding `4px 4px` (giữ width/textAlign sẵn có) → nội dung 2 cột kề nhau cách 8px (4+4), khớp header `6px 4px`.
- STT: thêm `textAlign: center` cho Td STT; giữ nguyên spinner (không `hideControls`).
- Indicator: thêm id `{"type": "admin-param-row", "index": id}` cho mỗi `TableTr` + thêm Output pattern-ALL `style` vào chính `handle_p_select_click` (cùng 1 click: panel LOV + state + highlight). Dùng helper chung `_param_row_style(is_selected)` cho cả render và callback. KHÔNG re-render cả bảng — tránh mất nhãn đang gõ dở (nhãn chỉ lưu khi bấm Lưu nháp, task 38).
- Canvas: `gridTemplateColumns: "repeat(12, minmax(0, 1fr))"`, box thêm `minWidth: 0`, nhóm Hàng/Cột ngoài cùng `wrap="nowrap"` → `wrap="wrap"` (2 nhóm con vẫn nowrap; test task 37 assert "nowrap" vẫn pass).

## Các bước
1. Đọc code + phân tích (xong).
2. Docs + test đỏ.
3. Sửa footer + bảng + canvas; cập nhật test cũ `test_wizard_footer_compact` (mã hóa kích thước cũ 18px/20px — yêu cầu đã đổi).
4. Typecheck + lint + full suite + Playwright (footer 36px, bảng 8px/STT giữa/click Mã đổi indicator, canvas 4 card span 2 rộng bằng nhau, không tràn) + xuất patch.
