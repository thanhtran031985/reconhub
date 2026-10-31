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
    return dmc.Button(
        text,
        id=id,
        color="primary",
        variant="filled",
        size=size,
        radius="md",
        leftSection=left_sec,
        loading=loading,
        disabled=disabled,
        **kwargs,
    )


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
    return dmc.Button(
        text,
        id=id,
        color="crit",
        variant="filled",
        size=size,
        radius="md",
        leftSection=left_sec,
        loading=loading,
        disabled=disabled,
        **kwargs,
    )


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
    return dmc.Button(
        text,
        id=id,
        color=color,
        variant="subtle",
        size=size,
        radius="md",
        leftSection=left_sec,
        **kwargs,
    )

