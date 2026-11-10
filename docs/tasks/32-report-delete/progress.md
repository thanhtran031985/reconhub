# Tiến độ — 32-report-delete

Trạng thái: ⬜ (đã tạo task + nhánh, plan chưa duyệt, chưa code)

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 0 | Tạo task + nhánh `feat/32-report-delete` từ `adecaa7`, viết plan | ✅ | 2026-11-10 |  |
| 1 | Service `delete_report` + test viết trước | ⬜ |  |  |
| 2 | UI: mục "Xóa" + modal xác nhận + callback | ⬜ |  |  |
| 3 | Kiểm chứng cuối + xuất patch | ⬜ |  |  |

## Nhật ký

- 2026-11-10: Người dùng báo dòng "Hoạt động" nhưng cột Thao tác trống trên
  `/report-admin` và muốn bổ sung action xóa; trợ lý phân tích xong, người
  dùng chọn "Xóa hẳn khỏi DB". Người dùng yêu cầu tách nhánh + task riêng
  vì sửa nhiều. Đã tạo nhánh `feat/32-report-delete` từ `adecaa7` và hồ sơ
  task; plan đang chờ duyệt, chưa code.
- 2026-11-10: Người dùng sửa quyết định chặn: **xóa luôn dù có lần chạy**.
  Đã cập nhật task.md/plan.md/decisions.md (cascade thêm run + export,
  bỏ test chặn `CONFLICT`); plan đang chờ duyệt lại, chưa code.
