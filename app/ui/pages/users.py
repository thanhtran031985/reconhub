from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.schemas.user import UserCreateDTO, UserResponse, UserUpdateDTO
from app.services.perm import is_admin, page_gate
from app.services.role import list_roles
from app.services.user import (
    create_user,
    get_login_log,
    list_users,
    reset_password,
    set_active,
    unlock_user,
    update_user,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.field import form_field
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_datetime

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/users",
        title="Người dùng — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "user"

# Vai trò mặc định khi chưa có bảng RECON_ROLE (trước migration task 19).
_FALLBACK_ROLES = [
    {"label": "Admin", "value": "ADMIN"},
    {"label": "Template Owner", "value": "TEMPLATE_OWNER"},
    {"label": "Operator", "value": "OPERATOR"},
    {"label": "Viewer", "value": "VIEWER"},
]


def _role_options(ctx: Ctx | None) -> list[dict[str, str]]:
    """Lựa chọn vai trò từ RECON_ROLE (kể cả vai trò tự tạo ở /roles)."""
    if ctx is None:
        return list(_FALLBACK_ROLES)
    res = list_roles(ctx)
    if not res.ok or not res.data:
        return list(_FALLBACK_ROLES)
    return [{"label": str(r["name"]), "value": str(r["code"])} for r in res.data]


def render_users_table(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    status_filter: str | None = None,
) -> Any:
    """Dựng bảng người dùng theo trạng thái, hỗ trợ 4 trạng thái: Loading, Empty, Error, Data."""
    try:
        active_val: bool | None = None
        if status_filter == "ACTIVE":
            active_val = True
        elif status_filter == "DISABLED":
            active_val = False

        role_val = None if not role or role == "ALL" else role

        users = list_users(ctx, q=q if q else None, role=role_val, active=active_val)
        if not users.ok:
            return alert_box(
                f"Không tải được danh sách người dùng. Lỗi: {users.message}",
                tone="crit",
                action=button_subtle("Thử lại", id="users-retry-btn", size="sm"),
            )

        user_list: list[UserResponse] = users.data or []

        # Lọc thêm nếu status_filter == 'LOCKED'
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if status_filter == "LOCKED":
            user_list = [u for u in user_list if u.locked_until and u.locked_until > now]

        if not user_list:
            return empty_state(
                title="Chỉ có tài khoản của bạn",
                description="Thêm người dùng để giao việc đăng ký template, chạy đối soát.",
                action=button_primary("Thêm người dùng", id="users-empty-add-btn", icon="lucide:plus"),
            )

        rows: list[Any] = []
        for u in user_list:
            # Xác định trạng thái chip
            is_locked = bool(u.locked_until and u.locked_until > now)
            if is_locked and u.locked_until:
                time_str = u.locked_until.strftime("%H:%M")
                user_status = status_chip("LOCKED", label=f"Tạm khóa đến {time_str}")
            elif not u.is_active:
                user_status = status_chip("DISABLED", label="Đã tắt")
            elif u.must_change_pw:
                user_status = status_chip("MUST_CHANGE_PW", label="Chờ đổi mật khẩu")
            else:
                user_status = status_chip("ACTIVE", label="Hoạt động")

            # Roles badges
            roles_badges = dmc.Group(
                [
                    dmc.Badge(
                        r,
                        size="xs",
                        variant="light",
                        color="primary" if r == "ADMIN" else "gray",
                        radius="sm",
                    )
                    for r in u.roles
                ],
                gap=4,
            )

            # Thao tác
            actions_list: list[Any] = [
                dmc.Button(
                    "Sửa",
                    size="xs",
                    variant="default",
                    id={"type": "user-edit-btn", "index": u.id},
                ),
                dmc.Button(
                    "Đặt lại mật khẩu",
                    size="xs",
                    variant="default",
                    id={"type": "user-reset-pw-btn", "index": u.id},
                ),
            ]
            if is_locked:
                actions_list.append(
                    dmc.Button(
                        "Mở khóa",
                        size="xs",
                        variant="default",
                        leftSection=DashIconify(icon="lucide:unlock", width=14),
                        id={"type": "user-unlock-btn", "index": u.id},
                    )
                )

            tr = html.Tr(
                [
                    html.Td(
                        html.Span(u.username, className="mono", style={"fontWeight": 600}),
                        style={"padding": "10px 14px"},
                    ),
                    html.Td(u.full_name, style={"padding": "10px 14px"}),
                    html.Td(u.email or "—", style={"padding": "10px 14px"}),
                    html.Td(roles_badges, style={"padding": "10px 14px"}),
                    html.Td(user_status, style={"padding": "10px 14px"}),
                    html.Td(format_datetime(u.last_login_at), style={"padding": "10px 14px"}),
                    html.Td(
                        dmc.Group(actions_list, gap="xs"),
                        style={"padding": "10px 14px", "textAlign": "right"},
                    ),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
            rows.append(tr)

        th_style = {
            "padding": "8px 12px",
            "position": "sticky",
            "top": 0,
            "background": "var(--bg-subtle, #f8fafc)",
            "zIndex": 1,
        }
        table = dmc.Table(
            striped=True,
            highlightOnHover=True,
            children=[
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Username", style=th_style),
                            html.Th("Họ tên", style=th_style),
                            html.Th("Email", style=th_style),
                            html.Th("Vai trò", style=th_style),
                            html.Th("Trạng thái", style=th_style),
                            html.Th("Đăng nhập cuối", style=th_style),
                            html.Th("", style=th_style),
                        ],
                    )
                ),
                html.Tbody(rows),
            ],
        )

        return dmc.Paper(
            table,
            withBorder=True,
            radius="sm",
            shadow="xs",
            style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflowY": "auto"},
        )
    except Exception as exc:
        return alert_box(
            f"Không tải được danh sách người dùng. Đang hiển thị dữ liệu cũ. Chi tiết: {exc}",
            tone="crit",
            action=button_subtle("Thử lại", id="users-retry-btn", size="sm"),
        )


