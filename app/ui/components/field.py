from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash import html


def form_field(
    input_component: Any,
    label: str | None = None,
    hint: str | None = None,
    error: str | None = None,
    required: bool = False,
    field_id: str | None = None,
) -> Any:
    """Wrapper ô nhập liệu bổ sung label, hint, error và thuộc tính trợ năng aria-describedby."""
    fid = field_id or getattr(input_component, "id", None)
    if isinstance(fid, dict):
        fid = str(fid.get("type", "field")) + "-" + str(fid.get("index", ""))

    error_id = f"{fid}-error" if fid else None
    hint_id = f"{fid}-hint" if fid else None

    # Áp dụng các thuộc tính lên input component nếu hỗ trợ. Không dùng
    # hasattr để kiểm tra: với component Dash, một prop chưa được set thì
    # hasattr trả False dù prop đó hoàn toàn hợp lệ, nên label, hint và
    # dấu * bắt buộc từng bị rớt mất (drawer /users là nạn nhân). Kiểm tra
    # thẳng trong available_properties mới đúng.
    supported = set(getattr(input_component, "available_properties", []) or [])
    if label is not None and "label" in supported:
        input_component.label = label
    if hint is not None and "description" in supported:
        input_component.description = hint
    if "withAsterisk" in supported:
        input_component.withAsterisk = required

    if error:
        if "error" in supported:
            input_component.error = error
        if error_id:
            input_component.aria_describedby = error_id
            setattr(input_component, "aria-describedby", error_id)
    else:
        if hint and hint_id:
            input_component.aria_describedby = hint_id
            setattr(input_component, "aria-describedby", hint_id)

    return dmc.Box(
        children=[
            input_component,
            html.Div(
                id=error_id,
                children=error,
                style={"display": "none"} if not error else {"display": "none"},
            )
            if error_id and error
            else html.Div(),
        ],
        mb="sm",
    )
