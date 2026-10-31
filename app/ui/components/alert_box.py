from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify

TONE_ICONS: dict[str, str] = {
    "ok": "lucide:check-circle",
    "crit": "lucide:alert-circle",
    "warn": "lucide:alert-triangle",
    "info": "lucide:info",
}


def alert_box(
    title: str | None = None,
    message: Any = None,
    tone: str = "info",
    icon: str | None = None,
    action: Any = None,
    **kwargs: Any,
) -> dmc.Alert:
    """Khối thông báo Alert theo thiết kế Alert."""
    icon_name = icon or TONE_ICONS.get(tone, "lucide:info")
    icon_node = DashIconify(icon=icon_name, width=18)

    children_list: list[Any] = []
    if message:
        if isinstance(message, (str, int, float)):
            children_list.append(dmc.Text(str(message), size="sm"))
        else:
            children_list.append(message)
    if action:
        children_list.append(dmc.Box(action, mt="xs"))

    return dmc.Alert(
        title=title,
        color=tone,
        icon=icon_node,
        radius="md",
        children=dmc.Stack(children_list, gap="xs")
        if len(children_list) > 1
        else (children_list[0] if children_list else None),
        **kwargs,
    )
