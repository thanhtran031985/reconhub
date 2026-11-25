from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, html
from dash_iconify import DashIconify
from flask import has_request_context, request

from app.db.engine import get_recon_engine
from app.services.password_reset import request_password_reset
from app.services.smtp_settings import DEFAULT_APP_BASE_URL, get_app_base_url

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/forgot-password",
        title="Quên mật khẩu — ReconHub",
    )
except Exception:
    pass


def _resolve_request_context() -> tuple[str | None, str]:
    """Lấy địa chỉ IP người gửi và Base URL an toàn cho liên kết email."""
    ip = request.remote_addr if has_request_context() else None
    configured = get_app_base_url()
    if configured != DEFAULT_APP_BASE_URL:
        return ip, configured
    if has_request_context() and request.host_url:
        return ip, request.host_url.rstrip("/")
    return ip, configured


def layout() -> html.Div:
    """Giao diện yêu cầu đặt lại mật khẩu."""
    return html.Div(
        [
            dmc.Center(
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:key-round", width=22),
                                    size="lg",
                                    radius="md",
                                    color="primary",
                                    variant="light",
                                ),
                                dmc.Title("Quên mật khẩu", order=3),
                            ],
                            gap="xs",
                            mb="xs",
                        ),
                        dmc.Text(
                            "Nhập tên đăng nhập và địa chỉ email đã đăng ký để nhận liên kết xác thực đặt lại mật khẩu.",
                            c="dimmed",
                            size="xs",
                            mb="md",
                        ),
                        html.Div(id="forgot-alert-container", children=[]),
                        dmc.Stack(
                            [
                                dmc.TextInput(
                                    id="forgot-username-input",
                                    label="Tên đăng nhập",
                                    placeholder="ví dụ: nguyenvana",
                                    withAsterisk=True,
                                    size="sm",
                                ),
                                dmc.TextInput(
                                    id="forgot-email-input",
                                    label="Địa chỉ email",
                                    placeholder="ví dụ: user@company.local",
                                    withAsterisk=True,
                                    size="sm",
                                ),
                                html.Div(
                                    [
                                        dmc.Progress(
                                            value=100,
                                            animated=True,
                                            striped=True,
                                            size="sm",
                                            color="primary",
                                        ),
                                        dmc.Text(
                                            "Đang kiểm tra thông tin và gửi email...",
                                            size="xs",
                                            c="dimmed",
                                            ta="center",
                                            mt=4,
                                        ),
                                    ],
                                    id="forgot-progress-wrap",
                                    style={"display": "none"},
                                ),
                                dmc.Button(
                                    "Gửi liên kết đặt lại mật khẩu",
                                    id="forgot-submit-btn",
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


@callback(
    Output("forgot-alert-container", "children"),
    Output("forgot-username-input", "value"),
    Output("forgot-email-input", "value"),
    Input("forgot-submit-btn", "n_clicks"),
    State("forgot-username-input", "value"),
    State("forgot-email-input", "value"),
    running=[
        (Output("forgot-username-input", "disabled"), True, False),
        (Output("forgot-email-input", "disabled"), True, False),
        (Output("forgot-submit-btn", "disabled"), True, False),
        (Output("forgot-submit-btn", "loading"), True, False),
        (Output("forgot-progress-wrap", "style"), {"display": "block"}, {"display": "none"}),
    ],
    prevent_initial_call=True,
)
def handle_forgot_password(
    n_clicks: int | None,
    username: str | None,
    email: str | None,
) -> tuple[Any, Any, Any]:
    """Xử lý gửi yêu cầu đặt lại mật khẩu."""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update

    clean_user = (username or "").strip()
    clean_email = (email or "").strip()
    if not clean_user or not clean_email:
        return (
            dmc.Alert(
                "Vui lòng nhập đầy đủ tên đăng nhập và địa chỉ email.",
                color="yellow",
                variant="light",
                icon=DashIconify(icon="lucide:alert-circle"),
                mb="md",
                p="xs",
            ),
            dash.no_update,
            dash.no_update,
        )

    engine = get_recon_engine()
    ip, base_url = _resolve_request_context()
    res = request_password_reset(
        engine=engine,
        username=clean_user,
        email=clean_email,
        ip=ip,
        base_url=base_url,
    )
    msg = res.data.get("message") if res.data else "Yêu cầu đã được tiếp nhận."

    return (
        dmc.Alert(
            msg,
            color="green",
            variant="light",
            icon=DashIconify(icon="lucide:check-circle"),
            mb="md",
            p="xs",
        ),
        "",
        "",
    )
