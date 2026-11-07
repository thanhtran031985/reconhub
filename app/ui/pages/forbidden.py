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
                    DashIconify(icon="lucide:shield-alert", width=36),
                    size=64,
                    radius="xl",
                    color="red",
                    variant="light",
                ),
                dmc.Title("Truy cập bị từ chối (403)", order=3),
                dmc.Text(
                    "Tài khoản của bạn không có đủ quyền hạn để thực hiện thao tác hoặc truy cập trang này.",
                    c="dimmed",
                    size="sm",
                    ta="center",
                    maw=440,
                ),
                dmc.Anchor(
                    dmc.Button(
                        "Quay về Trang chủ",
                        leftSection=DashIconify(icon="lucide:arrow-left", width=14),
                        variant="default",
                        size="sm",
                    ),
                    href="/",
                    underline=False,
                ),
            ],
            align="center",
            gap="sm",
        ),
        style={"height": "calc(100vh - 48px)", "overflow": "hidden"},
    )
