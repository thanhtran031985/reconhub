# Quyết định — 14-issue-handling

| Ngày | Quyết định | Lý do | Ảnh hưởng spec/thiết kế |
|---|---|---|---|
| 2026-11-01 | Danh mục nguyên nhân chuẩn được nạp sẵn (seed) gồm 6 mã phổ biến: `ROUNDING`, `TIMING`, `SYSTEM_BUG`, `DATA_INPUT`, `POLICY_EXCEPTION`, `OTHER`. Quản trị viên quản lý danh mục, người dùng nghiệp vụ (Operator, Owner) được chọn khi xử lý chênh lệch. | Đảm bảo tính nhất quán trong phân loại chênh lệch và thống kê báo cáo theo chuẩn PRD C9. | `RECON_ISSUE_REASON` khởi tạo cùng hệ thống; API cho phép chọn danh sách active. |
| 2026-11-01 | Issue được quản lý độc lập với run, định danh duy nhất theo tuple `(TEMPLATE_ID, PROFILE_CODE, KEY_HASH)`. | Cho phép theo dõi vòng đời của một chênh lệch qua nhiều lần chạy đối soát liên tiếp mà không bị nhân bản bản ghi. | Bảng `RECON_ISSUE` lưu `FIRST_RUN_ID` và `LAST_RUN_ID`. |

## Câu hỏi còn mở
- —
