from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from flask import has_request_context, request

from app.db.engine import get_recon_engine
from app.services.password_reset import perform_password_reset, validate_reset_token

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/reset-password",
        title="Đặt lại mật khẩu — ReconHub",
    )
except Exception:
    pass


def layout(token: str | None = None, **kwargs: Any) -> html.Div:
    """Giao diện đặt lại mật khẩu mới từ liên kết email."""
    if not token or not token.strip():
        return _render_error_card("Liên kết đặt lại mật khẩu không hợp lệ hoặc bị thiếu.")

    engine = get_recon_engine()
    val_res = validate_reset_token(engine, token.strip())
    if not val_res.ok or not val_res.data:
        err_msg = val_res.message or "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."
        return _render_error_card(err_msg)

    user_info = val_res.data
    full_name = user_info.get("full_name") or user_info.get("username")

    return html.Div(
        [
            dcc.Location(id="reset-redirect-loc", refresh=True),
            dcc.Store(id="reset-token-store", data=token.strip()),
            dmc.Center(
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:shield-check", width=22),
                                    size="lg",
                                    radius="md",
                                    color="primary",
                                    variant="light",
                                ),
                                dmc.Title("Đặt lại mật khẩu", order=3),
                            ],
                            gap="xs",
                            mb="xs",
                        ),
                        dmc.Text(
                            f"Xin chào {full_name}, vui lòng nhập mật khẩu mới cho tài khoản của bạn.",
                            c="dimmed",
                            size="xs",
                            mb="md",
                        ),
                        html.Div(id="reset-alert-container", children=[]),
                        dmc.Stack(
                            [
                                dmc.PasswordInput(
                                    id="reset-pw-new",
                                    label="Mật khẩu mới",
                                    placeholder="••••••••",
                                    withAsterisk=True,
                                    size="sm",
                                ),
                                dmc.PasswordInput(
                                    id="reset-pw-confirm",
                                    label="Xác nhận mật khẩu mới",
                                    placeholder="••••••••",
                                    withAsterisk=True,
                                    size="sm",
                                ),
                                dmc.Button(
                                    "Xác nhận đặt lại mật khẩu",
                                    id="reset-submit-btn",
                                    fullWidth=True,
                                    color="primary",
                                    size="sm",
                                    mt="xs",
                                ),
                                dmc.Anchor(
                                    "← Quay lại trang đăng nhập",
                                    href="/login",
                                    size="xs",
                                    ta="center",
                                    mt="xs",
                                    style={"display": "block", "textAlign": "center"},
                                ),
                            ],
                            gap="sm",
                        ),
                    ],
                    withBorder=True,
                    shadow="xs",
                    p="lg",
                    radius="md",
                    w=380,
                    style={"maxWidth": "95vw"},
                ),
                style={"height": "100vh", "backgroundColor": "var(--bg)", "overflow": "hidden"},
            ),
        ],
        style={"height": "100vh", "overflow": "hidden"},
    )


def _render_error_card(error_msg: str) -> html.Div:
    """Hiển thị card thông báo liên kết lỗi/hết hạn."""
    return html.Div(
        [
            dmc.Center(
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:alert-triangle", width=22),
                                    size="lg",
                                    radius="md",
                                    color="red",
                                    variant="light",
                                ),
                                dmc.Title("Liên kết không hợp lệ", order=3),
                            ],
                            gap="xs",
                            mb="sm",
                        ),
                        dmc.Alert(
                            error_msg,
                            color="red",
                            variant="light",
                            icon=DashIconify(icon="lucide:x-circle"),
                            mb="md",
                            p="xs",
                        ),
                        dmc.Anchor(
                            dmc.Button(
                                "Quay lại trang Đăng nhập",
                                fullWidth=True,
                                color="primary",
                                size="sm",
                            ),
                            href="/login",
                            style={"textDecoration": "none"},
                        ),
                    ],
                    withBorder=True,
                    shadow="xs",
                    p="lg",
                    radius="md",
                    w=380,
                    style={"maxWidth": "95vw"},
                ),
                style={"height": "100vh", "backgroundColor": "var(--bg)", "overflow": "hidden"},
            ),
        ],
        style={"height": "100vh", "overflow": "hidden"},
    )


@callback(
    Output("reset-alert-container", "children"),
    Output("reset-redirect-loc", "href"),
    Input("reset-submit-btn", "n_clicks"),
    State("reset-pw-new", "value"),
    State("reset-pw-confirm", "value"),
    State("reset-token-store", "data"),
    prevent_initial_call=True,
)
def handle_reset_submit(
    n_clicks: int | None,
    pw_new: str | None,
    pw_confirm: str | None,
    token: str | None,
) -> tuple[Any, str | None]:
    """Xử lý submit đặt lại mật khẩu mới."""
    if not n_clicks:
        return dash.no_update, None

    clean_new = (pw_new or "").strip()
    clean_confirm = (pw_confirm or "").strip()

    if not clean_new or not clean_confirm:
        return (
            dmc.Alert(
                "Vui lòng nhập đầy đủ mật khẩu mới và xác nhận mật khẩu.",
                color="yellow",
                variant="light",
                icon=DashIconify(icon="lucide:alert-circle"),
                mb="md",
                p="xs",
            ),
            None,
        )

    if clean_new != clean_confirm:
        return (
            dmc.Alert(
                "Mật khẩu xác nhận không khớp. Vui lòng kiểm tra lại.",
                color="red",
                variant="light",
                icon=DashIconify(icon="lucide:alert-triangle"),
                mb="md",
                p="xs",
            ),
            None,
        )

    if len(clean_new) < 6:
        return (
            dmc.Alert(
                "Mật khẩu phải có tối thiểu 6 ký tự.",
                color="red",
                variant="light",
                icon=DashIconify(icon="lucide:alert-triangle"),
                mb="md",
                p="xs",
            ),
            None,
        )

    if not token:
        return (
            dmc.Alert(
                "Mã token không hợp lệ hoặc phiên thao tác đã hết hạn.",
                color="red",
                variant="light",
                icon=DashIconify(icon="lucide:x-circle"),
                mb="md",
                p="xs",
            ),
            None,
        )

    engine = get_recon_engine()
    ip = request.remote_addr if has_request_context() else None
    res = perform_password_reset(engine=engine, raw_token=token, new_password=clean_new, ip=ip)
    if not res.ok:
        return (
            dmc.Alert(
                res.message or "Không thể đặt lại mật khẩu. Vui lòng thử lại.",
                color="red",
                variant="light",
                icon=DashIconify(icon="lucide:x-circle"),
                mb="md",
                p="xs",
            ),
            None,
        )

    return None, "/login?msg=reset_success"
