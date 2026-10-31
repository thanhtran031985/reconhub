from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc

from app.ui.components.button import button_danger, button_primary, button_subtle


def modal_confirm(
    id: str,
    title: str,
    description: Any,
    confirm_text: str | None = None,
    confirm_label: str = "Xác nhận",
    cancel_label: str = "Hủy",
    danger: bool = True,
    opened: bool = False,
) -> dmc.Modal:
    """Hộp thoại xác nhận thao tác quan trọng hoặc xóa dữ liệu."""
    body_items: list[Any] = [
        dmc.Text(description, size="sm", c="dimmed", mb="md")
        if isinstance(description, str)
        else description,
    ]

    if confirm_text:
        body_items.append(
            dmc.Text(
                f"Vui lòng gõ '{confirm_text}' vào ô bên dưới để xác nhận:",
                size="xs",
                fw=600,
                c="dark",
                mb="xs",
            )
        )
        body_items.append(
            dmc.TextInput(
                id=f"{id}-input",
                placeholder=f"Gõ {confirm_text}",
                size="sm",
                mb="md",
            )
        )

    confirm_btn = (
        button_danger(confirm_label, id=f"{id}-confirm")
        if danger
        else button_primary(confirm_label, id=f"{id}-confirm")
    )
    cancel_btn = button_subtle(cancel_label, id=f"{id}-cancel")

    footer = dmc.Group(
        [cancel_btn, confirm_btn],
        justify="flex-end",
        gap="sm",
        mt="lg",
    )

    body_items.append(footer)

    return dmc.Modal(
        id=id,
        title=dmc.Text(title, fw=700, size="md"),
        opened=opened,
        children=dmc.Stack(body_items, gap=0),
        radius="lg",
        withCloseButton=True,
    )

