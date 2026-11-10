# Tiến độ — Task 43

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Service JOIN + lọc | Xong | 2026-11-10 |  |
| 3 | Trang history: cột, lọc, phân trang, chạy lại | Đang làm | 2026-11-10 |  |
| 4 | Viewer ?rerun_from= | Chưa làm |  |  |
| 5 | Kiểm chứng cuối + xuất patch | Xong | 2026-11-10 | Full suite 1452 pass / 6 skipped; Playwright 18/18; patch ~/workspace/reconhub-task43.patch, verify `git am` sạch từ `b015955`. |

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 10 fail / 0 pass (service chưa JOIN/lọc, bảng chưa có
  cột mới, viewer chưa hỗ trợ `rerun_from`).
- Targeted: 52 pass (43 + page runs + viewer), typecheck 0, lint sạch.
- Playwright check-43: 18/18 (xem trên).
- Lưu ý: icon Excel/mũi tên không hiện trong môi trường kiểm chứng vì
  proxy chặn CDN iconify (cảnh báo có sẵn) — link vẫn bấm được nhờ
  vùng bấm tối thiểu 36×28px; trên máy người dùng có mạng sẽ hiện icon.
- Full suite: 1452 pass / 6 skipped (1443 cũ + 9 mới ròng: thêm 10 test
  task 43, bỏ 2 test chạy-lại-cũ, thêm 1 test link rerun).

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 10 fail / 0 pass (service chưa JOIN/lọc, bảng chưa có
  cột mới, viewer chưa hỗ trợ `rerun_from`).
