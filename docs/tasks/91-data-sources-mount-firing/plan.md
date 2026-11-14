# Plan — Task 91

1. Đọc kỹ 4 callback đích + test hiện có của trang data_sources.
2. Sửa `app/ui/pages/data_sources.py`:
   - **D1** `handle_ds_active_toggle`: sau khi có `ds_id` + `new_checked`,
     đọc `IS_ACTIVE` hiện tại trong DB; nếu đã bằng trạng thái đích thì
     `raise dash.exceptions.PreventUpdate` (không gọi service, không
     bump trigger, không ghi audit).
   - **D2** `load_storage_data`: thêm `Input("ds-tabs", "value")`; nếu
     tab khác `"storage"` thì trả `dash.no_update`.
   - **D3** `handle_purge_preview`: thêm guard `if not n_clicks:
     raise dash.exceptions.PreventUpdate` ngay đầu.
   - **D4** `handle_drawer_open`: nhánh `not triggered` và nhánh
     `not trigger_val` (mount, không có click thật) trả
     `(dash.no_update,) * 12` thay vì tuple reset; nhánh Hủy và nhánh
     Thêm/Sửa giữ nguyên.
3. Test (red → green) trong `tests/unit/test_page_data_sources.py`
   (tạo mới nếu chưa có): D1 mount (cùng trạng thái → PreventUpdate,
   không gọi service, trigger không đổi), D1 click thật (đổi trạng thái
   → service chạy), D3 preview không click → PreventUpdate.
4. Live check `check-91-data-sources.py` (port 8147, DB check88f.db):
   mở trang → `ds-store-list` chỉ 1 lần, không có request trigger;
   đếm audit trước/sau = bằng nhau; bấm Switch thật → audit +1 và
   badge đổi; bấm tab Lưu trữ → storage tải; mở tab không tự preview.
5. `uv run poe tasks-dashboard` + revert `dashboard.html`; typecheck +
   lint; full suite.
6. Commit (explicit paths) → patch `reconhub-task91.patch` → verify
   `git am` trên worktree tại 9b2ada5 → cập nhật MEMORY.md → giao patch
   (áp sau patch 90; không db-migrate; restart app).
