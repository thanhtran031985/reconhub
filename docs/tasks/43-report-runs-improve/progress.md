# Tiến độ — Task 43

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Service JOIN + lọc | Xong | 2026-11-10 |  |
| 3 | Trang history: cột, lọc, phân trang, chạy lại | Đang làm | 2026-11-10 |  |
| 4 | Viewer ?rerun_from= | Chưa làm |  |  |
| 5 | Kiểm chứng cuối + xuất patch | Đang làm | 2026-11-10 | Playwright ~/workspace/check-43.py: 18/18 pass (tên/nhóm, 14,585, thời gian, tham số, bỏ Xem, icon tải + tải được file, lọc tên/ngày/người, cỡ trang, rerun_from điền sẵn + Xem ra kết quả, không lỗi console mới). |

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 10 fail / 0 pass (service chưa JOIN/lọc, bảng chưa có
  cột mới, viewer chưa hỗ trợ `rerun_from`).
- Targeted: 52 pass (43 + page runs + viewer), typecheck 0, lint sạch.
- Playwright check-43: 18/18 (xem trên).
- Lưu ý: icon Excel/mũi tên không hiện trong môi trường kiểm chứng vì
  proxy chặn CDN iconify (cảnh báo có sẵn) — link vẫn bấm được nhờ
  vùng bấm tối thiểu 36×28px; trên máy người dùng có mạng sẽ hiện icon.
- Full suite: đang chạy.

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 10 fail / 0 pass (service chưa JOIN/lọc, bảng chưa có
  cột mới, viewer chưa hỗ trợ `rerun_from`).
