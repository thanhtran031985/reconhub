# Task 59 — plan

## Các bước
1. Test trước (đỏ): thêm class `TestAdminPageSize` vào
   `tests/unit/test_page_report_admin.py` — cỡ trang 20 hiện 20
   dòng trang 1, cỡ 50 hiện hết 25 dòng 1 trang, trang vượt quá
   kẹp về trang cuối, `handle_admin_filter` đổi cỡ trang → về
   trang 1, bấm phân trang giữ nguyên trang với cỡ trang đã chọn.
2. Code (`app/ui/pages/report_admin.py`):
   - Hằng số `ADMIN_PAGE_SIZE_OPTIONS = [10, 20, 50, 100]`,
     `DEFAULT_ADMIN_PAGE_SIZE = 10`.
   - Thanh phân trang trong `render_report_list`: thêm
     `dmc.Select(id="admin-page-size")` ("N dòng/trang",
     value = cỡ trang hiện tại), luôn hiện kể cả khi chỉ 1 trang.
   - `handle_admin_filter`: thêm `Input("admin-page-size",
     "value")`; parse + kẹp cỡ trang về danh sách cho phép
     (sai/không hợp lệ → 10); đổi cỡ trang → về trang 1 (cùng
     nhánh với đổi lọc); truyền `page_size` xuống
     `render_report_list`.
3. Kiểm tra: chỉ chạy test của task (`tests/unit/
   test_page_report_admin.py`) với `TMPDIR=/run/pytest-tmp`;
   `uv run ruff check` trên file sửa; `uv run poe typecheck`
   nếu nhanh (chỉ báo kết quả, không sửa ngoài phạm vi).
4. Kiểm chứng live: chạy lại `~/workspace/check-59-paging.py`
   mở rộng — đổi cỡ trang 20 → 20 dòng/trang 1, đổi 50 → hết
   25 dòng 1 trang, bấm trang 2 với cỡ 20 đúng dòng 21–25,
   không lỗi JS.
5. Báo cáo lại cho agent cha (không commit, không full suite):
   danh sách nào đã có/không có phân trang trước khi sửa, đã
   sửa gì, kết quả test/ruff, điểm nào chưa kiểm chứng live.
