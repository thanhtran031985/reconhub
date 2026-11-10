"""Task 46: dọn 2 lỗi console (tiếp task 45).

- page_header nhận component làm title thì không bọc thêm Title (h4
  trong h4 ở /history).
- handle_drag_drop_reorder không còn Output admin-col-preview-container
  (lỗi Output khi tải /report-admin ở chế độ danh sách).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _find_by_type(component: Any, type_name: str) -> list[Any]:
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


class TestPageHeaderTitle:
    def test_string_title_wrapped_once(self):
        import dash_mantine_components as dmc

        from app.ui.components.page_header import page_header

        header = page_header(title="Lịch sử", subtitle="Phụ đề")
        titles = _find_by_type(header, "Title")
        assert len(titles) == 1, len(titles)
        assert titles[0].children == "Lịch sử"
        assert titles[0].order == 4

    def test_component_title_not_wrapped(self):
        import dash_mantine_components as dmc

        from app.ui.components.page_header import page_header

        inner = dmc.Title("Lịch sử: 3 run trong tháng 11/2026", order=4, size=18, fw=600, id="history-title")
        header = page_header(title=inner, subtitle="Phụ đề")
        titles = _find_by_type(header, "Title")
        assert len(titles) == 1, len(titles)
        assert titles[0].id == "history-title"
        assert titles[0].children == "Lịch sử: 3 run trong tháng 11/2026"


class TestDragDropReorder:
    def _call(self, monkeypatch, drag_data, state=None):
        from dash.exceptions import PreventUpdate

        from app.core.context import Ctx
        from app.ui.pages.report_admin import handle_drag_drop_reorder

        ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
        monkeypatch.setattr("app.ui.pages.report_admin.get_current_ctx", lambda: ctx)
        monkeypatch.setattr(
            "app.ui.pages.report_admin.move_param", lambda *a, **k: SimpleNamespace(ok=True, data={"moved": True})
        )
        return handle_drag_drop_reorder(drag_data, state or {"version_id": 1, "rev": 0})

    def test_param_drag_returns_two_values(self, monkeypatch):
        result = self._call(
            monkeypatch, {"type": "param", "from_id": 1, "to_row": 1, "to_index": 0}
        )
        assert isinstance(result, tuple) and len(result) == 2, result
        new_state, _alert = result
        assert new_state["rev"] == 1

    def test_empty_drag_raises_prevent_update(self, monkeypatch):
        import pytest
        from dash.exceptions import PreventUpdate

        with pytest.raises(PreventUpdate):
            self._call(monkeypatch, None)

    def test_non_param_drag_raises_prevent_update(self, monkeypatch):
        import pytest
        from dash.exceptions import PreventUpdate

        with pytest.raises(PreventUpdate):
            self._call(monkeypatch, {"type": "column", "from_id": 1})
