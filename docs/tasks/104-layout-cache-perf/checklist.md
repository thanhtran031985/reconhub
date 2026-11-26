# Checklist kiểm thử — 104-layout-cache-perf

Mục đích: Ghi nhận và cập nhật danh sách test case chi tiết cho task, theo dõi trạng thái kiểm thử trước và sau khi hoàn thành code.

---

## 1. Kiểm thử chức năng (Functional Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-FN-01** | Đổi route trong shell cùng user (`/templates` → `/report-runs`) | `update_app_shell_container` trả `PreventUpdate` (giữ nguyên AppShell); `sync_shell_on_navigate` cập nhật breadcrumb, active nav và reset menu search | ✅ |
| **TC-FN-02** | Đổi mode `shellless` ↔ `shell` (`/login` ↔ `/`) hoặc đổi `user_id` | `update_app_shell_container` dựng lại AppShell mới và cập nhật `app-shell-mode`; `sync_shell_on_navigate` bỏ qua (`PreventUpdate`) | ✅ |
| **TC-FN-03** | Cache `_sidebar_tree` và `_tables_exist` | Gọi lặp cùng `PERM_REVISION` không chạy `inspect().get_table_names()` hay SQL lặp; tự làm mới khi `PERM_REVISION` đổi hoặc gọi `clear_perm_cache()` | ✅ |
| **TC-FN-04** | Cache `get_active_environment`, `MAINTENANCE_MODE` và `_get_cached_storage_usage` | Tránh `os.walk` và SQL lặp lại; đọc đúng cột `KEY`/`VALUE` của `RECON_APP_SETTING`; invalidate đúng khi cấu hình đổi | ✅ |
| **TC-FN-05** | Gộp N+1 trong `list_exports_by_runs`, `list_reports` (`template_count`) và `list_templates` | Số câu SQL giữ hằng số (batch `IN`/subquery hoặc `GROUP BY`) khi tăng số bản ghi | ✅ |
| **TC-FN-06** | Skeleton-first ở `report_runs.layout()` + `load_runner_options` | `layout()` trả khung `rowData=None`, không chạy `list_runs`/`list_exports` khi chuyển trang; giữ nguyên 12 output của `handle_runs_refresh` | ✅ |
| **TC-FN-07** | `cached_layout` ở `templates`, `batch_defs`, `dashboard`, `report_runs` | Cache hit theo `(engine, key)` trong TTL; tự xóa khi gọi `clear_perm_cache()` / `clear_layout_cache()` | ✅ |
| **TC-FN-08** | Lazy-load asset nặng (`mermaid.min.js`, `tabulator.min.js`, `tabulator.min.css`) | Trang `/login`, `/report-runs` không nạp bundle không liên quan trong HTML; `/assets/lazy/*` tải được khi cần | ✅ |
| **TC-FN-09** | Nén HTTP Gzip và `Cache-Control` | Response >= 512B trả `Content-Encoding: gzip`, `Vary: Accept-Encoding`; static assets có `Cache-Control: public, max-age=...` | ✅ |
| **TC-FN-10** | SWR `sessionStorage` + fingerprint trên `/templates`, `/batches`, `/report-runs` | `dcc.Store` dùng `storage_type="session"`; callback trả `no_update` khi fingerprint khớp và cập nhật khi dữ liệu đổi | ✅ |

---

## 2. Kiểm thử giao diện & Trải nghiệm (UI/UX Test Cases)

| Mã TC | Nội dung kiểm thử | Kết quả mong đợi | Trạng thái |
|---|---|---|---|
| **TC-UI-01** | Chuyển trang qua lại trên trình duyệt thật (Playwright) giữa `/`, `/templates`, `/batches`, `/report-runs` | AppShell không bị tháo/dựng lại, breadcrumb và mục menu active cập nhật đúng, 0 lỗi console/pageerror | ✅ |
| **TC-UI-02** | Giao diện 1440×900 và 1366×768 | Không có cuộn ngang/dọc toàn trang trên các màn chính | ✅ |
| **TC-UI-03** | `/report-runs` chế độ Skeleton-first trên Playwright | Mở trang với `rowData=None`, sau đó AG Grid nạp đủ dữ liệu và dropdown người chạy; Saved Views và cột hoạt động đúng ở 1440×900 và 1366×768 | ✅ |
| **TC-UI-04** | Playwright xác minh toàn diện Bước 1–4 (`verify_all_optimizations.py`) | `/login`, `/report-runs` không tải Mermaid/Tabulator; `/templates` lazy-load Tabulator; `/templates/{id}/diagram` lazy-load Mermaid; SWR lưu `sessionStorage`; 0 lỗi console ở 1440×900 và 1366×768 | ✅ |

---

## 3. Kiểm thử hồi quy & Chất lượng kỹ thuật (Regression & Quality)

| Mã TC | Lệnh kiểm tra | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-REG-01** | `uv run poe lint` | Không có lỗi ruff | ✅ |
| **TC-REG-02** | `uv run poe typecheck` | Không có lỗi mypy | ✅ |
| **TC-REG-03** | `uv run pytest tests/unit/test_layout_cache_perf.py tests/unit/test_ui_shell.py tests/unit/test_ui_foundation.py tests/unit/test_console_cleanup45.py tests/unit/test_notifications78.py tests/e2e/test_forgot_password_flow.py tests/e2e/test_e2e_screens.py` | Toàn bộ test xanh | ✅ |
| **TC-REG-04** | `uv run pytest tests/unit/test_layout_cache_step2.py tests/unit/test_layout_cache_perf.py tests/unit/test_template_service.py tests/unit/test_report_export_download.py tests/unit/test_page_reports.py tests/unit/test_page_templates.py tests/unit/test_batch_def_pages.py tests/unit/test_history_aggrid55.py tests/unit/test_history_refresh53.py tests/unit/test_report_runs_fit44.py tests/unit/test_report_runs_history43.py tests/unit/test_console_cleanup45.py tests/e2e/test_e2e_screens.py` | Toàn bộ 137 test xanh | ✅ |
| **TC-REG-05** | `uv run poe typecheck`, `uv run poe lint`, bộ 14 file unit Bước 1–4 + toàn bộ `tests/e2e/` | 0 lỗi mypy (174 file), ruff đạt, 175 passed | ✅ |
| **TC-REG-06** | Cập nhật `test_page_report_runs.py` (2 ca Skeleton-first) và chạy nốt phần còn lại | 24/24 ca Bước 1–4 + `test_page_report_runs.py` xanh; 13/13 ca `test_ui_auth` + `test_file_routes` + `test_session_middleware` xanh; phần 70%–100% unit test còn lại đạt (chỉ còn 2 fail nền sẵn ở `test_wizard_enhancements.py`) | ✅ |

---

## 4. Kiểm thử bảo mật tự động & An toàn (Security & Safety)

| Mã TC | Lệnh / Nội dung kiểm thử | Tiêu chí đạt | Trạng thái |
|---|---|---|---|
| **TC-SEC-01** | `uv run poe security-check` | Toàn bộ kiểm tra bảo mật tự động đạt (6/6) | ✅ |
| **TC-SEC-02** | Phân quyền & tách biệt user trong cache | Cache menu/quyền khóa theo `user_id` + `PERM_REVISION`; SWR `sessionStorage` kiểm tra `user_id` và xóa khi vào `/login`/`/logout` | ✅ |