def build_header_title(ctx: Ctx) -> str:
    """Tính toán tiêu đề với tổng số tài khoản và số tài khoản đang tạm khóa."""
    try:
        users = list_users(ctx)
        if users.ok and users.data:
            user_list = users.data
            total = len(user_list)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            locked = sum(1 for u in user_list if u.locked_until and u.locked_until > now)
            return f"Người dùng: {total} tài khoản, {locked} đang tạm khóa"
    except Exception:
        pass
    return "Người dùng"


def layout() -> Any:
    """Layout chính màn hình Quản lý Người dùng (Screen11)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="users-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang quản lý người dùng.", tone="crit"),
            ]
        )
    if ctx is None or not is_admin(ctx):
        return html.Div(
            [
                dcc.Location(id="users-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn không có quyền truy cập trang quản lý người dùng.", tone="crit"),
            ]
        )

    header_title_text = build_header_title(ctx)

    return html.Div(
        id="users-page-root",
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
        children=[
            # Header
            dmc.Group(
                justify="space-between",
                align="center",
                mb="xs",
                style={"flexShrink": 0},
                children=[
                    dmc.Group(
                        gap="xs",
                        align="baseline",
                        children=[
                            dmc.Title(
                                header_title_text,
                                id="users-header-title",
                                order=4,
                                size=18,
                                fw=600,
                                style={"lineHeight": 1.3},
                            ),
                            dmc.Text(
                                "Một người có thể có nhiều vai trò. Luôn còn ít nhất một Admin hoạt động.",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                    ),
                    dmc.Group(
                        [
                            button_primary("Thêm người dùng", id="users-add-btn", icon="lucide:plus", size="xs"),
                            button_subtle("", id="users-refresh-btn", icon="lucide:refresh-cw", size="xs"),
                        ],
                        gap="xs",
                    ),
                ],
            ),
            # Filter bar
            dmc.Group(
                align="flex-end",
                mb="xs",
                gap="xs",
                style={"flexShrink": 0},
                children=[
                    dmc.TextInput(
                        id="users-search-input",
                        placeholder="Tìm username, họ tên, email…",
                        leftSection=DashIconify(icon="lucide:search", width=14),
                        style={"width": 260},
                        size="xs",
                        debounce=300,
                    ),
                    dmc.Select(
                        id="users-role-filter",
                        data=[{"label": "Tất cả vai trò", "value": "ALL"}, *_role_options(ctx)],
                        value="ALL",
                        size="xs",
                        style={"width": 160},
                    ),
                    dmc.Select(
                        id="users-status-filter",
                        data=[
                            {"label": "Tất cả trạng thái", "value": "ALL"},
                            {"label": "Hoạt động", "value": "ACTIVE"},
                            {"label": "Tạm khóa", "value": "LOCKED"},
                            {"label": "Đã tắt", "value": "DISABLED"},
                        ],
                        value="ALL",
                        size="xs",
                        style={"width": 160},
                    ),
                ],
            ),
            # Table container
            html.Div(
                id="users-table-container",
                children=render_users_table(ctx),
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
            ),
            # Drawer Thêm / Sửa người dùng
            drawer_right(
                id="users-drawer",
                title="Thêm người dùng",
                size=540,
                opened=False,
                # Drawer thành cột flex để chân nút luôn ở đáy màn hình:
                # nội dung cuộn trong vùng flex:1, chân nút không cuộn theo
                # và không phụ thuộc nội dung dài hay ngắn (ví dụ có hay
                # không có lịch sử đăng nhập). Chỉ áp cho drawer này, không
                # đổi drawer_right dùng chung.
                styles={
                    "content": {"display": "flex", "flexDirection": "column"},
                    "body": {"flex": "1", "display": "flex", "flexDirection": "column", "minHeight": 0},
                },
                children=html.Div(
                    [
                        html.Div(
                            [
                                dcc.Store(id="users-drawer-state-store", data={"mode": "create", "user_id": None}),
                                form_field(
                                    dmc.TextInput(
                                        id="users-input-username",
                                        placeholder="vd nguyenvana",
                                        className="mono",
                                    ),
                                    label="Tên đăng nhập",
                                    hint="Chữ thường, số, dấu chấm, gạch dưới. Không đổi được sau khi tạo.",
                                    required=True,
                                ),
                                form_field(
                                    dmc.TextInput(id="users-input-fullname", placeholder="vd Nguyễn Văn A"),
                                    label="Họ tên",
                                    required=True,
                                ),
                                form_field(
                                    dmc.TextInput(id="users-input-email", placeholder="vd a.nguyen@example.com"),
                                    label="Email",
                                ),
                                form_field(
                                    dmc.CheckboxGroup(
                                        id="users-input-roles",
                                        value=["VIEWER"],
                                        children=dmc.Group(
                                            [
                                                dmc.Checkbox(label=o["label"], value=o["value"])
                                                for o in _role_options(ctx)
                                            ],
                                            gap="md",
                                            mt=4,
                                        ),
                                    ),
                                    label="Vai trò",
                                    required=True,
                                ),
                                # Khối mật khẩu (chỉ khi tạo mới)
                                html.Div(
                                    id="users-create-pw-box",
                                    children=[
                                        form_field(
                                            dmc.PasswordInput(id="users-input-password"),
                                            label="Mật khẩu ban đầu",
                                            hint="Không được để trống.",
                                            required=True,
                                        ),
                                        dmc.Checkbox(
                                            id="users-input-must-change-pw",
                                            label="Bắt đổi mật khẩu ở lần đăng nhập đầu",
                                            checked=True,
                                            mt="sm",
                                        ),
                                    ],
                                ),
                                # Khối trạng thái (chỉ khi sửa). Lịch sử đăng
                                # nhập tách ra vùng riêng bên dưới để cuộn
                                # riêng, form phía trên luôn cố định.
                                html.Div(
                                    id="users-edit-status-box",
                                    style={"display": "none"},
                                    children=[
                                        dmc.Text("Trạng thái tài khoản", size="sm", fw=600),
                                        dmc.Group(
                                            [
                                                dmc.Button(
                                                    "Tắt tài khoản",
                                                    id="users-toggle-active-btn",
                                                    color="red",
                                                    variant="light",
                                                    size="sm",
                                                    leftSection=DashIconify(icon="lucide:lock", width=14),
                                                ),
                                            ],
                                            mt="xs",
                                        ),
                                        dmc.Box(id="users-toggle-error-msg", mt="xs"),
                                    ],
                                ),
                                dmc.Box(id="users-form-error-alert", mt="md"),
                            ],
                            style={"flex": "0 1 auto", "overflowY": "auto", "minHeight": 0},
                        ),
                        # Vùng lịch sử đăng nhập: chiếm phần còn lại của
                        # drawer và cuộn riêng trong đó, form nhập liệu phía
                        # trên và chân nút phía dưới đều đứng yên. Ẩn ở chế
                        # độ tạo mới (callback mở drawer điều khiển style).
                        html.Div(
                            [
                                dmc.Text("Lịch sử đăng nhập gần nhất", size="sm", fw=600, mt="sm"),
                                dmc.Box(
                                    id="users-history-container",
                                    mt="xs",
                                    style={"flex": "1", "overflowY": "auto", "minHeight": 0},
                                ),
                            ],
                            id="users-history-box",
                            style={
                                "display": "none",
                                "flexDirection": "column",
                                "flex": "1",
                                "minHeight": 0,
                            },
                        ),
                        # Chân drawer cố định ở đáy màn hình: marginTop auto
                        # đẩy chân xuống đáy kể cả khi vùng lịch sử đang ẩn
                        # (chế độ tạo mới), còn khi lịch sử hiện thì vùng
                        # flex:1 đã chiếm hết phần còn lại.
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="users-drawer-cancel-btn"),
                                button_primary("Lưu", id="users-drawer-save-btn"),
                            ],
                            justify="flex-end",
                            pt="md",
                            pb="xs",
                            style={
                                "flexShrink": 0,
                                "marginTop": "auto",
                                "background": "var(--mantine-color-body)",
                                "borderTop": "1px solid var(--border-subtle, #e2e8f0)",
                            },
                        ),
                    ],
                    style={"display": "flex", "flexDirection": "column", "height": "100%"},
                ),
            ),
            # Modal Đặt lại mật khẩu
            dmc.Modal(
                id="users-reset-modal",
                title="Đặt lại mật khẩu",
                opened=False,
                children=html.Div(
                    [
                        dcc.Store(id="users-reset-target-store", data=None),
                        dmc.Text(
                            id="users-reset-modal-desc",
                            size="sm",
                            c="dimmed",
                            mb="md",
                        ),
                        form_field(
                            dmc.PasswordInput(id="users-reset-input-pw"),
                            label="Mật khẩu mới",
                            required=True,
                        ),
                        dmc.Checkbox(
                            id="users-reset-must-change-cb",
                            label="Bắt đổi mật khẩu ở lần đăng nhập tới",
                            checked=True,
                            mt="sm",
                            mb="md",
                        ),
                        alert_box(
                            "Các phiên đang mở của người dùng này sẽ bị đăng xuất. "
                            "Nếu đang bị khóa, tài khoản cũng được mở khóa.",
                            tone="info",
                        ),
                        dmc.Box(id="users-reset-error-msg", mt="sm"),
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="users-reset-cancel-btn"),
                                button_primary("Đặt lại", id="users-reset-confirm-btn"),
                            ],
                            justify="flex-end",
                            mt="lg",
                        ),
                    ]
                ),
            ),
            # Notification container
            html.Div(id="users-notification-container"),
        ],
    )


def _render_login_history_table(history_logs: Any) -> Any:
    """Bảng lịch sử đăng nhập trong drawer Sửa, cùng kiểu bảng danh sách
    người dùng: nền header + kẻ dòng. Không có 2 thứ này bảng nhìn như
    mấy dòng chữ rời, không ra bảng."""
    if not (history_logs.ok and history_logs.data):
        return dmc.Text("Chưa có lịch sử đăng nhập.", size="xs", c="dimmed")
    h_rows = []
    for log in history_logs.data:
        time_val = format_datetime(log.get("CREATED_AT"))
        success = log.get("SUCCESS") == "Y"
        res_chip = (
            status_chip("ACTIVE", label="Thành công") if success else status_chip("INVALID", label="Sai mật khẩu")
        )
        ip_val = log.get("IP") or "—"
        h_rows.append(
            html.Tr(
                [
                    html.Td(time_val, style={"padding": "10px 14px"}),
                    html.Td(res_chip, style={"padding": "10px 14px"}),
                    html.Td(html.Span(ip_val, className="mono"), style={"padding": "10px 14px"}),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )
    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        # Mantine căn giữa th mặc định, trong khi td căn
                        # trái, nên không ghi textAlign thì tiêu đề "Thời
                        # gian" lệch khỏi cột dữ liệu bên dưới. Tiêu đề dính
                        # trên cùng vùng cuộn của bảng để cuộn dòng vẫn thấy.
                        html.Th(
                            "Thời gian",
                            style={
                                "padding": "10px 14px",
                                "textAlign": "left",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--bg-subtle, #f8fafc)",
                            },
                        ),
                        html.Th(
                            "Kết quả",
                            style={
                                "padding": "10px 14px",
                                "textAlign": "left",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--bg-subtle, #f8fafc)",
                            },
                        ),
                        html.Th(
                            "IP",
                            style={
                                "padding": "10px 14px",
                                "textAlign": "left",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--bg-subtle, #f8fafc)",
                            },
                        ),
                    ],
                    style={"background": "var(--bg-subtle, #f8fafc)"},
                )
            ),
            html.Tbody(h_rows),
        ],
    )


# Callbacks


@callback(
    Output("users-table-container", "children"),
    Output("users-header-title", "children"),
    Input("users-search-input", "value"),
    Input("users-role-filter", "value"),
    Input("users-status-filter", "value"),
    Input("users-refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_filter_users(q: str | None, role: str | None, status_filter: str | None, _refresh: int | None) -> Any:
    """Lọc danh sách người dùng và cập nhật số lượng."""
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return alert_box("Bạn không có quyền truy cập.", tone="crit"), "Người dùng"

    table = render_users_table(ctx, q=q, role=role, status_filter=status_filter)
    title = build_header_title(ctx)
    return table, title


@callback(
    Output("users-drawer", "opened", allow_duplicate=True),
    Output("users-drawer-state-store", "data", allow_duplicate=True),
    Output("users-input-username", "value"),
    Output("users-input-username", "disabled"),
    Output("users-input-fullname", "value"),
    Output("users-input-email", "value"),
    Output("users-input-roles", "value"),
    Output("users-create-pw-box", "style"),
    Output("users-edit-status-box", "style"),
    Output("users-toggle-active-btn", "children"),
    Output("users-toggle-active-btn", "color"),
    Output("users-history-container", "children"),
    Output("users-form-error-alert", "children", allow_duplicate=True),
    Output("users-toggle-error-msg", "children", allow_duplicate=True),
    Output("users-history-box", "style"),
    Input("users-add-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_open_create_drawer(n_clicks: int | None) -> Any:
    """Mở ngăn kéo thêm người dùng mới."""
    if not n_clicks:
        return dash.no_update
    options = _role_options(get_current_ctx())
    default_roles = (
        ["VIEWER"] if any(o["value"] == "VIEWER" for o in options) else ([options[0]["value"]] if options else [])
    )
    return (
        True,
        {"mode": "create", "user_id": None},
        "",  # username
        False,  # username not disabled
        "",  # full name
        "",  # email
        default_roles,  # roles
        {"display": "block"},  # create pw box
        {"display": "none"},  # edit status box
        "Tắt tài khoản",
        "red",
        None,  # history
        None,  # form error
        None,  # toggle error
        {"display": "none"},  # history box
    )


@callback(
    Output("users-drawer", "opened", allow_duplicate=True),
    Output("users-drawer-state-store", "data", allow_duplicate=True),
    Output("users-input-username", "value", allow_duplicate=True),
    Output("users-input-username", "disabled", allow_duplicate=True),
    Output("users-input-fullname", "value", allow_duplicate=True),
    Output("users-input-email", "value", allow_duplicate=True),
    Output("users-input-roles", "value", allow_duplicate=True),
    Output("users-create-pw-box", "style", allow_duplicate=True),
    Output("users-edit-status-box", "style", allow_duplicate=True),
    Output("users-toggle-active-btn", "children", allow_duplicate=True),
    Output("users-toggle-active-btn", "color", allow_duplicate=True),
    Output("users-history-container", "children", allow_duplicate=True),
    Output("users-form-error-alert", "children", allow_duplicate=True),
    Output("users-toggle-error-msg", "children", allow_duplicate=True),
    Output("users-history-box", "style", allow_duplicate=True),
    Input({"type": "user-edit-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_open_edit_drawer(n_clicks_list: list[int | None]) -> Any:
    """Mở ngăn kéo sửa thông tin người dùng."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not any(n_clicks_list):
        return dash.no_update

    triggered_prop = ctx_dash.triggered[0]["prop_id"]
    # Trích xuất user_id từ prop_id dạng {"index":2,"type":"user-edit-btn"}.n_clicks
    import json

    prop_json = triggered_prop.split(".")[0]
    target_id = json.loads(prop_json)["index"]

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return dash.no_update

    users_res = list_users(ctx)
    if not users_res.ok or not users_res.data:
        return dash.no_update

    target_user: UserResponse | None = None
    for u in users_res.data:
        if u.id == target_id:
            target_user = u
            break

    if target_user is None:
        return dash.no_update

    # Nút bật / tắt
    btn_text = "Tắt tài khoản" if target_user.is_active else "Bật tài khoản"
    btn_color = "red" if target_user.is_active else "green"

    # Lịch sử đăng nhập
    history_logs = get_login_log(ctx, user_id=target_id, limit=10)
    history_table = _render_login_history_table(history_logs)

    return (
        True,
        {"mode": "edit", "user_id": target_user.id, "is_active": target_user.is_active},
        target_user.username,
        True,  # username disabled
        target_user.full_name,
        target_user.email or "",
        target_user.roles,
        {"display": "none"},  # create pw box
        {"display": "block"},  # edit status box
        btn_text,
        btn_color,
        history_table,
        None,  # form error
        None,  # toggle error
        {
            "display": "flex",
            "flexDirection": "column",
            "flex": "1",
            "minHeight": 0,
        },  # history box
    )


