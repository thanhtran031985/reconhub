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
