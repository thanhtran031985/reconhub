"""Tests cho registry menu — Bước 3 task 19 (test viết trước).

Mọi page Dash (trừ danh sách miễn trừ) phải khai báo MENU_CODE.
Mọi hàm @service có tham số ctx phải gắn requires_menu (trừ danh sách
miễn trừ có lý do rõ ràng). Mọi mã menu được tham chiếu phải tồn tại.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import app.services as services_pkg
import app.ui.pages as pages_pkg
from app.ui.menus import MENU_BY_CODE

# Page không cần menu_code (Q6): tài khoản cá nhân, đăng nhập, trang lỗi,
# trang tạm ngưng, gallery dev.
EXEMPT_PAGES = {"account", "login", "forbidden", "suspended", "dev_gallery"}

# Hàm @service có ctx nhưng không gắn menu_code, kèm lý do:
# - file_service.get_file: quyền tải file theo chủ sở hữu (Q8), kiểm tra ở bước 4.
# - user.change_password: tự đổi mật khẩu của chính mình, không gắn menu.
# - menu_sync.sync_from_code / sync_menus_safely: chạy khi khởi động, không có ctx.
EXEMPT_SERVICES = {
    ("file_service", "get_file"): "quyền tải file theo chủ sở hữu (Q8, bước 4)",
    ("user", "change_password"): "tự đổi mật khẩu của chính mình",
}


def _iter_service_modules():
    for mod in pkgutil.iter_modules(services_pkg.__path__):
        yield mod.name


def _iter_page_modules():
    for mod in pkgutil.iter_modules(pages_pkg.__path__):
        yield mod.name


class TestPageMenuRegistry:
    def test_every_page_declares_menu_code(self):
        missing = []
        for name in _iter_page_modules():
            if name in EXEMPT_PAGES:
                continue
            mod = importlib.import_module(f"app.ui.pages.{name}")
            code = getattr(mod, "MENU_CODE", None)
            if code is None:
                missing.append(name)
            else:
                assert code in MENU_BY_CODE, f"page {name} khai MENU_CODE không tồn tại: {code}"
        assert not missing, f"page thiếu MENU_CODE: {missing}"

    def test_page_menu_codes_match_expected(self):
        expected = {
            "dashboard": "dashboard",
            "new_run": "run",
            "run_result": "result",
            "history": "history",
            "issues": "issue",
            "templates": "template",
            "template_wizard": "template",
            "template_diagram": "template",
            "data_sources": "data_source",
            "lookups": "lookup",
            "users": "user",
            "roles": "role",
            "menus": "menu_admin",
            # Task 27: 4 trang báo cáo động.
            "reports": "report_center",
            "report_viewer": "report_center",
            "report_runs": "report_history",
            "report_admin": "report_admin",
        }
        for name, code in expected.items():
            mod = importlib.import_module(f"app.ui.pages.{name}")
            assert getattr(mod, "MENU_CODE", None) == code, f"page {name}"


class TestServiceMenuRegistry:
    def test_every_service_with_ctx_declares_menu(self):
        missing = []
        bad_codes = []
        for name in _iter_service_modules():
            mod = importlib.import_module(f"app.services.{name}")
            for fname, fn in inspect.getmembers(mod, inspect.isfunction):
                if fn.__module__ != f"app.services.{name}":
                    continue
                if not getattr(fn, "_is_service", False):
                    continue
                params = list(inspect.signature(fn).parameters)
                if not params or params[0] != "ctx":
                    continue
                if (name, fname) in EXEMPT_SERVICES:
                    continue
                codes = getattr(fn, "menu_codes", None)
                if not codes:
                    missing.append(f"{name}.{fname}")
                    continue
                for code in codes:
                    if code not in MENU_BY_CODE:
                        bad_codes.append(f"{name}.{fname}:{code}")
        assert not missing, f"service có ctx nhưng thiếu menu_code: {missing}"
        assert not bad_codes, f"service khai menu_code không tồn tại: {bad_codes}"

    def test_service_menu_mapping_matches_expected(self):
        expected = {
            ("dashboard", "get_dashboard_summary"): ["dashboard"],
            ("dashboard", "compare_runs"): ["dashboard"],
            ("dashboard", "get_previous_run"): ["dashboard"],
            ("data_source", "list_data_sources"): ["data_source"],
            ("data_source", "options_data_sources"): ["template", "data_source"],
            ("excel_load", "load_excel_to_temp"): ["run"],
            ("file_service", "upload_file"): ["run", "template"],
            ("issue", "list_issues"): ["issue"],
            ("issue", "update_issue_by_id"): ["issue"],
            ("lookup", "list_lookup_types"): ["lookup"],
            ("lookup", "create_lookup_type"): ["lookup"],
            ("metadata_migration", "start_migration"): ["data_source"],
            ("run_service", "create_run"): ["run"],
            ("run_service", "get_run"): ["result"],
            ("run_service", "list_runs"): ["result"],
            ("run_service", "export_run"): ["result"],
            ("temp_data", "mark_checked"): ["result"],
            ("temp_data", "purge_runs"): ["history", "result"],
            ("temp_data", "usage"): ["dashboard", "data_source"],
            ("template", "list_templates"): ["template", "issue"],
            ("template", "get_template"): ["template", "result"],
            ("template", "save_draft_template"): ["template"],
            ("template", "delete_template"): ["template"],
            ("template_export_import", "export_template"): ["template"],
            ("template_export_import", "export_template_sample_excel"): ["template"],
            ("template_export_import", "import_template"): ["template"],
            ("template_validate", "validate_template_connected"): ["template"],
            ("user", "list_users"): ["user"],
            ("user", "create_user"): ["user"],
            # Task 28 bước 1: toàn bộ service báo cáo động (T28-02).
            ("report", "archive_report"): ["report_admin"],
            ("report", "create_report"): ["report_admin"],
            ("report", "get_report"): ["report_center"],
            ("report", "list_reports"): ["report_center"],
            ("report", "set_report_favorite"): ["report_center"],
            ("report", "update_report"): ["report_admin"],
            ("report_template", "activate_version"): ["report_admin"],
            ("report_template", "archive_template"): ["report_admin"],
            ("report_template", "archive_version"): ["report_admin"],
            ("report_template", "clone_version"): ["report_admin"],
            ("report_template", "create_template"): ["report_admin"],
            ("report_template", "get_template"): ["report_center"],
            ("report_template", "get_version"): ["report_center"],
            ("report_template", "list_templates"): ["report_center"],
            ("report_template", "update_template"): ["report_admin"],
            ("report_template", "update_version_source"): ["report_admin"],
            ("report_source", "analyze_version_source"): ["report_admin"],
            ("report_source", "apply_source_diff"): ["report_admin"],
            ("report_source", "list_report_columns"): ["report_admin"],
            ("report_source", "list_report_objects"): ["report_admin"],
            ("report_source", "validate_version_sql"): ["report_admin"],
            ("report_param", "auto_layout"): ["report_admin"],
            ("report_param", "create_param"): ["report_admin"],
            ("report_param", "delete_param"): ["report_admin"],
            ("report_param", "move_param"): ["report_admin"],
            ("report_param", "preview_layout"): ["report_center"],
            ("report_param", "reorder_params"): ["report_admin"],
            ("report_param", "resolve_lov"): ["report_center"],
            ("report_param", "resolve_param_values"): ["report_center"],
            ("report_param", "update_param"): ["report_admin"],
            ("report_param", "validate_layout"): ["report_center"],
            ("report_column", "get_result_layout"): ["report_center"],
            ("report_column", "list_columns"): ["report_center"],
            ("report_column", "move_column"): ["report_admin"],
            ("report_column", "preview_result_layout"): ["report_center"],
            ("report_column", "refresh_columns"): ["report_admin"],
            ("report_column", "reorder_columns"): ["report_admin"],
            ("report_column", "restore_column_order"): ["report_admin"],
            ("report_column", "update_column"): ["report_admin"],
            ("report_column", "update_columns"): ["report_admin"],
            ("report_run", "apply_preset"): ["report_center"],
            ("report_run", "cancel_report_run"): ["report_center"],
            ("report_run", "create_preset"): ["report_center"],
            ("report_run", "create_report_run"): ["report_center"],
            ("report_run", "delete_preset"): ["report_center"],
            ("report_run", "dry_run_version"): ["report_admin"],
            ("report_run", "execute_report_run"): ["report_center"],
            ("report_run", "get_report_page"): ["report_center"],
            ("report_run", "get_report_run"): ["report_center"],
            ("report_run", "list_presets"): ["report_center"],
            ("report_run", "list_report_runs"): ["report_center"],
            ("report_run", "report_run_metrics"): ["report_center"],
            ("report_export", "cancel_export"): ["report_center"],
            ("report_export", "download_export"): ["report_center"],
            ("report_export", "get_export"): ["report_center"],
            ("report_export", "list_exports"): ["report_center"],
            ("report_export", "request_export"): ["report_center"],
            ("report_export", "retry_export"): ["report_center"],
        }
        for (mod_name, fname), codes in expected.items():
            mod = importlib.import_module(f"app.services.{mod_name}")
            fn = getattr(mod, fname)
            assert sorted(getattr(fn, "menu_codes", [])) == sorted(codes), (
                f"{mod_name}.{fname}: {getattr(fn, 'menu_codes', None)} != {codes}"
            )
            any_of = getattr(fn, "menu_any_of", False)
            assert any_of == (len(codes) > 1), f"{mod_name}.{fname} any_of sai"
