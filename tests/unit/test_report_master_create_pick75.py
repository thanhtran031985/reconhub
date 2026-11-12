"""Tests task 75 — tạo mã báo cáo riêng + đăng ký template chọn mã báo cáo.

- Modal "Tạo mã báo cáo" trên /reports: lưu gọi create_report (service
  đã có), thành công -> đóng modal, toast, hub làm mới với badge
  0 template; trùng mã báo cáo -> CONFLICT, modal ở lại mở + lỗi;
  mã sai định dạng / thiếu mã -> lỗi validation, modal ở lại mở.
- Wizard bước 1 (chỉ luồng tạo mới): ô "Báo cáo *" là Select có search
  (options = list_reports + "Báo cáo mới" mặc định); chọn báo cáo có
  sẵn -> state nhận report_id, các ô báo cáo khóa lại hiện đúng giá
  trị, chỉ ô template nhập được; chọn lại "Báo cáo mới" -> mở lại
  các ô; lưu khi đã chọn báo cáo chỉ tạo template (nhánh D4 task 74),
  không tạo thêm báo cáo.
- Service create_report trùng mã -> CONFLICT đã có test ở
  test_reporting_services.py (không lặp lại ở đây).
"""

from __future__ import annotations

from types import SimpleNamespace

import dash
import pytest
from dash.exceptions import PreventUpdate

from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_page_reports import reports_env
from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx", "reports_env"]


def _fresh_state() -> dict:
    return {
        "mode": "wizard",
        "report_id": None,
        "template_id": None,
        "version_id": None,
        "version_status": "DRAFT",
        "step": 1,
        "max_step": 1,
        "analyzed": False,
        "dry_run_ok": False,
        "editing_param_id": None,
    }


def _store_reports(admin_ctx) -> list[dict]:
    """Dữ liệu reports-store như hub đang giữ (kèm template_count)."""
    from app.services.report import list_reports
    from app.services.report_template import list_templates

    out = []
    for r in list_reports(admin_ctx).data:
        t_res = list_templates(admin_ctx, int(r["id"]))
        count = len(t_res.data) if t_res.ok and isinstance(t_res.data, list) else 0
        out.append({**r, "template_count": count})
    return out


class TestNewReportModalSave:
    def test_save_success_adds_report_badge_0(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        store = _store_reports(admin_ctx)
        before = len(store)
        opened, modal_alert, new_store, sections, meta, toast = page.handle_new_report_save(
            1, "NEW_RPT", "Báo cáo mới", "FINANCE", "FIN", "Mô tả mới", store, "", "all", False
        )
        assert opened is False
        assert modal_alert is None
        assert toast is not None and "Đã tạo mã báo cáo NEW_RPT" in _dump(toast)
        assert len(new_store) == before + 1
        assert new_store[-1]["code"] == "NEW_RPT"
        assert int(new_store[-1]["template_count"]) == 0
        assert "NEW_RPT" in _dump(sections)
        assert meta == f"{before + 1} báo cáo"
        from app.services.report import list_reports

        assert any(r["code"] == "NEW_RPT" for r in list_reports(admin_ctx).data)

    def test_save_duplicate_keeps_modal_open(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        store = _store_reports(admin_ctx)
        opened, modal_alert, new_store, sections, meta, toast = page.handle_new_report_save(
            1, "FIN_REVENUE", "Trùng mã", "FINANCE", "FIN", "", store, "", "all", False
        )
        assert opened is True
        assert new_store is dash.no_update
        assert modal_alert is not None and "đã tồn tại" in _dump(modal_alert)

    def test_save_bad_code_keeps_modal_open(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        store = _store_reports(admin_ctx)
        for bad_code in ("", "fin-revenue"):
            opened, modal_alert, new_store, _s, _m, _t = page.handle_new_report_save(
                1, bad_code, "Sai mã", "FINANCE", "FIN", "", store, "", "all", False
            )
            assert opened is True
            assert new_store is dash.no_update
            assert modal_alert is not None

    def test_save_no_click_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        with pytest.raises(PreventUpdate):
            page.handle_new_report_save(None, "NEW_RPT", "Báo cáo mới", "FINANCE", "FIN", "", [], "", "all", False)

    def test_save_no_ctx_no_update(self, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: None)
        with pytest.raises(PreventUpdate):
            page.handle_new_report_save(1, "NEW_RPT", "Báo cáo mới", "FINANCE", "FIN", "", [], "", "all", False)


class TestNewReportModalToggle:
    def test_toggle_open_clears_form(self, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[{"prop_id": "x.n_clicks"}], triggered_id="reports-new-report-btn"),
        )
        out = page.handle_new_report_modal_toggle(1, None)
        assert out == (True, "", "", "FINANCE", "", "", None)

    def test_toggle_cancel_closes(self, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[{"prop_id": "x.n_clicks"}], triggered_id="reports-new-report-cancel"),
        )
        opened, *_rest = page.handle_new_report_modal_toggle(None, 1)
        assert opened is False

    def test_toggle_no_click_no_update(self, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered=[], triggered_id=None),
        )
        out = page.handle_new_report_modal_toggle(None, None)
        assert all(v is dash.no_update for v in out)


