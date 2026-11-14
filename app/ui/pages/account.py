from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.telegram_notify import (
    generate_link_code,
    get_telegram_link_status,
    set_telegram_enabled,
    unlink_telegram,
)
from app.services.user import change_password
from app.ui.components.page_header import page_header

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/account",
        title="Tài khoản – ReconHub",
    )
except Exception:
    pass


def _telegram_status_text(linked: bool, chat_id: Any, enabled: bool) -> Any:
    """Dòng trạng thái liên kết Telegram (task 94)."""
    if linked:
        return dmc.Text(
            f"Đã liên kết Telegram (chat {chat_id}). Run đối soát xong/lỗi sẽ báo về đây."
            + ("" if enabled else " Hiện đang tắt nhận thông báo Telegram."),
            size="sm",
        )
    return dmc.Text("Chưa liên kết Telegram.", size="sm", c="dimmed")


def layout(**kwargs: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            page_header(title="Tài khoản", subtitle="Vui lòng đăng nhập để xem thông tin"),
            style={"padding": "24px"},
        )

    roles_badges = [dmc.Badge(r, variant="light", color="primary", size="sm") for r in ctx.roles]

    tg_linked, tg_chat_id, tg_enabled = False, None, True
    tg_res = get_telegram_link_status(ctx)
    if tg_res.ok and isinstance(tg_res.data, dict):
        tg_linked = bool(tg_res.data.get("linked"))
        tg_chat_id = tg_res.data.get("chat_id")
        tg_enabled = bool(tg_res.data.get("enabled"))

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
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Title("Telegram", order=5),
                                    dmc.Text(
                                        "Liên kết Telegram để nhận tin khi run đối soát xong "
                                        "hoặc lỗi. Bấm 'Lấy mã liên kết', nhắn /start kèm mã "
                                        "cho bot, hệ thống tự lưu chat của bạn.",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                    html.Div(
                                        id="account-telegram-status",
                                        children=_telegram_status_text(tg_linked, tg_chat_id, tg_enabled),
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.Button(
                                                "Lấy mã liên kết",
                                                id="account-telegram-link-btn",
                                                color="primary",
                                                size="sm",
                                            ),
                                            dmc.Button(
                                                "Hủy liên kết",
                                                id="account-telegram-unlink-btn",
                                                variant="outline",
                                                color="red",
                                                size="sm",
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    html.Div(id="account-telegram-code"),
                                    dmc.Switch(
                                        id="account-telegram-enabled",
                                        label="Nhận thông báo Telegram",
                                        checked=tg_enabled,
                                        size="sm",
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
                    mx="auto",
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
            "padding": "8px 12px",
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


@callback(
    Output("account-telegram-status", "children"),
    Output("account-telegram-code", "children"),
    Input("account-telegram-link-btn", "n_clicks"),
    Input("account-telegram-unlink-btn", "n_clicks"),
    Input("account-telegram-enabled", "checked"),
    prevent_initial_call=True,
)
def handle_account_telegram_actions(
    link_clicks: int | None,
    unlink_clicks: int | None,
    enabled: bool | None,
) -> tuple[Any, Any]:
    """Liên kết / hủy liên kết / bật-tắt nhận tin Telegram (task 94)."""
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, dash.no_update
    triggered = dash.callback_context.triggered_id
    if triggered == "account-telegram-link-btn":
        if not link_clicks:
            return dash.no_update, dash.no_update
        res = generate_link_code(ctx)
        if not res.ok:
            return dash.no_update, dmc.Alert(
                res.message or "Không lấy được mã liên kết.",
                color="red",
                icon=DashIconify(icon="lucide:alert-triangle"),
            )
        data = res.data or {}
        return dash.no_update, dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Text("Mã liên kết:", size="sm", c="dimmed"),
                        dmc.Code(str(data.get("code") or "")),
                    ],
                    gap="xs",
                ),
                dmc.Anchor(
                    str(data.get("link") or ""),
                    href=str(data.get("link") or ""),
                    target="_blank",
                    size="sm",
                ),
                dmc.Text("Mã hết hạn sau 15 phút. Nhắn /start kèm mã cho bot.", size="xs", c="dimmed"),
            ],
            gap="xs",
        )
    if triggered == "account-telegram-unlink-btn":
        if not unlink_clicks:
            return dash.no_update, dash.no_update
        res = unlink_telegram(ctx)
        if not res.ok:
            return dash.no_update, dmc.Alert(
                res.message or "Không hủy được liên kết.",
                color="red",
                icon=DashIconify(icon="lucide:alert-triangle"),
            )
        return _telegram_status_text(False, None, False), ""
    if triggered == "account-telegram-enabled":
        res = set_telegram_enabled(ctx, bool(enabled))
        if not res.ok:
            return dash.no_update, dash.no_update
        status = get_telegram_link_status(ctx)
        data = status.data if status.ok and isinstance(status.data, dict) else {}
        return (
            _telegram_status_text(bool(data.get("linked")), data.get("chat_id"), bool(data.get("enabled"))),
            dash.no_update,
        )
    return dash.no_update, dash.no_update
