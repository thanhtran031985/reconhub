"""Tests task 74 — thêm template vào báo cáo có sẵn (tab 1 wizard).

- Service create_template dưới báo cáo có sẵn: tạo template thứ 2
  (badge /reports 1 -> 2), trùng mã trong cùng báo cáo -> CONFLICT,
  cùng mã ở báo cáo khác -> OK, template mới có version 1 DRAFT.
- Wizard: ô "Mã template" thành Select có search (chỉ khi đang sửa),
  chọn mã khác -> wizard chuyển sang template đó, ô "Tên template"
  disable và hiện tên theo mã; nút "Tạo mới template" mở modal
  (Mã/Tên/Thứ tự) -> lưu gọi create_template, wizard chuyển sang
  template mới; đường lưu bước 1 với report_id có sẵn nhưng chưa có
  template_id thì chỉ tạo template (bỏ qua create_report).
"""

from __future__ import annotations

import dash
import pytest
from dash.exceptions import PreventUpdate

from app.schemas.errors import ErrorCode
from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _state_for(template_id: int, version_id: int, step: int = 1) -> dict:
    return {
        "mode": "wizard",
        "report_id": None,
        "template_id": template_id,
        "version_id": version_id,
        "version_status": "DRAFT",
        "step": step,
        "max_step": 1,
        "analyzed": False,
        "dry_run_ok": False,
        "editing_param_id": None,
    }


def _draft_state(run_env) -> dict:
    """State đang sửa template DRAFT1 (template id 3, version id 3)."""
    state = _state_for(int(run_env["draft_version_id"]), int(run_env["draft_version_id"]))
    state["report_id"] = int(run_env["report_id"])
    return state


def _make_second_template(run_env, admin_ctx, code: str = "NEW1") -> dict:
    from app.services.report_template import create_template

    res = create_template(
        admin_ctx,
        int(run_env["report_id"]),
        {"code": code, "name": f"Mẫu {code}", "display_order": 20},
    )
    assert res.ok, res.message
    return dict(res.data)


class TestCreateTemplateService:
    def test_create_second_template_same_report(self, run_env, admin_ctx):
        from app.services.report_template import list_templates

        data = _make_second_template(run_env, admin_ctx, "TPL2")
        versions = data.get("versions") or []
        assert versions and versions[0]["status"] == "DRAFT"
        assert data.get("active_version_id") is None
        tpl_res = list_templates(admin_ctx, int(run_env["report_id"]))
        assert tpl_res.ok
        # list_templates xếp theo (DISPLAY_ORDER, CODE): cả 3 mẫu có sẵn
        # đều order 10 nên xếp theo mã ABC, TPL2 order 20 xếp cuối.
        assert [t["code"] for t in tpl_res.data] == ["DRAFT1", "SQL1", "VIEW1", "TPL2"]

    def test_create_template_duplicate_code_same_report_conflict(self, run_env, admin_ctx):
        from app.services.report_template import create_template

        _make_second_template(run_env, admin_ctx, "TPL2")
        res = create_template(
            admin_ctx,
            int(run_env["report_id"]),
            {"code": "TPL2", "name": "Trùng mã", "display_order": 30},
        )
        assert not res.ok
        assert res.code == ErrorCode.CONFLICT
        assert "đã tồn tại" in (res.message or "")

    def test_create_template_same_code_other_report_ok(self, run_env, admin_ctx):
        from app.services.report import create_report
        from app.services.report_template import create_template, list_templates

        rep = create_report(
            admin_ctx,
            {"code": "FIN_REV2", "name": "Doanh thu 2", "category_code": "FIN", "owner": "admin"},
        )
        assert rep.ok, rep.message
        res = create_template(
            admin_ctx,
            int(rep.data["id"]),
            {"code": "SQL1", "name": "Cùng mã khác báo cáo", "display_order": 10},
        )
        assert res.ok, res.message
        tpl_res = list_templates(admin_ctx, int(rep.data["id"]))
        assert [t["code"] for t in tpl_res.data] == ["SQL1"]


