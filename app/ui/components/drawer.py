from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def drawer_right(
    id: str,
    title: str,
    children: Any,
    size: int | str = 540,
    opened: bool = False,
    **kwargs: Any,
) -> dmc.Drawer:
    """Ngăn kéo trượt từ bên phải kích thước chuẩn 540px."""
    return dmc.Drawer(
        id=id,
        title=dmc.Text(title, fw=700, size="lg"),
        children=children,
        position="right",
        size=size,
        opened=opened,
        padding="lg",
        shadow="xl",
        **kwargs,
    )

