# Decisions — Task 82

- D1: preview 2/3 = 227px (340 × 2/3 = 226,67 → 227). Cả 2 card xem trước hẹp cùng lúc vì chung cột phải; thanh bên thật chỉ ~200px nên 227px vẫn xem trước đúng tỉ lệ.
- D2: icon thao tác theo tiền lệ `data_sources.py` (`dmc.Tooltip` label + `dmc.ActionIcon` variant subtle, size sm, withArrow). Icon: Tạm ẩn `eye-off`, Bỏ ẩn `eye`, Đã xem `check`, Mặc định `rotate-ccw`. Màu giữ gray mặc định (như nút chữ cũ), không đổi ngữ nghĩa màu.
- D3: toggle ẩn/hiện bằng `dcc.Store` bool + 1 callback duy nhất (2 Input nút toggle/X, dispatch theo triggered) — state không bị mất khi bảng vẽ lại (cột phải nằm ngoài vùng bảng vẽ lại). Không lưu trạng thái lâu dài (reload về mặc định hiện).
- D4: nút toggle đặt ở cuối phải command bar (gần cột preview), nút X đặt ở đầu card xem trước (Group tiêu đề + ActionIcon X). Cả 2 cùng điều khiển một Store.
- D5: không ép độ rộng cột bảng theo % (khác task 81): bảng này nặng input (ô tên 200px, Select nhóm 140px) nên để cột theo nội dung; chỉ cột Thao tác thu lại nhờ icon.
- D6: chỉ chuyển px inline ở vùng chạm tới sang class `.menus-*` (theo tiền lệ task 81 `.qh-*`); không refactor toàn bộ trang 1355 dòng.
- D7 (check live 13/11/2026): console có 1 warning CÓ SẴN từ trước task 82:
  `Warning: 'value' prop on 'textarea' should not be null` — do
  `handle_menus_hide_open` trả `None` cho `menus-hide-reason`
  (Textarea) khi mở modal Tạm ẩn. Đã chứng minh trên cây base
  edbfb8c (worktree, chưa có code task 82): mở modal cũng ra đúng
  warning này; diff task 82 không chạm dòng nào của modal. Ngoài
  phạm vi task 82 (plan: giữ nguyên modal); check script lọc đúng
  warning này như tiền lệ ERR_TUNNEL_CONNECTION_FAILED. Cách sửa
  (task riêng sau): trả `""` thay cho `None` ở `handle_menus_hide_open`.