class TestTplSwitch:
    def test_switch_changes_template(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        new_tpl = _make_second_template(run_env, admin_ctx, "NEW1")
        new_version_id = int((new_tpl.get("versions") or [{}])[0].get("id"))
        state = _draft_state(run_env)
        new_state, alert = page.handle_tpl_switch(str(new_tpl["id"]), state)
        assert int(new_state["template_id"]) == int(new_tpl["id"])
        assert int(new_state["version_id"]) == new_version_id
        assert int(new_state["step"]) == 1
        assert alert is None

    def test_switch_same_template_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        with pytest.raises(PreventUpdate):
            page.handle_tpl_switch(str(state["template_id"]), state)

    def test_switch_empty_or_garbage_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        for bad in ("", "abc", None):
            with pytest.raises(PreventUpdate):
                page.handle_tpl_switch(bad, state)

    def test_switch_no_draft_bumps_state_and_errors(self, run_env, admin_ctx, monkeypatch):
        """VIEW1 chỉ có version ACTIVE -> không sửa được: báo lỗi và
        bump rev để wizard vẽ lại, Select quay về template đang sửa."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        new_state, alert = page.handle_tpl_switch(str(run_env["view_template_id"]), state)
        assert int(new_state["template_id"]) == int(state["template_id"])
        assert int(new_state.get("rev") or 0) == 1
        assert "không có version DRAFT" in _dump(alert)


class TestNewTemplateModal:
    def test_save_success_switches_wizard(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        opened, new_state, alert, modal_alert = page.handle_new_template_save(1, state, "TPL2", "Template 2", 20)
        assert opened is False
        assert modal_alert is None
        assert alert is not None and "Đã tạo template" in _dump(alert)
        assert int(new_state["template_id"]) != int(state["template_id"])
        assert int(new_state["version_id"]) > 0
        assert int(new_state["step"]) == 1
        tpl_res = list_templates(admin_ctx, int(run_env["report_id"]))
        assert [t["code"] for t in tpl_res.data] == ["DRAFT1", "SQL1", "VIEW1", "TPL2"]

    def test_save_duplicate_keeps_modal_open(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        _make_second_template(run_env, admin_ctx, "TPL2")
        opened, new_state, alert, modal_alert = page.handle_new_template_save(1, state, "TPL2", "Template 2", 20)
        assert opened is True
        assert new_state is dash.no_update
        assert modal_alert is not None and "đã tồn tại" in _dump(modal_alert)

    def test_save_empty_code_errors(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        opened, new_state, alert, modal_alert = page.handle_new_template_save(1, state, "", "Thiếu mã", 10)
        assert opened is True
        assert new_state is dash.no_update
        assert modal_alert is not None

    def test_save_without_report_errors(self, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = {
            "mode": "wizard",
            "report_id": None,
            "template_id": None,
            "version_id": None,
            "step": 1,
            "max_step": 1,
        }
        opened, new_state, alert, modal_alert = page.handle_new_template_save(1, state, "TPL9", "Không có báo cáo", 10)
        assert opened is True
        assert new_state is dash.no_update
        assert modal_alert is not None

    def test_save_no_click_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        with pytest.raises(PreventUpdate):
            page.handle_new_template_save(None, state, "TPL2", "Template 2", 20)


class TestSaveStep1ReportOnly:
    def test_report_only_creates_template_not_report(self, run_env, admin_ctx, monkeypatch):
        """State có report_id nhưng chưa có template_id -> lưu bước 1
        chỉ gọi create_template, bỏ qua create_report (plan bước 3)."""
        import app.ui.pages.report_admin as page
        from app.services.report import get_report, list_reports
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        rep = get_report(admin_ctx, int(run_env["report_id"])).data
        reports_before = list_reports(admin_ctx).data
        state = {
            "mode": "wizard",
            "report_id": int(run_env["report_id"]),
            "template_id": None,
            "version_id": None,
            "version_status": "DRAFT",
            "step": 1,
            "max_step": 1,
            "analyzed": False,
            "dry_run_ok": False,
            "editing_param_id": None,
        }
        new_state, alert = page.handle_save_step1(
            1,
            state,
            rep["code"],
            rep["name"],
            rep["category_code"],
            rep["owner"],
            rep["description"],
            rep["is_visible"],
            rep["default_favorite"],
            "BRANCH1",
            "Branch 1",
            5,
            300,
            100,
            1000000,
        )
        assert alert is None or "Đã lưu" in _dump(alert)
        assert int(new_state["step"]) == 2
        assert int(new_state["template_id"]) > 0
        assert int(new_state["version_id"]) > 0
        assert len(list_reports(admin_ctx).data) == len(reports_before)
        tpl_res = list_templates(admin_ctx, int(run_env["report_id"]))
        # BRANCH1 order 5 xếp đầu, còn lại order 10 xếp theo mã ABC.
        assert [t["code"] for t in tpl_res.data] == ["BRANCH1", "DRAFT1", "SQL1", "VIEW1"]


class TestRenderStep1:
    def test_editing_shows_tpl_select_and_new_button(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        comp = page.render_step_content(1, state)
        text = _dump(comp)
        assert "Tạo mới template" in text
        select = _find_by_id(comp, "admin-s1-tpl-code")
        assert select is not None
        assert type(select).__name__ == "Select"
        assert getattr(select, "searchable", False) is True
        assert str(getattr(select, "value", "")) == str(state["template_id"])
        labels = [str(d.get("label", "")) for d in (getattr(select, "data", None) or [])]
        assert any("SQL1" in label for label in labels)
        assert any("VIEW1" in label for label in labels)
        assert any("DRAFT1" in label for label in labels)
        name_input = _find_by_id(comp, "admin-s1-tpl-name")
        assert name_input is not None
        assert getattr(name_input, "disabled", False) is True
        assert str(getattr(name_input, "value", "")) == "Mẫu DRAFT1"

    def test_new_keeps_tpl_textbox(self):
        import app.ui.pages.report_admin as page

        comp = page.render_step_content(1, _state_for(None, None))
        # Chưa có báo cáo nên không có nút tạo mới (chỉ có dòng chữ trong
        # alert giới thiệu tính năng) và Mã template vẫn là textbox.
        assert _find_by_id(comp, "admin-s1-new-tpl-btn") is None
        code_input = _find_by_id(comp, "admin-s1-tpl-code")
        assert code_input is not None
        assert type(code_input).__name__ == "TextInput"
        name_input = _find_by_id(comp, "admin-s1-tpl-name")
        assert name_input is not None
        assert not getattr(name_input, "disabled", False)
