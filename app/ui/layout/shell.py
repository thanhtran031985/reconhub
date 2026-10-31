from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import select

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting
from app.services.temp_data import usage
from app.ui.components.alert_box import alert_box
from app.ui.formatters import format_bytes


def build_breadcrumbs(pathname: str | None) -> list[dict[str, str]]:
    """Tạo breadcrumbs dựa trên đường dẫn hiện tại."""
    if not pathname or pathname == "/":
        return [{"label": "Trang chủ", "href": "/"}]

    items: list[dict[str, str]] = [{"label": "Trang chủ", "href": "/"}]

    if pathname.startswith("/templates/new"):
        items.extend([
            {"label": "Templates", "href": "/templates"},
            {"label": "Đăng ký mới"},
        ])
    elif pathname.startswith("/templates/") and pathname.endswith("/diagram"):
        items.extend([
            {"label": "Templates", "href": "/templates"},
            {"label": "Sơ đồ diễn giải"},
        ])
    elif pathname == "/templates":
        items.extend([
            {"label": "Cấu hình"},
            {"label": "Templates"},
        ])
    elif pathname == "/runs/new":
        items.extend([
            {"label": "Đối soát"},
            {"label": "Chạy đối soát"},
        ])
    elif pathname.startswith("/runs/"):
        items.extend([
            {"label": "Lịch sử", "href": "/history"},
            {"label": "Kết quả run"},
        ])
    elif pathname == "/history":
        items.extend([
            {"label": "Đối soát"},
            {"label": "Lịch sử run"},
        ])
    elif pathname == "/data-sources":
        items.extend([
            {"label": "Cấu hình"},
            {"label": "Data Sources & Lưu trữ"},
        ])
    elif pathname == "/users":
        items.extend([
            {"label": "Hệ thống"},
            {"label": "Người dùng"},
        ])
    elif pathname == "/account":
        items.extend([
            {"label": "Tài khoản cá nhân"},
        ])
    elif pathname == "/dev/ui":
        items.extend([
            {"label": "Phát triển"},
            {"label": "Thư viện UI"},
        ])
    else:
        items.append({"label": pathname.strip("/").capitalize()})

    return items


def get_nav_items_for_roles(roles: set[Role] | set[str]) -> list[dict[str, Any]]:
    """Trả về danh sách mục menu navbar phù hợp với vai trò của người dùng."""
    norm_roles = {str(r).upper() for r in roles}
    is_admin = ("ADMIN" in norm_roles) or ("AD" in norm_roles)
    is_to = ("TEMPLATE_OWNER" in norm_roles) or ("TO" in norm_roles)
    is_op = ("OPERATOR" in norm_roles) or ("OP" in norm_roles)

    groups: list[dict[str, Any]] = []

    # Nhóm 1: Đối soát
    recon_items: list[dict[str, str]] = [
        {"label": "Dashboard", "href": "/", "icon": "lucide:layout-dashboard"},
    ]
    if is_admin or is_to or is_op:
        recon_items.append({"label": "Chạy đối soát", "href": "/runs/new", "icon": "lucide:play-circle"})
    recon_items.append({"label": "Lịch sử", "href": "/history", "icon": "lucide:history"})

    groups.append({"title": "ĐỐI SOÁT", "items": recon_items})

    # Nhóm 2: Cấu hình
    config_items: list[dict[str, str]] = []
    if is_admin or is_to or is_op:
        config_items.append({"label": "Templates", "href": "/templates", "icon": "lucide:file-spreadsheet"})
    if is_admin or is_to:
        config_items.append({"label": "Đăng ký template", "href": "/templates/new", "icon": "lucide:file-plus"})
    if is_admin:
        config_items.append({"label": "Data Sources", "href": "/data-sources", "icon": "lucide:database"})
        config_items.append({"label": "Người dùng", "href": "/users", "icon": "lucide:users"})

    if config_items:
        groups.append({"title": "CẤU HÌNH", "items": config_items})

    # Nhóm 3: Hệ thống
    sys_items: list[dict[str, str]] = []
    if is_admin:
        sys_items.append({"label": "Thư viện UI", "href": "/dev/ui", "icon": "lucide:palette"})

    if sys_items:
        groups.append({"title": "HỆ THỐNG", "items": sys_items})

    return groups


def render_banners(
    is_maintenance: bool,
    storage_warning: bool,
    user_roles: set[Role] | set[str],
    temp_bytes: int,
    warning_gb: float,
) -> list[Any]:
    """Tạo danh sách banner thông báo (bảo trì & cảnh báo dữ liệu tạm)."""
    banners: list[Any] = []
    norm_roles = {str(r).upper() for r in user_roles}
    is_admin = ("ADMIN" in norm_roles) or ("AD" in norm_roles)

    if is_maintenance:
        banners.append(
            alert_box(
                title="Hệ thống đang bảo trì",
                message="Hệ thống đang ở chế độ bảo trì. Một số tác vụ ghi và chạy đối soát có thể bị tạm dừng.",
                tone="warn",
                icon="lucide:alert-triangle",
                mb="sm",
            )
        )

    if storage_warning and is_admin:
        banners.append(
            alert_box(
                title="Cảnh báo dung lượng dữ liệu tạm",
                message=f"Dung lượng dữ liệu tạm đã đạt {format_bytes(temp_bytes)} vượt ngưỡng cảnh báo ({warning_gb:.1f} GB).",
                tone="warn",
                icon="lucide:database",
                action=dmc.Anchor("Xem và xóa dữ liệu tạm →", href="/data-sources?tab=storage", size="xs", fw=600),
                mb="sm",
            )
        )

    return banners


