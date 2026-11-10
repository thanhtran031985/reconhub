# Task 47 — progress

## Bước 1 — Đọc code + phân tích (xong, 22:03 10/11/2026)
- Footer `_render_wizard_footer`: nút 18px/chữ 10px, footer 20px.
- Bảng bước 3 `render_step3`: body Td thiếu padding thống nhất; STT Td không center; indicator kẹt dòng đầu vì `handle_p_select_click` không re-render bảng.
- Canvas `_render_param_canvas`: lưới `repeat(12, 1fr)` bị đội track do min-content card span 2 (~141px) > track (~135px).
- Nhánh `feat/47-wizard-ui-fixes` từ `bc15cd8`.

## Bước 2 — Sửa (xong)
- Footer: nút Quay lại/Tiếp theo (cả 3 biến thể) size sm, cao 36px, chữ 13px, padding 0 18px, icon 16; footer 20px → 48px.
- Bảng bước 3: mọi Td body padding `4px 4px` (cột cách 8px); STT Td thêm `textAlign: center`, giữ spinner (không hideControls); mỗi TableTr thêm id `admin-param-row`; helper `_param_row_style` dùng chung.
- Indicator: `handle_p_select_click` thêm Output pattern-ALL `style` cho các dòng (trả thêm list style) — click Mã đổi highlight + panel LOV + state trong cùng 1 callback, không re-render bảng (giữ nhãn đang gõ dở).
- Canvas: lưới `repeat(12, minmax(0, 1fr))`, box thêm `minWidth: 0`, nhóm Hàng/Cột ngoài cùng `wrap="nowrap"` → `wrap="wrap"`.
- Test cũ `test_wizard_footer_compact` cập nhật theo yêu cầu mới (36px/48px). Test mới `tests/unit/test_wizard_ui_fixes47.py` (5 test, đỏ trước — cả 5 fail — rồi xanh).
- Lưu ý khi viết test: `_dump` serialize top-level bằng JSON (`"height": "48px"`) nhưng component con bằng repr (`'height': '36px'`); `wrap` là prop nên repr là `wrap='wrap'`.

## Bước 3 — Kiểm chứng (xong, 22:16 10/11/2026)
- Typecheck 0 lỗi, lint sạch, full suite **1473 pass / 6 skipped** (+5 test mới).
- Playwright `~/workspace/check-47.py` **14/14**: nút Tiếp theo/Quay lại 36px, footer 48px; 36 ô body padding 4px; STT giữa + 2 nút tăng/giảm; ban đầu highlight dòng 1, click Mã dòng 2 → highlight sang dòng 2 + panel LOV "Setup LOV: p_to"; canvas span 3 rộng 208.9px, span 2 rộng 137.2px (đúng N/12 lưới 853.5px, cùng span bằng nhau, ô Cột không bị cắt); không lỗi console mới.
- Lưu ý: lần đầu check canvas fail 2/14 do script tưởng cả 4 card đều span 2 — thực tế seed check-39 là p_from/p_to span 3, p_app/p_org span 2; layout đúng, đã sửa lại script đo theo span từng card rồi chạy lại 14/14.
