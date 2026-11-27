from __future__ import annotations

import time
import unicodedata
from typing import Any
from weakref import WeakKeyDictionary

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.context import Ctx, Role
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_app_setting, recon_notification
from app.services.data_source import get_active_environment
from app.services.notification import (
    count_unread,
    list_notifications,
    mark_all_read,
    mark_read,
    maybe_notify_worker_health,
)
from app.services.perm import (
    effective_menus,
    get_perm_revision,
    is_admin,
    register_cache_clear_hook,
    user_role_codes,
)
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
    elif pathname == "/menus":
        items.extend(
            [
                {"label": "Quản trị"},
                {"label": "Danh sách menu"},
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
    elif pathname == "/batches":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Bộ đối soát"},
            ]
        )
    elif pathname.startswith("/batches/"):
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Bộ đối soát", "href": "/batches"},
                {"label": "Chi tiết"},
            ]
        )
    elif pathname.startswith("/batch-runs") and pathname.endswith("/result"):
        items.extend(
            [
                {"label": "Đối soát"},
                {"label": "Kết quả lần chạy bộ"},
            ]
        )
    elif pathname.startswith("/batch-runs"):
        items.extend(
            [
                {"label": "Đối soát"},
                {"label": "Chạy bộ đối soát"},
            ]
        )
    elif pathname == "/report-models":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Mô hình báo cáo"},
            ]
        )
    elif pathname.startswith("/report-models/"):
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Mô hình báo cáo", "href": "/report-models"},
                {"label": "Model Studio"},
            ]
        )
    elif pathname == "/report-studio":
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Report Studio"},
            ]
        )
    elif pathname.startswith("/report-studio/"):
        items.extend(
            [
                {"label": "Cấu hình"},
                {"label": "Report Studio", "href": "/report-studio"},
                {"label": "Thiết kế báo cáo"},
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
        recon_items.append({"label": "Chạy bộ đối soát", "href": "/batch-runs", "icon": "lucide:layers"})
    recon_items.append({"label": "Lịch sử", "href": "/history", "icon": "lucide:history"})
    recon_items.append({"label": "Xử lý chênh lệch", "href": "/issues", "icon": "lucide:alert-circle"})

    groups.append({"title": "ĐỐI SOÁT", "items": recon_items})

    # Nhóm 2: Cấu hình
    config_items: list[dict[str, str]] = []
    if is_admin or is_to or is_op:
        config_items.append({"label": "Templates", "href": "/templates", "icon": "lucide:file-spreadsheet"})
    if is_admin or is_to:
        config_items.append({"label": "Đăng ký template", "href": "/templates/new", "icon": "lucide:file-plus"})
    if is_admin or is_to or is_op:
        config_items.append({"label": "Bộ đối soát", "href": "/batches", "icon": "lucide:layers"})
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
# trang chi tiết run (/runs/<id>).
_SIDEBAR_SKIP_CODES = {"result"}


def get_nav_items_for_menus(menus: set[str], engine: Any = None, is_admin: bool = False) -> list[dict[str, Any]]:
    """Nhóm menu thanh bên từ menu hiệu lực của người dùng (task 19, 20).

    Nhóm/menu lấy tên, thứ tự hiển thị từ DB (DISPLAY_*), không lấy từ
    code (task 20 bước 3); chưa migration thì dùng lại hằng số code.
    Menu đã gỡ không hiện với ai; menu đang ẩn chỉ hiện với ADMIN, kèm
    nhãn "Đang ẩn" (bước 2); cờ is_new vẫn gắn vào nav item nhưng thanh
    bên không còn hiển thị nhãn "Mới" (task 30). `menu_admin` mở từ
    bước 4 (trang /menus).
    """
    visible = set(menus)
    engine = engine or get_recon_engine()
    tree = _sidebar_tree(engine)
    groups_src: list[dict[str, Any]]
    menus_src: list[dict[str, Any]]
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


_SIDEBAR_TABLES_READY: WeakKeyDictionary[Engine, bool] = WeakKeyDictionary()
_SIDEBAR_TREE_CACHE: WeakKeyDictionary[Engine, tuple[int, float, dict[str, Any] | None]] = WeakKeyDictionary()
_SIDEBAR_TREE_TTL_S = 10.0

_MAINT_CACHE: WeakKeyDictionary[Engine, tuple[bool, float]] = WeakKeyDictionary()
_MAINT_TTL_S = 30.0
_STORAGE_USAGE_CACHE: WeakKeyDictionary[Engine, dict[int, tuple[tuple[int, float, bool], float]]] = WeakKeyDictionary()
_STORAGE_USAGE_TTL_S = 300.0


def invalidate_sidebar_tree_cache() -> None:
    """Xóa cache cây menu thanh bên."""
    _SIDEBAR_TABLES_READY.clear()
    _SIDEBAR_TREE_CACHE.clear()


def invalidate_shell_meta_cache() -> None:
    """Xóa cache thông tin bảo trì và dung lượng tạm của shell."""
    _MAINT_CACHE.clear()
    _STORAGE_USAGE_CACHE.clear()


register_cache_clear_hook(invalidate_sidebar_tree_cache)
register_cache_clear_hook(invalidate_shell_meta_cache)


def _sidebar_tree(engine: Any) -> dict[str, Any] | None:
    """Cây nhóm + menu hiển thị từ DB (cache theo PERM_REVISION + TTL 10s)."""
    rev = get_perm_revision(engine)
    now = time.monotonic()
    cached = _SIDEBAR_TREE_CACHE.get(engine)
    if cached is not None and cached[0] == rev and (now - cached[1]) < _SIDEBAR_TREE_TTL_S:
        return cached[2]

    if not _SIDEBAR_TABLES_READY.get(engine):
        try:
            names = inspect(engine).get_table_names()
        except SQLAlchemyError:
            return None
        if "RECON_MENU" not in names or "RECON_MENU_GROUP" not in names:
            return None
        _SIDEBAR_TABLES_READY[engine] = True

    from app.services.menu_sync import read_display_tree

    with engine.connect() as conn:
        tree = read_display_tree(conn)
    _SIDEBAR_TREE_CACHE[engine] = (rev, now, tree)
    return tree


def _get_cached_maintenance_mode(engine: Engine) -> bool:
    """Kiểm tra chế độ bảo trì từ RECON_APP_SETTING (cache TTL 30s)."""
    now = time.monotonic()
    cached = _MAINT_CACHE.get(engine)
    if cached is not None and (now - cached[1]) < _MAINT_TTL_S:
        return cached[0]

    is_maint = False
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                select(recon_app_setting.c.VALUE).where(
                    recon_app_setting.c.KEY.in_(["MAINTENANCE", "MAINTENANCE_MODE"])
                )
            ).fetchall()
            is_maint = any(str(r[0]) == "Y" for r in rows if r and r[0] is not None)
    except Exception:
        is_maint = False
    _MAINT_CACHE[engine] = (is_maint, now)
    return is_maint


def _get_cached_storage_usage(ctx: Ctx, engine: Engine) -> tuple[int, float, bool]:
    """Đọc dung lượng dữ liệu tạm cho Admin (cache TTL 300s để tránh os.walk lặp)."""
    now = time.monotonic()
    by_user = _STORAGE_USAGE_CACHE.setdefault(engine, {})
    uid = int(ctx.user_id)
    cached = by_user.get(uid)
    if cached is not None and (now - cached[1]) < _STORAGE_USAGE_TTL_S:
        return cached[0]

    result = (0, 2.0, False)
    try:
        res_usage = usage(ctx)
        if res_usage.ok and res_usage.data:
            data = res_usage.data
            if isinstance(data, dict):
                t_bytes = int(data.get("total_bytes") or data.get("temp_bytes") or 0)
                w_gb = float(data.get("warn_gb") or data.get("warning_gb") or 2.0)
                is_warn = bool(data.get("is_warning", False))
            else:
                t_bytes = int(getattr(data, "total_bytes", getattr(data, "temp_bytes", 0)) or 0)
                w_gb = float(getattr(data, "warn_gb", getattr(data, "warning_gb", 2.0)) or 2.0)
                is_warn = bool(getattr(data, "is_warning", False))
            result = (t_bytes, w_gb, is_warn)
    except Exception:
        pass
    by_user[uid] = (result, now)
    return result


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


# --- Task 30: tìm kiếm menu ở header ---

MAX_MENU_SEARCH_RESULTS = 8

_MENU_SEARCH_RESULTS_STYLE: dict[str, Any] = {
    "position": "absolute",
    "top": "38px",
    "left": 0,
    "width": "320px",
    "zIndex": 1000,
    "maxHeight": "320px",
    "overflow": "auto",
    "display": "none",
}


def _strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt + chữ thường để so khớp tên menu không dấu."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("Đ", "D").replace("đ", "d").lower()


def _flatten_nav_items(nav_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Làm phẳng các nhóm menu thanh bên thành danh sách cho ô tìm kiếm."""
    return [
        {"label": item["label"], "href": item["href"], "icon": item["icon"], "group": group["title"]}
        for group in nav_groups
        for item in group["items"]
    ]


def filter_menu_items(items: list[dict[str, Any]] | None, query: str) -> list[dict[str, Any]]:
    """Lọc menu theo tên (khớp chuỗi con, có dấu hay không dấu đều ra)."""
    q = _strip_accents(query.strip())
    if not q:
        return []
    return [item for item in items or [] if q in _strip_accents(item["label"])]


def build_breadcrumb_nodes(pathname: str | None) -> list[Any]:
    """Dựng danh sách component cho dmc.Breadcrumbs từ pathname."""
    breadcrumbs_data = build_breadcrumbs(pathname)
    bc_elements: list[Any] = []
    for i, b in enumerate(breadcrumbs_data):
        if "href" in b and i < len(breadcrumbs_data) - 1:
            bc_elements.append(dmc.Anchor(b["label"], href=b["href"], size="sm", c="dimmed", underline=False))
        else:
            bc_elements.append(dmc.Text(b["label"], size="sm", fw=600, c="var(--ink)"))
    return bc_elements


def create_header(
    ctx: Ctx | None,
    env: str,
    pathname: str | None,
    is_mini: bool = False,
    nav_groups: list[dict[str, Any]] | None = None,
) -> Any:
    """Tạo thanh header 44px chuẩn Fluent Compact với nút toggle sidebar, breadcrumb, nhãn ENV và User Menu."""
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

    bc_elements = build_breadcrumb_nodes(pathname)

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

    # Task 30: ô tìm kiếm menu ở giữa header (sau breadcrumb, trước badge môi trường).
    # Danh sách lấy từ cùng nguồn với thanh bên nên chỉ hiện menu tài khoản được thấy.
    search_items: list[dict[str, Any]] = []
    if ctx is not None:
        resolved_groups = (
            nav_groups
            if nav_groups is not None
            else get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))
        )
        search_items = _flatten_nav_items(resolved_groups)
    menu_search = dmc.Box(
        [
            dcc.Store(id="app-menu-search-store", data=search_items),
            dmc.TextInput(
                id="app-menu-search-input",
                placeholder="Tìm kiếm menu...",
                leftSection=DashIconify(icon="lucide:search", width=16),
                radius="xl",
                size="sm",
                value="",
                style={"width": "320px"},
            ),
            dmc.Paper(
                id="app-menu-search-results-paper",
                children=[html.Div(id="app-menu-search-results")],
                shadow="md",
                radius="md",
                withBorder=True,
                style=dict(_MENU_SEARCH_RESULTS_STYLE),
            ),
        ],
        style={"position": "relative", "width": "320px"},
        visibleFrom="md",
    )

    # Task 78: chuông thông báo — badge số chưa đọc, bấm mở panel 5 mục mới nhất.
    bell: Any = html.Div()
    if ctx is not None:
        try:
            unread = count_unread(get_recon_engine(), ctx.user_id)
        except Exception:  # noqa: BLE001 — badge lỗi không được vỡ header
            unread = 0
        bell = dmc.Menu(
            [
                dmc.MenuTarget(
                    dmc.Indicator(
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:bell", width=18),
                            id="app-notif-bell",
                            variant="subtle",
                            color="gray",
                            size="md",
                            **{"aria-label": "Thông báo"},
                        ),
                        id="app-notif-indicator",
                        label=str(unread) if unread > 0 else "",
                        disabled=unread == 0,
                        color="red",
                        size=16,
                        position="top-end",
                    )
                ),
                dmc.MenuDropdown(
                    [
                        dmc.MenuLabel("Thông báo"),
                        # Task 79: tab Tất cả / Chưa đọc trong popover.
                        dmc.Tabs(
                            [
                                dmc.TabsList(
                                    [
                                        dmc.TabsTab("Tất cả", value="all"),
                                        dmc.TabsTab("Chưa đọc", value="unread"),
                                    ]
                                ),
                            ],
                            id="app-notif-tabs",
                            value="all",
                        ),
                        html.Div(id="app-notif-panel"),
                        dmc.MenuDivider(),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Đánh dấu tất cả đã đọc",
                                    id="app-notif-mark-all-read",
                                    variant="subtle",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:check", width=14),
                                ),
                                dmc.Anchor(
                                    "Xem tất cả →",
                                    href="/notifications",
                                    size="sm",
                                ),
                            ],
                            justify="space-between",
                            gap="xs",
                            px="xs",
                            pb="xs",
                        ),
                    ],
                    style={"width": "360px"},
                ),
            ],
            id="app-notif-menu",
            position="bottom-end",
            withArrow=True,
        )

    return dmc.Group(
        [
            dmc.Group(
                [
                    toggle_button,
                    dmc.Breadcrumbs(id="app-header-breadcrumbs", children=bc_elements, separator="/"),
                ],
                gap="md",
                align="center",
            ),
            menu_search,
            dmc.Group(
                [
                    dmc.Badge(
                        env.upper(),
                        id="app-header-env-badge",
                        color=env_badge_color,
                        variant="light",
                        size="sm",
                    ),
                    bell,
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
        px="md",
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


def create_navbar(
    ctx: Ctx | None,
    pathname: str | None,
    is_mini: bool = False,
    nav_groups: list[dict[str, Any]] | None = None,
) -> Any:
    """Tạo thanh navbar 200px (hoặc 48px rail mini) với các nhóm menu phân quyền và vạch active 3px."""
    if nav_groups is None:
        if ctx is None:
            nav_groups = get_nav_items_for_roles(set())
        else:
            nav_groups = get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))
    active_href = get_active_nav_href(nav_groups, pathname)

    content_children: list[Any] = []

    if not is_mini:
        # 1. Logo ReconHub Full (44px)
        content_children.append(
            dmc.Box(
                dmc.Anchor(
                    dmc.Group(
                        [
                            dmc.ThemeIcon(
                                DashIconify(icon="lucide:layers", width=20),
                                size="md",
                                radius="md",
                                color="primary",
                                variant="filled",
                            ),
                            dmc.Text("ReconHub", fw=700, size="md", c="var(--ink)"),
                        ],
                        gap="xs",
                        align="center",
                        h="100%",
                    ),
                    href="/",
                    underline=False,
                ),
                px="sm",
                h="44px",
                style={
                    "borderBottom": "1px solid var(--line, #E0E0E0)",
                    "display": "flex",
                    "alignItems": "center",
                },
            )
        )

        # 2. Các nhóm menu (Accordion collapsible theo nhóm, lưu trạng thái)
        accordion_items: list[Any] = []
        all_group_titles: list[str] = [str(g["title"]) for g in nav_groups]
        for group in nav_groups:
            group_links: list[Any] = []
            for item in group["items"]:
                is_active = item["href"] == active_href
                # Task 30: bỏ hẳn badge "Mới" ở menu thanh bên (kể cả menu thêm sau này).
                label_node: Any = item["label"]
                group_links.append(
                    dmc.NavLink(
                        label=label_node,
                        leftSection=DashIconify(icon=item["icon"], width=16),
                        href=item["href"],
                        active=is_active,
                        variant="subtle",
                        px="xs",
                        py=0,
                        styles={
                            "root": {
                                "height": "30px",
                                "borderRadius": "4px",
                                "borderLeft": "3px solid var(--primary, #0F6CBD)"
                                if is_active
                                else "3px solid transparent",
                                "backgroundColor": "var(--primary-soft, #EBF3FC)" if is_active else "transparent",
                                "margin": "1px 4px",
                            },
                            "label": {
                                "fontWeight": 600 if is_active else 500,
                                "fontSize": "13px",
                                "color": "var(--ink, #242424)",
                            },
                        },
                    )
                )
            accordion_items.append(
                dmc.AccordionItem(
                    children=[
                        dmc.AccordionControl(
                            dmc.Text(
                                group["title"],
                                size="xs",
                                fw=600,
                                c="dimmed",
                                style={"letterSpacing": "0.3px", "fontSize": "11px", "userSelect": "none"},
                            ),
                            px="sm",
                            py=4,
                            h="28px",
                        ),
                        dmc.AccordionPanel(group_links),
                    ],
                    value=group["title"],
                    style={"border": "none"},
                )
            )

        content_children.append(
            dmc.Accordion(
                id="sidebar-nav-accordion",
                multiple=True,
                value=all_group_titles,
                persistence=True,
                persistence_type="local",
                chevronPosition="right",
                chevronSize=14,
                styles={
                    "item": {"border": "none"},
                    "control": {
                        "padding": "4px 8px 4px 12px",
                        "borderRadius": "4px",
                        "backgroundColor": "transparent",
                    },
                    "content": {"padding": "0"},
                    "chevron": {
                        "width": 14,
                        "height": 14,
                        "color": "var(--ink-soft, #888)",
                    },
                },
                children=accordion_items,
            )
        )
    else:
        # Mini mode (Rail 48px)
        # 1. Logo Icon centered kèm Tooltip (44px)
        content_children.append(
            dmc.Box(
                dmc.Anchor(
                    dmc.Tooltip(
                        dmc.ThemeIcon(
                            DashIconify(icon="lucide:layers", width=20),
                            size="md",
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
                h="44px",
                w="100%",
                style={
                    "borderBottom": "1px solid var(--line, #E0E0E0)",
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                },
            )
        )

        # 2. Icon các mục menu dạng ActionIcon giống icon trang chủ kèm Tooltip & Vạch active 3px
        for idx, group in enumerate(nav_groups):
            if idx > 0:
                content_children.append(
                    dmc.Box(
                        dmc.Divider(color="var(--line, #E0E0E0)"),
                        px="xs",
                        py="xs",
                        w="100%",
                    )
                )
            for item in group["items"]:
                is_active = item["href"] == active_href
                item_children: list[Any] = [
                    dmc.Anchor(
                        dmc.Tooltip(
                            dmc.ActionIcon(
                                DashIconify(icon=item["icon"], width=18),
                                size="md",
                                radius="sm",
                                variant="subtle",
                                style={
                                    "color": "var(--primary, #0F6CBD)" if is_active else "var(--ink-soft, #616161)",
                                    "backgroundColor": "var(--primary-soft, #EBF3FC)" if is_active else "transparent",
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
                    )
                ]
                if is_active:
                    item_children.append(
                        dmc.Box(
                            style={
                                "position": "absolute",
                                "left": 0,
                                "top": "6px",
                                "bottom": "6px",
                                "width": "3px",
                                "borderRadius": "2px",
                                "backgroundColor": "var(--primary, #0F6CBD)",
                            }
                        )
                    )
                content_children.append(
                    dmc.Box(
                        item_children,
                        py=2,
                        w="100%",
                        style={
                            "display": "flex",
                            "justifyContent": "center",
                            "alignItems": "center",
                            "position": "relative",
                        },
                    )
                )

    return dmc.Stack(
        content_children,
        gap=0,
        h="100%",
        align="center" if is_mini else "stretch",
        style={"overflowX": "hidden", "overflowY": "auto"},
    )


def create_shell_layout() -> Any:
    """Layout gốc kết hợp Location, Store trạng thái sidebar và container AppShell."""
    return html.Div(
        [
            dcc.Location(id="app-location", refresh=False),
            dcc.Store(id="app-sidebar-collapsed", storage_type="local", data=False),
            dcc.Store(id="app-shell-mode", data=None),
            # Kiểm tra PERM_REVISION mỗi 5 giây: đổi quyền thì dựng lại
            # thanh bên trong tối đa 5 giây (spec 11 mục 6).
            dcc.Store(id="app-perm-revision", data=None),
            dcc.Interval(id="app-perm-revision-check", interval=5000, n_intervals=0),
            # Task 78: đếm badge chuông mỗi 60s (1 câu COUNT) + kiểm tra
            # sức khỏe worker để báo ADMIN (D8).
            dcc.Interval(id="app-notif-poll", interval=60000, n_intervals=0),
            dmc.NotificationContainer(position="top-right", zIndex=9999),
            html.Div(id="app-shell-container"),
        ]
    )


_SHELLLESS_PATHS = frozenset({"/login", "/forgot-password", "/reset-password"})


def render_app_shell(pathname: str | None, is_collapsed_data: Any) -> Any:
    """Hàm thuần dựng khung AppShell hoàn chỉnh (dùng khi khởi tạo, đổi mode hoặc đổi user)."""
    ctx = get_current_ctx()

    if pathname in _SHELLLESS_PATHS:
        return html.Div(
            [
                dash.page_container,
                html.Div(
                    [
                        html.Div(id="app-shell"),
                        html.Div(id="app-shell-navbar"),
                        html.Div(id="app-sidebar-toggle-btn"),
                        html.Div(id="app-sidebar-toggle-tooltip"),
                    ],
                    style={"display": "none"},
                ),
            ]
        )

    is_mini = bool(is_collapsed_data)

    # Lấy thông tin bảo trì và dung lượng tạm (đã cache để không chặn request)
    is_maintenance = False
    temp_bytes = 0
    warning_gb = 2.0
    storage_warn = False

    try:
        engine = get_recon_engine()
        is_maintenance = _get_cached_maintenance_mode(engine)

        if ctx and is_admin(ctx):
            temp_bytes, warning_gb, storage_warn = _get_cached_storage_usage(ctx, engine)
    except Exception:
        pass

    nav_groups = (
        get_nav_items_for_menus(effective_menus(ctx), is_admin=is_admin(ctx))
        if ctx is not None
        else None
    )
    active_env = get_active_environment()
    header_content = create_header(ctx, active_env, pathname, is_mini=is_mini, nav_groups=nav_groups)
    navbar_content = create_navbar(ctx, pathname, is_mini=is_mini, nav_groups=nav_groups)
    user_roles = user_role_codes(ctx) if ctx else set()
    banners = render_banners(is_maintenance, storage_warn, user_roles, temp_bytes, warning_gb)

    main_content: list[Any] = []
    if banners:
        main_content.append(dmc.Box(banners, px="md", pt="xs"))
    main_content.append(
        dmc.Box(
            dash.page_container,
            h="100%",
            style={
                "minHeight": 0,
                "overflow": "auto",
                "display": "flex",
                "flexDirection": "column",
                "flex": 1,
            },
        )
    )

    return dmc.AppShell(
        id="app-shell",
        header={"height": 44},
        navbar={"width": 48 if is_mini else 200, "breakpoint": "sm"},
        children=[
            dmc.AppShellHeader(
                header_content,
                style={"borderBottom": "1px solid var(--line, #E0E0E0)"},
            ),
            dmc.AppShellNavbar(
                id="app-shell-navbar",
                children=navbar_content,
                style={"borderRight": "1px solid var(--line, #E0E0E0)"},
            ),
            dmc.AppShellMain(
                main_content,
                style={
                    # Task 45: height 100vh — header fixed nên main bắt đầu
                    # từ y=0; calc(100vh - 44px) làm main kết thúc sớm 44px,
                    # lộ nền trắng body dưới đáy màn hình.
                    "height": "100vh",
                    "minHeight": 0,
                    "overflow": "hidden",
                    "display": "flex",
                    "flexDirection": "column",
                    "backgroundColor": "var(--bg, #F5F5F5)",
                },
            ),
        ],
    )


@callback(
    Output("app-shell-container", "children"),
    Output("app-shell-mode", "data"),
    Input("app-location", "pathname"),
    State("app-sidebar-collapsed", "data"),
    State("app-shell-mode", "data"),
)
def update_app_shell_container(
    pathname: str | None,
    is_collapsed_data: Any,
    shell_state: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """Persistent AppShell: chỉ dựng lại toàn bộ shell khi đổi mode hoặc đổi user."""
    ctx = get_current_ctx()
    uid = ctx.user_id if ctx else None
    target_mode = "shellless" if pathname in _SHELLLESS_PATHS else "shell"

    if isinstance(shell_state, dict):
        cur_mode = shell_state.get("mode")
        if target_mode == "shellless" and cur_mode == "shellless":
            raise dash.exceptions.PreventUpdate
        if target_mode == "shell" and cur_mode == "shell" and shell_state.get("user_id") == uid:
            raise dash.exceptions.PreventUpdate

    return render_app_shell(pathname, is_collapsed_data), {"mode": target_mode, "user_id": uid}


@callback(
    Output("app-header-breadcrumbs", "children"),
    Output("app-shell-navbar", "children", allow_duplicate=True),
    Output("app-menu-search-input", "value", allow_duplicate=True),
    Output("app-menu-search-results", "children", allow_duplicate=True),
    Output("app-menu-search-results-paper", "style", allow_duplicate=True),
    Input("app-location", "pathname"),
    State("app-sidebar-collapsed", "data"),
    State("app-shell-mode", "data"),
    prevent_initial_call=True,
)
def sync_shell_on_navigate(
    pathname: str | None,
    is_collapsed_data: Any,
    shell_state: Any = None,
) -> tuple[Any, Any, str, list[Any], dict[str, Any]]:
    """Cập nhật nhẹ Breadcrumbs, Navbar active và reset tìm kiếm menu khi đổi trang trong Persistent Shell."""
    if pathname in _SHELLLESS_PATHS:
        raise dash.exceptions.PreventUpdate
    if not isinstance(shell_state, dict) or shell_state.get("mode") != "shell":
        raise dash.exceptions.PreventUpdate
    ctx = get_current_ctx()
    uid = ctx.user_id if ctx else None
    if shell_state.get("user_id") != uid:
        raise dash.exceptions.PreventUpdate

    bc_elements = build_breadcrumb_nodes(pathname)
    navbar_children = create_navbar(ctx, pathname, is_mini=bool(is_collapsed_data))
    return bc_elements, navbar_children, "", [], dict(_MENU_SEARCH_RESULTS_STYLE)


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
    if pathname in _SHELLLESS_PATHS:
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
    if pathname in _SHELLLESS_PATHS:
        raise dash.exceptions.PreventUpdate

    is_mini = bool(is_collapsed)
    ctx = get_current_ctx()
    navbar_config = {"width": 48 if is_mini else 200, "breakpoint": "sm"}
    navbar_children = create_navbar(ctx, pathname, is_mini=is_mini)
    toggle_icon = DashIconify(
        icon="lucide:panel-left-open" if is_mini else "lucide:panel-left-close",
        width=18,
    )
    toggle_label = "Mở rộng menu" if is_mini else "Thu nhỏ menu"
    return navbar_config, navbar_children, toggle_icon, toggle_label


@callback(
    Output("app-menu-search-results", "children"),
    Output("app-menu-search-results-paper", "style"),
    Output("app-location", "href"),
    Output("app-menu-search-input", "value"),
    Input("app-menu-search-input", "value"),
    Input("app-menu-search-input", "n_submit"),
    State("app-menu-search-store", "data"),
    prevent_initial_call=True,
)
def handle_menu_search(
    value: str | None, n_submit: int | None, items: list[dict[str, Any]] | None
) -> tuple[Any, Any, Any, Any]:
    """Task 30: tìm kiếm menu ở header — gõ để lọc, Enter tới kết quả đầu.

    Task 45: bỏ Input pathname — callback chạy lúc tải trang, trước khi
    header kịp render ô tìm kiếm, nên Dash báo ReferenceError (input
    không tồn tại trong layout gốc chỉ có app-shell-container rỗng).
    Không mất hành vi xóa khi đổi trang vì render_app_shell dựng lại
    header (ô tìm kiếm mới value="", dropdown ẩn) mỗi lần đổi trang.
    """
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    matches = filter_menu_items(items, value or "")
    if "n_submit" in triggered:
        if not matches:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        return [], dict(_MENU_SEARCH_RESULTS_STYLE), matches[0]["href"], ""
    if not (value or "").strip():
        return [], dict(_MENU_SEARCH_RESULTS_STYLE), dash.no_update, dash.no_update
    if not matches:
        return (
            [dmc.Text("Không tìm thấy menu nào", size="sm", c="dimmed", px="sm", py="xs")],
            {**_MENU_SEARCH_RESULTS_STYLE, "display": "block"},
            dash.no_update,
            dash.no_update,
        )
    shown = matches[:MAX_MENU_SEARCH_RESULTS]
    nodes: list[Any] = [
        dmc.NavLink(
            label=dmc.Group(
                [
                    dmc.Text(item["label"], size="sm", fw=500),
                    dmc.Text(item["group"], size="xs", c="dimmed"),
                ],
                gap="xs",
                justify="space-between",
            ),
            leftSection=DashIconify(icon=item["icon"], width=16),
            href=item["href"],
            variant="subtle",
            py=4,
        )
        for item in shown
    ]
    if len(matches) > MAX_MENU_SEARCH_RESULTS:
        nodes.append(
            dmc.Text(
                f"…và {len(matches) - MAX_MENU_SEARCH_RESULTS} kết quả khác",
                size="xs",
                c="dimmed",
                px="sm",
                py=4,
            )
        )
    return nodes, {**_MENU_SEARCH_RESULTS_STYLE, "display": "block"}, dash.no_update, dash.no_update


# --- Task 78: chuông thông báo ------------------------------------------------


def _notif_badge(ctx: Ctx) -> tuple[str, bool]:
    """(label, disabled) của badge chuông theo số chưa đọc."""
    try:
        unread = count_unread(get_recon_engine(), ctx.user_id)
    except Exception:  # noqa: BLE001 — badge lỗi không được vỡ header
        return "", True
    return (str(unread) if unread > 0 else ""), unread == 0


def _notif_panel_items(ctx: Ctx, unread_only: bool = False) -> list[Any]:
    """5 thông báo mới nhất cho panel chuông (tab Tất cả / Chưa đọc)."""
    res = list_notifications(ctx, page=1, page_size=5, unread_only=unread_only)
    if not res.ok or not res.data:
        return [dmc.Text("Chưa có thông báo.", size="sm", c="dimmed", px="sm", py="xs")]
    items = res.data.get("items") or []
    if not items:
        return [dmc.Text("Chưa có thông báo.", size="sm", c="dimmed", px="sm", py="xs")]
    nodes: list[Any] = []
    for item in items:
        title = str(item.get("title") or "")
        created = str(item.get("created_at") or "")[:16].replace("T", " ")
        label = dmc.Group(
            [
                dmc.Text(title, size="sm", fw=600 if not item.get("is_read") else 400),
                dmc.Text(created, size="xs", c="dimmed"),
            ],
            gap="xs",
            justify="space-between",
        )
        nodes.append(
            dmc.MenuItem(
                label,
                id={"type": "app-notif-panel-item", "index": int(item["id"])},
            )
        )
    return nodes


@callback(
    Output("app-notif-indicator", "label"),
    Output("app-notif-indicator", "disabled"),
    Input("app-notif-poll", "n_intervals"),
    Input("app-location", "pathname"),
    prevent_initial_call=True,
)
def handle_notif_poll(_n_intervals: int, pathname: str | None) -> tuple[str, bool]:
    """Đếm badge chuông khi đổi trang + mỗi 60s.

    Chỉ khi Interval tick mới kiểm tra sức khỏe worker để báo ADMIN
    (D8) — đổi trang chỉ đếm badge.
    """
    ctx = get_current_ctx()
    if ctx is None or pathname in _SHELLLESS_PATHS:
        raise dash.exceptions.PreventUpdate
    try:
        triggered = dash.callback_context.triggered_id
        if triggered == "app-notif-poll":
            maybe_notify_worker_health(get_recon_engine())
        return _notif_badge(ctx)
    except Exception:  # noqa: BLE001 — badge lỗi không được vỡ header
        raise dash.exceptions.PreventUpdate from None


@callback(
    Output("app-notif-panel", "children"),
    Input("app-notif-bell", "n_clicks"),
    Input("app-notif-poll", "n_intervals"),
    Input("app-notif-tabs", "value"),
    prevent_initial_call=True,
)
def handle_notif_panel(_n_clicks: int | None, _n_intervals: int, tab_value: str | None) -> Any:
    """Vẽ lại panel chuông khi bấm chuông (hoặc mỗi 60s nếu đang mở)
    hoặc khi đổi tab Tất cả / Chưa đọc."""
    ctx = get_current_ctx()
    if ctx is None:
        raise dash.exceptions.PreventUpdate
    try:
        return _notif_panel_items(ctx, unread_only=(tab_value == "unread"))
    except Exception:  # noqa: BLE001 — panel lỗi không được vỡ header
        raise dash.exceptions.PreventUpdate from None


@callback(
    Output("app-notif-indicator", "label", allow_duplicate=True),
    Output("app-notif-indicator", "disabled", allow_duplicate=True),
    Output("app-notif-panel", "children", allow_duplicate=True),
    Input("app-notif-mark-all-read", "n_clicks"),
    State("app-notif-tabs", "value"),
    prevent_initial_call=True,
)
def handle_notif_popover_mark_all(_n_clicks: int | None, tab_value: str | None) -> tuple[str, bool, Any]:
    """'Đánh dấu tất cả đã đọc' trong popover chuông (task 79)."""
    ctx = get_current_ctx()
    if ctx is None or not _n_clicks:
        raise dash.exceptions.PreventUpdate
    try:
        mark_all_read(ctx)
        label, disabled = _notif_badge(ctx)
        return label, disabled, _notif_panel_items(ctx, unread_only=(tab_value == "unread"))
    except Exception:  # noqa: BLE001 — lỗi đánh dấu không được vỡ header
        raise dash.exceptions.PreventUpdate from None


def handle_panel_item_click(ctx: Ctx, notif_id: int) -> tuple[str, bool, Any, Any]:
    """Thuần: đánh dấu 1 thông báo đã đọc; trả (badge label, disabled,
    panel mới, link để điều hướng)."""
    mark_read(ctx, notif_id)
    link: Any = dash.no_update
    try:
        with get_recon_engine().connect() as conn:
            row = conn.execute(
                select(recon_notification.c.LINK).where(recon_notification.c.ID == int(notif_id))
            ).scalar_one_or_none()
        if row:
            link = str(row)
    except Exception:  # noqa: BLE001 — không lấy được link thì ở lại trang
        link = dash.no_update
    label, disabled = _notif_badge(ctx)
    return label, disabled, _notif_panel_items(ctx), link


@callback(
    Output("app-notif-indicator", "label", allow_duplicate=True),
    Output("app-notif-indicator", "disabled", allow_duplicate=True),
    Output("app-notif-panel", "children", allow_duplicate=True),
    Output("app-location", "href", allow_duplicate=True),
    Input({"type": "app-notif-panel-item", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_notif_panel_item_click(_n_clicks: list[int | None] | None) -> tuple[str, bool, Any, Any]:
    """Bấm 1 mục trong panel chuông -> đánh dấu đã đọc + tới link.

    MenuItem KHÔNG dùng href: href + n_clicks thì click điều hướng
    ngay, n_clicks mất (đã chứng minh bằng debug live task 78) —
    callback tự điều hướng qua app-location.href SAU khi đánh dấu đọc
    nên chắc chắn đã đọc trước khi chuyển trang.
    """
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None:
        raise dash.exceptions.PreventUpdate
    if not any(c for c in (_n_clicks or []) if c):
        raise dash.exceptions.PreventUpdate
    try:
        notif_id = int(triggered["index"])
    except (TypeError, ValueError):
        raise dash.exceptions.PreventUpdate from None
    try:
        return handle_panel_item_click(ctx, notif_id)
    except Exception:  # noqa: BLE001 — lỗi đánh dấu không được vỡ header
        raise dash.exceptions.PreventUpdate from None
