from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash_iconify import DashIconify

dash.register_page(  # type: ignore[no-untyped-call]
    __name__,
    path="/forbidden",
    title="403 Truy cập bị từ chối – ReconHub",
)


def layout(**kwargs: Any) -> Any:
    return dmc.Center(
        dmc.Stack(
            [
                dmc.ThemeIcon(
                    DashIconify(icon="lucide:shield-alert", width=48),
                    size=80,
                    radius="xl",
                    color="red",
                    variant="light",
                ),
                dmc.Title("Truy cập bị từ chối (403)", order=2),
                dmc.Text(
                    "Tài khoản của bạn không có đủ quyền hạn để thực hiện thao tác hoặc truy cập trang này.",
                    c="dimmed",
                    ta="center",
                    maw=480,
                ),
                dmc.Anchor(
                    dmc.Button(
                        "Quay về Trang chủ",
                        leftSection=DashIconify(icon="lucide:arrow-left"),
                        variant="default",
                    ),
                    href="/",
                ),
            ],
            align="center",
            gap="md",
        ),
        style={"minHeight": "80vh"},
    )
