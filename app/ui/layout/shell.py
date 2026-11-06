from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.context import Ctx, Role
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting
from app.services.data_source import get_active_environment
from app.services.perm import effective_menus, get_perm_revision, is_admin, user_role_codes
from app.services.temp_data import usage
from app.ui.components.alert_box import alert_box
from app.ui.formatters import format_bytes
from app.ui.menus import GROUPS, MENUS


def build_breadcrumbs(pathname: str | None) -> list[dict[str, str]]:
    """Tạo breadcrumbs dựa trên đường dẫn hiện tại."""
    if not pathname or pathname == "/":
        return [{"label": "Trang chủ", "href": "/"}]

    items: list[dict[str, str]] = [{"label": "Trang chủ", "href": "/"}]

    if pathname.startswith("/templates/new"):
        items.extend(
            [
                {"label": "Templates", "href": "/templates"},
                {"label": "Đăng ký mới"},
            ]
        )
    elif pathname.startswith("/templates/") and pathname.endswith("/diagram"):
        items.extend(
            [
                {"label": "Templates", "href": "/templates"},
                {"label": "Sơ đồ diễn giải"},
            ]
        )
    elif pathname == "/templates":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Templates"},
            ]
        )
    elif pathname == "/runs/new":
        items.extend(
            [
                {"label": "Đối soát"},
                {"label": "Chạy đối soát"},
            ]
        )
    elif pathname.startswith("/runs/"):
        items.extend(
            [
                {"label": "Lịch sử", "href": "/history"},
                {"label": "Kết quả run"},
            ]
        )
    elif pathname == "/history":
        items.extend(
            [
                {"label": "Đối soát"},
                {"label": "Lịch sử run"},
            ]
        )
    elif pathname == "/issues":
        items.extend(
            [
                {"label": "Đối soát"},
                {"label": "Xử lý chênh lệch"},
            ]
        )
    elif pathname == "/data-sources":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Data Sources & Lưu trữ"},
            ]
        )
    elif pathname == "/lookups":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Danh mục Lookups"},
            ]
        )
    elif pathname == "/users":
        items.extend(
            [
                {"label": "Hệ thống"},
                {"label": "Người dùng"},
            ]
        )
    elif pathname == "/account":
        items.extend(
            [
                {"label": "Tài khoản cá nhân"},
            ]
        )
    elif pathname == "/dev/ui":
        items.extend(
            [
                {"label": "Phát triển"},
                {"label": "Thư viện UI"},
            ]
        )
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
    recon_items.append({"label": "Xử lý chênh lệch", "href": "/issues", "icon": "lucide:alert-circle"})

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
        config_items.append({"label": "Danh mục Lookups", "href": "/lookups", "icon": "lucide:list"})

    if config_items:
        groups.append({"title": "CẤU HÌNH", "items": config_items})

    # Nhóm 3: Hệ thống
    sys_items: list[dict[str, str]] = []
    if is_admin:
        sys_items.append({"label": "Thư viện UI", "href": "/dev/ui", "icon": "lucide:palette"})

    if sys_items:
        groups.append({"title": "HỆ THỐNG", "items": sys_items})

    return groups


# Menu có trong effective_menus nhưng chưa có trang thanh bên: "result" là
# trang chi tiết run (/runs/<id>), "batch_run"/"batch_def" thuộc task 18
# (chưa làm), "menu_admin" thuộc task 20 (Q7: khai báo + seed nhưng ẩn
# khỏi thanh bên tới task 20). Khi các task đó xong, bỏ mã khỏi tập này.
_SIDEBAR_SKIP_CODES = {"result", "batch_run", "batch_def", "menu_admin"}


