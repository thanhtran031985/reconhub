from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def kpi_card(
    label: str,
    value: Any,
    tone: str = "primary",
    meta: str | None = None,
    icon: str | None = None,
    size: str = "md",
) -> dmc.Paper:
    """Thẻ chỉ số theo thiết kế KpiCard."""
    val_size = "xl" if size == "md" else "lg"
    icon_node = (
        dmc.ThemeIcon(
            DashIconify(icon=icon, width=20),
            color=tone,
            variant="light",
            radius="md",
            size="lg",
        )
        if icon
        else None
    )

    header_children = [
        dmc.Text(label, size="sm", c="dimmed", fw=500),
    ]
    if icon_node:
        header = dmc.Group(
            [header_children[0], icon_node],
            justify="space-between",
            align="flex-start",
        )
    else:
        header = header_children[0]

    content_children = [
        header,
        dmc.Text(str(value), size=val_size, fw=700, c=tone if tone in ("crit", "warn") else "dark", mt="xs"),
    ]
    if meta:
        content_children.append(dmc.Text(meta, size="xs", c="dimmed", mt=4))

    return dmc.Paper(
        dmc.Stack(content_children, gap=0),
        withBorder=True,
        p="md" if size == "md" else "sm",
        radius="lg",
        shadow="xs",
    )
