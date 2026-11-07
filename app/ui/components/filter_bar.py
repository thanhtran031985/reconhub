from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def filter_bar(
    children: list[Any] | Any,
    actions: list[Any] | Any = None,
    id: str | None = None,
    **kwargs: Any,
) -> dmc.Paper:
    """Thanh bộ lọc FilterBar chuẩn Fluent Compact (lưới lọc linh hoạt + hành động áp dụng/đặt lại)."""
    filter_elements: list[Any] = []
    if isinstance(children, list):
        filter_elements.extend(children)
    else:
        filter_elements.append(children)

    action_elements: list[Any] = []
    if actions:
        if isinstance(actions, list):
            action_elements.extend(actions)
        else:
            action_elements.append(actions)

    body = dmc.Group(
        [
            dmc.Group(filter_elements, gap="xs", align="flex-end", style={"flex": "1 1 auto", "minWidth": 0}),
            dmc.Group(action_elements, gap="xs", align="flex-end", style={"flexShrink": 0}),
        ],
        justify="space-between",
        align="flex-end",
        gap="xs",
    )

    paper_kwargs: dict[str, Any] = {
        "withBorder": True,
        "radius": "sm",
        "p": "xs",
        "mb": "xs",
        "bg": "var(--p2, #FAFAFA)",
        "style": {"flexShrink": 0, "minWidth": 0},
    }
    if id is not None:
        paper_kwargs["id"] = id

    return dmc.Paper(
        body,
        **paper_kwargs,
        **kwargs,
    )