def get_nav_items_for_menus(menus: set[str], engine: Any = None, is_admin: bool = False) -> list[dict[str, Any]]:
    """Nhóm menu thanh bên từ menu hiệu lực của người dùng (task 19, 20).

    Nhóm/menu lấy tên, thứ tự hiển thị từ DB (DISPLAY_*), không lấy từ
    code (task 20 bước 3); chưa migration thì dùng lại hằng số code.
    Menu đã gỡ không hiện với ai; menu đang ẩn chỉ hiện với ADMIN, kèm
    nhãn "Đang ẩn" (bước 2); menu mới gắn cờ is_new để ADMIN thấy nhãn
    "Mới" (bước 3). `menu_admin` đang ẩn nên cũng không hiện, theo Q7 —
    tới bước 4 mới mở.
    """
    visible = set(menus)
    engine = engine or get_recon_engine()
    tree = _sidebar_tree(engine)
    if tree is None:
        groups_src = [{"code": g.code, "label": g.label, "order": g.order} for g in GROUPS]
        menus_src = [
            {
                "code": m.code,
                "label": m.label,
                "path": m.path,
                "icon": m.icon,
                "group": m.group,
                "order": m.order,
                "is_hidden": False,
                "is_removed": False,
                "is_new": False,
            }
            for m in MENUS
        ]
    else:
        groups_src = tree["groups"]
        menus_src = tree["menus"]
    groups: list[dict[str, Any]] = []
    for group in sorted(groups_src, key=lambda g: g["order"]):
        items: list[dict[str, Any]] = []
        for menu in sorted([m for m in menus_src if m["group"] == group["code"]], key=lambda m: m["order"]):
            if menu["code"] not in visible or menu["code"] in _SIDEBAR_SKIP_CODES:
                continue
            if menu["is_removed"]:
                continue
            label = str(menu["label"])
            if menu["is_hidden"]:
                if not is_admin:
                    continue
                label = f"{label} (Đang ẩn)"
            item: dict[str, Any] = {"label": label, "href": menu["path"], "icon": menu["icon"]}
            if menu["is_new"] and is_admin:
                item["is_new"] = True
            items.append(item)
        if items:
            groups.append({"title": group["label"].upper(), "items": items})
    return groups


def _sidebar_tree(engine: Any) -> dict[str, Any] | None:
    """Cây nhóm + menu hiển thị từ DB; None khi chưa có bảng menu (pre-migration)."""
    try:
        names = inspect(engine).get_table_names()
    except SQLAlchemyError:
        return None
    if "RECON_MENU" not in names or "RECON_MENU_GROUP" not in names:
        return None
    from app.services.menu_sync import read_display_tree

    with engine.connect() as conn:
        return read_display_tree(conn)


def first_nav_href(ctx: Ctx | None, engine: Any = None) -> str | None:
    """Href của mục thanh bên đầu tiên người dùng có (task 20, Q2).

    Dùng khi trang chủ bị ẩn: chuyển tới menu đầu tiên thay vì trang
    "Chức năng tạm ngưng". Trả None khi người dùng không có menu nào.
    """
    if ctx is None:
        return None
    groups = get_nav_items_for_menus(effective_menus(ctx, engine=engine), engine=engine, is_admin=is_admin(ctx))
    for group in groups:
        for item in group["items"]:
            return str(item["href"])
    return None


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


def create_header(ctx: Ctx | None, env: str, pathname: str | None, is_mini: bool = False) -> Any:
    """Tạo thanh header 56px với nút toggle sidebar, breadcrumb, nhãn ENV và User Menu."""
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
                            refresh=True,
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
            bc_elements.append(dmc.Anchor(b["label"], href=b["href"], size="sm", c="dimmed", underline=False))
        else:
            bc_elements.append(dmc.Text(b["label"], size="sm", fw=600, c="dark"))

    toggle_button = dmc.Tooltip(
        dmc.ActionIcon(
            DashIconify(
                icon="lucide:panel-left-open" if is_mini else "lucide:panel-left-close",
                width=18,
            ),
            id="app-sidebar-toggle-btn",
            variant="subtle",
            color="gray",
            size="md",
        ),
        id="app-sidebar-toggle-tooltip",
        label="Mở rộng menu" if is_mini else "Thu nhỏ menu",
        position="bottom",
        withArrow=True,
    )

    return dmc.Group(
        [
            dmc.Group(
                [
                    toggle_button,
                    dmc.Breadcrumbs(children=bc_elements, separator="/"),
                ],
                gap="md",
                align="center",
            ),
            dmc.Group(
                [
                    dmc.Badge(
                        env.upper(),
                        id="app-header-env-badge",
                        color=env_badge_color,
                        variant="light",
                        size="sm",
                    ),
                    dmc.ColorSchemeToggle(
                        id="app-color-scheme-toggle",
                        lightIcon=DashIconify(icon="lucide:sun", width=16),
                        darkIcon=DashIconify(icon="lucide:moon", width=16),
                        variant="subtle",
                        color="gray",
                        size="sm",
                    ),
                    user_menu if user_menu is not None else html.Div(),
                ],
                gap="sm",
                align="center",
            ),
        ],
        justify="space-between",
        align="center",
        h="100%",
        px="lg",
    )


