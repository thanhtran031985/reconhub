from __future__ import annotations

import re
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html
from dash_iconify import DashIconify

from app.core.config import get_settings
from app.core.session import get_current_ctx
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.notification import notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/sso-flow",
        title="Kiến trúc Luồng SSO — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "sso_flow"


def set_sso_enabled_setting(enabled: bool) -> None:
    """Cập nhật trạng thái SSO vào cấu hình runtime và lưu bền vững vào file .env."""
    settings = get_settings()
    settings.SSO_ENABLED = enabled
    env_path = settings.PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            val_str = "true" if enabled else "false"
            if re.search(r"^SSO_ENABLED=.*$", content, flags=re.MULTILINE):
                new_content = re.sub(
                    r"^SSO_ENABLED=.*$",
                    f"SSO_ENABLED={val_str}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                new_content = content + f"\nSSO_ENABLED={val_str}\n"
            env_path.write_text(new_content, encoding="utf-8")
        except Exception:
            pass


def _render_status_badge(enabled: bool) -> dmc.Badge:
    if enabled:
        return dmc.Badge("SSO Đang Bật", color="green", variant="filled", size="sm")
    return dmc.Badge("SSO Đang Tắt (Local Only)", color="gray", variant="light", size="sm")


def layout() -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="sso-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập sơ đồ kiến trúc SSO.", tone="crit"),
            ]
        )

    settings = get_settings()
    status_badge = _render_status_badge(settings.SSO_ENABLED)

    return dmc.Container(
        fluid=True,
        px="md",
        py="xs",
        children=[
            html.Div(id="sso-toast-container"),
            # Header trang: Full width, tinh gọn
            page_header(
                title="Sơ đồ Kiến trúc & Luồng Xác thực SSO",
                actions=[
                    dmc.Group(
                        [
                            dmc.Badge(
                                f"Server: {settings.SSO_SERVER_URL}",
                                variant="outline",
                                color="gray",
                                size="sm",
                                h=20,
                                style={"textTransform": "none"},
                            ),
                            dmc.Badge(
                                "Callback: /auth/sso/callback",
                                variant="outline",
                                color="gray",
                                size="sm",
                                h=20,
                                style={"textTransform": "none"},
                            ),
                            dmc.Badge(
                                "TTL: 60s",
                                variant="outline",
                                color="gray",
                                size="sm",
                                h=20,
                                style={"textTransform": "none"},
                            ),
                            dmc.Badge(
                                f"Phiên: {settings.SESSION_HOURS}h",
                                variant="outline",
                                color="gray",
                                size="sm",
                                h=20,
                                style={"textTransform": "none"},
                            ),
                            html.Div(id="sso-status-badge-container", children=status_badge),
                            dmc.Switch(
                                id="sso-toggle-switch",
                                checked=settings.SSO_ENABLED,
                                label="Bật SSO",
                                size="sm",
                                color="primary",
                            ),
                            html.A(
                                dmc.Badge(
                                    "Thử nghiệm Đăng nhập SSO",
                                    leftSection=DashIconify(icon="lucide:log-in", width=12),
                                    color="primary",
                                    variant="filled",
                                    size="sm",
                                    h=20,
                                    style={"cursor": "pointer", "textTransform": "none", "lineHeight": "20px"},
                                ),
                                href="/auth/sso/login",
                                target="_blank",
                                style={"textDecoration": "none", "display": "inline-flex", "alignItems": "center"},
                            ),
                            html.A(
                                dmc.Badge(
                                    "Mở toàn màn hình",
                                    leftSection=DashIconify(icon="lucide:maximize-2", width=12),
                                    color="gray",
                                    variant="light",
                                    size="sm",
                                    h=20,
                                    style={"cursor": "pointer", "textTransform": "none", "lineHeight": "20px"},
                                ),
                                href="/assets/sso_flow_archify.html",
                                target="_blank",
                                style={"textDecoration": "none", "display": "inline-flex", "alignItems": "center"},
                            ),
                        ],
                        gap="xs",
                        align="center",
                    ),
                ],
            ),
            # Khung sơ đồ Archify Interactive (Sơ đồ bên trái, Card diễn giải flow bên phải có nút ẩn/mở)
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p=4,
                mt="xs",
                style={"backgroundColor": "var(--surface, #ffffff)"},
                children=[
                    html.Iframe(
                        src="/assets/sso_flow_archify.html",
                        id="sso-archify-frame",
                        style={
                            "width": "100%",
                            "height": "calc(100vh - 120px)",
                            "minHeight": "640px",
                            "border": "none",
                            "display": "block",
                            "backgroundColor": "transparent",
                        },
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("sso-status-badge-container", "children"),
    Output("sso-toast-container", "children"),
    Input("sso-toggle-switch", "checked"),
    prevent_initial_call=True,
)
def handle_toggle_sso(is_checked: bool) -> tuple[Any, Any]:
    """Xử lý bật/tắt SSO trực tiếp trên giao diện."""
    set_sso_enabled_setting(is_checked)
    badge = _render_status_badge(is_checked)
    msg = "Đã kích hoạt chế độ đăng nhập SSO." if is_checked else "Đã tắt chế độ đăng nhập SSO (chỉ dùng tài khoản cục bộ)."
    notif = notify_success(msg, title="Cập nhật cấu hình")
    return badge, notif
