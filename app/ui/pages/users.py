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
from app.services.user_export import (
    export_users_list_docx,
    export_users_list_excel,
    export_users_list_pdf,
    send_users_list_email,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.field import form_field
from app.ui.components.page_header import page_header
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

            # Thao tác: chuyển sang ActionIcon kèm Tooltip hover
            actions_list: list[Any] = [
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:pencil", width=14),
                        id={"type": "user-edit-btn", "index": u.id},
                        size="sm",
                        variant="subtle",
                        color="blue",
                        radius="sm",
                        **{"aria-label": "Sửa người dùng"},
                    ),
                    label="Sửa người dùng",
                    position="top",
                    withArrow=True,
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:key-round", width=14),
                        id={"type": "user-reset-pw-btn", "index": u.id},
                        size="sm",
                        variant="subtle",
                        color="gray",
                        radius="sm",
                        **{"aria-label": "Đặt lại mật khẩu"},
                    ),
                    label="Đặt lại mật khẩu",
                    position="top",
                    withArrow=True,
                ),
            ]
            if is_locked:
                actions_list.append(
                    dmc.Tooltip(
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:unlock", width=14),
                            id={"type": "user-unlock-btn", "index": u.id},
                            size="sm",
                            variant="subtle",
                            color="orange",
                            radius="sm",
                            **{"aria-label": "Mở khóa tài khoản"},
                        ),
                        label="Mở khóa tài khoản",
                        position="top",
                        withArrow=True,
                    )
                )

            tr = html.Tr(
                [
                    html.Td(
                        html.Span(u.username, className="mono", style={"fontWeight": 600}),
                        style={"padding": "8px 12px"},
                    ),
                    html.Td(u.full_name, style={"padding": "8px 12px"}),
                    html.Td(
                        u.email or html.Span("—", style={"color": "var(--ink-soft, #94a3b8)"}),
                        style={"padding": "8px 12px"},
                    ),
                    html.Td(roles_badges, style={"padding": "8px 12px"}),
                    html.Td(user_status, style={"padding": "8px 12px"}),
                    html.Td(
                        format_datetime(u.last_login_at)
                        if u.last_login_at
                        else html.Span("—", style={"color": "var(--ink-soft, #94a3b8)"}),
                        style={"padding": "8px 12px", "fontSize": "12px", "color": "var(--ink-soft, #616161)"},
                    ),
                    html.Td(
                        dmc.Group(actions_list, gap=4, justify="flex-end"),
                        style={"padding": "6px 12px", "textAlign": "right"},
                    ),
                ],
                style={"borderBottom": "1px solid var(--line, #e2e8f0)"},
            )
            rows.append(tr)

        th_style = {
            "padding": "8px 12px",
            "position": "sticky",
            "top": 0,
            "background": "var(--surface-2, #f8fafc)",
            "zIndex": 1,
            "fontSize": "12px",
            "fontWeight": 600,
            "color": "var(--ink-soft, #616161)",
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
                            html.Th("Thao tác", style={**th_style, "textAlign": "right"}),
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

    export_menu = dmc.Menu(
        [
            dmc.MenuTarget(
                button_subtle(
                    "Xuất danh sách",
                    id="users-export-menu-btn",
                    icon="lucide:download",
                    rightSection=DashIconify(icon="lucide:chevron-down", width=12),
                    size="xs",
                )
            ),
            dmc.MenuDropdown(
                [
                    dmc.MenuItem(
                        "Xuất Excel (.xlsx)",
                        id="users-export-excel-btn",
                        leftSection=DashIconify(icon="lucide:file-spreadsheet", width=14, color="#1D6F42"),
                    ),
                    dmc.MenuItem(
                        "Xuất Word (.docx)",
                        id="users-export-word-btn",
                        leftSection=DashIconify(icon="lucide:file-text", width=14, color="#185ABD"),
                    ),
                    dmc.MenuItem(
                        "Xuất PDF (.pdf)",
                        id="users-export-pdf-btn",
                        leftSection=DashIconify(icon="lucide:file-type-2", width=14, color="#E02424"),
                    ),
                    dmc.MenuDivider(),
                    dmc.MenuItem(
                        "Gửi qua Email...",
                        id="users-export-email-btn",
                        leftSection=DashIconify(icon="lucide:mail", width=14, color="#0C8599"),
                    ),
                ]
            ),
        ],
        position="bottom-end",
        withArrow=True,
    )

    return html.Div(
        id="users-page-root",
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
        },
        children=[
            # Header
            page_header(
                title=dmc.Title(
                    header_title_text,
                    id="users-header-title",
                    order=4,
                    size=18,
                    fw=600,
                    style={"lineHeight": 1.3, "whiteSpace": "nowrap"},
                ),
                subtitle="Một người có thể có nhiều vai trò. Luôn còn ít nhất một Admin hoạt động.",
                actions=[
                    export_menu,
                    button_primary("Thêm người dùng", id="users-add-btn", icon="lucide:plus", size="xs"),
                    button_subtle("", id="users-refresh-btn", icon="lucide:refresh-cw", size="xs"),
                ],
            ),
            # Filter bar
            dmc.Paper(
                dmc.Group(
                    [
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
                    gap="xs",
                    align="center",
                ),
                withBorder=True,
                p="xs",
                radius="sm",
                mb="xs",
                style={"flexShrink": 0},
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
                                        size="xs",
                                    ),
                                    label="Tên đăng nhập",
                                    hint="Chữ thường, số, dấu chấm, gạch dưới. Không đổi được sau khi tạo.",
                                    required=True,
                                ),
                                form_field(
                                    dmc.TextInput(
                                        id="users-input-fullname",
                                        placeholder="vd Nguyễn Văn A",
                                        size="xs",
                                    ),
                                    label="Họ tên",
                                    required=True,
                                ),
                                form_field(
                                    dmc.TextInput(
                                        id="users-input-email",
                                        placeholder="vd a.nguyen@example.com",
                                        size="xs",
                                    ),
                                    label="Email",
                                ),
                                form_field(
                                    dmc.CheckboxGroup(
                                        id="users-input-roles",
                                        value=["VIEWER"],
                                        size="xs",
                                        children=dmc.SimpleGrid(
                                            cols=2,
                                            spacing="xs",
                                            mt=4,
                                            children=[
                                                dmc.Checkbox(label=o["label"], value=o["value"], size="xs")
                                                for o in _role_options(ctx)
                                            ],
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
                                            dmc.PasswordInput(
                                                id="users-input-password",
                                                placeholder="Nhập mật khẩu ban đầu...",
                                                size="xs",
                                            ),
                                            label="Mật khẩu ban đầu",
                                            hint="Không được để trống.",
                                            required=True,
                                        ),
                                        dmc.Checkbox(
                                            id="users-input-must-change-pw",
                                            label="Bắt đổi mật khẩu ở lần đăng nhập đầu",
                                            checked=True,
                                            size="xs",
                                            mt="sm",
                                        ),
                                    ],
                                ),
                                # Khối trạng thái (chỉ khi sửa)
                                html.Div(
                                    id="users-edit-status-box",
                                    style={"display": "none"},
                                    children=[
                                        dmc.Text("Trạng thái tài khoản", size="xs", fw=600),
                                        dmc.Group(
                                            [
                                                dmc.Button(
                                                    "Tắt tài khoản",
                                                    id="users-toggle-active-btn",
                                                    color="red",
                                                    variant="light",
                                                    size="xs",
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
                        # Vùng lịch sử đăng nhập
                        html.Div(
                            [
                                dmc.Text("Lịch sử đăng nhập gần nhất", size="xs", fw=600, mt="sm"),
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
                        # Chân drawer cố định ở đáy màn hình
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="users-drawer-cancel-btn", size="xs"),
                                button_primary("Lưu", id="users-drawer-save-btn", size="xs"),
                            ],
                            justify="flex-end",
                            pt="md",
                            pb="xs",
                            style={
                                "flexShrink": 0,
                                "marginTop": "auto",
                                "background": "var(--mantine-color-body)",
                                "borderTop": "1px solid var(--line, #e2e8f0)",
                            },
                        ),
                    ],
                    style={"display": "flex", "flexDirection": "column", "height": "100%"},
                ),
            ),
            # Modal Đặt lại mật khẩu
            dmc.Modal(
                id="users-reset-modal",
                title=dmc.Text("Đặt lại mật khẩu", fw=600, size="sm"),
                opened=False,
                centered=True,
                radius="sm",
                size="md",
                children=html.Div(
                    dmc.Stack(
                        [
                            dcc.Store(id="users-reset-target-store", data=None),
                            dmc.Text(
                                id="users-reset-modal-desc",
                                size="xs",
                                c="dimmed",
                            ),
                            form_field(
                                dmc.PasswordInput(
                                    id="users-reset-input-pw",
                                    placeholder="Nhập mật khẩu mới cho người dùng...",
                                    size="xs",
                                ),
                                label="Mật khẩu mới",
                                required=True,
                            ),
                            dmc.Checkbox(
                                id="users-reset-must-change-cb",
                                label="Bắt đổi mật khẩu ở lần đăng nhập tới",
                                checked=True,
                                size="xs",
                            ),
                            alert_box(
                                "Các phiên đang mở của người dùng này sẽ bị đăng xuất. "
                                "Nếu đang bị khóa, tài khoản cũng được mở khóa.",
                                tone="info",
                            ),
                            dmc.Box(id="users-reset-error-msg"),
                            dmc.Group(
                                [
                                    button_subtle("Hủy", id="users-reset-cancel-btn", size="xs"),
                                    button_primary("Đặt lại mật khẩu", id="users-reset-confirm-btn", size="xs"),
                                ],
                                justify="flex-end",
                                gap="xs",
                                pt="xs",
                                style={"borderTop": "1px solid var(--line, #e2e8f0)"},
                            ),
                        ],
                        gap="sm",
                    )
                ),
            ),
            # Download & Email Modal cho Xuất danh sách
            dcc.Download(id="users-list-download"),
            html.Div(id="users-email-toast"),
            dmc.Modal(
                id="users-email-modal",
                title=dmc.Text("Gửi danh sách Người dùng qua Email", fw=700, size="md"),
                opened=False,
                size="md",
                children=dmc.Stack(
                    [
                        dmc.Text(
                            "Chọn định dạng tệp đính kèm và nhập danh sách địa chỉ email nhận thư. "
                            "Hệ thống sẽ kết xuất theo đúng bộ lọc hiện tại và gửi thư qua máy chủ SMTP đã cấu hình.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.CheckboxGroup(
                            id="users-email-formats",
                            label="Định dạng tệp đính kèm",
                            description="Chọn ít nhất 1 định dạng",
                            children=dmc.Group(
                                [
                                    dmc.Checkbox(label="Excel (.xlsx)", value="XLSX"),
                                    dmc.Checkbox(label="Word (.docx)", value="DOCX"),
                                    dmc.Checkbox(label="PDF (.pdf)", value="PDF"),
                                ],
                                gap="md",
                            ),
                            value=["XLSX"],
                        ),
                        dmc.TextInput(
                            id="users-email-recipients",
                            label="Người nhận (To)",
                            placeholder="vd: admin@company.com, ketoan@company.com",
                            description="Nhiều email cách nhau bằng dấu phẩy",
                            required=True,
                        ),
                        dmc.TextInput(
                            id="users-email-subject",
                            label="Tiêu đề email",
                            placeholder="vd: [ReconHub] Danh sách tài khoản người dùng",
                            required=True,
                        ),
                        dmc.Textarea(
                            id="users-email-notes",
                            label="Lời nhắn kèm theo (tùy chọn)",
                            placeholder="Nhập nội dung ghi chú cho người nhận...",
                            minRows=3,
                        ),
                        html.Div(
                            [
                                dmc.Group(
                                    [
                                        DashIconify(icon="lucide:loader-2", width=14, color="#228be6"),
                                        dmc.Text(
                                            "Đang kết xuất tệp và gửi email qua SMTP...",
                                            size="xs",
                                            c="blue",
                                            fw=500,
                                        ),
                                    ],
                                    gap=6,
                                    mb=4,
                                ),
                                dmc.Progress(
                                    value=100,
                                    animated=True,
                                    striped=True,
                                    color="blue",
                                    size="sm",
                                    radius="xs",
                                ),
                            ],
                            id="users-email-progress-container",
                            style={"display": "none"},
                        ),
                        html.Div(id="users-email-alert"),
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="users-email-cancel-btn"),
                                button_primary("Gửi email", id="users-email-submit-btn", icon="lucide:send"),
                            ],
                            justify="flex-end",
                            gap="sm",
                            mt="sm",
                        ),
                    ],
                    gap="sm",
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
                style={"borderBottom": "1px solid var(--line, #e2e8f0)"},
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
                                "textAlign": "center",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--surface-2, #f8fafc)",
                            },
                        ),
                        html.Th(
                            "Kết quả",
                            style={
                                "padding": "10px 14px",
                                "textAlign": "center",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--surface-2, #f8fafc)",
                            },
                        ),
                        html.Th(
                            "IP",
                            style={
                                "padding": "10px 14px",
                                "textAlign": "center",
                                "position": "sticky",
                                "top": 0,
                                "background": "var(--surface-2, #f8fafc)",
                            },
                        ),
                    ],
                    style={"background": "var(--surface-2, #f8fafc)"},
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
    Output("users-drawer", "title", allow_duplicate=True),
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
        "Thêm người dùng",
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
    Output("users-drawer", "title", allow_duplicate=True),
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
        f"Sửa người dùng: {target_user.username}",
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


