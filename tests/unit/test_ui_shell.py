from __future__ import annotations

from app.core.context import Role
from app.ui.layout.shell import (
    build_breadcrumbs,
    create_navbar,
    get_active_nav_href,
    get_nav_items_for_roles,
    render_banners,
)


def test_nav_items_by_role() -> None:
    # 1. Admin: thấy toàn bộ menu
    admin_nav = get_nav_items_for_roles({Role.ADMIN})
    urls = [item["href"] for group in admin_nav for item in group["items"]]
    assert "/" in urls
    assert "/runs/new" in urls
    assert "/history" in urls
    assert "/issues" in urls
    assert "/templates" in urls
    assert "/templates/new" in urls
    assert "/data-sources" in urls
    assert "/users" in urls

    # 2. Template Owner: thấy Đăng ký template, không thấy Data Sources và Users
    to_nav = get_nav_items_for_roles({Role.TEMPLATE_OWNER})
    urls_to = [item["href"] for group in to_nav for item in group["items"]]
    assert "/templates" in urls_to
    assert "/templates/new" in urls_to
    assert "/data-sources" not in urls_to
    assert "/users" not in urls_to

    # 3. Operator: không thấy Đăng ký template, không thấy Data Sources và Users
    op_nav = get_nav_items_for_roles({Role.OPERATOR})
    urls_op = [item["href"] for group in op_nav for item in group["items"]]
    assert "/templates" in urls_op
    assert "/templates/new" not in urls_op
    assert "/data-sources" not in urls_op
    assert "/users" not in urls_op

    # 4. Viewer: chỉ xem, không chạy đối soát, không cấu hình
    vi_nav = get_nav_items_for_roles({Role.VIEWER})
    urls_vi = [item["href"] for group in vi_nav for item in group["items"]]
    assert "/" in urls_vi
    assert "/history" in urls_vi
    assert "/issues" in urls_vi
    assert "/runs/new" not in urls_vi
    assert "/templates" not in urls_vi
    assert "/data-sources" not in urls_vi
    assert "/users" not in urls_vi


def test_banners_maintenance_and_storage() -> None:
    # 1. Không có cảnh báo
    banners = render_banners(
        is_maintenance=False,
        storage_warning=False,
        user_roles={Role.ADMIN},
        temp_bytes=1000,
        warning_gb=2.0,
    )
    assert len(banners) == 0

    # 2. Có chế độ bảo trì: hiện banner bảo trì cho mọi người
    banners_maint = render_banners(
        is_maintenance=True,
        storage_warning=False,
        user_roles={Role.OPERATOR},
        temp_bytes=1000,
        warning_gb=2.0,
    )
    assert len(banners_maint) == 1
    assert "bảo trì" in str(banners_maint[0].children) or "bảo trì" in str(banners_maint[0])

    # 3. Cảnh báo dữ liệu tạm: CHỈ hiện cho Admin
    banners_storage_admin = render_banners(
        is_maintenance=False,
        storage_warning=True,
        user_roles={Role.ADMIN},
        temp_bytes=3 * 1024 * 1024 * 1024,
        warning_gb=2.0,
    )
    assert len(banners_storage_admin) == 1
    assert "vượt ngưỡng" in str(banners_storage_admin[0].children) or "vượt ngưỡng" in str(banners_storage_admin[0])

    banners_storage_operator = render_banners(
        is_maintenance=False,
        storage_warning=True,
        user_roles={Role.OPERATOR},
        temp_bytes=3 * 1024 * 1024 * 1024,
        warning_gb=2.0,
    )
    assert len(banners_storage_operator) == 0


def test_build_breadcrumbs() -> None:
    bc_templates = build_breadcrumbs("/templates")
    labels = [b["label"] for b in bc_templates]
    assert "Trang chủ" in labels
    assert "Templates" in labels

    bc_users = build_breadcrumbs("/users")
    labels_users = [b["label"] for b in bc_users]
    assert "Trang chủ" in labels_users

    bc_issues = build_breadcrumbs("/issues")
    labels_issues = [b["label"] for b in bc_issues]
    assert "Trang chủ" in labels_issues
    assert "Xử lý chênh lệch" in labels_issues
    assert "Người dùng" in labels_users


