# Task 50 — decisions

- D1: Bỏ hẳn luật nhãn cột duy nhất (theo yêu cầu user "đừng chặn gì cả"),
  không giữ lại dưới dạng cảnh báo. Hai cột trùng nhãn hiển thị giống nhau
  là chấp nhận được theo ý user.
- D2: Chỉ bỏ chặn ở service (`update_column` / `update_columns`); DB vốn
  không có UNIQUE trên LABEL nên không cần migration, không sửa schema.
- D3: Nhánh `feat/50-tab4-duplicate-labels-allowed` từ `3801901` (tip task 49);
  patch áp sau patch 49. Task 48 vẫn TẠM DỪNG ở nhánh riêng, không động vào.