class TestReportPick:
    def test_pick_existing_report(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        new_state, alert = page.handle_report_pick(str(run_env["report_id"]), state)
        assert int(new_state["report_id"]) == int(run_env["report_id"])
        assert new_state.get("template_id") is None
        assert int(new_state["step"]) == 1
        assert alert is None

    def test_pick_new_after_picked_clears(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        state["report_id"] = int(run_env["report_id"])
        new_state, alert = page.handle_report_pick("new", state)
        assert new_state.get("report_id") is None
        assert alert is None

    def test_pick_new_when_already_new_no_update(self, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        with pytest.raises(PreventUpdate):
            page.handle_report_pick("new", _fresh_state())

    def test_pick_same_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        state["report_id"] = int(run_env["report_id"])
        with pytest.raises(PreventUpdate):
            page.handle_report_pick(str(run_env["report_id"]), state)

    def test_pick_empty_or_garbage_no_update(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        for bad in ("", None, "abc"):
            with pytest.raises(PreventUpdate):
                page.handle_report_pick(bad, state)

    def test_pick_missing_report_bumps_and_errors(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        new_state, alert = page.handle_report_pick("999999", state)
        assert new_state.get("report_id") is None
        assert int(new_state.get("rev") or 0) == 1
        assert "Không tìm thấy báo cáo" in _dump(alert)

    def test_pick_no_state_no_update(self, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        with pytest.raises(PreventUpdate):
            page.handle_report_pick("1", None)


class TestPickThenSaveStep1:
    def test_picked_report_save_creates_template_only(self, run_env, admin_ctx, monkeypatch):
        """Chọn báo cáo ở Select rồi lưu bước 1 -> chỉ tạo template,
        không tạo thêm báo cáo (nhánh D4 task 74, đi qua handler pick)."""
        import app.ui.pages.report_admin as page
        from app.services.report import get_report, list_reports
        from app.services.report_template import list_templates

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        rep = get_report(admin_ctx, int(run_env["report_id"])).data
        reports_before = list_reports(admin_ctx).data
        state, alert = page.handle_report_pick(str(run_env["report_id"]), _fresh_state())
        assert alert is None
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
            "PICK1",
            "Pick 1",
            5,
            300,
            100,
            1000000,
        )
        assert alert is None or "Đã lưu" in _dump(alert)
        assert int(new_state["step"]) == 2
        assert int(new_state["template_id"]) > 0
        assert len(list_reports(admin_ctx).data) == len(reports_before)
        tpl_res = list_templates(admin_ctx, int(run_env["report_id"]))
        assert "PICK1" in [t["code"] for t in tpl_res.data]


class TestRenderStep1ReportPick:
    def test_new_flow_shows_report_pick_select(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        comp = page.render_step_content(1, _fresh_state())
        select = _find_by_id(comp, "admin-s1-report-pick")
        assert select is not None
        assert type(select).__name__ == "Select"
        assert getattr(select, "searchable", False) is True
        assert str(getattr(select, "value", "")) == "new"
        labels = [str(d.get("label", "")) for d in (getattr(select, "data", None) or [])]
        assert any("Báo cáo mới" in label for label in labels)
        assert any("FIN_REVENUE" in label for label in labels)
        code_input = _find_by_id(comp, "admin-s1-report-code")
        assert code_input is not None
        assert not getattr(code_input, "disabled", False)
        # Luồng mới chưa có nút tạo template (chỉ có khi đang sửa).
        assert _find_by_id(comp, "admin-s1-new-tpl-btn") is None

    def test_picked_report_locks_report_fields(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        state["report_id"] = int(run_env["report_id"])
        comp = page.render_step_content(1, state)
        select = _find_by_id(comp, "admin-s1-report-pick")
        assert select is not None
        assert str(getattr(select, "value", "")) == str(run_env["report_id"])
        code_input = _find_by_id(comp, "admin-s1-report-code")
        assert code_input is not None
        assert str(getattr(code_input, "value", "")) == "FIN_REVENUE"
        assert getattr(code_input, "disabled", False) is True
        name_input = _find_by_id(comp, "admin-s1-report-name")
        assert name_input is not None
        assert getattr(name_input, "disabled", False) is True
        category = _find_by_id(comp, "admin-s1-category")
        assert category is not None
        assert getattr(category, "disabled", False) is True
        owner = _find_by_id(comp, "admin-s1-owner")
        assert owner is not None
        assert getattr(owner, "disabled", False) is True
        description = _find_by_id(comp, "admin-s1-description")
        assert description is not None
        assert getattr(description, "disabled", False) is True
        # Chỉ ô template nhập được.
        tpl_code = _find_by_id(comp, "admin-s1-tpl-code")
        assert tpl_code is not None
        assert not getattr(tpl_code, "disabled", False)

    def test_editing_has_no_report_pick(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _fresh_state()
        state["report_id"] = int(run_env["report_id"])
        state["template_id"] = int(run_env["draft_version_id"])
        state["version_id"] = int(run_env["draft_version_id"])
        comp = page.render_step_content(1, state)
        assert _find_by_id(comp, "admin-s1-report-pick") is None

    def test_new_flow_without_ctx_only_new_option(self):
        import app.ui.pages.report_admin as page

        comp = page.render_step_content(1, _fresh_state())
        select = _find_by_id(comp, "admin-s1-report-pick")
        assert select is not None
        assert str(getattr(select, "value", "")) == "new"
        data = getattr(select, "data", None) or []
        assert [str(d.get("value", "")) for d in data] == ["new"]


class TestReportsHubModal:
    def test_layout_admin_has_create_report_button_and_modal(self, reports_env, admin_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        layout = page.layout()
        text = _dump(layout)
        assert "Tạo mã báo cáo" in text
        assert _find_by_id(layout, "reports-new-report-btn") is not None
        assert _find_by_id(layout, "reports-new-report-modal") is not None
        code = _find_by_id(layout, "reports-new-report-code")
        assert code is not None and type(code).__name__ == "TextInput"
        assert _find_by_id(layout, "reports-new-report-name") is not None
        category = _find_by_id(layout, "reports-new-report-category")
        assert category is not None and type(category).__name__ == "Select"
        assert _find_by_id(layout, "reports-new-report-owner") is not None
        assert _find_by_id(layout, "reports-new-report-description") is not None
        assert _find_by_id(layout, "reports-new-report-save") is not None
        assert _find_by_id(layout, "reports-new-report-cancel") is not None

    def test_layout_operator_no_create_report_button(self, reports_env, operator_ctx, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        layout = page.layout()
        text = _dump(layout)
        assert "Tạo mã báo cáo" not in text
        assert _find_by_id(layout, "reports-new-report-btn") is None
        assert _find_by_id(layout, "reports-new-report-modal") is None
