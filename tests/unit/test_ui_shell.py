from __future__ import annotations

from app.core.context import Role
from app.ui.layout.shell import (
    build_breadcrumbs,
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
