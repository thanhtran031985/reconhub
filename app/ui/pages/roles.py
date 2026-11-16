"""app/ui/pages/roles.py — Màn hình Vai trò và phân quyền (Screen14).

Theo spec 11 mục 7.1, 3 tab: Vai trò / Quyền thực tế của người dùng /
Mô phỏng phạm vi dữ liệu. Bảng "Phạm vi dữ liệu và thao tác đặc biệt"
của prototype được thay bằng một dòng ghi chú (spec 11 mục 7.1).
Chỉ ADMIN truy cập (menu `role`).

Giao diện Fluent Compact + Master–Detail theo đúng .agents/rules/ui-dash.md:
- Khung cố định, không cuộn toàn trang ở 1366×768 trở lên (flex 1, minHeight 0).
- Mật độ Compact (size="xs", gap="xs", padding="sm", radius="sm").
- Bảng hiển thị dùng dmc.Table có sọc, hover, theme-aware (không dùng html.Table thô).
- Master–Detail: Trái là danh sách vai trò (320px), Phải là chi tiết & phân quyền.
- Chế độ sáng/tối tự động tương thích với Theme tokens.
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.schemas.run import RunListFilter
from app.services.menu_sync import list_menu_tree
from app.services.perm import is_admin, page_gate
from app.services.role import (
    clone_role,
    create_role,
    delete_role,
    effective_of_user,
    get_role,
    list_roles,
    update_role,
    users_of,
)
from app.services.run_service import list_runs
from app.services.user import list_users
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.page_header import page_header
from app.ui.layout.shell import _SIDEBAR_SKIP_CODES, get_nav_items_for_menus

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/roles",
        title="Vai trò và phân quyền — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "role"

_SCOPE_NOTE = "Vai trò thường: chỉ thấy run do mình chạy; thao tác nhạy cảm chỉ ADMIN."


def _ctx_or_none() -> Ctx | None:
    return get_current_ctx()


def _role_rows(ctx: Ctx) -> list[dict[str, Any]]:
    res = list_roles(ctx, include_inactive=True)
    if not res.ok or not res.data:
        return []
    return list(res.data)


def _menu_tree(ctx: Ctx) -> list[dict[str, Any]]:
    res = list_menu_tree(ctx)
    if not res.ok or not res.data:
        return []
    return list(res.data)


def _menu_label_map(ctx: Ctx) -> dict[str, str]:
    labels: dict[str, str] = {}
    for group in _menu_tree(ctx):
        for menu in group["menus"]:
            labels[menu["code"]] = menu["label"]
    return labels


def _role_is_system(ctx: Ctx, role_id: int) -> bool:
    """Vai trò có phải hệ thống không (để xem trước thanh bên như ADMIN)."""
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        return False
    return bool(res.data["is_system"])


def _effective_role_menus(ctx: Ctx, role: dict[str, Any]) -> list[str]:
    """Menu hiệu lực của một vai trò để xem trước thanh bên.

    Vai trò hệ thống không lưu dòng role_menu nhưng luôn có toàn bộ menu,
    nên dùng đủ các mã menu thay vì danh sách đã lưu (rỗng).
    """
    if role["is_system"]:
        return sorted({m["code"] for g in _menu_tree(ctx) for m in g["menus"]})
    return sorted(role["menus"])


def _role_snapshot(ctx: Ctx, role: dict[str, Any]) -> dict[str, Any]:
    """Snapshot form để so sánh thay đổi (dirty check)."""
    menus = _effective_role_menus(ctx, role)
    return {
        "menus": menus,
        "name": str(role["name"]),
        "description": str(role["description"] or ""),
        "is_active": bool(role["is_active"]),
        "row_version": int(role["row_version"]),
    }


def render_roles_list(ctx: Ctx, q: str | None = None, selected_id: int | None = None) -> Any:
    """Cột trái: danh sách vai trò dạng thẻ Compact theo chuẩn Fluent Master-Detail."""
    rows = _role_rows(ctx)
    if q:
        term = q.strip().lower()
        rows = [r for r in rows if term in str(r["code"]).lower() or term in str(r["name"]).lower()]
    if not rows:
        return empty_state(
            "Chưa có vai trò nào khớp.",
            "Thử từ khóa khác hoặc thêm vai trò mới.",
        )
    items: list[Any] = []
    tree = _menu_tree(ctx)
    total_menus = sum(len(g["menus"]) for g in tree)

    for r in rows:
        rid = int(r["id"])
        is_selected = selected_id is not None and rid == selected_id
        menu_count = total_menus if r["is_system"] else len(r["menus"])

        meta_badges = [
            dmc.Badge(
                f"{r['user_count']} người dùng",
                size="xs",
                color="gray",
                variant="light",
            ),
            dmc.Badge(
                f"{menu_count}/{total_menus} menu",
                size="xs",
                color="gray",
                variant="light",
            ),
        ]
        status_badges = []
        if r["is_system"]:
            status_badges.append(dmc.Badge("Hệ thống", size="xs", color="blue", variant="light"))
        if not r["is_active"]:
            status_badges.append(dmc.Badge("Đã tắt", size="xs", color="orange", variant="light"))

        items.append(
            dmc.Button(
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Text(str(r["name"]), fw=600, size="sm", style={"textAlign": "left"}),
                                *status_badges,
                            ],
                            justify="space-between",
                            align="center",
                            w="100%",
                        ),
                        dmc.Text(
                            str(r["code"]),
                            size="xs",
                            c="dimmed",
                            style={"fontFamily": "monospace", "textAlign": "left"},
                        ),
                        dmc.Group(meta_badges, gap="xs", style={"marginTop": 2}),
                    ],
                    gap=2,
                    w="100%",
                ),
                id={"type": "role-select-btn", "index": rid},
                variant="light" if is_selected else "subtle",
                color="blue" if is_selected else "gray",
                fullWidth=True,
                justify="flex-start",
                h="auto",
                py="xs",
                px="sm",
                mb="xs",
                radius="sm",
                style={
                    "borderLeft": "3px solid var(--mantine-color-blue-filled)"
                    if is_selected
                    else "3px solid transparent",
                    "textAlign": "left",
                },
            )
        )
    return html.Div(items)


def render_menu_checkboxes(ctx: Ctx, role_id: int) -> Any:
    """Checkbox menu theo nhóm trong lưới 3 cột, kèm nhãn Mới / Đang ẩn (spec 11 mục 7.1)."""
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy vai trò.", tone="crit")
    role = res.data
    is_system = bool(role["is_system"])
    current = set(role["menus"])
    tree = _menu_tree(ctx)
    if is_system:
        current = {m["code"] for g in tree for m in g["menus"]}
    group_cols: list[Any] = []
    for group in tree:
        boxes: list[Any] = []
        for menu in group["menus"]:
            badges: list[Any] = []
            if menu["is_new"]:
                badges.append(dmc.Badge("Mới", size="xs", color="green", variant="light"))
            if menu["is_hidden"]:
                badges.append(dmc.Badge("Đang ẩn", size="xs", color="orange", variant="light"))
            boxes.append(
                dmc.Checkbox(
                    label=dmc.Group(
                        [dmc.Text(menu["label"], size="xs"), *badges],
                        gap="xs",
                        align="center",
                    ),
                    value=menu["code"],
                    disabled=is_system,
                    size="xs",
                )
            )
        checked = len({m["code"] for m in group["menus"]} & current)

        # Nếu số lượng menu > 4, chia thành 2 phần (2 cột) để vừa vặn chiều cao, không bị dài/scroll
        if len(boxes) > 4:
            mid = (len(boxes) + 1) // 2
            boxes_content = dmc.Grid(
                [
                    dmc.GridCol(dmc.Stack(boxes[:mid], gap="xs"), span=6),
                    dmc.GridCol(dmc.Stack(boxes[mid:], gap="xs"), span=6),
                ],
                gutter="xs",
            )
        else:
            boxes_content = dmc.Stack(boxes, gap="xs")

        group_cols.append(
            dmc.GridCol(
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.Text(group["label"], fw=600, size="xs"),
                                dmc.Badge(
                                    f"{checked}/{len(group['menus'])}",
                                    size="xs",
                                    color="gray",
                                    variant="light",
                                ),
                            ],
                            justify="space-between",
                            mb="xs",
                        ),
                        boxes_content,
                    ],
                    withBorder=True,
                    radius="sm",
                    p="xs",
                    bg="var(--surface-2, #f8fafc)",
                    style={"height": "100%", "display": "flex", "flexDirection": "column", "width": "100%"},
                ),
                span={"base": 12, "sm": 6, "lg": 4},
                style={"display": "flex"},
            )
        )

    action_buttons = (
        dmc.Group(
            [
                button_subtle("Chọn tất cả", id="roles-select-all-menus", size="xs"),
                button_subtle("Bỏ chọn tất cả", id="roles-deselect-all-menus", size="xs"),
            ],
            gap="xs",
        )
        if not is_system
        else None
    )

    return dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Group(
                        [
                            DashIconify(icon="lucide:shield-check", width=16),
                            dmc.Text("Menu được truy cập", fw=600, size="sm"),
                            dmc.Badge(
                                f"{len(current)}/{sum(len(g['menus']) for g in tree)} menu",
                                size="xs",
                                color="gray",
                                variant="light",
                            ),
                        ],
                        gap="xs",
                        align="center",
                    ),
                    action_buttons if action_buttons else html.Div(),
                ],
                justify="space-between",
                align="center",
                mb=4,
            ),
            dmc.Text(
                "Có menu = thấy menu ở thanh bên và thao tác được trong màn đó. "
                "Quyền được kiểm ở server, không chỉ ẩn menu.",
                size="xs",
                c="dimmed",
                mb="xs",
            ),
            dmc.CheckboxGroup(
                id="roles-menus-group",
                value=sorted(current),
                children=dmc.Grid(group_cols, gutter="xs"),
            ),
        ],
        withBorder=True,
        radius="sm",
        p="sm",
    )


def render_sidebar_preview(ctx: Ctx, menu_codes: list[str], is_admin: bool = False) -> Any:
    """Xem trước thanh bên người có các menu này sẽ thấy."""
    groups = get_nav_items_for_menus(set(menu_codes), is_admin=is_admin)
    items: list[Any] = []
    if not groups:
        items.append(dmc.Text("Không thấy menu nào ở thanh bên.", size="xs", c="dimmed"))
    for group in groups:
        items.append(dmc.Text(group["title"], size="xs", fw=700, c="dimmed", mt=6, mb=2))
        for item in group["items"]:
            items.append(
                dmc.Group(
                    [
                        DashIconify(icon=item["icon"], width=14),
                        dmc.Text(item["label"], size="xs"),
                    ],
                    gap="xs",
                    align="center",
                    py=2,
                )
            )
    panel = dmc.Paper(items, bg="var(--surface-2, #f8fafc)", withBorder=True, radius="sm", p="xs")
    blocks: list[Any] = [panel]
    labels = _menu_label_map(ctx)
    not_shown = [labels.get(c, c) for c in menu_codes if c in _SIDEBAR_SKIP_CODES and c in labels]
    if not_shown:
        blocks.append(
            dmc.Text(
                f"Không hiện ở thanh bên: {', '.join(not_shown)}.",
                size="xs",
                c="dimmed",
                mt="xs",
            )
        )
    return html.Div(blocks)


def render_role_detail(ctx: Ctx, role_id: int) -> Any:
    """Cột phải: form sửa vai trò + phân quyền + xem trước + người dùng mang vai trò."""
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy vai trò.", tone="crit")
    role = res.data
    is_system = bool(role["is_system"])
    users_res = users_of(ctx, role_id)
    users = users_res.data if users_res.ok and users_res.data else []

    user_rows: list[Any] = []
    for u in users:
        is_u_active = bool(u["is_active"])
        user_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(str(u["username"]), size="xs", fw=500, style={"fontFamily": "monospace"})
                    ),
                    dmc.TableTd(dmc.Text(str(u["full_name"]), size="xs")),
                    dmc.TableTd(
                        dmc.Badge(
                            "Đang dùng" if is_u_active else "Đã tắt",
                            size="xs",
                            color="green" if is_u_active else "gray",
                            variant="light",
                        )
                    ),
                ]
            )
        )

    users_table = (
        dmc.Table(
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
            withColumnBorders=False,
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("Username", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}),
                            dmc.TableTh("Họ tên", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}),
                            dmc.TableTh(
                                "Trạng thái", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}
                            ),
                        ]
                    )
                ),
                dmc.TableTbody(user_rows),
            ],
        )
        if user_rows
        else dmc.Text(
            "Chưa có người dùng nào mang vai trò này.",
            size="xs",
            c="dimmed",
            py="sm",
            style={"textAlign": "center"},
        )
    )

    role_status_badge = (
        dmc.Badge("Hệ thống", size="xs", color="blue", variant="light")
        if is_system
        else (
            dmc.Badge("Đang dùng", size="xs", color="green", variant="light")
            if role["is_active"]
            else dmc.Badge("Đã tắt", size="xs", color="orange", variant="light")
        )
    )

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "height": "100%", "overflow": "hidden"},
        children=[
            # Header cố định của Detail panel
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Group(
                                [
                                    DashIconify(
                                        icon="lucide:shield", width=20, color="var(--mantine-color-blue-filled)"
                                    ),
                                    dmc.Title(str(role["name"]), order=4, size=16, fw=600),
                                    dmc.Text(
                                        str(role["code"]),
                                        size="xs",
                                        c="dimmed",
                                        style={"fontFamily": "monospace"},
                                    ),
                                    role_status_badge,
                                ],
                                gap="xs",
                                align="center",
                            ),
                            dmc.Group(
                                [
                                    button_subtle(
                                        "Nhân bản",
                                        id="roles-clone-btn",
                                        icon="lucide:copy",
                                        size="xs",
                                    ),
                                    button_subtle(
                                        "Xóa vai trò",
                                        id="roles-delete-btn",
                                        icon="lucide:trash-2",
                                        color="red",
                                        disabled=is_system,
                                        size="xs",
                                    ),
                                ],
                                gap="xs",
                            ),
                        ],
                        justify="space-between",
                        align="center",
                    ),
                ],
                withBorder=True,
                radius="sm",
                p="xs",
                mb="xs",
            ),
            # Nội dung Detail cuộn độc lập bên trong
            html.Div(
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "overflowY": "auto",
                    "overflowX": "hidden",
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "8px",
                    "paddingRight": "2px",
                },
                children=[
                    # Section 1: Thông tin cơ bản
                    dmc.Paper(
                        [
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        dmc.TextInput(
                                            id="roles-name-input",
                                            label="Tên vai trò",
                                            value=str(role["name"]),
                                            required=True,
                                            disabled=is_system,
                                            size="xs",
                                        ),
                                        span={"base": 12, "md": 5},
                                    ),
                                    dmc.GridCol(
                                        dmc.TextInput(
                                            id="roles-desc-input",
                                            label="Mô tả vai trò",
                                            value=str(role["description"] or ""),
                                            placeholder="Diễn giải vai trò...",
                                            size="xs",
                                        ),
                                        span={"base": 12, "md": 5},
                                    ),
                                    dmc.GridCol(
                                        dmc.Stack(
                                            [
                                                dmc.Text("Kích hoạt", size="xs", fw=500),
                                                dmc.Switch(
                                                    id="roles-active-switch",
                                                    label="Đang dùng",
                                                    checked=bool(role["is_active"]),
                                                    disabled=is_system,
                                                    size="xs",
                                                ),
                                            ],
                                            gap=2,
                                        ),
                                        span={"base": 12, "md": 2},
                                    ),
                                ],
                                gutter="xs",
                                align="flex-end",
                            ),
                            dmc.Text(
                                "Tắt thì người có vai trò này mất các menu của vai trò khi đăng nhập lại hoặc trong vài giây.",
                                size="xs",
                                c="dimmed",
                                mt="xs",
                            ),
                            dmc.Alert(
                                "Vai trò hệ thống Admin luôn có toàn bộ menu, xem tất cả dữ liệu và làm được "
                                "các thao tác nhạy cảm. Không sửa, không xóa được.",
                                color="blue",
                                mt="xs",
                            )
                            if is_system
                            else html.Div(),
                        ],
                        withBorder=True,
                        radius="sm",
                        p="sm",
                    ),
                    # Section 2: Menu được truy cập
                    render_menu_checkboxes(ctx, role_id),
                    # Section 3: Xem trước thanh bên & Người dùng mang vai trò (chia 2 cột)
                    dmc.Grid(
                        gutter="xs",
                        children=[
                            dmc.GridCol(
                                dmc.Paper(
                                    [
                                        dmc.Group(
                                            [
                                                dmc.Text("Xem trước thanh bên", fw=600, size="sm"),
                                                dmc.Text("Người có vai trò này sẽ thấy", size="xs", c="dimmed"),
                                            ],
                                            justify="space-between",
                                            mb="xs",
                                        ),
                                        html.Div(
                                            id="roles-sidebar-preview",
                                            children=render_sidebar_preview(
                                                ctx, _effective_role_menus(ctx, role), is_admin=is_system
                                            ),
                                            style={"maxHeight": "240px", "overflowY": "auto"},
                                        ),
                                        dmc.Divider(my="xs"),
                                        dmc.Text(_SCOPE_NOTE, size="xs", c="dimmed"),
                                    ],
                                    withBorder=True,
                                    radius="sm",
                                    p="sm",
                                    style={"height": "100%"},
                                ),
                                span={"base": 12, "lg": 6},
                            ),
                            dmc.GridCol(
                                dmc.Paper(
                                    [
                                        dmc.Group(
                                            [
                                                dmc.Text(
                                                    f"Người dùng có vai trò này ({len(users)})", fw=600, size="sm"
                                                ),
                                                dmc.Text("Gán vai trò ở màn Người dùng", size="xs", c="dimmed"),
                                            ],
                                            justify="space-between",
                                            mb="xs",
                                        ),
                                        html.Div(
                                            users_table,
                                            style={"maxHeight": "260px", "overflowY": "auto"},
                                        ),
                                    ],
                                    withBorder=True,
                                    radius="sm",
                                    p="sm",
                                    style={"height": "100%"},
                                ),
                                span={"base": 12, "lg": 6},
                            ),
                        ],
                    ),
                ],
            ),
            # Sticky Dirty Bar ở chân panel
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Text("Chưa có thay đổi.", size="xs", c="dimmed", id="roles-dirty-text"),
                        dmc.Group(
                            [
                                button_subtle("Hủy thay đổi", id="roles-discard-btn", size="xs", disabled=True),
                                button_primary("Lưu vai trò", id="roles-save-btn", size="xs", disabled=True),
                            ],
                            gap="xs",
                        ),
                    ],
                    justify="space-between",
                    align="center",
                ),
                id="roles-dirty-bar",
                withBorder=True,
                radius="sm",
                shadow="xs",
                p="xs",
                mt="xs",
                style={"position": "sticky", "bottom": 0, "zIndex": 10},
            ),
        ],
    )


def render_effective_panel(ctx: Ctx, user_id: int) -> Any:
    """Tab 2: quyền thực tế của một người dùng (Fluent Compact Grid 2 cột)."""
    res = effective_of_user(ctx, user_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy người dùng.", tone="crit")
    data = res.data
    labels = _menu_label_map(ctx)
    all_roles = _role_rows(ctx)
    role_menus = {str(r["code"]): set(r["menus"]) for r in all_roles}

    rows: list[Any] = []
    for code in data["menus"]:
        granters = [rc for rc in data["roles"] if code in role_menus.get(rc, set())]
        if data["is_admin"]:
            granters = ["ADMIN (hệ thống)"]
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(labels.get(code, code), size="xs", fw=500)),
                    dmc.TableTd(
                        dmc.Text(
                            ", ".join(granters) if granters else "—",
                            size="xs",
                            c="dimmed",
                            style={"fontFamily": "monospace"},
                        )
                    ),
                ]
            )
        )

    menu_table = (
        dmc.Table(
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
            withColumnBorders=False,
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("Menu", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}),
                            dmc.TableTh(
                                "Có từ vai trò", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}
                            ),
                        ]
                    )
                ),
                dmc.TableTbody(rows),
            ],
        )
        if rows
        else empty_state("Người dùng này chưa có menu nào.", "")
    )

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "8px"},
        children=[
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Group(
                            [
                                DashIconify(
                                    icon="lucide:user", width=18, color="var(--mantine-color-blue-filled)"
                                ),
                                dmc.Text(f"{data['full_name']} ({data['username']})", fw=600, size="sm"),
                                dmc.Badge(
                                    "Admin" if data["is_admin"] else "Vai trò thường",
                                    color="blue" if data["is_admin"] else "gray",
                                    size="xs",
                                    variant="light",
                                ),
                            ],
                            gap="xs",
                            align="center",
                        ),
                        dmc.Text(
                            "Xem tất cả dữ liệu." if data["is_admin"] else "Chỉ thấy run do mình chạy.",
                            size="xs",
                            c="dimmed",
                        ),
                    ],
                    justify="space-between",
                    align="center",
                ),
                withBorder=True,
                radius="sm",
                p="xs",
            ),
            dmc.Grid(
                gutter="xs",
                children=[
                    dmc.GridCol(
                        dmc.Paper(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text("Menu thực tế", fw=600, size="sm"),
                                        dmc.Badge(
                                            f"{len(data['menus'])} menu", size="xs", color="gray", variant="light"
                                        ),
                                    ],
                                    justify="space-between",
                                    mb="xs",
                                ),
                                html.Div(
                                    menu_table,
                                    style={"maxHeight": "calc(100vh - 240px)", "overflowY": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            p="sm",
                            style={"height": "100%"},
                        ),
                        span={"base": 12, "lg": 6},
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            [
                                dmc.Text("Thanh bên người này thấy", fw=600, size="sm", mb="xs"),
                                html.Div(
                                    render_sidebar_preview(
                                        ctx, list(data["menus"]), is_admin=bool(data["is_admin"])
                                    ),
                                    style={"maxHeight": "calc(100vh - 240px)", "overflowY": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            p="sm",
                            style={"height": "100%"},
                        ),
                        span={"base": 12, "lg": 6},
                    ),
                ],
            ),
        ],
    )


def render_sim_panel(ctx: Ctx, user_id: int) -> Any:
    """Tab 3: mô phỏng — cùng dữ liệu run, mỗi người thấy khác nhau (Fluent Compact Table)."""
    users_res = list_users(ctx)
    if not users_res.ok or not users_res.data:
        return alert_box("Không tải được danh sách người dùng.", tone="crit")
    target = next((u for u in users_res.data if int(u.id) == user_id), None)
    if target is None:
        return alert_box("Không tìm thấy người dùng.", tone="crit")
    target_ctx = Ctx(
        user_id=int(target.id),
        username=str(target.username),
        full_name=str(target.full_name),
        roles=list(target.roles),
    )
    res = list_runs(target_ctx, RunListFilter(page=1, page_size=50))
    if not res.ok:
        return alert_box(f"Không tải được lịch sử cho {target.username}: {res.message}", tone="crit")
    items = res.data.get("items", []) if isinstance(res.data, dict) else []

    rows: list[Any] = []
    for run in items:
        status_val = str(run.get("status") or "")
        st_color = (
            "green"
            if status_val == "DONE"
            else ("red" if status_val == "FAILED" else ("blue" if status_val == "RUNNING" else "gray"))
        )
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(f"Run #{run.get('id')}", size="xs", fw=500, style={"fontFamily": "monospace"})
                    ),
                    dmc.TableTd(
                        dmc.Text(str(run.get("template_code") or run.get("template_name") or ""), size="xs")
                    ),
                    dmc.TableTd(
                        dmc.Text(str(run.get("created_by") or ""), size="xs", style={"fontFamily": "monospace"})
                    ),
                    dmc.TableTd(
                        dmc.Badge(status_val, size="xs", color=st_color, variant="light")
                        if status_val
                        else dmc.Text("—", size="xs", c="dimmed")
                    ),
                ]
            )
        )

    sim_table = (
        dmc.Table(
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
            withColumnBorders=False,
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("Run", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}),
                            dmc.TableTh(
                                "Template", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}
                            ),
                            dmc.TableTh(
                                "Người chạy", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}
                            ),
                            dmc.TableTh(
                                "Trạng thái", style={"background": "var(--surface-2, #f8fafc)", "fontSize": 12}
                            ),
                        ]
                    )
                ),
                dmc.TableTbody(rows),
            ],
        )
        if rows
        else empty_state("Người dùng này chưa thấy run nào.", "Run mới do họ chạy sẽ hiện ở đây.")
    )

    return dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Text(
                        f"Minh họa màn Lịch sử: {target.username} thấy {len(rows)} run.",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Badge(f"{len(rows)} run", size="xs", color="gray", variant="light"),
                ],
                justify="space-between",
                align="center",
                mb="xs",
            ),
            html.Div(
                sim_table,
                style={"maxHeight": "calc(100vh - 220px)", "overflowY": "auto"},
            ),
        ],
        withBorder=True,
        radius="sm",
        p="sm",
    )


def _user_options(ctx: Ctx) -> list[dict[str, str]]:
    res = list_users(ctx)
    if not res.ok or not res.data:
        return []
    return [{"label": f"{u.full_name} ({u.username})", "value": str(u.id)} for u in res.data]


def layout() -> Any:
    """Layout chính màn hình Vai trò và phân quyền (Screen14) theo Fluent Compact."""
    ctx = _ctx_or_none()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="roles-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang vai trò và phân quyền.", tone="crit"),
            ]
        )
    if ctx is None or not is_admin(ctx):
        return html.Div(
            [
                dcc.Location(id="roles-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn không có quyền truy cập trang vai trò và phân quyền.", tone="crit"),
            ]
        )

    rows = _role_rows(ctx)
    first_id = int(rows[0]["id"]) if rows else None
    first_snapshot = None
    if first_id is not None:
        first_res = get_role(ctx, first_id)
        if first_res.ok and first_res.data:
            first_snapshot = _role_snapshot(ctx, first_res.data)
    user_opts = _user_options(ctx)
    first_user = user_opts[0]["value"] if user_opts else None

    return html.Div(
        id="roles-page-root",
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
        },
        children=[
            dcc.Store(id="roles-selected-store", data=first_id),
            dcc.Store(id="roles-form-store", data=first_snapshot),
            dcc.Store(id="roles-dirty-store", data=False),
            # 1. Header trang 1 dòng chuẩn Fluent Compact
            page_header(
                title="Vai trò và phân quyền",
                subtitle="Phân quyền theo menu: vai trò có menu nào thì người dùng thấy menu đó và thao tác được trong màn đó.",
                style={"marginBottom": "8px"},
            ),
            # 2. Tabs Bar
            dmc.Tabs(
                id="roles-tabs",
                value="roles",
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab("Vai trò", value="roles"),
                            dmc.TabsTab("Quyền thực tế của người dùng", value="users"),
                            dmc.TabsTab("Mô phỏng phạm vi dữ liệu", value="sim"),
                        ],
                        mb="xs",
                    ),
                    # Tab 1: Vai trò (Master–Detail 2 cột)
                    dmc.TabsPanel(
                        value="roles",
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                        children=[
                            dmc.Box(
                                style={
                                    "display": "flex",
                                    "flexDirection": "row",
                                    "flex": 1,
                                    "minHeight": 0,
                                    "gap": "12px",
                                    "overflow": "hidden",
                                },
                                children=[
                                    # Master (Trái): Danh sách vai trò (320px)
                                    dmc.Paper(
                                        [
                                            # Header danh sách vai trò
                                            dmc.Group(
                                                [
                                                    dmc.Group(
                                                        [
                                                            dmc.Text("Vai trò", fw=700, size="sm"),
                                                            dmc.Badge(
                                                                f"{len(rows)} vai trò",
                                                                id="roles-count-badge",
                                                                size="xs",
                                                                color="gray",
                                                                variant="light",
                                                            ),
                                                        ],
                                                        gap="xs",
                                                        align="center",
                                                    ),
                                                    button_primary(
                                                        "+ Thêm vai trò",
                                                        id="roles-add-btn",
                                                        icon="lucide:plus",
                                                        size="xs",
                                                    ),
                                                ],
                                                justify="space-between",
                                                align="center",
                                                mb="xs",
                                            ),
                                            # Ô tìm kiếm vai trò
                                            dmc.TextInput(
                                                id="roles-search-input",
                                                placeholder="Tên hoặc mã vai trò...",
                                                leftSection=DashIconify(icon="lucide:search", width=14),
                                                size="xs",
                                                debounce=300,
                                                mb="xs",
                                            ),
                                            # Danh sách thẻ vai trò cuộn độc lập
                                            dmc.Box(
                                                id="roles-list",
                                                children=render_roles_list(ctx, selected_id=first_id),
                                                style={"flex": 1, "minHeight": 0, "overflowY": "auto"},
                                            ),
                                        ],
                                        withBorder=True,
                                        radius="sm",
                                        p="xs",
                                        style={
                                            "width": "320px",
                                            "minWidth": "320px",
                                            "maxWidth": "320px",
                                            "display": "flex",
                                            "flexDirection": "column",
                                            "minHeight": 0,
                                            "height": "100%",
                                        },
                                    ),
                                    # Detail (Phải): Chi tiết & Phân quyền vai trò
                                    html.Div(
                                        id="roles-detail",
                                        children=render_role_detail(ctx, first_id)
                                        if first_id
                                        else empty_state(
                                            "Chưa có vai trò nào.",
                                            "Thêm vai trò để giao quyền cho người dùng khác.",
                                        ),
                                        style={
                                            "flex": 1,
                                            "minWidth": 0,
                                            "minHeight": 0,
                                            "height": "100%",
                                            "overflow": "hidden",
                                            "display": "flex",
                                            "flexDirection": "column",
                                        },
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Tab 2: Quyền thực tế của người dùng
                    dmc.TabsPanel(
                        value="users",
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                        children=[
                            dmc.Paper(
                                dmc.Group(
                                    [
                                        dmc.Select(
                                            id="roles-effective-user",
                                            label="Chọn người dùng",
                                            data=user_opts,
                                            value=first_user,
                                            size="xs",
                                            w=320,
                                            leftSection=DashIconify(icon="lucide:user", width=14),
                                        ),
                                        dmc.Text(
                                            "Kiểm tra tổng hợp các menu mà người dùng được cấp quyền từ tất cả vai trò.",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    justify="space-between",
                                    align="flex-end",
                                ),
                                withBorder=True,
                                radius="sm",
                                p="xs",
                                mb="xs",
                            ),
                            dmc.Box(
                                id="roles-effective-panel",
                                children=render_effective_panel(ctx, int(first_user))
                                if first_user
                                else empty_state("Chưa có người dùng nào.", ""),
                                style={"flex": 1, "minHeight": 0, "overflowY": "auto"},
                            ),
                        ],
                    ),
                    # Tab 3: Mô phỏng phạm vi dữ liệu
                    dmc.TabsPanel(
                        value="sim",
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                        children=[
                            dmc.Paper(
                                dmc.Group(
                                    [
                                        dmc.Select(
                                            id="roles-sim-user",
                                            label="Đăng nhập như",
                                            data=user_opts,
                                            value=first_user,
                                            size="xs",
                                            w=320,
                                            leftSection=DashIconify(icon="lucide:user-check", width=14),
                                        ),
                                        dmc.Text(
                                            "Xem trước danh sách Run mà người dùng này có thể nhìn thấy theo phân quyền.",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    justify="space-between",
                                    align="flex-end",
                                ),
                                withBorder=True,
                                radius="sm",
                                p="xs",
                                mb="xs",
                            ),
                            dmc.Box(
                                id="roles-sim-panel",
                                children=render_sim_panel(ctx, int(first_user))
                                if first_user
                                else empty_state("Chưa có người dùng nào.", ""),
                                style={"flex": 1, "minHeight": 0, "overflowY": "auto"},
                            ),
                        ],
                    ),
                ],
            ),
            # Modals
            dmc.Modal(
                id="roles-create-modal",
                title="Thêm vai trò",
                opened=False,
                radius="sm",
                size="md",
                trapFocus=False,
                children=[
                    dmc.TextInput(
                        id="roles-create-code",
                        label="Mã vai trò",
                        placeholder="VD: AUDITOR",
                        required=True,
                        size="xs",
                    ),
                    dmc.TextInput(
                        id="roles-create-name",
                        label="Tên vai trò",
                        placeholder="VD: Kiểm toán viên",
                        required=True,
                        size="xs",
                        mt="xs",
                    ),
                    dmc.Textarea(
                        id="roles-create-desc",
                        label="Mô tả",
                        placeholder="Mô tả vai trò...",
                        size="xs",
                        mt="xs",
                    ),
                    dmc.Select(
                        id="roles-create-copy-from",
                        label="Sao chép menu từ vai trò",
                        data=[{"label": "Không sao chép", "value": ""}]
                        + [{"label": f"{r['name']} ({r['code']})", "value": str(r["id"])} for r in rows],
                        value="",
                        size="xs",
                        mt="xs",
                    ),
                    html.Div(id="roles-create-error", style={"marginTop": "8px"}),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="roles-create-cancel", size="xs"),
                            button_primary("Tạo vai trò", id="roles-create-confirm", size="xs"),
                        ],
                        justify="flex-end",
                        mt="md",
                    ),
                ],
            ),
            dmc.Modal(
                id="roles-save-modal",
                title="Lưu vai trò",
                opened=False,
                radius="sm",
                size="sm",
                trapFocus=False,
                children=[
                    html.Div(id="roles-save-modal-body"),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="roles-save-cancel", size="xs"),
                            button_primary("Lưu", id="roles-save-confirm", size="xs"),
                        ],
                        justify="flex-end",
                        mt="md",
                    ),
                ],
            ),
            modal_confirm(
                "roles-delete-modal",
                "Xóa vai trò",
                "Xóa vai trò này? Người dùng đang mang vai trò sẽ mất các menu của vai trò.",
                confirm_label="Xóa vai trò",
            ),
            html.Div(id="roles-toast"),
        ],
    )


# ---------- Callbacks ----------


@callback(
    Output("roles-list", "children"),
    Input("roles-search-input", "value"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_roles_search(q: str | None, selected_id: int | None) -> Any:
    ctx = _ctx_or_none()
    if ctx is None:
        raise dash.exceptions.PreventUpdate
    return render_roles_list(ctx, q=q, selected_id=selected_id)


@callback(
    Output("roles-selected-store", "data"),
    Output("roles-detail", "children"),
    Output("roles-dirty-store", "data", allow_duplicate=True),
    Output("roles-form-store", "data", allow_duplicate=True),
    Output("roles-list", "children", allow_duplicate=True),
    Input({"type": "role-select-btn", "index": ALL}, "n_clicks"),
    State("roles-search-input", "value"),
    prevent_initial_call=True,
)
def handle_select_role(n_clicks_list: list[int | None], search_q: str | None = None) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    role_id = int(triggered["index"])
    res = get_role(ctx, role_id)
    snapshot = _role_snapshot(ctx, res.data) if res.ok and res.data else None
    return (
        role_id,
        render_role_detail(ctx, role_id),
        False,
        snapshot,
        render_roles_list(ctx, q=search_q, selected_id=role_id),
    )


@callback(
    Output("roles-create-modal", "opened"),
    Input("roles-add-btn", "n_clicks"),
    Input("roles-create-cancel", "n_clicks"),
    State("roles-create-modal", "opened"),
    prevent_initial_call=True,
)
def handle_create_modal(add_clicks: int | None, cancel_clicks: int | None, opened: bool) -> bool:
    if not add_clicks and not cancel_clicks:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered == "roles-add-btn":
        return True
    return False


@callback(
    Output("roles-create-modal", "opened", allow_duplicate=True),
    Output("roles-create-error", "children"),
    Output("roles-list", "children", allow_duplicate=True),
    Output("roles-selected-store", "data", allow_duplicate=True),
    Output("roles-detail", "children", allow_duplicate=True),
    Output("roles-count-badge", "children", allow_duplicate=True),
    Input("roles-create-confirm", "n_clicks"),
    State("roles-create-code", "value"),
    State("roles-create-name", "value"),
    State("roles-create-desc", "value"),
    State("roles-create-copy-from", "value"),
    prevent_initial_call=True,
)
def handle_create_role(
    _n: int | None,
    code: str | None,
    name: str | None,
    desc: str | None,
    copy_from: str | None,
) -> Any:
    ctx = _ctx_or_none()
    if ctx is None:
        raise dash.exceptions.PreventUpdate
    menus: list[str] = []
    if copy_from:
        src = get_role(ctx, int(copy_from))
        if src.ok and src.data:
            menus = list(src.data["menus"])
    res = create_role(ctx, code=code or "", name=name or "", description=desc or None, menus=menus)
    if not res.ok:
        return (
            False,
            alert_box(res.message, tone="crit"),
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    new_data: dict[str, Any] = res.data if isinstance(res.data, dict) else {}
    new_id = int(new_data["id"])
    return (
        False,
        None,
        render_roles_list(ctx, selected_id=new_id),
        new_id,
        render_role_detail(ctx, new_id),
        f"{len(_role_rows(ctx))} vai trò",
    )


@callback(
    Output("roles-dirty-store", "data"),
    Output("roles-save-btn", "disabled"),
    Output("roles-discard-btn", "disabled"),
    Output("roles-dirty-text", "children"),
    Output("roles-sidebar-preview", "children", allow_duplicate=True),
    Input("roles-name-input", "value"),
    Input("roles-desc-input", "value"),
    Input("roles-active-switch", "checked"),
    Input("roles-menus-group", "value"),
    State("roles-form-store", "data"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_role_form_change(
    name: str | None,
    desc: str | None,
    is_active: bool | None,
    menus: list[str] | None,
    snapshot: dict[str, Any] | None,
    role_id: int | None,
) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or snapshot is None or role_id is None:
        raise dash.exceptions.PreventUpdate
    dirty = (
        (name or "") != snapshot["name"]
        or (desc or "") != snapshot["description"]
        or bool(is_active) != bool(snapshot["is_active"])
        or sorted(menus or []) != sorted(snapshot["menus"])
    )
    preview = render_sidebar_preview(ctx, list(menus or []), is_admin=_role_is_system(ctx, role_id))
    if not dirty:
        return False, True, True, "Chưa có thay đổi.", preview
    return True, False, False, "Đã có thay đổi chưa lưu.", preview


@callback(
    Output("roles-save-modal", "opened"),
    Output("roles-save-modal-body", "children"),
    Input("roles-save-btn", "n_clicks"),
    State("roles-selected-store", "data"),
    State("roles-name-input", "value"),
    State("roles-desc-input", "value"),
    State("roles-active-switch", "checked"),
    State("roles-menus-group", "value"),
    State("roles-form-store", "data"),
    prevent_initial_call=True,
)
def handle_save_modal_open(
    _n: int | None,
    role_id: int | None,
    name: str | None,
    desc: str | None,
    is_active: bool | None,
    menus: list[str] | None,
    snapshot: dict[str, Any] | None,
) -> Any:
    if not _n:
        raise dash.exceptions.PreventUpdate
    ctx = _ctx_or_none()
    if ctx is None or role_id is None or snapshot is None:
        raise dash.exceptions.PreventUpdate
    labels = _menu_label_map(ctx)
    added = sorted(set(menus or []) - set(snapshot["menus"]))
    removed = sorted(set(snapshot["menus"]) - set(menus or []))
    role_res = get_role(ctx, role_id)
    affected = int(role_res.data["user_count"]) if role_res.ok and role_res.data else 0
    lines: list[Any] = []
    if added:
        lines.append(dmc.Text(f"Thêm menu: {', '.join(labels.get(c, c) for c in added)}", size="xs"))
    if removed:
        lines.append(dmc.Text(f"Bỏ menu: {', '.join(labels.get(c, c) for c in removed)}", size="xs"))
    if (name or "") != snapshot["name"]:
        lines.append(dmc.Text(f"Đổi tên: {snapshot['name']} → {name}", size="xs"))
    if bool(is_active) != bool(snapshot["is_active"]):
        lines.append(
            dmc.Text(
                "Tắt vai trò." if not is_active else "Bật lại vai trò.",
                size="xs",
            )
        )
    if not lines:
        lines.append(dmc.Text("Không có thay đổi nào.", size="xs"))
    lines.append(
        dmc.Text(
            f"Ảnh hưởng tới {affected} người dùng đang mang vai trò này. Quyền mới có hiệu lực trong tối đa 5 giây.",
            size="xs",
            c="dimmed",
            mt="xs",
        )
    )
    return True, html.Div(lines)


@callback(
    Output("roles-save-modal", "opened", allow_duplicate=True),
    Output("roles-detail", "children", allow_duplicate=True),
    Output("roles-dirty-store", "data", allow_duplicate=True),
    Output("roles-form-store", "data", allow_duplicate=True),
    Output("roles-list", "children", allow_duplicate=True),
    Output("roles-toast", "children"),
    Input("roles-save-confirm", "n_clicks"),
    Input("roles-save-cancel", "n_clicks"),
    State("roles-selected-store", "data"),
    State("roles-name-input", "value"),
    State("roles-desc-input", "value"),
    State("roles-active-switch", "checked"),
    State("roles-menus-group", "value"),
    State("roles-form-store", "data"),
    prevent_initial_call=True,
)
def handle_save_role(
    _confirm: int | None,
    _cancel: int | None,
    role_id: int | None,
    name: str | None,
    desc: str | None,
    is_active: bool | None,
    menus: list[str] | None,
    snapshot: dict[str, Any] | None,
) -> Any:
    ctx = _ctx_or_none()
    triggered = dash.callback_context.triggered_id
    if ctx is None or role_id is None or snapshot is None:
        raise dash.exceptions.PreventUpdate
    if triggered == "roles-save-cancel":
        return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, None
    res = update_role(
        ctx,
        role_id,
        name=name,
        description=desc,
        menus=list(menus or []),
        row_version=int(snapshot["row_version"]),
        is_active=bool(is_active),
    )
    if not res.ok:
        return (
            True,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            alert_box(res.message, tone="crit"),
        )
    new_data: dict[str, Any] = res.data if isinstance(res.data, dict) else {}
    new_snapshot = _role_snapshot(ctx, new_data)
    return (
        False,
        render_role_detail(ctx, role_id),
        False,
        new_snapshot,
        render_roles_list(ctx, selected_id=role_id),
        None,
    )


@callback(
    Output("roles-detail", "children", allow_duplicate=True),
    Output("roles-dirty-store", "data", allow_duplicate=True),
    Output("roles-form-store", "data", allow_duplicate=True),
    Input("roles-discard-btn", "n_clicks"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_discard_role(_n: int | None, role_id: int | None) -> Any:
    if not _n:
        raise dash.exceptions.PreventUpdate
    ctx = _ctx_or_none()
    if ctx is None or role_id is None:
        raise dash.exceptions.PreventUpdate
    res = get_role(ctx, role_id)
    snapshot = _role_snapshot(ctx, res.data) if res.ok and res.data else None
    return render_role_detail(ctx, role_id), False, snapshot


@callback(
    Output("roles-list", "children", allow_duplicate=True),
    Output("roles-selected-store", "data", allow_duplicate=True),
    Output("roles-detail", "children", allow_duplicate=True),
    Output("roles-toast", "children", allow_duplicate=True),
    Output("roles-count-badge", "children", allow_duplicate=True),
    Input("roles-clone-btn", "n_clicks"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_clone_role(_n: int | None, role_id: int | None) -> Any:
    if not _n:
        raise dash.exceptions.PreventUpdate
    ctx = _ctx_or_none()
    if ctx is None or role_id is None:
        raise dash.exceptions.PreventUpdate
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        raise dash.exceptions.PreventUpdate
    base_code = str(res.data["code"])
    new_id = None
    for suffix in range(2, 10):
        clone = clone_role(ctx, role_id, new_code=f"{base_code}_{suffix}", new_name=f"{res.data['name']} (bản sao)")
        if clone.ok and clone.data:
            new_id = int(clone.data["id"])
            break
        if clone.code != "ROLE_CODE_EXISTS":
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                alert_box(clone.message, tone="crit"),
                dash.no_update,
            )
    if new_id is None:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            alert_box("Không tạo được bản sao, mã vai trò đã tồn tại.", tone="crit"),
            dash.no_update,
        )
    return (
        render_roles_list(ctx, selected_id=new_id),
        new_id,
        render_role_detail(ctx, new_id),
        None,
        f"{len(_role_rows(ctx))} vai trò",
    )


@callback(
    Output("roles-delete-modal", "opened"),
    Input("roles-delete-btn", "n_clicks"),
    Input("roles-delete-modal-cancel", "n_clicks"),
    State("roles-delete-modal", "opened"),
    prevent_initial_call=True,
)
def handle_delete_modal(_del: int | None, _cancel: int | None, opened: bool) -> bool:
    if not _del and not _cancel:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered == "roles-delete-btn":
        return True
    return False


@callback(
    Output("roles-delete-modal", "opened", allow_duplicate=True),
    Output("roles-list", "children", allow_duplicate=True),
    Output("roles-selected-store", "data", allow_duplicate=True),
    Output("roles-detail", "children", allow_duplicate=True),
    Output("roles-toast", "children", allow_duplicate=True),
    Output("roles-count-badge", "children", allow_duplicate=True),
    Input("roles-delete-modal-confirm", "n_clicks"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_delete_role(_n: int | None, role_id: int | None) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or role_id is None:
        raise dash.exceptions.PreventUpdate
    res = delete_role(ctx, role_id)
    if not res.ok:
        return True, dash.no_update, dash.no_update, dash.no_update, alert_box(res.message, tone="crit"), dash.no_update
    rows = _role_rows(ctx)
    new_id = int(rows[0]["id"]) if rows else None
    detail = render_role_detail(ctx, new_id) if new_id else empty_state("Chưa có vai trò nào.", "")
    return False, render_roles_list(ctx, selected_id=new_id), new_id, detail, None, f"{len(rows)} vai trò"


@callback(
    Output("roles-menus-group", "value", allow_duplicate=True),
    Input("roles-select-all-menus", "n_clicks"),
    Input("roles-deselect-all-menus", "n_clicks"),
    prevent_initial_call=True,
)
def handle_select_all_menus(_on: int | None, _off: int | None) -> list[str]:
    if not _on and not _off:
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered == "roles-select-all-menus":
        ctx = _ctx_or_none()
        if ctx is None:
            raise dash.exceptions.PreventUpdate
        codes: list[str] = []
        for group in _menu_tree(ctx):
            codes.extend(m["code"] for m in group["menus"])
        return codes
    return []


@callback(
    Output("roles-effective-panel", "children"),
    Input("roles-effective-user", "value"),
    prevent_initial_call=True,
)
def handle_effective_user_change(user_id: str | None) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or not user_id:
        raise dash.exceptions.PreventUpdate
    return render_effective_panel(ctx, int(user_id))


@callback(
    Output("roles-sim-panel", "children"),
    Input("roles-sim-user", "value"),
    prevent_initial_call=True,
)
def handle_sim_user_change(user_id: str | None) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or not user_id:
        raise dash.exceptions.PreventUpdate
    return render_sim_panel(ctx, int(user_id))
