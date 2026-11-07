from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def skeleton_grid(
    rows: int = 8,
    cols: int = 4,
    row_height: int = 32,
    header_height: int = 34,
    id: str | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Component skeleton giả lập bảng AgGrid Fluent Compact khi đang tải dữ liệu."""
    header_skeletons = [
        dmc.Skeleton(
            h=header_height - 12,
            radius="xs",
            style={"flex": 1, "margin": "0 4px"},
        )
        for _ in range(cols)
    ]

    header_row = dmc.Box(
        header_skeletons,
        style={
            "display": "flex",
            "flexDirection": "row",
            "alignItems": "center",
            "height": f"{header_height}px",
            "padding": "0 8px",
            "backgroundColor": "var(--p2, #FAFAFA)",
            "borderBottom": "1px solid var(--line, #E0E0E0)",
        },
    )

    body_rows: list[Any] = []
    for r in range(rows):
        row_skeletons = [
            dmc.Skeleton(
                h=row_height - 14,
                radius="xs",
                style={"flex": 1, "margin": "0 4px"},
            )
            for _ in range(cols)
        ]
        body_rows.append(
            dmc.Box(
                row_skeletons,
                style={
                    "display": "flex",
                    "flexDirection": "row",
                    "alignItems": "center",
                    "height": f"{row_height}px",
                    "padding": "0 8px",
                    "borderBottom": "1px solid var(--line, #E0E0E0)" if r < rows - 1 else "none",
                },
            )
        )

    box_kwargs: dict[str, Any] = {
        "style": {
            "display": "flex",
            "flexDirection": "column",
            "border": "1px solid var(--line, #E0E0E0)",
            "borderRadius": "6px",
            "backgroundColor": "var(--p, #FFFFFF)",
            "overflow": "hidden",
            "width": "100%",
        }
    }
    if id is not None:
        box_kwargs["id"] = id

    return dmc.Box(
        [header_row] + body_rows,
        **box_kwargs,
        **kwargs,
    )


def skeleton_panel(
    lines: int = 5,
    id: str | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Component skeleton giả lập Panel chi tiết khi đang tải."""
    items: list[Any] = [
        dmc.Skeleton(h=20, w="40%", radius="xs", mb="md"),
        dmc.Skeleton(h=12, w="80%", radius="xs", mb="lg"),
    ]
    for _ in range(lines):
        items.extend(
            [
                dmc.Skeleton(h=14, w="30%", radius="xs", mb=4),
                dmc.Skeleton(h=30, w="100%", radius="xs", mb="sm"),
            ]
        )

    panel_kwargs: dict[str, Any] = {
        "p": "md",
        "style": {
            "display": "flex",
            "flexDirection": "column",
            "width": "100%",
        },
    }
    if id is not None:
        panel_kwargs["id"] = id

    return dmc.Box(
        items,
        **panel_kwargs,
        **kwargs,
    )
