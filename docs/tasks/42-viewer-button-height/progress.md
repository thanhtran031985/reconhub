# Tiến độ — Task 42

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Sửa nút Xem size sm | Xong | 2026-11-10 |  |
| 3 | Kiểm chứng cuối + xuất patch | Đang làm | 2026-11-10 |  |

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 1 fail / 1 pass — nút Xem đang `size="xs"` (30px),
  ô nhập mặc định sm (36px).
- Typecheck 0 lỗi, lint sạch, test viewer 37 pass.
- Playwright `~/workspace/check-42.py`: **5/5 PASS** — nút Xem cao
  36px, bằng ô Từ ngày (DateInput) và ô Org (Select), đáy thẳng hàng,
  console không lỗi mới.
