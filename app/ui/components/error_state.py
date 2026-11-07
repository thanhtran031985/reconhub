from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app.ui.components.button import button_primary


def error_state(
    title: str = "Không thể tải dữ liệu",
    message: str | None = None,
    retry_id: str | None = None,
    retry_label: str = "Thử lại",
    action: Any = None,
    banner_only: bool = False,
    id: str | None = None,
    **kwargs: Any,
) -> Any:
    """Component hiển thị trạng thái lỗi 4-state chuẩn Fluent Compact kèm nút Thử lại."""
    actions_list: list[Any] = []
    if retry_id:
        actions_list.append(
            button_primary(
                retry_label,
                id=retry_id,
                icon="lucide:refresh-cw",
                size="xs",
            )
        )
    if action:
        if isinstance(action, list):
            actions_list.extend(action)
        else:
            actions_list.append(action)

    if banner_only:
        action_node = dmc.Group(actions_list, gap="xs") if actions_list else None
        alert_kwargs: dict[str, Any] = {
            "title": title,
            "color": "red",
            "icon": DashIconify(icon="lucide:alert-circle", width=18),
            "radius": "sm",
            "p": "xs",
        }
        if id is not None:
            alert_kwargs["id"] = id

        return dmc.Alert(
            children=dmc.Group(
                [
                    dmc.Text(message or "", size="xs", style={"flex": "1 1 auto"}),
                    action_node,
                ],
                justify="space-between",
                align="center",
            )
            if action_node
            else (dmc.Text(message, size="xs") if message else None),
            **alert_kwargs,
            **kwargs,
        )

    # Full paper error state
    content_items: list[Any] = [
        dmc.ThemeIcon(
            DashIconify(icon="lucide:alert-octagon", width=32),
            size=56,
            radius="xl",
            color="red",
            variant="light",
        ),
        dmc.Text(title, fw=600, size="md", c="red", ta="center"),
    ]
    if message:
        content_items.append(
            dmc.Text(message, size="sm", c="dimmed", ta="center", maw=440)
        )
    if actions_list:
        content_items.append(dmc.Group(actions_list, gap="xs", mt="xs"))

    paper_kwargs: dict[str, Any] = {
        "withBorder": True,
        "radius": "sm",
        "p": "xl",
        "bg": "var(--p2, #FAFAFA)",
    }
    if id is not None:
        paper_kwargs["id"] = id

    return dmc.Paper(
        dmc.Stack(content_items, align="center", gap="xs", py="xl"),
        **paper_kwargs,
        **kwargs,
    )
