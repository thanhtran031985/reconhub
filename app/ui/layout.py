from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html
from dash_iconify import DashIconify

from app.core.config import get_settings
from app.core.session import get_current_ctx


def create_header(ctx: Any, env: str) -> Any:
    """Tạo thanh header tối giản với Logo, nhãn ENV và User Menu."""
    env_badge_color = {
        "dev": "blue",
        "test": "gray",
        "uat": "yellow",
        "prod": "red",
    }.get(env.lower(), "blue")

    user_menu = None
    if ctx is not None:
        user_menu = dmc.Menu(
            [
                dmc.MenuTarget(
                    dmc.Button(
                        dmc.Group(
                            [
                                dmc.Avatar(
                                    ctx.full_name[:2].upper() if ctx.full_name else "RH",
                                    radius="xl",
                                    size="sm",
                                    color="primary",
                                ),
                                dmc.Text(ctx.full_name, size="sm", fw=500),
                                DashIconify(icon="lucide:chevron-down", width=14),
                            ],
                            gap="xs",
                        ),
                        variant="subtle",
                        color="gray",
                        px="xs",
                    )
                ),
                dmc.MenuDropdown(
                    [
                        dmc.MenuLabel(f"@{ctx.username}"),
                        dmc.MenuItem(
                            "Tài khoản",
                            href="/account",
                            leftSection=DashIconify(icon="lucide:user", width=16),
                        ),
                        dmc.MenuDivider(),
                        dmc.MenuItem(
                            "Đăng xuất",
                            href="/logout",
                            color="red",
                            leftSection=DashIconify(icon="lucide:log-out", width=16),
                        ),
                    ]
                ),
            ],
            position="bottom-end",
            withArrow=True,
        )

    return dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Anchor(
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:layers", width=20),
                                    size="lg",
                                    radius="md",
                                    color="primary",
                                    variant="filled",
                                ),
                                dmc.Text("ReconHub", fw=700, size="lg", c="dark"),
                            ],
                            gap="xs",
                        ),
                        href="/",
                        underline=False,
                    ),
                    dmc.Badge(env.upper(), color=env_badge_color, variant="light", size="sm"),
                ],
                gap="md",
            ),
            user_menu if user_menu is not None else html.Div(),
        ],
        justify="space-between",
        h="100%",
        px="lg",
    )


def create_shell_layout() -> Any:
    """Tạo layout ứng dụng kết hợp MantineProvider và AppShell."""
    return html.Div(
        [
            dcc.Location(id="app-location", refresh=False),
            html.Div(id="app-shell-container"),
        ]
    )


@callback(
    Output("app-shell-container", "children"),
    Input("app-location", "pathname"),
)
def render_app_shell(pathname: str | None) -> Any:
    settings = get_settings()
    ctx = get_current_ctx()

    # Trang login không hiển thị AppShell khung ngoài
    if pathname == "/login":
        return dash.page_container

    header_content = create_header(ctx, settings.APP_ENV)

    return dmc.AppShell(
        header={"height": 56},
        children=[
            dmc.AppShellHeader(header_content),
            dmc.AppShellMain(dash.page_container),
        ],
    )