# Callback xuất danh sách người dùng ra Excel, Word (.docx), hoặc PDF (.pdf)
@callback(
    Output("users-list-download", "data"),
    Input("users-export-excel-btn", "n_clicks"),
    Input("users-export-word-btn", "n_clicks"),
    Input("users-export-pdf-btn", "n_clicks"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_export_users_list(
    excel_clicks: Any,
    word_clicks: Any,
    pdf_clicks: Any,
    search_val: str | None,
    role_val: str | None,
    status_val: str | None,
) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    ctx = get_current_ctx()
    if ctx is None:
        return None

    q = search_val or ""
    role = role_val or ""
    st = status_val or ""

    if trigger_id == "users-export-excel-btn":
        res = export_users_list_excel(ctx, q=q, role=role, status=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_nguoi_dung.xlsx"),
            )
    elif trigger_id == "users-export-word-btn":
        res = export_users_list_docx(ctx, q=q, role=role, status=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_nguoi_dung.docx"),
            )
    elif trigger_id == "users-export-pdf-btn":
        res = export_users_list_pdf(ctx, q=q, role=role, status=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_nguoi_dung.pdf"),
            )

    return None


# Clientside callback kích hoạt thanh Progress bar và vô hiệu hóa nút Gửi ngay khi click
dash.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        return [{"display": "block", "marginTop": "8px", "marginBottom": "8px"}, true];
    }
    """,
    Output("users-email-progress-container", "style", allow_duplicate=True),
    Output("users-email-submit-btn", "disabled", allow_duplicate=True),
    Input("users-email-submit-btn", "n_clicks"),
    prevent_initial_call=True,
)


# Callback điều khiển mở/đóng và gửi email danh sách người dùng
@callback(
    Output("users-email-modal", "opened"),
    Output("users-email-subject", "value"),
    Output("users-email-recipients", "value"),
    Output("users-email-alert", "children"),
    Output("users-email-toast", "children"),
    Output("users-email-progress-container", "style", allow_duplicate=True),
    Output("users-email-submit-btn", "disabled", allow_duplicate=True),
    Input("users-export-email-btn", "n_clicks"),
    Input("users-email-cancel-btn", "n_clicks"),
    Input("users-email-submit-btn", "n_clicks"),
    State("users-email-modal", "opened"),
    State("users-email-recipients", "value"),
    State("users-email-formats", "value"),
    State("users-email-subject", "value"),
    State("users-email-notes", "value"),
    State("users-search-input", "value"),
    State("users-role-filter", "value"),
    State("users-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_users_email_modal_actions(
    export_clicks: Any,
    cancel_clicks: Any,
    submit_clicks: Any,
    is_opened: bool,
    recipients_val: str | None,
    formats_val: list[str] | None,
    subject_val: str | None,
    notes_val: str | None,
    search_val: str | None,
    role_val: str | None,
    status_val: str | None,
) -> tuple[Any, Any, Any, Any, Any, dict[str, str], bool]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]

    # 1. Bấm mở Modal từ menu "Gửi qua Email..."
    if trigger_id == "users-export-email-btn":
        today_str = datetime.now().strftime("%d/%m/%Y")
        default_subject = f"[ReconHub] Danh sách tài khoản người dùng — {today_str}"
        return True, default_subject, "", None, dash.no_update, {"display": "none"}, False

    # 2. Bấm nút Hủy
    if trigger_id == "users-email-cancel-btn":
        return False, dash.no_update, dash.no_update, None, dash.no_update, {"display": "none"}, False

    # 3. Bấm nút Gửi email
    if trigger_id == "users-email-submit-btn":
        ctx = get_current_ctx()
        if ctx is None:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Chưa đăng nhập.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        recipients_raw = (recipients_val or "").strip()
        if not recipients_raw:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Vui lòng nhập ít nhất một địa chỉ email người nhận.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
        formats = formats_val or []
        if not formats:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Vui lòng chọn ít nhất một định dạng tệp đính kèm.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        q = search_val or ""
        role = role_val or ""
        st = status_val or ""
        custom_subj = (subject_val or "").strip()
        custom_notes = (notes_val or "").strip()

        res = send_users_list_email(
            ctx=ctx,
            to_emails=recipients,
            format_types=formats,
            q=q,
            role=role,
            status=st,
            custom_subject=custom_subj,
            notes=custom_notes,
        )

        if not res.ok:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box(f"Không thể gửi email: {res.message}", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        toast = dmc.Notification(
            title="Gửi email thành công",
            message=f"Đã gửi danh sách người dùng đến {len(recipients)} người nhận.",
            color="green",
            icon=DashIconify(icon="lucide:check", width=18),
            action="show",
            autoClose=4000,
        )
        return False, dash.no_update, "", None, toast, {"display": "none"}, False

    return False, dash.no_update, dash.no_update, None, dash.no_update, {"display": "none"}, False
