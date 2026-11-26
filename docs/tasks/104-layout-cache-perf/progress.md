# Tiến độ — 104-layout-cache-perf

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Persistent AppShell và Cache Metadata/Sidebar | ✅ | 2026-11-25 | |
| 2 | Skeleton-first, gộp N+1 query và Server Layout Cache | ✅ | 2026-11-25 | |
| 3 | Asset Lazy-Load, Nén HTTP và Cache-Control | ✅ | 2026-11-25 | |
| 4 | Client-side Stale-While-Revalidate (SWR) | ✅ | 2026-11-25 | |

## Nhật ký
- **2026-11-25 — Bước 1**:
  - Đã tách hàm thuần `render_app_shell` và callback `update_app_shell_container` + `sync_shell_on_navigate` trong `app/ui/layout/shell.py` theo mẫu Persistent AppShell (giữ nguyên khung AppShell khi chuyển trang cùng user, chỉ cập nhật breadcrumb, navbar active và reset ô tìm kiếm menu).
  - Bổ sung cache dùng `WeakKeyDictionary[Engine, ...]` cho `_tables_exist` (`app/services/perm.py`), `get_active_environment()` (`app/services/data_source.py`), `_sidebar_tree`, `_get_cached_maintenance_mode` (sửa lỗi query cột `KEY`/`VALUE`) và `_get_cached_storage_usage` TTL 300s (`app/ui/layout/shell.py`), tránh quét ổ cứng `os.walk` và `inspect()` lặp lại.
  - Kiểm tra: `uv run poe typecheck` (0 lỗi, 171 file), `uv run poe lint` (đạt), `uv run pytest tests/unit/test_layout_cache_perf.py tests/unit/test_ui_shell.py tests/unit/test_ui_foundation.py tests/unit/test_console_cleanup45.py tests/unit/test_notifications78.py tests/e2e/test_forgot_password_flow.py tests/e2e/test_e2e_screens.py` (87 passed), Playwright xác nhận `#app-shell` không remount khi đổi route `/ -> /templates -> /batches -> /report-runs`, không cuộn trang ở 1440×900 và 1366×768.
  - Tự suy ra: Tách `build_breadcrumb_nodes` và truyền `nav_groups` dùng chung giữa `create_header` và `create_navbar` để loại bỏ lần gọi `_sidebar_tree`/`effective_menus` thứ hai khi dựng shell; dùng `register_cache_clear_hook` để `clear_perm_cache()` tự động dọn cache shell trong test.
- **2026-11-25 — Bước 2**:
  - Tạo `app/ui/layout_cache.py` (`cached_layout`, `clear_layout_cache` gắn qua `register_cache_clear_hook` trong `app/services/perm.py`) để cache cây layout theo `(engine, key)` với TTL 30s cho các trang tĩnh/theo capability (`templates.py`, `batch_defs.py`, `dashboard.py` sau `page_gate`, `report_runs.py` skeleton).
  - Chuyển `app/ui/pages/report_runs.py` sang Skeleton-first (`rowData=None`, `overlayLoadingTemplate`, `total=0`) kèm callback `load_runner_options` tách riêng để giữ nguyên đúng 12 output của `handle_runs_refresh`.
  - Gộp truy vấn N+1: thêm `list_exports_by_runs` trong `app/services/report_export.py` (dùng trong `report_runs._load_page_data`); gộp `template_count` bằng `GROUP BY` trong `app/services/report.py` (`list_reports`, dùng bởi `app/ui/pages/reports.py`); gộp batch `recon_template_version`, `recon_file`, `recon_run` trong `app/services/template.py` (`list_templates`).
  - Kiểm tra: `uv run poe typecheck` (0 lỗi, 172 file), `uv run poe lint` (đạt), `uv run pytest` 13 file kiểm thử liên quan Bước 2 + hồi quy + E2E (137 passed), Playwright xác nhận `/report-runs` ở 1440×900 và 1366×768 (`REPORT_RUNS_PW_OK`, `PERSISTENT_SHELL_PW_OK True True True`, bảng AG Grid nạp đủ dữ liệu và không cuộn trang).
  - Tự suy ra: Với `dashboard.py`, đặt `cached_layout` sau `page_gate` để trang `/suspended` vẫn bị chặn trước khi đọc cache; tách `load_runner_options` thành callback riêng thay vì gộp vào `handle_runs_refresh` để không phá hợp đồng 12 output hiện hữu.
