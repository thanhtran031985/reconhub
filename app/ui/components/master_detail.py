from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def master_detail_layout(
    master_content: Any,
    detail_content: Any = None,
    detail_width: int | str = 380,
    detail_visible: bool = True,
    id: str | None = None,
    master_id: str | None = None,
    detail_id: str | None = None,
    master_style: dict[str, Any] | None = None,
    detail_style: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Master–Detail container chuẩn Fluent Compact.

    Desktop (>=900px): 2 cột ngang độc lập, không phát sinh cuộn trang ngoài.
    Detail có viền trái, cuộn độc lập.
    """
    m_style: dict[str, Any] = {
        "flex": 1,
        "minWidth": 0,
        "minHeight": 0,
        "height": "100%",
        "overflow": "auto",
        "display": "flex",
        "flexDirection": "column",
    }
    if master_style:
        m_style.update(master_style)

    master_kwargs: dict[str, Any] = {"style": m_style}
    if master_id is not None:
        master_kwargs["id"] = master_id
    master_box = dmc.Box(master_content, **master_kwargs)

    children = [master_box]

    if detail_visible and detail_content is not None:
        width_val = f"{detail_width}px" if isinstance(detail_width, int) else detail_width
        d_style: dict[str, Any] = {
            "width": width_val,
            "minWidth": width_val,
            "maxWidth": width_val,
            "minHeight": 0,
            "height": "100%",
            "overflow": "auto",
            "borderLeft": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "var(--p2, #FAFAFA)",
            "display": "flex",
            "flexDirection": "column",
        }
        if detail_style:
            d_style.update(detail_style)

        detail_kwargs: dict[str, Any] = {"style": d_style}
        if detail_id is not None:
            detail_kwargs["id"] = detail_id
        detail_box = dmc.Box(detail_content, **detail_kwargs)
        children.append(detail_box)

    container_style: dict[str, Any] = {
        "display": "flex",
        "flexDirection": "row",
        "flex": 1,
        "height": "100%",
        "minHeight": 0,
        "minWidth": 0,
        "overflow": "hidden",
        "border": "1px solid var(--line, #E0E0E0)",
        "borderRadius": "6px",
        "backgroundColor": "var(--p, #FFFFFF)",
    }

    container_kwargs: dict[str, Any] = {"style": container_style}
    if id is not None:
        container_kwargs["id"] = id

    return dmc.Box(
        children,
        **container_kwargs,
        **kwargs,
    )
