# 104-layout-cache-perf — Cache layout, Persistent AppShell và tối ưu tốc độ tải trang

- Ngày tạo: 2026-11-25
- Giai đoạn: GĐ3
- Phụ thuộc: 08, 19, 20, 27
- Nhánh git: feat/104-layout-cache-perf

## Mục tiêu
Tối ưu tốc độ mở và chuyển trang trong ReconHub theo các pattern chuẩn công nghiệp (Persistent AppShell, Revision-based Server Cache, Skeleton-first + Server Layout Cache, Compression/Lazy-load Assets và Client-side Stale-While-Revalidate), giảm tối đa số query DB lặp lại, loại bỏ quét ổ đĩa đồng bộ khi render khung trang và không phá hủy/dựng lại Header + Navbar mỗi lần đổi route.

## Phạm vi
- `app/ui/layout/shell.py`: Persistent AppShell (không rebuild `app-shell-container` khi chuyển giữa các trang có shell của cùng người dùng), tách cập nhật breadcrumb + active nav link + reset tìm kiếm menu; loại bỏ `inspect()` và `usage()` (`os.walk`) lặp lại trong luồng render đồng bộ.
- `app/services/perm.py`, `app/services/data_source.py`, `app/services/temp_data.py`: Cache theo `WeakKeyDictionary` + TTL + `PERM_REVISION` (tự xóa khi `clear_perm_cache()` hoặc đổi dữ liệu cấu hình).
- Các bước tiếp theo (2–4): Skeleton-first cho page còn query đồng bộ trong `layout()` (như `report_runs.py`) + gộp N+1 query + cache layout tĩnh; nén HTTP/cache-control/lazy-load asset nặng; Client-side SWR cho danh sách.

## Ngoài phạm vi
- Không thay đổi database schema hoặc migration.
- Không thay đổi nghiệp vụ phân quyền menu (`PERM_REVISION`) hay logic tính dung lượng lưu trữ tạm.

## Thiết kế
- `designs/reference/preview-fluent.html`

## Spec liên quan
- `docs/specs/08_production_architecture.md`
- `docs/PRD.md`

## Quyết định kiến trúc
- Giữ nguyên signature và kiểu trả về của các hàm thuần `render_app_shell(pathname, is_collapsed_data)`, `create_header(...)`, `create_navbar(...)`, `sync_sidebar_ui(...)` để tương thích 100% với unit/E2E tests hiện có.
- Dùng `WeakKeyDictionary[Engine, ...]` kết hợp `PERM_REVISION` và TTL ngắn cho cache metadata/sidebar để tránh rò rỉ hoặc đụng độ `id(engine)` giữa các test fixture.
- Tách callback `@callback` cập nhật `app-shell-container` (`update_app_shell_container`) ra khỏi hàm thuần `render_app_shell`, theo dõi `app-shell-mode` (`mode`, `user_id`) để chỉ dựng lại AppShell khi đổi giữa `shell` ↔ `shellless` hoặc đổi `user_id`.

## Các bước
### Bước 1 — Persistent AppShell và Cache Metadata/Sidebar
- Làm: Tách `update_app_shell_container` + `sync_shell_on_navigate` trong `app/ui/layout/shell.py`; gán `id="app-header-breadcrumbs"` cho `dmc.Breadcrumbs`; truyền `nav_groups` dùng chung giữa `create_header` và `create_navbar`; sửa bug cột `RECON_APP_SETTING` (`KEY`/`VALUE`) và bỏ `os.walk` (`usage()`) khỏi luồng chặn chuyển trang (cache TTL 300s); cache `_sidebar_tree` và `_tables_exist` trong `app/services/perm.py` & `app/ui/layout/shell.py`; cache TTL ngắn cho `get_active_environment()` trong `app/services/data_source.py` (kèm invalidation khi thay đổi Data Source).
- Test viết trước: `tests/unit/test_layout_cache_perf.py` kiểm tra Persistent Shell trả `PreventUpdate` khi đổi route cùng user và cập nhật breadcrumb + navbar active + reset ô tìm kiếm; kiểm tra `_sidebar_tree`, `_tables_exist`, `get_active_environment`, `usage_cached` hit cache (không query lặp / không `os.walk` mỗi lần chuyển trang) và invalidate khi `PERM_REVISION` đổi hoặc gọi `clear_perm_cache()`.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run pytest tests/unit/test_layout_cache_perf.py tests/unit/test_ui_shell.py tests/unit/test_ui_foundation.py tests/unit/test_console_cleanup45.py tests/unit/test_notifications78.py tests/e2e/test_forgot_password_flow.py tests/e2e/test_e2e_screens.py` → toàn bộ xanh; kiểm chứng Playwright chuyển trang qua lại mượt, active nav + breadcrumb đúng.

### Bước 2 — Skeleton-first, gộp N+1 query và Server Layout Cache
- Làm: Tách query DB đồng bộ khỏi `layout()` ở các page nặng (trước hết `report_runs.py` + gộp N+1 `list_exports` theo lô `RUN_ID IN (...)`); thêm cache layout tĩnh theo `(route, role_set, perm_revision)`.
- Test viết trước: Test benchmark/đếm số SQL query và kiểm tra `layout()` không truy vấn nặng khi render khung ban đầu.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run pytest` xanh.

### Bước 3 — Asset Lazy-Load, Nén HTTP và Cache-Control
- Làm: Bật nén HTTP (Gzip), đặt `Cache-Control` cho static assets và lazy-load các bundle JS nặng (`mermaid.min.js`, `tabulator.min.js`) theo đúng page cần dùng.
- Test viết trước: Test kiểm tra header `Content-Encoding` / `Cache-Control` và trang `/login`, `/report-runs` không nạp thư viện không liên quan.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run pytest` xanh.

### Bước 4 — Client-side Stale-While-Revalidate (SWR)
- Làm: Bổ sung `dcc.Store(storage_type="session")` kết hợp `fingerprint` cho các màn danh sách hay chuyển qua lại (`/templates`, `/batches`, `/report-runs`) để hiển thị tức thì dữ liệu gần nhất và đồng bộ nền.
- Test viết trước: Test callback trả `no_update` khi fingerprint khớp và cập nhật khi dữ liệu đổi.
- Kiểm tra: `uv run poe typecheck`, `uv run poe lint`, `uv run pytest` xanh.

## Chấp nhận khi
- [ ] Chuyển giữa các trang trong shell không dựng lại `AppShell` (`app-shell-container` giữ nguyên, breadcrumb và active nav cập nhật đúng).
- [ ] `_sidebar_tree`, `_tables_exist`, `get_active_environment`, kiểm tra `MAINTENANCE_MODE` và `usage` được cache hợp lý, không quét ổ đĩa `os.walk` ở mỗi lần chuyển trang.
- [ ] `uv run poe typecheck`, `uv run poe lint`, bộ test UI shell + E2E xanh.

### Data Model Impact
- [x] Task không thay đổi database schema.

## Câu hỏi mở
- Không có.
