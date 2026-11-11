# Task 50 — Cho phép lưu trùng nhãn cột (tab 4)

## Bối cảnh
Sau task 49, user báo tab 4: sửa nhãn rồi Lưu cột vẫn về giá trị cũ.
Chẩn đoán (đã tái hiện bằng test): `update_columns` kiểm tra trùng nhãn
trên nhãn hiệu dụng đã đổi format — trùng nhãn có sẵn từ trước (vd 1 cột
đặt tay "Transaction Date" + 1 cột tên thô đổi ra cùng nhãn) chặn toàn bộ
lần lưu với lỗi `LABEL 'Transaction Date' đã tồn tại`.

## Quyết định của user (11/11/2026)
Cho phép lưu trùng nhãn, đừng chặn gì cả — bỏ hẳn luật uniqueness của nhãn
cột, không chỉ nới lỏng cho trùng có sẵn.

## Vị trí sửa
- `app/services/report_column.py`:
  - `update_columns`: bỏ khối kiểm tra trùng `merged` (nhãn duy nhất trên
    trạng thái cuối).
  - `_validate_column_rules`: bỏ nhánh kiểm tra `final_label` /
    `other_labels`; bỏ tham số đó khỏi signature.
  - `update_column`: bỏ tính `other_labels` + `final_label`, gọi
    `_validate_column_rules` chỉ với dto + data_type.
- DB không có UNIQUE trên LABEL (chỉ UNIQUE(VERSION_ID, FIELD_NAME)) nên
  bỏ chặn ở service là đủ, không cần migration.

## Các bước
1. Kiểm tra DB + caller (xong).
2. Docs + test đỏ (trùng nhãn lưu được, cả trùng có sẵn lẫn trùng mới).
3. Bỏ chặn trùng nhãn.
4. Cập nhật test cũ khẳng định hành vi chặn (TestLabelUnique) sang hành vi
   mới; typecheck + lint + full suite + Playwright + xuất patch.