def test_get_active_nav_href() -> None:
    admin_nav = get_nav_items_for_roles({Role.ADMIN})

    # Khi vào /templates/new: CHỈ /templates/new được active, KHÔNG PHẢI /templates
    assert get_active_nav_href(admin_nav, "/templates/new") == "/templates/new"

    # Khi vào /templates: CHỈ /templates được active
    assert get_active_nav_href(admin_nav, "/templates") == "/templates"

    # Khi xem chi tiết template con /templates/123: /templates được active
    assert get_active_nav_href(admin_nav, "/templates/123") == "/templates"

    # Khi vào trang chủ /: Dashboard được active
    assert get_active_nav_href(admin_nav, "/") == "/"

    # Khi vào /runs/new: /runs/new được active
    assert get_active_nav_href(admin_nav, "/runs/new") == "/runs/new"


def test_navbar_active_item_exact_templates_new() -> None:
    from app.core.context import Ctx

    ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    navbar = create_navbar(ctx, pathname="/templates/new")

    # Duyệt tìm các NavLink con trong navbar
    def find_nav_links(component: object) -> list[object]:
        links: list[object] = []
        if hasattr(component, "href") and hasattr(component, "active"):
            links.append(component)
        children = getattr(component, "children", None)
        if isinstance(children, list):
            for child in children:
                links.extend(find_nav_links(child))
        elif children is not None:
            links.extend(find_nav_links(children))
        return links

    nav_links = find_nav_links(navbar)
    active_links = [getattr(link, "href", None) for link in nav_links if getattr(link, "active", False)]

    # /templates/new thuộc menu template nên chỉ /templates active (task 19:
    # thanh bên theo menu, không còn mục riêng "Đăng ký template")
    assert active_links == ["/templates"]


def test_navbar_mini_mode_and_tooltips() -> None:
    from app.core.context import Ctx

    ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    navbar = create_navbar(ctx, pathname="/templates", is_mini=True)

    def find_components_by_type(component: object, comp_type_name: str) -> list[object]:
        found: list[object] = []
        if type(component).__name__ == comp_type_name:
            found.append(component)
        children = getattr(component, "children", None)
        if isinstance(children, list):
            for child in children:
                found.extend(find_components_by_type(child, comp_type_name))
        elif children is not None:
            found.extend(find_components_by_type(children, comp_type_name))
        return found

    # Tìm các Tooltip trong navbar mini
    tooltips = find_components_by_type(navbar, "Tooltip")
    tooltip_labels = [getattr(t, "label", None) for t in tooltips]

    # Kiểm tra có tooltip cho các mục menu
    assert "ReconHub Trang chủ" in tooltip_labels
    assert "Dashboard" in tooltip_labels
    assert "Templates" in tooltip_labels
    assert "Data Sources" in tooltip_labels

    # Tìm các ActionIcon con và kiểm tra active
    anchors = find_components_by_type(navbar, "Anchor")
    active_hrefs: list[str] = []
    for a in anchors:
        action_icons = find_components_by_type(a, "ActionIcon")
        for icon in action_icons:
            style = getattr(icon, "style", {}) or {}
            if getattr(icon, "variant", "") == "filled" or "var(--primary-soft" in style.get("backgroundColor", ""):
                active_hrefs.append(getattr(a, "href", ""))
    assert active_hrefs == ["/templates"]


def test_sidebar_toggle_callbacks() -> None:
    import pytest
    from dash.exceptions import PreventUpdate

    from app.ui.layout.shell import handle_sidebar_toggle, sync_sidebar_ui

    # 1. Toggle handler
    assert handle_sidebar_toggle(1, False) is True
    assert handle_sidebar_toggle(2, True) is False
    with pytest.raises(PreventUpdate):
        handle_sidebar_toggle(0, False)

    # 2. Sync UI khi collapsed = True
    nav_config_mini, nav_children_mini, icon_mini, label_mini = sync_sidebar_ui(True, "/history")
    assert nav_config_mini["width"] == 48
    assert label_mini == "Mở rộng menu"
    assert icon_mini.icon == "lucide:panel-left-open"

    # 3. Sync UI khi collapsed = False
    nav_config_full, nav_children_full, icon_full, label_full = sync_sidebar_ui(False, "/history")
    assert nav_config_full["width"] == 200
    assert label_full == "Thu nhỏ menu"
    assert icon_full.icon == "lucide:panel-left-close"

    # 4. Khi ở trang login thì PreventUpdate
    with pytest.raises(PreventUpdate):
        sync_sidebar_ui(True, "/login")