def get_active_nav_href(nav_groups: list[dict[str, Any]], pathname: str | None) -> str | None:
    """Xác định href của mục menu đang active phù hợp nhất với pathname."""
    if not pathname:
        return "/"

    all_hrefs = [item["href"] for group in nav_groups for item in group["items"] if "href" in item]

    # 1. So khớp chính xác tuyệt đối
    if pathname in all_hrefs:
        return pathname

    # 2. So khớp tiền tố dài nhất (loại trừ root "/" để không kích hoạt nhầm)
    matched_href: str | None = None
    for h in all_hrefs:
        if h == "/":
            continue
        if pathname.startswith(f"{h}/") or pathname.startswith(f"{h}?"):
            if matched_href is None or len(h) > len(matched_href):
                matched_href = h

    return matched_href


def create_navbar(ctx: Ctx | None, pathname: str | None, is_mini: bool = False) -> Any:
    """Tạo thanh navbar 232px (hoặc 60px mini) với các nhóm menu phân quyền."""
    if ctx is None:
        nav_groups = get_nav_items_for_roles(set())
    else:
        nav_groups = get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))
    active_href = get_active_nav_href(nav_groups, pathname)

    content_children: list[Any] = []

    if not is_mini:
        # 1. Logo ReconHub Full
        content_children.append(
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
                            dmc.Text("ReconHub", fw=700, size="lg", c="dark"),
                        ],
                        gap="xs",
                        align="center",
                        h="100%",
                    ),
                    href="/",
                    underline=False,
                ),
                px="md",
                h="56px",
                style={
                    "borderBottom": "1px solid var(--mantine-color-gray-2)",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )

        # 2. Các nhóm menu
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
                is_active = item["href"] == active_href
                label_node: Any = item["label"]
                if item.get("is_new"):
                    label_node = dmc.Group(
                        [
                            dmc.Text(item["label"], size="sm", fw=500),
                            dmc.Badge("Mới", size="xs", color="green", variant="light"),
                        ],
                        gap="xs",
                    )
                content_children.append(
                    dmc.NavLink(
                        label=label_node,
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
    else:
        # Mini mode (Rail 60px)
        # 1. Logo Icon centered kèm Tooltip
        content_children.append(
            dmc.Box(
                dmc.Anchor(
                    dmc.Tooltip(
                        dmc.ThemeIcon(
                            DashIconify(icon="lucide:layers", width=22),
                            size="lg",
                            radius="md",
                            color="primary",
                            variant="filled",
                        ),
                        label="ReconHub Trang chủ",
                        position="right",
                        withArrow=True,
                        offset=12,
                    ),
                    href="/",
                    underline=False,
                    style={"display": "flex", "justifyContent": "center", "alignItems": "center"},
                ),
                h="56px",
                w="100%",
                style={
                    "borderBottom": "1px solid var(--mantine-color-gray-2)",
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                },
            )
        )

        # 2. Icon các mục menu dạng ActionIcon giống icon trang chủ kèm Tooltip
        for idx, group in enumerate(nav_groups):
            if idx > 0:
                content_children.append(
                    dmc.Box(
                        dmc.Divider(color="var(--mantine-color-gray-2)"),
                        px="sm",
                        py="xs",
                        w="100%",
                    )
                )
            for item in group["items"]:
                is_active = item["href"] == active_href
                content_children.append(
                    dmc.Box(
                        dmc.Anchor(
                            dmc.Tooltip(
                                dmc.ActionIcon(
                                    DashIconify(icon=item["icon"], width=20),
                                    size="lg",
                                    radius="md",
                                    variant="filled" if is_active else "subtle",
                                    color="primary" if is_active else "gray",
                                    styles={
                                        "root": {
                                            "color": "#ffffff" if is_active else "var(--mantine-color-gray-7)",
                                        }
                                    },
                                ),
                                label=item["label"],
                                position="right",
                                withArrow=True,
                                offset=12,
                                transitionProps={"transition": "fade", "duration": 150},
                            ),
                            href=item["href"],
                            underline=False,
                            style={"display": "flex", "justifyContent": "center", "alignItems": "center"},
                        ),
                        py=4,
                        w="100%",
                        style={"display": "flex", "justifyContent": "center", "alignItems": "center"},
                    )
                )

    return dmc.Stack(
        content_children,
        gap=0,
        h="100%",
        align="center" if is_mini else "stretch",
        style={"overflowX": "hidden"},
    )


def create_shell_layout() -> Any:
    """Layout gốc kết hợp Location, Store trạng thái sidebar và container AppShell."""
    return html.Div(
        [
            dcc.Location(id="app-location", refresh=False),
            dcc.Store(id="app-sidebar-collapsed", storage_type="local", data=False),
            # Kiểm tra PERM_REVISION mỗi 5 giây: đổi quyền thì dựng lại
            # thanh bên trong tối đa 5 giây (spec 11 mục 6).
            dcc.Store(id="app-perm-revision", data=None),
            dcc.Interval(id="app-perm-revision-check", interval=5000, n_intervals=0),
            html.Div(id="app-shell-container"),
        ]
    )


@callback(
    Output("app-shell-container", "children"),
    Input("app-location", "pathname"),
    State("app-sidebar-collapsed", "data"),
)
def render_app_shell(pathname: str | None, is_collapsed_data: Any) -> Any:
    ctx = get_current_ctx()

    if pathname == "/login":
        return dash.page_container

    is_mini = bool(is_collapsed_data)

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

        if ctx and is_admin(ctx):
            res_usage = usage(ctx)
            if res_usage.ok and res_usage.data:
                temp_bytes = res_usage.data.temp_bytes
                warning_gb = res_usage.data.warning_gb
                storage_warn = res_usage.data.is_warning
    except Exception:
        pass

    active_env = get_active_environment()
    header_content = create_header(ctx, active_env, pathname, is_mini=is_mini)
    navbar_content = create_navbar(ctx, pathname, is_mini=is_mini)
    user_roles = user_role_codes(ctx) if ctx else set()
    banners = render_banners(is_maintenance, storage_warn, user_roles, temp_bytes, warning_gb)

    main_content: list[Any] = []
    if banners:
        main_content.append(dmc.Box(banners, px="lg", pt="md"))
    main_content.append(dash.page_container)

    return dmc.AppShell(
        id="app-shell",
        header={"height": 56},
        navbar={"width": 60 if is_mini else 232, "breakpoint": "sm"},
        children=[
            dmc.AppShellHeader(header_content),
            dmc.AppShellNavbar(id="app-shell-navbar", children=navbar_content),
            dmc.AppShellMain(main_content),
        ],
    )


@callback(
    Output("app-shell-navbar", "children", allow_duplicate=True),
    Output("app-perm-revision", "data", allow_duplicate=True),
    Input("app-perm-revision-check", "n_intervals"),
    State("app-perm-revision", "data"),
    State("app-sidebar-collapsed", "data"),
    State("app-location", "pathname"),
    prevent_initial_call=True,
)
def handle_perm_revision_check(
    _n_intervals: int, last_revision: Any, is_collapsed_data: Any, pathname: str | None
) -> tuple[Any, Any]:
    """Dựng lại thanh bên khi PERM_REVISION đổi (quyền vừa bị thu/hồi)."""
    if pathname == "/login":
        raise dash.exceptions.PreventUpdate
    try:
        revision = get_perm_revision()
    except Exception:
        raise dash.exceptions.PreventUpdate from None
    if revision == last_revision:
        raise dash.exceptions.PreventUpdate
    ctx = get_current_ctx()
    navbar_children = create_navbar(ctx, pathname, is_mini=bool(is_collapsed_data))
    return navbar_children, revision


@callback(
    Output("app-sidebar-collapsed", "data"),
    Input("app-sidebar-toggle-btn", "n_clicks"),
    State("app-sidebar-collapsed", "data"),
    prevent_initial_call=True,
)
def handle_sidebar_toggle(n_clicks: Any, current: Any) -> bool:
    """Đổi trạng thái thu nhỏ / mở rộng của sidebar khi người dùng click nút."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return not bool(current)


@callback(
    Output("app-shell", "navbar"),
    Output("app-shell-navbar", "children"),
    Output("app-sidebar-toggle-btn", "children"),
    Output("app-sidebar-toggle-tooltip", "label"),
    Input("app-sidebar-collapsed", "data"),
    State("app-location", "pathname"),
    prevent_initial_call=True,
)
def sync_sidebar_ui(is_collapsed: Any, pathname: str | None) -> tuple[Any, ...]:
    """Cập nhật giao diện navbar (width, icons, tooltips) theo trạng thái collapsed."""
    if pathname == "/login":
        raise dash.exceptions.PreventUpdate

    is_mini = bool(is_collapsed)
    ctx = get_current_ctx()
    navbar_config = {"width": 60 if is_mini else 232, "breakpoint": "sm"}
    navbar_children = create_navbar(ctx, pathname, is_mini=is_mini)
    toggle_icon = DashIconify(
        icon="lucide:panel-left-open" if is_mini else "lucide:panel-left-close",
        width=18,
    )
    toggle_label = "Mở rộng menu" if is_mini else "Thu nhỏ menu"
    return navbar_config, navbar_children, toggle_icon, toggle_label