@callback(
    Output("users-drawer", "opened", allow_duplicate=True),
    Input("users-drawer-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_close_drawer(_n: int | None) -> bool:
    """Đóng ngăn kéo."""
    return False


@callback(
    Output("users-drawer", "opened", allow_duplicate=True),
    Output("users-table-container", "children", allow_duplicate=True),
    Output("users-header-title", "children", allow_duplicate=True),
    Output("users-form-error-alert", "children", allow_duplicate=True),
    Input("users-drawer-save-btn", "n_clicks"),
    State("users-drawer-state-store", "data"),
    State("users-input-username", "value"),
    State("users-input-fullname", "value"),
    State("users-input-email", "value"),
    State("users-input-roles", "value"),
    State("users-input-password", "value"),
    State("users-input-must-change-pw", "checked"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_save_user(
    n_clicks: int | None,
    drawer_state: dict[str, Any] | None,
    username: str | None,
    fullname: str | None,
    email: str | None,
    roles: list[str] | None,
    password: str | None,
    must_change_pw: bool | None,
    q: str | None,
    role_filter: str | None,
    status_filter: str | None,
) -> Any:
    """Lưu thêm mới hoặc cập nhật thông tin người dùng."""
    if not n_clicks:
        return dash.no_update

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return False, dash.no_update, dash.no_update, alert_box("Không có quyền thực hiện.", tone="crit")

    mode = drawer_state.get("mode") if drawer_state else "create"
    user_id = drawer_state.get("user_id") if drawer_state else None

    # Validate roles >= 1
    if not roles or len(roles) == 0:
        return True, dash.no_update, dash.no_update, alert_box("Phải chọn ít nhất một vai trò.", tone="crit")

    if mode == "create":
        if not username or not username.strip():
            return True, dash.no_update, dash.no_update, alert_box("Tên đăng nhập không được để trống.", tone="crit")
        if not fullname or not fullname.strip():
            return True, dash.no_update, dash.no_update, alert_box("Họ tên không được để trống.", tone="crit")
        if not password or not password.strip():
            return True, dash.no_update, dash.no_update, alert_box("Mật khẩu ban đầu không được để trống.", tone="crit")

        dto = UserCreateDTO(
            username=username.strip(),
            full_name=fullname.strip(),
            email=email.strip() if email else None,
            password=password,
            roles=roles,
            must_change_pw=bool(must_change_pw),
        )
        res = create_user(ctx, dto)
        if not res.ok:
            return True, dash.no_update, dash.no_update, alert_box(f"Lỗi: {res.message}", tone="crit")
    else:
        # Edit mode
        if not user_id:
            return True, dash.no_update, dash.no_update, alert_box("Không tìm thấy ID người dùng.", tone="crit")
        if not fullname or not fullname.strip():
            return True, dash.no_update, dash.no_update, alert_box("Họ tên không được để trống.", tone="crit")

        update_dto = UserUpdateDTO(
            full_name=fullname.strip(),
            email=email.strip() if email else None,
            roles=roles,
        )
        update_res = update_user(ctx, int(user_id), update_dto)
        if not update_res.ok:
            return True, dash.no_update, dash.no_update, alert_box(f"Lỗi: {update_res.message}", tone="crit")

    # Refresh table and title
    new_table = render_users_table(ctx, q=q, role=role_filter, status_filter=status_filter)
    new_title = build_header_title(ctx)
    return False, new_table, new_title, None


@callback(
    Output("users-toggle-active-btn", "children", allow_duplicate=True),
    Output("users-toggle-active-btn", "color", allow_duplicate=True),
    Output("users-drawer-state-store", "data", allow_duplicate=True),
    Output("users-toggle-error-msg", "children", allow_duplicate=True),
    Output("users-table-container", "children", allow_duplicate=True),
    Output("users-header-title", "children", allow_duplicate=True),
    Input("users-toggle-active-btn", "n_clicks"),
    State("users-drawer-state-store", "data"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_toggle_active_user(
    n_clicks: int | None,
    drawer_state: dict[str, Any] | None,
    q: str | None,
    role_filter: str | None,
    status_filter: str | None,
) -> Any:
    """Tắt hoặc bật tài khoản người dùng, bảo vệ quản trị viên cuối cùng."""
    if not n_clicks or not drawer_state:
        return dash.no_update

    user_id = drawer_state.get("user_id")
    current_active = drawer_state.get("is_active", True)
    if not user_id:
        return dash.no_update

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return dash.no_update

    target_active = not current_active
    res = set_active(ctx, int(user_id), is_active=target_active)
    if not res.ok:
        err_msg = alert_box(res.message, tone="crit")
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            err_msg,
            dash.no_update,
            dash.no_update,
        )

    # Success
    new_text = "Tắt tài khoản" if target_active else "Bật tài khoản"
    new_color = "red" if target_active else "green"
    new_state = {**drawer_state, "is_active": target_active}

    new_table = render_users_table(ctx, q=q, role=role_filter, status_filter=status_filter)
    new_title = build_header_title(ctx)

    return new_text, new_color, new_state, None, new_table, new_title


@callback(
    Output("users-table-container", "children", allow_duplicate=True),
    Output("users-header-title", "children", allow_duplicate=True),
    Input({"type": "user-unlock-btn", "index": ALL}, "n_clicks"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_unlock_user(
    n_clicks_list: list[int | None],
    q: str | None,
    role_filter: str | None,
    status_filter: str | None,
) -> Any:
    """Mở khóa nhanh tài khoản đang bị tạm khóa."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not any(n_clicks_list):
        return dash.no_update

    import json

    triggered_prop = ctx_dash.triggered[0]["prop_id"]
    prop_json = triggered_prop.split(".")[0]
    target_id = json.loads(prop_json)["index"]

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return dash.no_update

    unlock_res = unlock_user(ctx, int(target_id))
    if not unlock_res.ok:
        return dash.no_update

    new_table = render_users_table(ctx, q=q, role=role_filter, status_filter=status_filter)
    new_title = build_header_title(ctx)
    return new_table, new_title


@callback(
    Output("users-reset-modal", "opened"),
    Output("users-reset-modal-desc", "children"),
    Output("users-reset-target-store", "data"),
    Output("users-reset-input-pw", "value"),
    Output("users-reset-error-msg", "children"),
    Input({"type": "user-reset-pw-btn", "index": ALL}, "n_clicks"),
    Input("users-reset-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_open_or_cancel_reset_modal(
    n_clicks_list: list[int | None],
    cancel_clicks: int | None,
) -> Any:
    """Mở hoặc đóng modal đặt lại mật khẩu."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    if "users-reset-cancel-btn" in trigger_id:
        return False, "", None, "", None

    if not any(n_clicks_list):
        return dash.no_update

    import json

    prop_json = trigger_id.split(".")[0]
    target_id = json.loads(prop_json)["index"]

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return dash.no_update

    users_res = list_users(ctx)
    target_username = f"tài khoản ID {target_id}"
    if users_res.ok and users_res.data:
        for u in users_res.data:
            if u.id == target_id:
                target_username = u.username
                break

    desc = f"Đặt lại mật khẩu cho {target_username}."
    return True, desc, target_id, "", None


@callback(
    Output("users-reset-modal", "opened", allow_duplicate=True),
    Output("users-reset-error-msg", "children", allow_duplicate=True),
    Output("users-table-container", "children", allow_duplicate=True),
    Output("users-header-title", "children", allow_duplicate=True),
    Input("users-reset-confirm-btn", "n_clicks"),
    State("users-reset-target-store", "data"),
    State("users-reset-input-pw", "value"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_confirm_reset_password(
    n_clicks: int | None,
    target_id: int | None,
    new_pw: str | None,
    q: str | None,
    role_filter: str | None,
    status_filter: str | None,
) -> Any:
    """Xác nhận đặt lại mật khẩu cho người dùng."""
    if not n_clicks or not target_id:
        return dash.no_update

    if not new_pw or not new_pw.strip():
        return True, alert_box("Mật khẩu mới không được để trống.", tone="crit"), dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return False, None, dash.no_update, dash.no_update

    res = reset_password(ctx, int(target_id), new_pw.strip())
    if not res.ok:
        return True, alert_box(res.message, tone="crit"), dash.no_update, dash.no_update

    new_table = render_users_table(ctx, q=q, role=role_filter, status_filter=status_filter)
    new_title = build_header_title(ctx)
    return False, None, new_table, new_title
