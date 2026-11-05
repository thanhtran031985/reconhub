"""app/ui/pages/roles.py — Màn hình Vai trò và phân quyền (Screen14).

Theo spec 11 mục 7.1, 3 tab: Vai trò / Quyền thực tế của người dùng /
Mô phỏng phạm vi dữ liệu. Bảng "Phạm vi dữ liệu và thao tác đặc biệt"
của prototype được thay bằng một dòng ghi chú (spec 11 mục 7.1).
Chỉ ADMIN truy cập (menu `role`).

Phân quyền: chỉ ADMIN truy cập; người khác thấy thông báo không có quyền.
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
from app.ui.layout.shell import get_nav_items_for_menus

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


def _role_snapshot(ctx: Ctx, role: dict[str, Any]) -> dict[str, Any]:
    """Snapshot form để so sánh thay đổi (dirty check).

    Vai trò hệ thống không lưu dòng role_menu nhưng luôn có toàn bộ menu,
    nên snapshot ghi đủ các mã menu để tránh báo thay đổi giả.
    """
    menus = sorted(role["menus"])
    if role["is_system"]:
        menus = sorted({m["code"] for g in _menu_tree(ctx) for m in g["menus"]})
    return {
        "menus": menus,
        "name": str(role["name"]),
        "description": str(role["description"] or ""),
        "is_active": bool(role["is_active"]),
        "row_version": int(role["row_version"]),
    }


def render_roles_list(ctx: Ctx, q: str | None = None, selected_id: int | None = None) -> Any:
    """Cột trái: ô tìm kiếm + danh sách vai trò."""
    rows = _role_rows(ctx)
    if q:
        term = q.strip().lower()
        rows = [r for r in rows if term in str(r["code"]).lower() or term in str(r["name"]).lower()]
    if not rows:
        return empty_state(
            "Chưa có vai trò nào khớp.",
            "Thử từ khóa khác hoặc thêm vai trò mới.",
        )
    items = []
    for r in rows:
        is_selected = selected_id is not None and int(r["id"]) == selected_id
        items.append(
            dmc.Button(
                dmc.Group(
                    [
                        dmc.Stack(
                            [
                                dmc.Text(str(r["name"]), fw=600, size="sm"),
                                dmc.Text(
                                    str(r["code"]),
                                    size="xs",
                                    c="dimmed",
                                    style={"fontFamily": "monospace"},
                                ),
                            ],
                            gap=0,
                        ),
                        dmc.Badge(
                            f"{r['user_count']} người dùng",
                            size="xs",
                            color="gray",
                            variant="light",
                        ),
                    ],
                    justify="space-between",
                    w="100%",
                ),
                id={"type": "role-select-btn", "index": int(r["id"])},
                variant="light" if is_selected else "subtle",
                color="blue" if is_selected else "gray",
                fullWidth=True,
                justify="flex-start",
                mb="xs",
            )
        )
    return html.Div(items)


def render_menu_checkboxes(ctx: Ctx, role_id: int) -> Any:
    """Checkbox menu theo nhóm, kèm nhãn Mới / Đang ẩn (spec 11 mục 7.1)."""
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy vai trò.", tone="crit")
    role = res.data
    is_system = bool(role["is_system"])
    current = set(role["menus"])
    tree = _menu_tree(ctx)
    if is_system:
        # Vai trò hệ thống luôn có toàn bộ menu (không lưu dòng role_menu):
        # hiển thị tất cả đã tick, chỉ đọc.
        current = {m["code"] for g in tree for m in g["menus"]}
    groups = []
    for group in tree:
        boxes = []
        for menu in group["menus"]:
            badges = []
            if menu["is_new"]:
                badges.append(dmc.Badge("Mới", size="xs", color="green", variant="light"))
            if menu["is_hidden"]:
                badges.append(dmc.Badge("Đang ẩn", size="xs", color="orange", variant="light"))
            boxes.append(
                dmc.Checkbox(
                    label=dmc.Group(
                        [dmc.Text(menu["label"], size="sm"), *badges],
                        gap="xs",
                    ),
                    value=menu["code"],
                    disabled=is_system,
                )
            )
        groups.append(
            dmc.Stack(
                [
                    dmc.Text(group["label"], fw=600, size="sm"),
                    dmc.Stack(boxes, gap="xs"),
                ],
                gap="xs",
                mb="md",
            )
        )
    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Text("Menu được truy cập", fw=600, size="sm"),
                    button_subtle("Chọn tất cả", id="roles-select-all-menus", size="xs"),
                    button_subtle("Bỏ chọn tất cả", id="roles-deselect-all-menus", size="xs"),
                ],
                gap="sm",
            )
            if not is_system
            else dmc.Text("Menu được truy cập", fw=600, size="sm"),
            dmc.Text(
                "Có menu = thấy menu ở thanh bên và thao tác được trong màn đó. "
                "Quyền được kiểm ở server, không chỉ ẩn menu.",
                size="xs",
                c="dimmed",
                mb="md",
            ),
            dmc.CheckboxGroup(
                id="roles-menus-group",
                value=sorted(current),
                children=groups,
            ),
        ]
    )


def render_sidebar_preview(ctx: Ctx, menu_codes: list[str]) -> Any:
    """Xem trước thanh bên người có các menu này sẽ thấy."""
    groups = get_nav_items_for_menus(set(menu_codes))
    if not groups:
        return dmc.Text("Không thấy menu nào ở thanh bên.", size="sm", c="dimmed")
    blocks = []
    for group in groups:
        blocks.append(dmc.Text(group["title"], size="xs", fw=700, c="dimmed", mt="sm"))
        for item in group["items"]:
            blocks.append(
                dmc.Group(
                    [
                        DashIconify(icon=item["icon"], width=16),
                        dmc.Text(item["label"], size="sm"),
                    ],
                    gap="xs",
                )
            )
    return html.Div(blocks)


def render_role_detail(ctx: Ctx, role_id: int) -> Any:
    """Cột phải: form sửa vai trò + người dùng mang vai trò."""
    res = get_role(ctx, role_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy vai trò.", tone="crit")
    role = res.data
    is_system = bool(role["is_system"])
    users_res = users_of(ctx, role_id)
    users = users_res.data if users_res.ok and users_res.data else []
    user_rows = []
    for u in users:
        user_rows.append(
            html.Tr(
                [
                    html.Td(u["username"]),
                    html.Td(u["full_name"]),
                    html.Td("Đang dùng" if u["is_active"] else "Đã tắt"),
                ]
            )
        )
    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text(str(role["name"]), fw=700, size="lg"),
                            dmc.Text(
                                str(role["code"]),
                                size="sm",
                                c="dimmed",
                                style={"fontFamily": "monospace"},
                            ),
                        ],
                        gap=0,
                    ),
                    dmc.Group(
                        [
                            button_subtle("Nhân bản", id="roles-clone-btn", icon="lucide:copy"),
                            button_subtle(
                                "Xóa vai trò",
                                id="roles-delete-btn",
                                icon="lucide:trash-2",
                                color="red",
                                disabled=is_system,
                            ),
                        ],
                        gap="sm",
                    ),
                ],
                justify="space-between",
            ),
            dmc.TextInput(
                id="roles-name-input",
                label="Tên vai trò",
                value=str(role["name"]),
                required=True,
                disabled=is_system,
                mt="md",
            ),
            dmc.Textarea(
                id="roles-desc-input",
                label="Mô tả",
                value=str(role["description"] or ""),
                mt="sm",
            ),
            dmc.Switch(
                id="roles-active-switch",
                label="Đang dùng (tắt thì người có vai trò này mất các menu của vai trò khi đăng nhập lại hoặc trong vài giây)",
                checked=bool(role["is_active"]),
                disabled=is_system,
                mt="sm",
            ),
            dmc.Alert(
                "Vai trò hệ thống Admin luôn có toàn bộ menu, xem tất cả dữ liệu và làm được "
                "các thao tác nhạy cảm. Không sửa, không xóa được.",
                color="blue",
                mt="md",
            )
            if is_system
            else html.Div(),
            dmc.Divider(mt="lg", mb="md"),
            render_menu_checkboxes(ctx, role_id),
            dmc.Divider(mt="lg", mb="md"),
            dmc.Text("Xem trước thanh bên", fw=600, size="sm"),
            dmc.Text("Người có vai trò này sẽ thấy", size="xs", c="dimmed"),
            html.Div(id="roles-sidebar-preview", children=render_sidebar_preview(ctx, list(role["menus"]))),
            dmc.Divider(mt="lg", mb="md"),
            dmc.Text(f"Người dùng có vai trò này ({len(users)})", fw=600, size="sm"),
            dmc.Text("Gán vai trò ở màn Người dùng", size="xs", c="dimmed"),
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Username", style={"textAlign": "left"}),
                                html.Th("Họ tên", style={"textAlign": "left"}),
                                html.Th("Trạng thái", style={"textAlign": "left"}),
                            ]
                        )
                    ),
                    html.Tbody(user_rows),
                ],
                style={"width": "100%", "marginTop": 8},
            )
            if users
            else dmc.Text("Chưa có người dùng nào mang vai trò này.", size="sm", c="dimmed", mt="sm"),
            dmc.Group(
                [
                    dmc.Text("Chưa có thay đổi.", size="sm", c="dimmed", id="roles-dirty-text"),
                    button_subtle("Hủy thay đổi", id="roles-discard-btn"),
                    button_primary("Lưu vai trò", id="roles-save-btn"),
                ],
                justify="flex-end",
                mt="lg",
                id="roles-dirty-bar",
                style={"display": "none"},
            ),
        ]
    )


def render_effective_panel(ctx: Ctx, user_id: int) -> Any:
    """Tab 2: quyền thực tế của một người dùng."""
    res = effective_of_user(ctx, user_id)
    if not res.ok or not res.data:
        return alert_box("Không tìm thấy người dùng.", tone="crit")
    data = res.data
    labels = _menu_label_map(ctx)
    all_roles = _role_rows(ctx)
    role_menus = {str(r["code"]): set(r["menus"]) for r in all_roles}
    rows = []
    for code in data["menus"]:
        granters = [rc for rc in data["roles"] if code in role_menus.get(rc, set())]
        if data["is_admin"]:
            granters = ["ADMIN (hệ thống)"]
        rows.append(
            html.Tr(
                [
                    html.Td(labels.get(code, code)),
                    html.Td(", ".join(granters) if granters else "—"),
                ]
            )
        )
    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Text(f"{data['full_name']} ({data['username']})", fw=600, size="md"),
                    dmc.Badge(
                        "Admin" if data["is_admin"] else "Vai trò thường", color="blue" if data["is_admin"] else "gray"
                    ),
                ],
                gap="sm",
            ),
            dmc.Text(
                "Xem tất cả dữ liệu." if data["is_admin"] else "Chỉ thấy run do mình chạy.",
                size="sm",
                c="dimmed",
                mt="xs",
            ),
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Menu", style={"textAlign": "left"}),
                                html.Th("Có từ vai trò", style={"textAlign": "left"}),
                            ]
                        )
                    ),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "marginTop": 12},
            )
            if rows
            else empty_state("Người dùng này chưa có menu nào.", ""),
            dmc.Divider(mt="lg", mb="md"),
            dmc.Text("Thanh bên người này thấy", fw=600, size="sm"),
            render_sidebar_preview(ctx, list(data["menus"])),
        ]
    )


def render_sim_panel(ctx: Ctx, user_id: int) -> Any:
    """Tab 3: mô phỏng — cùng dữ liệu run, mỗi người thấy khác nhau."""
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
    rows = []
    for run in items:
        rows.append(
            html.Tr(
                [
                    html.Td(f"Run #{run.get('id')}"),
                    html.Td(str(run.get("template_code") or run.get("template_name") or "")),
                    html.Td(str(run.get("created_by") or "")),
                    html.Td(str(run.get("status") or "")),
                ]
            )
        )
    return html.Div(
        [
            dmc.Text(
                f"Minh họa màn Lịch sử: {target.username} thấy {len(rows)} run.",
                size="sm",
                c="dimmed",
            ),
            html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Run", style={"textAlign": "left"}),
                                html.Th("Template", style={"textAlign": "left"}),
                                html.Th("Người chạy", style={"textAlign": "left"}),
                                html.Th("Trạng thái", style={"textAlign": "left"}),
                            ]
                        )
                    ),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "marginTop": 12},
            )
            if rows
            else empty_state("Người dùng này chưa thấy run nào.", "Run mới do họ chạy sẽ hiện ở đây."),
        ]
    )


def _user_options(ctx: Ctx) -> list[dict[str, str]]:
    res = list_users(ctx)
    if not res.ok or not res.data:
        return []
    return [{"label": f"{u.full_name} ({u.username})", "value": str(u.id)} for u in res.data]


def layout() -> Any:
    """Layout chính màn hình Vai trò và phân quyền (Screen14)."""
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
        children=[
            dcc.Store(id="roles-selected-store", data=first_id),
            dcc.Store(id="roles-form-store", data=first_snapshot),
            dcc.Store(id="roles-dirty-store", data=False),
            dmc.Group(
                justify="space-between",
                align="flex-start",
                mb="lg",
                children=[
                    html.Div(
                        [
                            dmc.Title("Vai trò và phân quyền", order=2, fw=700),
                            dmc.Text(
                                "Phân quyền theo menu: vai trò có menu nào thì người dùng thấy menu đó "
                                "và thao tác được trong màn đó. Dữ liệu chạy đối soát: Admin xem tất cả, "
                                "vai trò khác chỉ thấy run do mình chạy.",
                                size="sm",
                                c="dimmed",
                                mt=4,
                            ),
                            dmc.Text(_SCOPE_NOTE, size="sm", mt="xs"),
                        ]
                    ),
                ],
            ),
            dmc.Tabs(
                id="roles-tabs",
                value="roles",
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab("Vai trò", value="roles"),
                            dmc.TabsTab("Quyền thực tế của người dùng", value="users"),
                            dmc.TabsTab("Mô phỏng phạm vi dữ liệu", value="sim"),
                        ]
                    ),
                    dmc.TabsPanel(
                        value="roles",
                        pt="md",
                        children=[
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        [
                                            dmc.TextInput(
                                                id="roles-search-input",
                                                label="Tìm vai trò",
                                                placeholder="Tên hoặc mã vai trò",
                                                leftSection=DashIconify(icon="lucide:search", width=16),
                                                debounce=300,
                                            ),
                                            dmc.Box(
                                                id="roles-list",
                                                children=render_roles_list(ctx, selected_id=first_id),
                                                mt="md",
                                            ),
                                            button_primary(
                                                "+ Thêm vai trò",
                                                id="roles-add-btn",
                                                icon="lucide:plus",
                                                fullWidth=True,
                                                mt="md",
                                            ),
                                        ],
                                        span=4,
                                    ),
                                    dmc.GridCol(
                                        html.Div(
                                            id="roles-detail",
                                            children=render_role_detail(ctx, first_id)
                                            if first_id
                                            else empty_state(
                                                "Chưa có vai trò nào.",
                                                "Thêm vai trò để giao quyền cho người dùng khác.",
                                            ),
                                        ),
                                        span=8,
                                    ),
                                ]
                            ),
                        ],
                    ),
                    dmc.TabsPanel(
                        value="users",
                        pt="md",
                        children=[
                            dmc.Select(
                                id="roles-effective-user",
                                label="Người dùng",
                                data=user_opts,
                                value=first_user,
                                style={"width": 320},
                            ),
                            dmc.Box(
                                id="roles-effective-panel",
                                children=render_effective_panel(ctx, int(first_user))
                                if first_user
                                else empty_state("Chưa có người dùng nào.", ""),
                                mt="md",
                            ),
                        ],
                    ),
                    dmc.TabsPanel(
                        value="sim",
                        pt="md",
                        children=[
                            dmc.Select(
                                id="roles-sim-user",
                                label="Đăng nhập như",
                                data=user_opts,
                                value=first_user,
                                style={"width": 320},
                            ),
                            dmc.Box(
                                id="roles-sim-panel",
                                children=render_sim_panel(ctx, int(first_user))
                                if first_user
                                else empty_state("Chưa có người dùng nào.", ""),
                                mt="md",
                            ),
                        ],
                    ),
                ],
            ),
            # Modal thêm vai trò
            dmc.Modal(
                id="roles-create-modal",
                title="Thêm vai trò",
                opened=False,
                children=[
                    dmc.TextInput(id="roles-create-code", label="Mã vai trò", placeholder="VD: AUDITOR", required=True),
                    dmc.TextInput(
                        id="roles-create-name",
                        label="Tên vai trò",
                        placeholder="VD: Kiểm toán viên",
                        required=True,
                        mt="sm",
                    ),
                    dmc.Textarea(id="roles-create-desc", label="Mô tả", mt="sm"),
                    dmc.Select(
                        id="roles-create-copy-from",
                        label="Sao chép menu từ vai trò",
                        data=[{"label": "Không sao chép", "value": ""}]
                        + [{"label": f"{r['name']} ({r['code']})", "value": str(r["id"])} for r in rows],
                        value="",
                        mt="sm",
                    ),
                    html.Div(id="roles-create-error"),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="roles-create-cancel"),
                            button_primary("Tạo vai trò", id="roles-create-confirm"),
                        ],
                        justify="flex-end",
                        mt="lg",
                    ),
                ],
            ),
            # Modal xác nhận lưu (liệt kê menu thêm/bỏ + số người ảnh hưởng)
            dmc.Modal(
                id="roles-save-modal",
                title="Lưu vai trò",
                opened=False,
                children=[
                    html.Div(id="roles-save-modal-body"),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="roles-save-cancel"),
                            button_primary("Lưu", id="roles-save-confirm"),
                        ],
                        justify="flex-end",
                        mt="lg",
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
    Input({"type": "role-select-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_select_role(n_clicks_list: list[int | None]) -> Any:
    ctx = _ctx_or_none()
    if ctx is None or not any(n_clicks_list):
        raise dash.exceptions.PreventUpdate
    triggered = dash.callback_context.triggered_id
    role_id = int(triggered["index"])
    res = get_role(ctx, role_id)
    snapshot = _role_snapshot(ctx, res.data) if res.ok and res.data else None
    return role_id, render_role_detail(ctx, role_id), False, snapshot


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
        return False, alert_box(res.message, tone="crit"), dash.no_update, dash.no_update, dash.no_update
    new_data: dict[str, Any] = res.data if isinstance(res.data, dict) else {}
    new_id = int(new_data["id"])
    return (
        False,
        None,
        render_roles_list(ctx, selected_id=new_id),
        new_id,
        render_role_detail(ctx, new_id),
    )


@callback(
    Output("roles-dirty-store", "data"),
    Output("roles-dirty-bar", "style"),
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
    preview = render_sidebar_preview(ctx, list(menus or []))
    if not dirty:
        return False, {"display": "none"}, "Chưa có thay đổi.", preview
    return True, {"display": "flex"}, "Đã có thay đổi chưa lưu.", preview


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
    # Nút Lưu nằm trong cột chi tiết, bị tạo lại mỗi lần chọn vai trò.
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
    lines = []
    if added:
        lines.append(dmc.Text(f"Thêm menu: {', '.join(labels.get(c, c) for c in added)}", size="sm"))
    if removed:
        lines.append(dmc.Text(f"Bỏ menu: {', '.join(labels.get(c, c) for c in removed)}", size="sm"))
    if (name or "") != snapshot["name"]:
        lines.append(dmc.Text(f"Đổi tên: {snapshot['name']} → {name}", size="sm"))
    if bool(is_active) != bool(snapshot["is_active"]):
        lines.append(
            dmc.Text(
                "Tắt vai trò." if not is_active else "Bật lại vai trò.",
                size="sm",
            )
        )
    if not lines:
        lines.append(dmc.Text("Không có thay đổi nào.", size="sm"))
    lines.append(
        dmc.Text(
            f"Ảnh hưởng tới {affected} người dùng đang mang vai trò này. Quyền mới có hiệu lực trong tối đa 5 giây.",
            size="sm",
            c="dimmed",
            mt="sm",
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
    # Nút Hủy thay đổi nằm trong cột chi tiết, bị tạo lại mỗi lần chọn vai trò.
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
    Input("roles-clone-btn", "n_clicks"),
    State("roles-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_clone_role(_n: int | None, role_id: int | None) -> Any:
    # Nút Nhân bản nằm trong cột chi tiết, bị tạo lại mỗi lần chọn vai trò.
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
            )
    if new_id is None:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            alert_box("Không tạo được bản sao, mã vai trò đã tồn tại.", tone="crit"),
        )
    return (
        render_roles_list(ctx, selected_id=new_id),
        new_id,
        render_role_detail(ctx, new_id),
        None,
    )


@callback(
    Output("roles-delete-modal", "opened"),
    Input("roles-delete-btn", "n_clicks"),
    Input("roles-delete-modal-cancel", "n_clicks"),
    State("roles-delete-modal", "opened"),
    prevent_initial_call=True,
)
def handle_delete_modal(_del: int | None, _cancel: int | None, opened: bool) -> bool:
    # Nút Xóa nằm trong cột chi tiết, bị tạo lại mỗi lần chọn vai trò:
    # Dash kích hoạt lại callback với n_clicks=None, phải chặn như handle_create_modal.
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
        return True, dash.no_update, dash.no_update, dash.no_update, alert_box(res.message, tone="crit")
    rows = _role_rows(ctx)
    new_id = int(rows[0]["id"]) if rows else None
    detail = render_role_detail(ctx, new_id) if new_id else empty_state("Chưa có vai trò nào.", "")
    return False, render_roles_list(ctx, selected_id=new_id), new_id, detail, None


@callback(
    Output("roles-menus-group", "value", allow_duplicate=True),
    Input("roles-select-all-menus", "n_clicks"),
    Input("roles-deselect-all-menus", "n_clicks"),
    prevent_initial_call=True,
)
def handle_select_all_menus(_on: int | None, _off: int | None) -> list[str]:
    # 2 nút nằm trong cột chi tiết, bị tạo lại mỗi lần chọn vai trò.
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