def create_header(ctx: Ctx | None, env: str, pathname: str | None) -> Any:
    """Tạo thanh header 56px với breadcrumb, nhãn ENV và User Menu."""
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

    breadcrumbs_data = build_breadcrumbs(pathname)
    bc_elements: list[Any] = []
    for i, b in enumerate(breadcrumbs_data):
        if "href" in b and i < len(breadcrumbs_data) - 1:
            bc_elements.append(
                dmc.Anchor(b["label"], href=b["href"], size="sm", c="dimmed", underline=False)
            )
        else:
            bc_elements.append(dmc.Text(b["label"], size="sm", fw=600, c="dark"))

    return dmc.Group(
        [
            dmc.Breadcrumbs(children=bc_elements, separator="/"),
            dmc.Group(
                [
                    dmc.Badge(env.upper(), color=env_badge_color, variant="light", size="sm"),
                    user_menu if user_menu is not None else html.Div(),
                ],
                gap="md",
            ),
        ],
        justify="space-between",
        align="center",
        h="100%",
        px="lg",
    )


def create_navbar(ctx: Ctx | None, pathname: str | None) -> Any:
    """Tạo thanh navbar 232px nền nav-bg với các nhóm menu phân quyền."""
    roles = set(ctx.roles) if ctx else set()
    nav_groups = get_nav_items_for_roles(roles)

    content_children: list[Any] = [
        # Logo ReconHub
        dmc.Box(
            dmc.Anchor(
                dmc.Group(
                    [
                        dmc.ThemeIcon(
                            DashIconify(icon="lucide:layers", width=22),
                            size="lg",
                            radius="md",
                            color="primary",
                            variant="filled",
                        ),
                        dmc.Text("ReconHub", fw=700, size="lg", c="white"),
                    ],
                    gap="xs",
                ),
                href="/",
                underline=False,
            ),
            p="md",
            style={"borderBottom": "1px solid rgba(255, 255, 255, 0.1)"},
        )
    ]

    for group in nav_groups:
        content_children.append(
            dmc.Text(
                group["title"],
                size="xs",
                fw=700,
                c="dimmed",
                px="md",
                pt="md",
                pb="xs",
                style={"letterSpacing": "0.5px"},
            )
        )
        for item in group["items"]:
            is_active = (pathname == item["href"]) or (
                item["href"] != "/" and pathname is not None and pathname.startswith(item["href"])
            )
            content_children.append(
                dmc.NavLink(
                    label=item["label"],
                    leftSection=DashIconify(icon=item["icon"], width=18),
                    href=item["href"],
                    active=is_active,
                    variant="filled",
                    color="primary",
                    px="md",
                    py="xs",
                    styles={"label": {"fontWeight": 500}},
                )
            )

    return dmc.Stack(
        content_children,
        gap=0,
        h="100%",
        bg="nav-bg",
    )


def create_shell_layout() -> Any:
    """Layout gốc kết hợp Location và container AppShell."""
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

    if pathname == "/login":
        return dash.page_container

    # Lấy thông tin bảo trì và dung lượng tạm
    is_maintenance = False
    temp_bytes = 0
    warning_gb = 2.0
    storage_warn = False

    try:
        engine = get_recon_engine()
        with engine.connect() as conn:
            stmt = select(recon_app_setting.c.SETTING_VALUE).where(
                recon_app_setting.c.SETTING_KEY == "MAINTENANCE_MODE"
            )
            row = conn.execute(stmt).fetchone()
            if row and row[0] == "Y":
                is_maintenance = True

        if ctx and Role.ADMIN in ctx.roles:
            res_usage = usage(ctx)
            if res_usage.ok and res_usage.data:
                temp_bytes = res_usage.data.temp_bytes
                warning_gb = res_usage.data.warning_gb
                storage_warn = res_usage.data.is_warning
    except Exception:
        pass

    header_content = create_header(ctx, settings.APP_ENV, pathname)
    navbar_content = create_navbar(ctx, pathname)
    user_roles = set(ctx.roles) if ctx else set()
    banners = render_banners(is_maintenance, storage_warn, user_roles, temp_bytes, warning_gb)

    main_content: list[Any] = []
    if banners:
        main_content.append(dmc.Box(banners, px="lg", pt="md"))
    main_content.append(dash.page_container)

    return dmc.AppShell(
        header={"height": 56},
        navbar={"width": 232, "breakpoint": "sm"},
        children=[
            dmc.AppShellHeader(header_content),
            dmc.AppShellNavbar(navbar_content),
            dmc.AppShellMain(main_content),
        ],
    )
