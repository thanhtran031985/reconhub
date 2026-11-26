"""Thanh công cụ Quản lý Template / Saved Views dùng chung cho /templates và /report-runs."""

from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

_SOFT_BORDER = "1px solid color-mix(in srgb, var(--mantine-color-default-border) 55%, transparent)"
_SOFT_RED_BORDER = "1px solid color-mix(in srgb, var(--mantine-color-red-6) 35%, transparent)"


def saved_view_toolbar(
    prefix: str,
    *,
    mb: str | None = None,
    select_id: str | None = None,
    btn_prefix: str | None = None,
    notification_id: str | None = None,
    select_w: int = 220,
) -> Any:
    """Dựng thanh công cụ Saved Views chuẩn Fluent Compact với border mờ cho các nút phụ."""
    sel_id = select_id or f"{prefix}-view-select"
    bp = btn_prefix or f"{prefix}-btn"
    notif_id = notification_id or f"{prefix}-grid-notification"

    paper_kwargs: dict[str, Any] = {
        "withBorder": True,
        "radius": "sm",
        "style": {"backgroundColor": "var(--surface-2, #FAFAFA)"},
    }
    if mb is not None:
        paper_kwargs["mb"] = mb

    return dmc.Paper(
        dmc.Group(
            [
                dmc.Group(
                    [
                        DashIconify(icon="lucide:layout-grid", width=16, color="var(--ink-soft)"),
                        dmc.Text("Template/View:", size="xs", fw=600),
                        dmc.Select(
                            id=sel_id,
                            data=[{"label": "Mặc định hệ thống", "value": "default"}],
                            value="default",
                            size="xs",
                            w=select_w,
                            styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                        ),
                        dmc.Button(
                            "Lưu vị trí cột",
                            id=f"{bp}-save-view",
                            size="xs",
                            color="blue",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Lưu thành View mới...",
                            id=f"{bp}-save-as-view",
                            size="xs",
                            variant="default",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Đặt mặc định",
                            id=f"{bp}-set-default",
                            size="xs",
                            variant="subtle",
                            color="gray",
                            style={"height": "28px", "fontSize": "12px", "border": _SOFT_BORDER},
                        ),
                        dmc.Button(
                            "Khôi phục gốc",
                            id=f"{bp}-reset-default",
                            size="xs",
                            variant="subtle",
                            color="gray",
                            style={"height": "28px", "fontSize": "12px", "border": _SOFT_BORDER},
                        ),
                        dmc.Button(
                            "Xóa View",
                            id=f"{bp}-delete-view",
                            size="xs",
                            variant="subtle",
                            color="red",
                            style={"height": "28px", "fontSize": "12px", "border": _SOFT_RED_BORDER},
                        ),
                    ],
                    gap="xs",
                    align="center",
                ),
                html.Span(
                    id=notif_id,
                    style={
                        "fontSize": "11px",
                        "color": "#2B8A3E",
                        "fontWeight": "600",
                        "transition": "opacity 0.3s ease",
                        "opacity": "0",
                    },
                ),
            ],
            justify="space-between",
            align="center",
            p="xs",
        ),
        **paper_kwargs,
    )
