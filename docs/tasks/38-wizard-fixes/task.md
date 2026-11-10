# 38-wizard-fixes — Footer nhỏ hơn, Lưu nháp bước 3 lưu nhãn, trả nút tăng/giảm Canvas

- Ngày tạo: 2026-11-10
- Giai đoạn: GĐ3 (fix, theo mẫu task 33/36/37 — không thêm dòng dashboard)
- Phụ thuộc: 37
- Nhánh git: feat/38-wizard-fixes (rẽ từ `7ae6f43`, đỉnh `feat/37-aggrid-step4-fixes`)

## Vấn đề (người dùng báo 10/11/2026, kèm ảnh footer + tab 3 sau khi áp 37)

1. **Footer vẫn to.** Task 37 đã thu footer 48px → 26px (nút 22px), nhưng
   người dùng vẫn muốn thu nhỏ hơn nữa (ảnh footer strip: nút xanh cao ~28px
   ở tỉ lệ zoom ~1,14x ≈ nút 22px hiện tại). Thu tiếp còn 20px (nút 18px,
   chữ 10px, capsule p=1).
2. **Tab 3: sửa Nhãn rồi bấm "Lưu nháp" không cập nhật nhãn.** Gốc:
   `handle_save_draft_click` chỉ xử lý bước 1 và bước 2; ở bước 3 nó rơi
   xuống nhánh chung, chỉ `_bump(state)` + toast "Đã lưu nháp tiến độ" mà
   KHÔNG ghi gì. Bảng tham số bước 3 (input Nhãn/Kiểu/Hiện/Bắt buộc/Mặc
   định/LOV/STT, id `admin-p-table-*`) không có callback lưu nào:
   `handle_param_save` là dead code (định nghĩa mà không nơi nào gọi).
   Nút duy nhất lưu ở bước 3 là "Lưu cấu hình LOV" (`handle_p_save_lov`),
   chỉ lưu LOV + control_type của tham số đang chọn. Hệ quả: sửa nhãn →
   Lưu nháp → toast thành công → render lại đọc nhãn cũ từ DB → nhãn
   hoàn về như cũ. Khi lưu được thì dry-run (bước 5) tự hiện nhãn mới vì
   `render_param_form` đọc `label` từ `preview_layout` (DB) mỗi lần render.
3. **Canvas Hàng/Cột mất nút tăng/giảm.** Task 37 đặt `hideControls=True`
   để căn giữa thật (nút tăng/giảm đẩy chữ lệch). Người dùng thích căn giữa
   nhưng muốn giữ nút tăng/giảm. Trả lại controls, giữ căn giữa
   (`textAlign: center` + `lineHeight: 22px` + `wrap="nowrap"`), nới rộng
   ô 34 → 46px để số không bị controls che.
