from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def empty_state(
    title: str,
    description: str,
    action: Any = None,
    icon: str = "lucide:inbox",
    **kwargs: Any,
) -> dmc.Paper:
    """Khối trạng thái trống theo thiết kế EmptyState."""
    items: list[Any] = [
        dmc.ThemeIcon(
            DashIconify(icon=icon, width=32),
            size=64,
            radius="xl",
            color="gray",
            variant="light",
        ),
        dmc.Text(title, fw=600, size="md", c="dark", ta="center"),
        dmc.Text(description, size="sm", c="dimmed", ta="center", maw=400),
    ]
    if action is not None:
        items.append(dmc.Box(action, mt="sm"))

    return dmc.Paper(
        dmc.Stack(items, align="center", gap="xs", py="xl"),
        withBorder=True,
        radius="lg",
        p="xl",
        bg="surface-2",
        **kwargs,
    )

