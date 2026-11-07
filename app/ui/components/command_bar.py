from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def command_bar(
    search_id: str | None = None,
    search_placeholder: str = "Tìm kiếm...",
    search_value: str | None = None,
    filters: list[Any] | Any = None,
    actions: list[Any] | Any = None,
    id: str | None = None,
    **kwargs: Any,
) -> dmc.Paper:
    """Thanh công cụ CommandBar chuẩn Fluent Compact (tìm kiếm, bộ lọc nhanh, hành động)."""
    left_items: list[Any] = []

    if search_id:
        left_items.append(
            dmc.TextInput(
                id=search_id,
                placeholder=search_placeholder,
                value=search_value,
                leftSection=DashIconify(icon="lucide:search", width=14),
                size="xs",
                style={"width": 260, "minWidth": 160},
                styles={
                    "input": {
                        "height": "28px",
                        "minHeight": "28px",
                        "fontSize": "13px",
                    }
                },
            )
        )

    if filters:
        if left_items:
            left_items.append(
                dmc.Divider(
                    orientation="vertical",
                    h=20,
                    color="var(--line, #E0E0E0)",
                    style={"alignSelf": "center"},
                )
            )
        if isinstance(filters, list):
            left_items.extend(filters)
        else:
            left_items.append(filters)

    right_items: list[Any] = []
    if actions:
        if isinstance(actions, list):
            right_items.extend(actions)
        else:
            right_items.append(actions)

    paper_kwargs: dict[str, Any] = {
        "withBorder": True,
        "radius": "sm",
        "p": "xs",
        "mb": "xs",
        "bg": "var(--p, #FFFFFF)",
        "style": {"flexShrink": 0, "minWidth": 0},
    }
    if id is not None:
        paper_kwargs["id"] = id

    return dmc.Paper(
        dmc.Group(
            [
                dmc.Group(left_items, gap="xs", align="center", style={"flex": "1 1 auto", "minWidth": 0}),
                dmc.Group(right_items, gap="xs", align="center", style={"flexShrink": 0}),
            ],
            justify="space-between",
            align="center",
            gap="xs",
        ),
        **paper_kwargs,
        **kwargs,
    )
