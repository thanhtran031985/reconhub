# Kế hoạch — 104-layout-cache-perf

## Implementation Plan

### Tổng quan
Task gồm 4 bước theo lộ trình đã duyệt:
1. **Bước 1 (làm ngay)**: Persistent AppShell + Cache Metadata/Sidebar (`shell.py`, `perm.py`, `data_source.py`, `temp_data.py`).
2. **Bước 2**: Skeleton-first + gộp N+1 query (`report_runs.py` và các page còn query trong `layout()`) + Server Layout Cache.
3. **Bước 3**: Nén HTTP Gzip + HTTP `Cache-Control` + Lazy-load JS nặng (`mermaid.min.js`, `tabulator.min.js`).
4. **Bước 4**: Client-side Stale-While-Revalidate (SWR) cho các màn danh sách.

### Chi tiết Bước 1 — Persistent AppShell & Cache Metadata/Sidebar
1. **File sửa/tạo**:
   - `app/services/perm.py`:
     - Cache `_tables_exist(engine)` bằng `WeakKeyDictionary[Engine, bool]` (chỉ cache khi `True`, xóa trong `clear_perm_cache()`).
   - `app/services/data_source.py`:
     - Cache `get_active_environment()` với TTL 30s (`WeakKeyDictionary[Engine, tuple[str, float]]`) kèm `invalidate_active_environment_cache()`, gọi invalidation khi tạo/sửa/kích hoạt/vô hiệu hóa Data Source.
   - `app/ui/layout/shell.py`:
     - Cache `_sidebar_tree(engine)` theo `(perm_revision, ttl=10s)` trong `WeakKeyDictionary`, dọn trong `clear_shell_caches()` (cũng gọi từ `clear_perm_cache()` hoặc tự check `perm_revision`).
     - Truyền tham số tùy chọn `nav_groups=None` vào `create_header(...)` và `create_navbar(...)` để `render_app_shell` tính `nav_groups` 1 lần dùng chung cho cả header search store và navbar.
     - Gắn `id="app-header-breadcrumbs"` cho `dmc.Breadcrumbs`.
     - Sửa truy vấn `MAINTENANCE_MODE` sang cột đúng (`recon_app_setting.c.KEY` / `.c.VALUE`) kèm cache TTL 30s (`invalidate_shell_meta_cache()`).
     - Thay thế việc gọi trực tiếp `usage(ctx)` (chạy `os.walk` đồng bộ mỗi lần mở shell) bằng helper `_get_cached_storage_usage(ctx)` cache 300s trong RAM theo `(user_id, is_admin)` và chỉ chạy khi dựng shell ban đầu (không chạy khi đổi route trong shell).
     - Thêm `dcc.Store(id="app-shell-mode", data=None)` trong `create_shell_layout()`.
     - Giữ hàm thuần `render_app_shell(pathname, is_collapsed_data)` trả về đúng 1 cây component như cũ (bảo toàn 100% unit test gọi trực tiếp).
     - Tách callback `@callback` `update_app_shell_container` (Output: `app-shell-container.children`, `app-shell-mode.data`) chỉ dựng lại AppShell khi đổi mode (`shell` ↔ `shellless`) hoặc đổi `user_id`; nếu đang ở `shell` cùng user thì `raise PreventUpdate`.
     - Thêm callback nhẹ `sync_shell_on_navigate` (Output: `app-header-breadcrumbs.children`, `app-shell-navbar.children`, `app-menu-search-input.value`, `app-menu-search-results.children`, `app-menu-search-results-paper.style`) chạy khi đổi route trong `shell` để cập nhật breadcrumb, active nav link và reset ô tìm kiếm menu mà không remount AppShell.
   - `tests/unit/test_layout_cache_perf.py`: Viết test trước cho Persistent AppShell, breadcrumb/navbar sync, cache `_sidebar_tree`, `_tables_exist`, `get_active_environment`, `_get_cached_storage_usage` và `MAINTENANCE_MODE`.
2. **Lệnh kiểm tra Bước 1**:
   - `uv run poe typecheck`
   - `uv run poe lint`
   - `uv run pytest tests/unit/test_layout_cache_perf.py tests/unit/test_ui_shell.py tests/unit/test_ui_foundation.py tests/unit/test_console_cleanup45.py tests/unit/test_notifications78.py tests/e2e/test_forgot_password_flow.py tests/e2e/test_e2e_screens.py`
   - Kiểm chứng Playwright chuyển trang qua lại giữa `/templates`, `/batches`, `/report-runs` giữ nguyên Header/AppShell, active nav + breadcrumb đúng, không lỗi console.
3. **Rủi ro & giảm thiểu**:
   - Rủi ro khi test gọi `render_app_shell(pathname, False)` trực tiếp: giữ nguyên signature và giá trị trả về là component đơn (không trả tuple), đặt callback multi-output ở hàm `update_app_shell_container` riêng.
   - Rủi ro cache cũ dính giữa các test: dùng `WeakKeyDictionary` theo `engine` + xóa toàn bộ cache khi gọi `clear_perm_cache()`.
   - Rủi ro chuyển từ `/login` → `/` hoặc `/` → `/login` (đổi mode `shellless` ↔ `shell`): kiểm tra `shell_state` trước khi `PreventUpdate` ở cả hai callback để tránh đụng component chưa mount.
4. **Package cài thêm**: Không cài thêm package nào ở Bước 1.
