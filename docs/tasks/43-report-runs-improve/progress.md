# Tiến độ — Task 43

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Service JOIN + lọc | Xong | 2026-11-10 |  |
| 3 | Trang history: cột, lọc, phân trang, chạy lại | Đang làm | 2026-11-10 |  |
| 4 | Viewer ?rerun_from= | Chưa làm |  |  |
| 5 | Kiểm chứng cuối + xuất patch | Chưa làm |  |  |

- Lưu ý sửa: lúc chèn helper `_parse_run_date` đã vô tình đặt nó dưới
  decorator `@service`/`@requires_menu` của `list_report_runs` (helper
  bị bọc service, hàm chính mất decorator) — đã sửa lại, test xanh.

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 10 fail / 0 pass (service chưa JOIN/lọc, bảng chưa có
  cột mới, viewer chưa hỗ trợ `rerun_from`).
