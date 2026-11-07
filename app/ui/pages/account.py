from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.user import change_password
from app.ui.components.page_header import page_header

dash.register_page(  # type: ignore[no-untyped-call]
    __name__,
    path="/account",
    title="Tài khoản – ReconHub",
)


def layout(**kwargs: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            page_header(title="Tài khoản", subtitle="Vui lòng đăng nhập để xem thông tin"),
            style={"padding": "24px"},
        )

    roles_badges = [dmc.Badge(r, variant="light", color="primary", size="sm") for r in ctx.roles]

    return html.Div(
        [
            page_header(
                title="Tài khoản cá nhân",
                subtitle=f"Thông tin người dùng @{ctx.username} và thiết lập bảo mật",
            ),
            html.Div(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Avatar(
                                    ctx.full_name[:2].upper() if ctx.full_name else "RH",
                                    radius="xl",
                                    color="primary",
                                    size="md",
                                ),
                                dmc.Stack(
                                    [
                                        dmc.Title(ctx.full_name, order=4),
                                        dmc.Text(
                                            f"@{ctx.username}",
                                            c="dimmed",
                                            size="xs",
                                            style={"fontFamily": "var(--font-mono)"},
                                        ),
                                    ],
                                    gap=0,
                                ),
                            ],
                            gap="sm",
                        ),
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Title("Thông tin tài khoản", order=5),
                                    dmc.Table(
                                        [
                                            dmc.TableTbody(
                                                [
                                                    dmc.TableTr(
                                                        [
                                                            dmc.TableTd("Tên đăng nhập", fw=500, w=160),
                                                            dmc.TableTd(
                                                                ctx.username,
                                                                style={"fontFamily": "var(--font-mono)"},
                                                            ),
                                                        ]
                                                    ),
                                                    dmc.TableTr(
                                                        [
                                                            dmc.TableTd("Họ và tên", fw=500),
                                                            dmc.TableTd(ctx.full_name),
                                                        ]
                                                    ),
                                                    dmc.TableTr(
                                                        [
                                                            dmc.TableTd("Vai trò", fw=500),
                                                            dmc.TableTd(dmc.Group(roles_badges, gap="xs")),
                                                        ]
                                                    ),
                                                ]
                                            )
                                        ]
                                    ),
                                ],
                                gap="sm",
                            ),
                            withBorder=True,
                            p="md",
                            radius="sm",
                        ),
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Title("Đổi mật khẩu", order=5),
                                    html.Div(id="account-pw-alert-container"),
                                    dmc.PasswordInput(
                                        id="account-old-pw",
                                        label="Mật khẩu hiện tại",
                                        placeholder="••••••••",
                                        withAsterisk=True,
                                        size="sm",
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.PasswordInput(
                                                id="account-new-pw",
                                                label="Mật khẩu mới",
                                                placeholder="••••••••",
                                                withAsterisk=True,
                                                size="sm",
                                                style={"flex": 1},
                                            ),
                                            dmc.PasswordInput(
                                                id="account-confirm-pw",
                                                label="Nhập lại mật khẩu mới",
                                                placeholder="••••••••",
                                                withAsterisk=True,
                                                size="sm",
                                                style={"flex": 1},
                                            ),
                                        ],
                                        grow=True,
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.Text(
                                                "Đổi mật khẩu sẽ tự động đăng xuất khỏi các phiên đăng nhập khác.",
                                                c="dimmed",
                                                size="xs",
                                            ),
                                            dmc.Button(
                                                "Đổi mật khẩu",
                                                id="account-change-pw-btn",
                                                color="primary",
                                                size="sm",
                                            ),
                                        ],
                                        justify="space-between",
                                        mt="xs",
                                    ),
                                ],
                                gap="sm",
                            ),
                            withBorder=True,
                            p="md",
                            radius="sm",
                        ),
                    ],
                    gap="md",
                    maw=640,
                ),
                style={
                    "flex": "1 1 0%",
                    "minHeight": 0,
                    "overflowY": "auto",
                    "padding": "16px 20px",
                },
            ),
        ],
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "var(--mantine-color-body)",
        },
    )


@callback(
    Output("account-pw-alert-container", "children"),
    Input("account-change-pw-btn", "n_clicks"),
    State("account-old-pw", "value"),
    State("account-new-pw", "value"),
    State("account-confirm-pw", "value"),
    prevent_initial_call=True,
)
def handle_account_change_password(
    n_clicks: int,
    old_pw: str | None,
    new_pw: str | None,
    confirm_pw: str | None,
) -> Any:
    if not n_clicks:
        return dash.no_update

    if not old_pw or not new_pw or not confirm_pw:
        return dmc.Alert(
            "Vui lòng điền đầy đủ mật khẩu hiện tại và mật khẩu mới",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
        )

    if new_pw != confirm_pw:
        return dmc.Alert(
            "Mật khẩu mới và mật khẩu nhập lại chưa trùng khớp",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
        )

    ctx = get_current_ctx()
    if ctx is None:
        return dmc.Alert(
            "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
        )

    res = change_password(ctx, old_pw, new_pw)
    if not res.ok:
        return dmc.Alert(
            res.message or "Đổi mật khẩu không thành công",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
        )

    return dmc.Alert(
        "Đổi mật khẩu thành công. Các phiên làm việc khác đã được đăng xuất.",
        color="green",
        icon=DashIconify(icon="lucide:check-circle"),
    )