- **2026-11-25 — Bước 3 & Bước 4 (tạm dừng trước khi đóng task để mai test tiếp)**:
  - **Bước 3 (Asset Lazy-Load, Gzip, Cache-Control)**:
    - Di chuyển `mermaid.min.js`, `mermaid_init.js`, `tabulator.min.js`, `tabulator.min.css`, `tabulator_fluent.css` sang `app/ui/assets/lazy/` và cấu hình `assets_path_ignore=[r"^lazy$"]` + `assets_ignore` trong `app/ui/app.py`.
    - Tạo `app/ui/assets/lazy_loader.js` (`window.reconLazy.ensureTabulator`, `ensureMermaid`, dọn SWR keys khi vào `/login` hoặc `/logout`) và tích hợp vào `mountTabulator` của `templates.py`, `batch_defs.py`.
    - Tạo `app/ui/http_cache.py` (`register_http_optimizations`): Gzip cho response `>= 512B` (`Content-Encoding: gzip`, `Vary: Accept-Encoding`, `ETag` `-gzip`) và `Cache-Control` (`immutable` 1 năm cho `/_dash-component-suites/` và `/assets/*?m=|v=`; `public, max-age=86400` cho `/assets/lazy/*`; `no-store` cho `/_dash-update-component`).
  - **Bước 4 (Client-side SWR & Fingerprint)**:
    - Tạo `app/ui/swr.py` (`compute_fingerprint`, `should_skip_swr_update`, `is_stale_user_store`).
    - Bật `dcc.Store(..., storage_type="session")` + bỏ qua `no_update` khi fingerprint khớp + chặn lộ dữ liệu khác `user_id` trên `/templates` (`tmpl-store-list`), `/batches` (`bdef-store-list`) và `/report-runs` (`report-runs-swr-store` + clientside hydrate/save).
  - **Đã test trong ngày 2026-11-25**:
    - `uv run poe typecheck`: 0 lỗi (174 file).
    - `uv run poe lint`: đạt (`All checks passed`).
    - `uv run poe security-check`: 6/6 đạt (0 vi phạm).
    - Bộ 14 file unit Bước 1–4 + toàn bộ `tests/e2e/`: **175 passed, 0 failed**.
    - Playwright trình duyệt thật (`verify_all_optimizations.py`, `verify_templates_ui.py`, `verify_report_runs_ui.py`, `verify_persistent_shell.py`): tất cả đạt (`ALL_OPTIMIZATIONS_PW_OK`, `REPORT_RUNS_PW_OK`, `PERSISTENT_SHELL_PW_OK`), 0 lỗi console/pageerror, không tràn trang ở 1440×900 và 1366×768.
    - `uv run poe test-engine`: chạy tới **70%** (`test_report_param_lov.py`) rồi tạm dừng theo yêu cầu để mai test tiếp. Ghi nhận 2 ca cần sửa trong phạm vi task: `tests/unit/test_page_report_runs.py` (`test_operator_sees_only_own_runs`, `test_admin_sees_all_runs` đang assert `layout()` trả row sync thay vì Skeleton-first + `handle_runs_refresh`); các file fail khác quan sát được tới 70% là lỗi nền trước đó (`test_perm_migration.py`, `test_dark_mode73.py`, `test_draft_reuse_code76.py`, `test_export_background52.py`, `test_menu_admin_service.py`, `test_menu_sync.py`, `test_page_roles.py`, `test_perm_registry.py`, `test_report_add_template74.py`).
  - **Việc còn lại ngày mai**: Cập nhật 2 test trong `tests/unit/test_page_report_runs.py` theo Skeleton-first, chạy nốt `uv run poe test-engine` (hoặc phần còn lại 70%–100%), rà soát bảng "Chấp nhận khi" và đóng task `104-layout-cache-perf`.
- **2026-11-26 — Hoàn tất kiểm tra & đóng task**:
  - Cập nhật 2 assertion trong `tests/unit/test_page_report_runs.py` (`test_operator_sees_only_own_runs`, `test_admin_sees_all_runs`) sang kiểm tra `handle_runs_refresh` phù hợp Skeleton-first; ghi nhận vào `decisions.md`.
  - Chạy lại xác minh sau chỉnh sửa cuối: `uv run poe typecheck` (0 lỗi, 174 file), `uv run poe lint` (đạt), `uv run poe security-check` (6/6 đạt), `uv run pytest tests/unit/test_page_report_runs.py tests/unit/test_layout_cache_perf.py tests/unit/test_layout_cache_step2.py tests/unit/test_layout_cache_step3.py tests/unit/test_layout_cache_step4.py` (24 passed).
  - Chạy phần còn lại 70%–100% của `tests/unit/` (656 passed; 2 fail sẵn có không liên quan ở `test_wizard_enhancements.py`), và xác minh riêng `tests/test_ui_auth.py`, `tests/integration/test_file_routes.py`, `tests/integration/test_session_middleware.py` (13/13 passed).
  - Đổi trạng thái task sang `✅` trong `docs/tasks/README.md` và `progress.md`.
