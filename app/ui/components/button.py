from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def button_primary(
    text: str,
    id: Any = None,
    icon: str | None = None,
    loading: bool = False,
    disabled: bool = False,
    size: str = "sm",
    **kwargs: Any,
) -> dmc.Button:
    """Nút chính màu primary."""
    left_sec = DashIconify(icon=icon, width=16) if icon else None
    kw: dict[str, Any] = {
        "color": "primary",
        "variant": "filled",
        "size": size,
        "radius": "md",
        "loading": loading,
        "disabled": disabled,
        **kwargs,
    }
    if id is not None:
        kw["id"] = id
    if left_sec is not None:
        kw["leftSection"] = left_sec
    return dmc.Button(text, **kw)


def button_danger(
    text: str,
    id: Any = None,
    icon: str | None = "lucide:trash-2",
    loading: bool = False,
    disabled: bool = False,
    size: str = "sm",
    **kwargs: Any,
) -> dmc.Button:
    """Nút nguy hiểm / xóa màu crit."""
    left_sec = DashIconify(icon=icon, width=16) if icon else None
    kw: dict[str, Any] = {
        "color": "crit",
        "variant": "filled",
        "size": size,
        "radius": "md",
        "loading": loading,
        "disabled": disabled,
        **kwargs,
    }
    if id is not None:
        kw["id"] = id
    if left_sec is not None:
        kw["leftSection"] = left_sec
    return dmc.Button(text, **kw)


def button_subtle(
    text: str,
    id: Any = None,
    icon: str | None = None,
    color: str = "gray",
    size: str = "sm",
    **kwargs: Any,
) -> dmc.Button:
    """Nút phụ dạng subtle."""
    left_sec = DashIconify(icon=icon, width=16) if icon else None
    kw: dict[str, Any] = {
        "color": color,
        "variant": "subtle",
        "size": size,
        "radius": "md",
        **kwargs,
    }
    if id is not None:
        kw["id"] = id
    if left_sec is not None:
        kw["leftSection"] = left_sec
    return dmc.Button(text, **kw)
