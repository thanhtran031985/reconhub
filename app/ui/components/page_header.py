from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def page_header(
    title: str,
    subtitle: str | None = None,
    actions: Any = None,
    breadcrumbs: list[dict[str, str]] | None = None,
    id: str | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Component tiêu đề trang chuẩn 1 dòng Fluent Compact (Title 18px + subtitle 12px dimmed + actions)."""
    title_elements: list[Any] = [
        dmc.Title(title, order=4, size=18, fw=600, style={"lineHeight": 1.3, "whiteSpace": "nowrap"}),
    ]

    if subtitle:
        title_elements.append(
            dmc.Text(
                subtitle,
                size="xs",
                c="dimmed",
                style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            )
        )

    left_group = dmc.Group(
        title_elements,
        gap="xs",
        align="baseline",
        style={"minWidth": 0, "flex": "1 1 auto"},
    )

    right_group = None
    if actions is not None:
        if isinstance(actions, list):
            right_group = dmc.Group(actions, gap="xs", align="center")
        else:
            right_group = dmc.Box(actions)

    header_row = dmc.Group(
        [left_group] + ([right_group] if right_group else []),
        justify="space-between",
        align="center",
        gap="sm",
        style={"minWidth": 0, "width": "100%"},
    )

    container_children: list[Any] = []
    if breadcrumbs:
        crumb_items = []
        for i, item in enumerate(breadcrumbs):
            is_last = i == len(breadcrumbs) - 1
            if is_last or not item.get("href"):
                crumb_items.append(dmc.Text(item["label"], size="xs", c="dimmed" if not is_last else "dark", fw=500))
            else:
                crumb_items.append(
                    dmc.Anchor(
                        item["label"],
                        href=item["href"],
                        size="xs",
                        c="dimmed",
                        underline=False,
                    )
                )
        container_children.append(dmc.Breadcrumbs(crumb_items, separator="/", mb=4))

    container_children.append(header_row)

    root_style: dict[str, Any] = {"flexShrink": 0, "minWidth": 0}
    if "style" in kwargs:
        root_style.update(kwargs.pop("style"))

    root_kwargs: dict[str, Any] = {
        "mb": "xs",
        "style": root_style,
    }
    if id is not None:
        root_kwargs["id"] = id

    return dmc.Box(
        container_children,
        **root_kwargs,
        **kwargs,
    )
