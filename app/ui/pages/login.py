from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import update

from app.core.auth import authenticate_user, hash_password
from app.core.config import get_settings
from app.core.session import get_current_ctx, login_session
from app.db.engine import get_recon_engine
from app.db.metadata import recon_user

dash.register_page(  # type: ignore[no-untyped-call]
    __name__,
    path="/login",
    title="Đăng nhập – ReconHub",
)


def layout(step: str | None = None, error: str | None = None, msg: str | None = None, **kwargs: Any) -> Any:
    """Giao diện đăng nhập hoặc đổi mật khẩu bắt buộc theo Screen10."""
    ctx = get_current_ctx()
    settings = get_settings()

    if step == "change":
        user_name = ctx.full_name if ctx else "người dùng"
        card_content = [
            dmc.Group(
                [
                    dmc.ThemeIcon(
                        DashIconify(icon="lucide:key-round", width=20),
                        size="lg",
                        radius="md",
                        color="primary",
                        variant="light",
                    ),
                    dmc.Title("Đổi mật khẩu", order=3),
                ],
                gap="sm",
                mb="md",
            ),
            dmc.Alert(
                f"Xin chào {user_name}. Đây là lần đăng nhập đầu (hoặc mật khẩu vừa được đặt lại), vui lòng đặt mật khẩu mới để tiếp tục.",
                color="blue",
                variant="light",
                icon=DashIconify(icon="lucide:info"),
                mb="md",
            ),
            html.Div(id="change-alert-container"),
            dmc.Stack(
                [
                    dmc.PasswordInput(
                        id="change-new-pw",
                        label="Mật khẩu mới",
                        placeholder="Nhập mật khẩu mới",
                        withAsterisk=True,
                        size="sm",
                    ),
                    dmc.PasswordInput(
                        id="change-confirm-pw",
                        label="Nhập lại mật khẩu mới",
                        placeholder="Nhập lại mật khẩu mới",
                        withAsterisk=True,
                        size="sm",
                    ),
                    dmc.Button(
                        "Lưu và tiếp tục",
                        id="change-submit-btn",
                        fullWidth=True,
                        color="primary",
                        size="sm",
                        mt="sm",
                    ),
                ],
                gap="md",
            ),
        ]
    else:
        status_alert = None
        if error:
            status_alert = dmc.Alert(
                f"Đăng nhập SSO không thành công: {error}",
                color="red",
                icon=DashIconify(icon="lucide:alert-triangle"),
                mb="md",
            )
        elif msg == "reset_success":
            status_alert = dmc.Alert(
                "Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới của bạn.",
                color="green",
                icon=DashIconify(icon="lucide:check-circle"),
                mb="md",
            )

        sso_bottom_section: list[Any] = []
        if settings.SSO_ENABLED:
            sso_bottom_section = [
                dmc.Divider(label="hoặc", labelPosition="center", my="xs"),
                html.A(
                    dmc.Button(
                        "Đăng nhập qua SSO Doanh nghiệp",
                        fullWidth=True,
                        color="primary",
                        variant="light",
                        size="sm",
                        leftSection=DashIconify(icon="lucide:shield-check", width=18),
                    ),
                    href="/auth/sso/login",
                    style={"textDecoration": "none", "display": "block"},
                ),
            ]

        card_content = [
            dmc.Group(
                [
                    dmc.ThemeIcon(
                        DashIconify(icon="lucide:layers", width=24),
                        size="xl",
                        radius="md",
                        color="primary",
                        variant="filled",
                    ),
                    dmc.Title("ReconHub", order=2),
                ],
                gap="sm",
                mb="md",
            ),
            status_alert if status_alert else html.Div(),
            html.Div(id="login-alert-container"),
            dmc.Stack(
                [
                    dmc.TextInput(
                        id="login-username",
                        label="Tên đăng nhập",
                        placeholder="username",
                        withAsterisk=True,
                        autoComplete="username",
                        size="sm",
                    ),
                    dmc.PasswordInput(
                        id="login-password",
                        label="Mật khẩu",
                        placeholder="••••••••",
                        withAsterisk=True,
                        autoComplete="current-password",
                        size="sm",
                    ),
                    dmc.Button(
                        "Đăng nhập",
                        id="login-submit-btn",
                        fullWidth=True,
                        color="primary",
                        size="sm",
                        mt="sm",
                    ),
                    dmc.Anchor(
                        "Quên mật khẩu?",
                        href="/forgot-password",
                        size="xs",
                        ta="center",
                        mt="xs",
                        style={"display": "block", "textAlign": "center"},
                    ),
                    *sso_bottom_section,
                ],
                gap="md",
            ),
        ]

    return html.Div(
        [
            dcc.Location(id="login-redirect-loc", refresh=True),
            dmc.Center(
                dmc.Paper(
                    card_content,
                    withBorder=True,
                    shadow="xs",
                    p="lg",
                    radius="md",
                    w=380,
                    style={"maxWidth": "95vw"},
                ),
                style={"height": "100vh", "backgroundColor": "var(--bg, #F5F5F5)", "overflow": "hidden"},
            ),
        ],
        style={"height": "100vh", "overflow": "hidden"},
    )


@callback(
    Output("login-redirect-loc", "href", allow_duplicate=True),
    Output("login-alert-container", "children"),
    Input("login-submit-btn", "n_clicks"),
    State("login-username", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(n_clicks: int, username: str | None, password: str | None) -> tuple[Any, Any]:
    if not n_clicks:
        return dash.no_update, dash.no_update

    if not username or not password:
        alert = dmc.Alert(
            "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
            mb="md",
        )
        return dash.no_update, alert

    engine = get_recon_engine()
    res = authenticate_user(engine, username, password)

    if not res.ok:
        alert = dmc.Alert(
            res.message or "Đăng nhập không thành công",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
            mb="md",
        )
        return dash.no_update, alert

    assert res.data is not None
    login_session(res.data)

    if res.data.must_change_pw:
        return "/login?step=change", None
    return "/", None


@callback(
    Output("login-redirect-loc", "href", allow_duplicate=True),
    Output("change-alert-container", "children"),
    Input("change-submit-btn", "n_clicks"),
    State("change-new-pw", "value"),
    State("change-confirm-pw", "value"),
    prevent_initial_call=True,
)
def handle_forced_password_change(n_clicks: int, new_pw: str | None, confirm_pw: str | None) -> tuple[Any, Any]:
    if not n_clicks:
        return dash.no_update, dash.no_update

    if not new_pw or not confirm_pw:
        alert = dmc.Alert(
            "Vui lòng nhập mật khẩu mới và xác nhận lại",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
            mb="md",
        )
        return dash.no_update, alert

    if new_pw != confirm_pw:
        alert = dmc.Alert(
            "Hai mật khẩu nhập lại chưa trùng khớp",
            color="red",
            icon=DashIconify(icon="lucide:alert-triangle"),
            mb="md",
        )
        return dash.no_update, alert

    ctx = get_current_ctx()
    if ctx is None:
        return "/login", None

    engine = get_recon_engine()
    new_hash = hash_password(new_pw)

    with engine.begin() as conn:
        conn.execute(
            update(recon_user)
            .where(recon_user.c.ID == ctx.user_id)
            .values(
                PASSWORD_HASH=new_hash,
                MUST_CHANGE_PW="N",
                SESSION_VERSION=recon_user.c.SESSION_VERSION + 1,
            )
        )

    # Đổi xong -> chuyển về trang chủ
    return "/", None
