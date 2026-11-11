"""Task 45: dọn khoảng trắng dưới trang + 3 lỗi console.

- AppShellMain height 100vh (không còn dải trắng 44px dưới main).
- render_param_control không còn truyền value=None (DATE/DATE_RANGE/
  SELECT/TEXT/NUMBER -> "", MULTI_SELECT -> []).
- handle_menu_search bỏ Input pathname (xem test_ui_shell.py đã cập nhật
  + Playwright check-45: không còn ReferenceError lúc tải trang).
"""

from __future__ import annotations

from typing import Any


def _find_by_type(component: Any, type_name: str) -> list[Any]:
    """Tìm mọi component theo tên class trong cây (children đệ quy)."""
    found: list[Any] = []
    if type(component).__name__ == type_name:
        found.append(component)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            found.extend(_find_by_type(child, type_name))
    elif children is not None:
        found.extend(_find_by_type(children, type_name))
    return found


class TestShellMainHeight:
    def test_main_touches_viewport_bottom(self, monkeypatch):
        from app.ui.layout.shell import render_app_shell

        monkeypatch.setattr("app.ui.layout.shell.get_current_ctx", lambda: None)
        tree = render_app_shell("/report-runs", False)
        mains = _find_by_type(tree, "AppShellMain")
        assert mains, "không tìm thấy AppShellMain"
        height = (mains[0].style or {}).get("height")
        assert height == "100vh", height
        assert "calc(100vh - 44px)" not in str(mains[0].style)


class TestParamControlNoNone:
    def _param(self, code: str, control_type: str, data_type: str = "STRING", value: Any = None) -> dict[str, Any]:
        return {"code": code, "label": "Thử", "data_type": data_type, "control_type": control_type, "value": value}

    def test_date_range_empty_is_empty_string(self):
        from app.ui.components.report_widgets import render_param_control

        comp = render_param_control(self._param("p_range", "DATE_RANGE", "DATE"), None)
        dates = _find_by_type(comp, "DateInput")
        assert len(dates) == 2
        assert all(d.value == "" for d in dates), [d.value for d in dates]

    def test_date_empty_is_empty_string(self):
        from app.ui.components.report_widgets import render_param_control

        comp = render_param_control(self._param("p_from", "DATE", "DATE"), None)
        assert comp.value == ""

    def test_select_empty_is_empty_string(self):
        from app.ui.components.report_widgets import render_param_control

        comp = render_param_control(self._param("p_org", "SELECT"), [{"label": "HN", "value": "HN"}])
        assert comp.value == ""

    def test_multi_select_empty_is_empty_list(self):
        from app.ui.components.report_widgets import render_param_control

        comp = render_param_control(self._param("p_org", "MULTI_SELECT"), [{"label": "HN", "value": "HN"}])
        assert comp.value == []

    def test_text_and_number_empty_is_empty_string(self):
        from app.ui.components.report_widgets import render_param_control

        assert render_param_control(self._param("p_app", "TEXT"), None).value == ""
        assert render_param_control(self._param("p_n", "NUMBER", "NUMBER"), None).value == ""

    def test_values_kept_when_present(self):
        from app.ui.components.report_widgets import render_param_control

        assert render_param_control(self._param("p_from", "DATE", "DATE", "2026-11-01"), None).value == "2026-11-01"
        comp = render_param_control(self._param("p_org", "SELECT", "STRING", "HN"), [{"label": "HN", "value": "HN"}])
        assert comp.value == "HN"
        comp = render_param_control(
            self._param("p_range", "DATE_RANGE", "DATE", {"from": "2026-11-01", "to": "2026-11-05"}), None
        )
        dates = _find_by_type(comp, "DateInput")
        assert [d.value for d in dates] == ["2026-11-01", "2026-11-05"]


class TestRunsFilterDatesNoNone:
    def test_command_bar_search_defaults_to_empty_string(self):
        from app.ui.components.command_bar import command_bar

        bar = command_bar(search_id="test-search")
        inputs = _find_by_type(bar, "TextInput")
        assert inputs and all(i.value == "" for i in inputs), [i.value for i in inputs]

    def test_refresh_returns_empty_string_for_blank_dates(self, monkeypatch):
        from types import SimpleNamespace

        from app.core.context import Ctx
        from app.ui.pages.report_runs import handle_runs_refresh

        ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
        monkeypatch.setattr("app.ui.pages.report_runs.get_current_ctx", lambda: ctx)
        monkeypatch.setattr("app.ui.pages.report_runs._load_page_data", lambda *a, **k: ([], 0, {}))
        monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id=None))
        out = handle_runs_refresh(1, "50", None, None, "all", "", "all", None, None, 1)
        assert out[4] == "" and out[5] == "", out[4:6]

    def test_clear_returns_empty_string_for_dates(self, monkeypatch):
        from types import SimpleNamespace

        from app.core.context import Ctx
        from app.ui.pages.report_runs import handle_runs_refresh

        ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
        monkeypatch.setattr("app.ui.pages.report_runs.get_current_ctx", lambda: ctx)
        monkeypatch.setattr("app.ui.pages.report_runs._load_page_data", lambda *a, **k: ([], 0, {}))
        monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id="report-runs-clear-btn"))
        out = handle_runs_refresh(1, "50", "2026-11-01", "2026-11-05", "FIN", "bc", "admin", "FAILED", 1, 1)
        assert out[4] == "" and out[5] == "" and out[6] == "all" and out[7] == ""
        assert out[9] == "all", out[9]  # task 58: "Xóa lọc" reset cả lọc trạng thái
