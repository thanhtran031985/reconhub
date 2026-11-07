from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc


def wizard_shell(
    steps: list[dict[str, Any]],
    current_step: int,
    content: Any,
    footer_actions: list[Any] | Any,
    error_message: str | None = None,
    id: str | None = None,
    content_id: str | None = None,
    footer_id: str | None = None,
    **kwargs: Any,
) -> dmc.Box:
    """Khung Wizard chuẩn Fluent Compact: Stepper 1 dòng ở đỉnh, Body flex 1 cuộn riêng, Footer cố định ở chân."""
    step_elements: list[Any] = []
    total_steps = len(steps)

    for i, step in enumerate(steps):
        is_active = i == current_step
        is_done = i < current_step
        step_num = i + 1

        circle_style: dict[str, Any] = {
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "width": "20px",
            "height": "20px",
            "borderRadius": "50%",
            "border": "1px solid var(--line, #E0E0E0)",
            "fontSize": "11px",
            "fontWeight": 600,
            "flexShrink": 0,
            "backgroundColor": "var(--p, #FFFFFF)",
            "color": "var(--ink-soft, #616161)",
        }
        if is_active:
            circle_style.update(
                {
                    "backgroundColor": "var(--primary, #0F6CBD)",
                    "borderColor": "var(--primary, #0F6CBD)",
                    "color": "#FFFFFF",
                }
            )
        elif is_done:
            circle_style.update(
                {
                    "borderColor": "var(--ok, #107C10)",
                    "color": "var(--ok, #107C10)",
                }
            )

        step_btn_style: dict[str, Any] = {
            "flex": "1 1 0",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "gap": "6px",
            "height": "34px",
            "padding": "0 8px",
            "border": "none",
            "borderRight": "1px solid var(--line, #E0E0E0)" if i < total_steps - 1 else "none",
            "backgroundColor": "var(--primary-soft, #EBF3FC)" if is_active else "transparent",
            "boxShadow": "inset 0 -2px 0 var(--primary, #0F6CBD)" if is_active else "none",
            "fontSize": "12px",
            "fontWeight": 600 if is_active else 400,
            "color": "var(--ink, #242424)" if (is_active or is_done) else "var(--ink-soft, #616161)",
            "whiteSpace": "nowrap",
            "minWidth": 0,
            "userSelect": "none",
        }

        step_elements.append(
            dmc.Box(
                [
                    dmc.Box(str(step_num), style=circle_style),
                    dmc.Text(
                        step.get("label", f"Bước {step_num}"),
                        size="xs",
                        fw=600 if is_active else 500,
                        style={"overflow": "hidden", "textOverflow": "ellipsis"},
                    ),
                ],
                style=step_btn_style,
            )
        )

    steps_bar = dmc.Box(
        step_elements,
        style={
            "display": "flex",
            "flexDirection": "row",
            "border": "1px solid var(--line, #E0E0E0)",
            "borderRadius": "6px",
            "backgroundColor": "var(--p, #FFFFFF)",
            "overflow": "hidden",
            "flexShrink": 0,
            "marginBottom": "8px",
        },
    )

    body_kwargs: dict[str, Any] = {
        "style": {
            "flex": 1,
            "minHeight": 0,
            "overflow": "auto",
            "padding": "12px 16px",
            "display": "flex",
            "flexDirection": "column",
        }
    }
    if content_id is not None:
        body_kwargs["id"] = content_id
    body_panel = dmc.Box(content, **body_kwargs)

    footer_right: list[Any] = []
    if isinstance(footer_actions, list):
        footer_right.extend(footer_actions)
    elif footer_actions is not None:
        footer_right.append(footer_actions)

    footer_left_elements: list[Any] = []
    if error_message:
        footer_left_elements.append(
            dmc.Text(
                error_message,
                size="xs",
                c="red",
                style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
            )
        )

    footer_kwargs: dict[str, Any] = {
        "style": {
            "flexShrink": 0,
            "padding": "8px 16px",
            "borderTop": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "var(--p2, #FAFAFA)",
        }
    }
    if footer_id is not None:
        footer_kwargs["id"] = footer_id

    footer = dmc.Box(
        dmc.Group(
            [
                dmc.Box(footer_left_elements, style={"flex": "1 1 auto", "minWidth": 0}),
                dmc.Group(footer_right, gap="xs", align="center"),
            ],
            justify="space-between",
            align="center",
            style={"width": "100%"},
        ),
        **footer_kwargs,
    )

    container_box = dmc.Box(
        [
            body_panel,
            footer,
        ],
        style={
            "flex": 1,
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "backgroundColor": "var(--p, #FFFFFF)",
            "border": "1px solid var(--line, #E0E0E0)",
            "borderRadius": "6px",
            "boxShadow": "var(--sh, 0 1px 2px #0000001f)",
            "overflow": "hidden",
        },
    )

    root_kwargs: dict[str, Any] = {
        "style": {
            "flex": 1,
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        }
    }
    if id is not None:
        root_kwargs["id"] = id

    return dmc.Box(
        [
            steps_bar,
            container_box,
        ],
        **root_kwargs,
        **kwargs,
    )
