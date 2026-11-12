"""Tests task 77 — viewer: chuyển tab template đổi form + xóa kết quả cũ.

- Layout viewer 2 template ACTIVE hiện đủ 2 tab (SQL1 + VIEW1).
- Handler switch: đổi sang template 2 -> form mới (tham số của template 2)
  + version-store mới + run-store rỗng + page 1 + hết lỗi; cùng template /
  giá trị rỗng -> PreventUpdate; template không có ACTIVE version -> lỗi,
  giữ nguyên form cũ (slot None = không đổi).
"""

from __future__ import annotations

import dash
import pytest
from dash.exceptions import PreventUpdate

from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import admin_ctx, operator_ctx, run_env

__all__ = ["run_env", "admin_ctx", "operator_ctx"]


def _stores(env, ctx):
    """(templates-store, version-store) như layout() dựng cho template đầu."""
    from app.services.report_template import get_version, list_templates

    templates = list_templates(ctx, env["report_id"]).data
    first = [t for t in templates if t.get("active_version_id")][0]
    version = get_version(ctx, int(first["active_version_id"])).data
    return templates, version


def _old_run_store(env):
    """Run-store cũ của template 1 (SQL1) — đổi tab phải xóa."""
    return {
        "run_id": 999,
        "template_id": env["sql_template_id"],
        "report_id": env["report_id"],
        "version_id": env["sql_version_id"],
        "total": 3,
        "total_pages": 1,
        "values": {"p_org": "HN"},
    }


class TestLayoutTwoTabs:
    def test_layout_shows_two_template_tabs(self, run_env, operator_ctx, monkeypatch):
        """Viewer 2 template ACTIVE hiện đủ 2 tab, tab đầu là SQL1."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout(run_env["report_id"])
        tabs = _find_by_id(tree, "viewer-tabs")
        assert tabs is not None
        tab_list = tabs.children[0]
        values = [t.value for t in tab_list.children]
        assert values == [str(run_env["sql_template_id"]), str(run_env["view_template_id"])]
        assert tabs.value == str(run_env["sql_template_id"])


class TestTabSwitchHandler:
    def test_switch_to_second_template_rebuilds_form(self, run_env, admin_ctx, monkeypatch):
        """Đổi sang VIEW1: form có tham số riêng của VIEW1, version-store
        mới, run-store rỗng, page 1, hết lỗi."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        templates, version = _stores(run_env, admin_ctx)
        assert int(version["template_id"]) == run_env["sql_template_id"]
        form, new_version, new_run, new_page, error = page.handle_viewer_tab_switch(
            str(run_env["view_template_id"]),
            version,
            templates,
            _old_run_store(run_env),
        )
        assert "Số tiền tối thiểu" in _dump(form)
        assert int(new_version["template_id"]) == run_env["view_template_id"]
        assert int(new_version["id"]) == run_env["view_version_id"]
        assert new_run == {}
        assert new_page == 1
        assert error == ""

    def test_switch_same_template_prevents_update(self, run_env, admin_ctx, monkeypatch):
        """Chọn lại đúng template hiện tại -> không làm gì."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        templates, version = _stores(run_env, admin_ctx)
        with pytest.raises(PreventUpdate):
            page.handle_viewer_tab_switch(
                str(run_env["sql_template_id"]),
                version,
                templates,
                _old_run_store(run_env),
            )

    def test_switch_empty_value_prevents_update(self, run_env, admin_ctx, monkeypatch):
        """Giá trị rỗng / None -> không làm gì."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        templates, version = _stores(run_env, admin_ctx)
        for bad in (None, ""):
            with pytest.raises(PreventUpdate):
                page.handle_viewer_tab_switch(
                    bad,
                    version,
                    templates,
                    _old_run_store(run_env),
                )

    def test_switch_template_without_active_version_errors_and_keeps_form(self, run_env, admin_ctx, monkeypatch):
        """Template đích không có ACTIVE version -> báo lỗi, giữ form cũ
        (các slot None = không đổi)."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        templates, version = _stores(run_env, admin_ctx)
        draft = [t for t in templates if t["code"] == "DRAFT1"][0]
        assert draft.get("active_version_id") is None
        form, new_version, new_run, new_page, error = page.handle_viewer_tab_switch(
            str(draft["id"]),
            version,
            templates,
            _old_run_store(run_env),
        )
        assert form is None and new_version is None and new_run is None and new_page is None
        assert "ACTIVE" in _dump(error)

    def test_switch_callback_maps_no_update(self, run_env, admin_ctx, monkeypatch):
        """Callback bọc handler: trường hợp lỗi -> form/version/run/page
        là dash.no_update, chỉ error đổi."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        templates, version = _stores(run_env, admin_ctx)
        draft = [t for t in templates if t["code"] == "DRAFT1"][0]
        out = page.handle_viewer_tab_switch_click(
            str(draft["id"]),
            version,
            templates,
            _old_run_store(run_env),
        )
        assert out[0] is dash.no_update
        assert out[1] is dash.no_update
        assert out[2] is dash.no_update
        assert out[3] is dash.no_update
        assert "ACTIVE" in _dump(out[4])
