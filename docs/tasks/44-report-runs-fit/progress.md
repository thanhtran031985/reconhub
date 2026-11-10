# Tiến độ — Task 44

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Khung vừa 1 trang + icon Chạy lại | Xong | 2026-11-10 |  |
| 3 | Kiểm chứng cuối + xuất patch | Xong | 2026-11-10 | Full suite 1454 pass / 6 skipped; Playwright 16/16; patch ~/workspace/reconhub-task44.patch, verify `git am` sạch từ `2b9f924`. |

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 2 fail / 0 pass (layout còn `height: 100%`, nút Chạy
  lại chưa có icon).
- Targeted: 19 pass, typecheck 0, lint sạch.
- Playwright check-44: 16/16.
- Full suite: 1454 pass / 6 skipped (1452 cũ + 2 test mới task 44).
- Nguyên nhân gốc: không chỉ `height: 100%` — `dcc.Loading` dùng `style`
  (đi vào lớp phủ spinner) nên khối Loading cao theo nội dung, đẩy phân
  trang ra khỏi khung rồi bị `overflow: hidden` cắt mất. Đã chuyển sang
  `parent_style` như viewer (task 39) — lúc đầu chỉ đổi height vẫn FAIL
  44b–44f, sau khi đổi parent_style mới pass hết.
