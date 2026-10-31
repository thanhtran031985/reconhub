from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash import dcc
from dash_iconify import DashIconify


def file_drop(
    id: str,
    label: str = "Kéo thả file Excel hoặc CSV vào đây",
    hint: str = "Hỗ trợ định dạng .xlsx, .csv — tối đa 50 MB",
    accept: str = ".xlsx,.csv",
    max_size: int = 52428800,  # 50MB
    **kwargs: Any,
) -> dcc.Upload:
    """Vùng kéo thả upload file chuẩn 50MB."""
    content = dmc.Paper(
        dmc.Stack(
            [
                dmc.ThemeIcon(
                    DashIconify(icon="lucide:upload-cloud", width=32),
                    size=64,
                    radius="xl",
                    color="primary",
                    variant="light",
                ),
                dmc.Text(label, fw=600, size="sm", c="dark", ta="center"),
                dmc.Text(hint, size="xs", c="dimmed", ta="center"),
            ],
            align="center",
            gap="xs",
            py="xl",
        ),
        withBorder=True,
        radius="lg",
        bg="surface-2",
        style={"borderStyle": "dashed", "cursor": "pointer"},
    )

    return dcc.Upload(
        id=id,
        children=content,
        max_size=max_size,
        accept=accept,
        style={"width": "100%"},
        **kwargs,
    )

