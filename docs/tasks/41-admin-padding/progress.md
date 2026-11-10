# Tiến độ — Task 41

| Bước | Nội dung | Trạng thái | Ngày | Ghi chú |
|------|----------|------------|------|---------|
| 1 | Docs + test đỏ | Xong | 2026-11-10 |  |
| 2 | Sửa padding 6 trang | Xong | 2026-11-10 |  |
| 3 | Kiểm chứng cuối + xuất patch | Xong | 2026-11-10 |  |

- Full suite: **1441 pass / 6 skipped** (1434 + 7 test mới).

## Số liệu kiểm chứng (10/11/2026)

- Test đỏ ban đầu: 6 fail / 1 pass — 5 trang chưa có padding root, /account
  chưa padding + chưa canh giữa; test tham chiếu /report-admin xanh.
- Phát hiện phụ: `account.py` là trang duy nhất gọi `dash.register_page`
  không bọc try/except (các trang khác đều bọc) nên import module khi
  chưa có app Dash sẽ crash — đã bọc giống các trang khác (cần cho test
  import layout).
- Phát hiện phụ 2: `test_page_lookups.py` patch `app.core.session.
  get_current_ctx` (chỉ có tác dụng khi module trang chưa được import);
  file test mới import module trang trước nên 4 test lookups fail theo
  thứ tự chạy — đã đổi 7 chỗ sang patch `app.ui.pages.lookups.
  get_current_ctx` như mọi test trang khác.
- Playwright `~/workspace/check-41.py`: **9/9 PASS** — 5 trang root
  padding 8px/12px (computed), /account root 8px/12px + cột 640px canh
  giữa chính xác (trái = phải = 288px), console không lỗi mới.
  Lưu ý: trình duyệt chuẩn hóa `calc(100vh - 48px)` thành
  `calc(-48px + 100vh)` nên selector kiểm chứng phải tìm theo `100vh`.
