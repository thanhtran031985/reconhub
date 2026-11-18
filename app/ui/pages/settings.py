"""Trang Cài đặt hệ thống (task 52) — chỉ ADMIN.

Cài đặt dọn file export chạy ngầm: chế độ manual (mặc định, không tự
xóa) hoặc scheduler (worker tự xóa file export đã kết thúc quá N ngày).
Task 57: số export chạy song song tối đa (mặc định 10).
Task 71: timeout truy vấn báo cáo (COUNT và dữ liệu).
Task 94: cấu hình bot Telegram gửi thông báo kết quả run.
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.engine.email_template import (
    SUPPORTED_EMAIL_FUNCTIONS,
    get_builtin_default_template,
    get_email_function_meta,
    render_email_body,
    render_email_subject,
)
from app.services.email_template import (
    get_email_template_internal,
    reset_email_template_to_default,
    save_email_template,
)
from app.services.export_retention import (
    get_export_concurrency_settings,
    get_export_retention_settings,
    set_export_concurrency,
    set_export_retention,
)
from app.services.perm import page_gate
from app.services.report_timeouts import (
    get_report_timeout_settings,
    set_report_timeouts,
)
from app.services.smtp_settings import (
    get_smtp_settings,
    set_smtp_settings,
    test_smtp_connection,
)
from app.services.telegram_notify import (
    get_telegram_settings,
    send_telegram_test,
    set_telegram_settings,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/settings", title="Cài đặt hệ thống – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "system_settings"


def render_token_badges(tokens: list[dict[str, Any]]) -> Any:
    """Hiển thị danh sách thẻ dữ liệu dưới dạng Badges có gợi ý khi hover."""
    if not tokens:
        return dmc.Text("Không có thẻ dữ liệu", size="xs", c="dimmed")
    badges = []
    for t in tokens:
        tok_str = t.get("token", "")
        lbl = t.get("label", "")
        ex = t.get("example", "")
        badges.append(
            dmc.Tooltip(
                dmc.Badge(
                    tok_str,
                    variant="light",
                    color="blue",
                    size="sm",
                    style={"cursor": "pointer", "userSelect": "all"},
                ),
                label=f"{lbl} (Ví dụ: {ex})" if ex else lbl,
                withArrow=True,
            )
        )
    return dmc.Group(badges, gap=6, wrap="wrap")


def render_fn_nav_list(active_code: str) -> list[Any]:
    """Hiển thị danh sách các phân hệ gửi mail dạng NavLink Master-Detail."""
    links = []
    for fn in SUPPORTED_EMAIL_FUNCTIONS:
        code = fn["code"]
        is_active = (code == active_code)
        right_badge = None
        if fn.get("is_fallback"):
            right_badge = dmc.Badge("Mặc định chung", size="xs", variant="light", color="indigo")
        links.append(
            dmc.NavLink(
                label=fn["label"],
                description=fn.get("description", ""),
                leftSection=DashIconify(icon=fn.get("icon", "lucide:file-text"), width=16),
                active=is_active,
                variant="subtle",
                rightSection=right_badge,
                id={"type": "settings-tmpl-fn-nav", "code": code},
                styles={
                    "root": {
                        "borderRadius": "4px",
                        "borderLeft": "3px solid var(--primary, #0F6CBD)" if is_active else "3px solid transparent",
                        "backgroundColor": "var(--primary-soft, #EBF3FC)" if is_active else "transparent",
                        "marginBottom": "4px",
                        "padding": "6px 8px",
                    },
                },
            )
        )
    return links


def render_tmpl_header_info(tmpl: dict[str, Any], fn_meta: dict[str, Any] | None) -> Any:
    """Hiển thị tên phân hệ đang soạn và badge trạng thái nguồn mẫu."""
    title = fn_meta.get("label", tmpl.get("function_code", "")) if fn_meta else tmpl.get("name", "")
    is_fallback = tmpl.get("is_fallback", False)
    badge_node = (
        dmc.Badge("Đang dùng mẫu Fallback chung", size="xs", color="orange", variant="light")
        if is_fallback
        else dmc.Badge("Mẫu riêng tùy biến", size="xs", color="teal", variant="light")
    )
    return dmc.Group(
        [
            dmc.Text(title, fw=600, size="sm"),
            badge_node,
        ],
        gap="xs",
        wrap="wrap",
    )


def layout(**kwargs: Any) -> Any:
    """Form cài đặt dọn file export, concurrency, timeouts và Telegram (ADMIN-only qua menu)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="settings-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem cài đặt hệ thống.", tone="crit"),
            ]
        )
    mode, days = "manual", 30
    max_concurrent = 10
    count_timeout, data_timeout = 300, 300
    tg_configured, tg_username = False, ""
    smtp_host, smtp_port, smtp_security = "", 587, "STARTTLS"
    smtp_username, smtp_has_pass = "", False
    smtp_from_email, smtp_from_name = "", "ReconHub"
    if ctx is not None:
        res = get_export_retention_settings(ctx)
        if res.ok and isinstance(res.data, dict):
            mode = str(res.data.get("mode") or "manual")
            days = int(res.data.get("days") or 30)
        c_res = get_export_concurrency_settings(ctx)
        if c_res.ok and isinstance(c_res.data, dict):
            max_concurrent = int(c_res.data.get("max_concurrent") or 10)
        t_res = get_report_timeout_settings(ctx)
        if t_res.ok and isinstance(t_res.data, dict):
            count_timeout = int(t_res.data.get("count_timeout_sec") or 300)
            data_timeout = int(t_res.data.get("data_timeout_sec") or 300)
        tg_res = get_telegram_settings(ctx)
        if tg_res.ok and isinstance(tg_res.data, dict):
            tg_configured = bool(tg_res.data.get("configured"))
            tg_username = str(tg_res.data.get("username") or "")
        s_res = get_smtp_settings(ctx)
        if s_res.ok and isinstance(s_res.data, dict):
            smtp_host = str(s_res.data.get("host") or "")
            smtp_port = int(s_res.data.get("port") or 587)
            smtp_security = str(s_res.data.get("security") or "STARTTLS")
            smtp_username = str(s_res.data.get("username") or "")
            smtp_has_pass = bool(s_res.data.get("has_password"))
            smtp_from_email = str(s_res.data.get("from_email") or "")
            smtp_from_name = str(s_res.data.get("from_name") or "ReconHub")

    return dmc.Box(
        [
            page_header(
                title="Cài đặt hệ thống",
                subtitle="Chỉ ADMIN. Cấu hình dọn file export, số export song song, timeout báo cáo, Telegram và máy chủ gửi email (SMTP).",
                actions=[
                    button_primary(
                        "Lưu cài đặt",
                        id="settings-save-btn",
                        icon="lucide:save",
                        size="sm",
                    ),
                ],
            ),
            html.Div(
                id="settings-alert",
                style={"width": "100%", "maxWidth": 1200, "marginBottom": "4px"},
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            html.Div(
                [
                    dmc.Tabs(
                        [
                            dmc.TabsList(
                                [
                                    dmc.TabsTab(
                                        "Dọn file export",
                                        value="retention",
                                        leftSection=DashIconify(icon="lucide:trash-2", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Export song song",
                                        value="concurrency",
                                        leftSection=DashIconify(icon="lucide:layers", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Timeout báo cáo",
                                        value="timeouts",
                                        leftSection=DashIconify(icon="lucide:clock", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Telegram",
                                        value="telegram",
                                        leftSection=DashIconify(icon="lucide:send", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Máy chủ Email (SMTP)",
                                        value="smtp",
                                        leftSection=DashIconify(icon="lucide:mail", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Mẫu Email",
                                        value="email_template",
                                        leftSection=DashIconify(icon="lucide:file-code", width=16),
                                    ),
                                ],
                                mb="md",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Chính sách dọn file export", order=4, size="sm"),
                                            dmc.Text(
                                                "File export đã kết thúc (DONE/FAILED/CANCELLED) được giữ "
                                                "lại để tải trong Lịch sử báo cáo. Chế độ manual: không tự "
                                                "xóa, ADMIN xóa tay từng file. Chế độ scheduler: worker tự "
                                                "xóa file quá số ngày đã chọn.",
                                                size="sm",
                                                c="dimmed",
                                            ),
                                            dmc.Select(
                                                id="settings-mode-select",
                                                label="Chế độ dọn file",
                                                data=[
                                                    {"label": "Manual — không tự xóa", "value": "manual"},
                                                    {"label": "Scheduler — tự xóa file quá hạn", "value": "scheduler"},
                                                ],
                                                value=mode,
                                                maw=480,
                                                w="100%",
                                                clearable=False,
                                            ),
                                            dmc.NumberInput(
                                                id="settings-days-input",
                                                label="Giữ file (ngày)",
                                                value=days,
                                                min=1,
                                                max=365,
                                                step=1,
                                                maw=480,
                                                w="100%",
                                                description="Chỉ dùng khi chế độ là Scheduler.",
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="retention",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Export chạy song song", order=4, size="sm"),
                                            dmc.Text(
                                                "Worker xử lý tối đa từng này export cùng lúc "
                                                "(mỗi người dùng tối đa từng này export đang chạy). "
                                                "Đổi xong có hiệu lực ở vòng poll tiếp theo, "
                                                "không cần khởi động lại worker.",
                                                size="sm",
                                                c="dimmed",
                                            ),
                                            dmc.NumberInput(
                                                id="settings-concurrent-input",
                                                label="Số export chạy song song tối đa",
                                                value=max_concurrent,
                                                min=1,
                                                max=50,
                                                step=1,
                                                maw=480,
                                                w="100%",
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="concurrency",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Timeout truy vấn báo cáo", order=4, size="sm"),
                                            dmc.Text(
                                                "Khi xem báo cáo, app chạy câu COUNT để đếm tổng số dòng "
                                                "rồi mới lấy 1 trang dữ liệu. Câu COUNT quét toàn bộ dữ "
                                                "liệu trong khoảng ngày nên có thể chạy lâu hơn. "
                                                "Hai timeout này (giây) áp dụng khi xem và xem trước.",
                                                size="sm",
                                                c="dimmed",
                                            ),
                                            dmc.Group(
                                                [
                                                    dmc.NumberInput(
                                                        id="settings-count-timeout-input",
                                                        label="Timeout câu COUNT (giây)",
                                                        value=count_timeout,
                                                        min=1,
                                                        max=3600,
                                                        step=1,
                                                        style={"flex": 1},
                                                    ),
                                                    dmc.NumberInput(
                                                        id="settings-data-timeout-input",
                                                        label="Timeout câu dữ liệu (giây)",
                                                        value=data_timeout,
                                                        min=1,
                                                        max=3600,
                                                        step=1,
                                                        style={"flex": 1},
                                                    ),
                                                ],
                                                grow=True,
                                                gap="sm",
                                                maw=480,
                                                w="100%",
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="timeouts",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Thông báo Telegram", order=4, size="sm"),
                                            dmc.Text(
                                                "Khi run đối soát xong hoặc lỗi, hệ thống gửi tin "
                                                "Telegram cho chính người chạy (task 94). Tạo bot qua "
                                                "@BotFather rồi nhập token và username vào đây; mỗi "
                                                "người dùng liên kết Telegram ở trang Tài khoản.",
                                                size="sm",
                                                c="dimmed",
                                            ),
                                            dmc.PasswordInput(
                                                id="settings-telegram-token",
                                                label="Token bot Telegram",
                                                placeholder="Đã lưu" if tg_configured else "Nhập token bot (từ @BotFather)",
                                                maw=480,
                                                w="100%",
                                            ),
                                            dmc.Group(
                                                [
                                                    dmc.TextInput(
                                                        id="settings-telegram-username",
                                                        label="Username bot",
                                                        placeholder="vd: reconhub_bot",
                                                        value=tg_username,
                                                        style={"flex": 1},
                                                    ),
                                                    dmc.Button(
                                                        "Gửi thử",
                                                        id="settings-telegram-test-btn",
                                                        variant="outline",
                                                        size="sm",
                                                        leftSection=DashIconify(icon="lucide:send", width=14),
                                                    ),
                                                ],
                                                align="flex-end",
                                                gap="sm",
                                                maw=480,
                                                w="100%",
                                            ),
                                            html.Div(id="settings-telegram-alert"),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="telegram",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Máy chủ gửi email (SMTP)", order=4, size="sm"),
                                            dmc.Text(
                                                "Cấu hình thông số máy chủ SMTP để gửi email đính kèm danh "
                                                "sách đối soát và báo cáo. Mật khẩu được mã hóa an toàn.",
                                                size="sm",
                                                c="dimmed",
                                            ),
                                            dmc.Group(
                                                [
                                                    dmc.TextInput(
                                                        id="settings-smtp-host",
                                                        label="Máy chủ SMTP (Host)",
                                                        placeholder="vd: smtp.company.com",
                                                        value=smtp_host,
                                                        style={"flex": 2},
                                                    ),
                                                    dmc.NumberInput(
                                                        id="settings-smtp-port",
                                                        label="Cổng",
                                                        value=smtp_port,
                                                        min=1,
                                                        max=65535,
                                                        step=1,
                                                        style={"flex": 1},
                                                    ),
                                                ],
                                                grow=True,
                                                gap="sm",
                                                maw=540,
                                                w="100%",
                                            ),
                                            dmc.Select(
                                                id="settings-smtp-security",
                                                label="Phương thức bảo mật",
                                                data=[
                                                    {"label": "STARTTLS (Cổng 587 phổ biến)", "value": "STARTTLS"},
                                                    {"label": "SSL/TLS (Cổng 465)", "value": "SSL"},
                                                    {"label": "Không bảo mật (Cổng 25 nội bộ)", "value": "NONE"},
                                                ],
                                                value=smtp_security,
                                                maw=540,
                                                w="100%",
                                                clearable=False,
                                            ),
                                            dmc.Group(
                                                [
                                                    dmc.TextInput(
                                                        id="settings-smtp-username",
                                                        label="Tên tài khoản (Username)",
                                                        placeholder="vd: user@company.com",
                                                        value=smtp_username,
                                                        style={"flex": 1},
                                                    ),
                                                    dmc.PasswordInput(
                                                        id="settings-smtp-password",
                                                        label="Mật khẩu",
                                                        placeholder="Đã lưu mật khẩu" if smtp_has_pass else "Nhập mật khẩu",
                                                        style={"flex": 1},
                                                    ),
                                                ],
                                                grow=True,
                                                gap="sm",
                                                maw=540,
                                                w="100%",
                                            ),
                                            dmc.Group(
                                                [
                                                    dmc.TextInput(
                                                        id="settings-smtp-from-email",
                                                        label="Email người gửi (From)",
                                                        placeholder="vd: reconhub@company.com",
                                                        value=smtp_from_email,
                                                        style={"flex": 1},
                                                    ),
                                                    dmc.TextInput(
                                                        id="settings-smtp-from-name",
                                                        label="Tên người gửi hiển thị",
                                                        placeholder="vd: ReconHub Notification",
                                                        value=smtp_from_name,
                                                        style={"flex": 1},
                                                    ),
                                                ],
                                                grow=True,
                                                gap="sm",
                                                maw=540,
                                                w="100%",
                                            ),
                                            dmc.Divider(my="xs", color="var(--line, #E0E0E0)"),
                                            dmc.Group(
                                                [
                                                    dmc.TextInput(
                                                        id="settings-smtp-test-email",
                                                        label="Gửi email thử nghiệm tới",
                                                        placeholder="vd: admin@company.com",
                                                        style={"flex": 1},
                                                    ),
                                                    dmc.Button(
                                                        "Gửi thử",
                                                        id="settings-smtp-test-btn",
                                                        variant="outline",
                                                        size="sm",
                                                        leftSection=DashIconify(icon="lucide:send", width=14),
                                                    ),
                                                ],
                                                align="flex-end",
                                                gap="sm",
                                                maw=540,
                                                w="100%",
                                            ),
                                            html.Div(id="settings-smtp-alert"),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="smtp",
                            ),
                            dmc.TabsPanel(
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dcc.Store(id="settings-tmpl-selected-fn", data="GENERAL_EXPORT"),
                                            dmc.Group(
                                                [
                                                    dmc.Stack(
                                                        [
                                                            dmc.Title("Quản lý mẫu email nghiệp vụ", order=4, size="sm"),
                                                            dmc.Text(
                                                                "Cấu hình Mẫu mặc định dùng chung (Fallback tự động cho mọi tính năng xuất như User, Menu, Template, Data Source...) "
                                                                "hoặc tùy biến riêng theo từng phân hệ. Xem trước thời gian thực (Live Preview).",
                                                                size="sm",
                                                                c="dimmed",
                                                            ),
                                                        ],
                                                        gap=2,
                                                    ),
                                                ],
                                                justify="space-between",
                                            ),
                                            html.Div(id="settings-tmpl-alert"),
                                            dmc.Grid(
                                                gutter="md",
                                                children=[
                                                    # CARD 1: Master List - Chức năng gửi email & Thẻ dữ liệu
                                                    dmc.GridCol(
                                                        dmc.Paper(
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Group(
                                                                        [
                                                                            DashIconify(icon="lucide:layers", width=18, color="#1971c2"),
                                                                            dmc.Text("Chức năng gửi email", fw=600, size="sm"),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                    dmc.Text(
                                                                        "Chọn phân hệ để cấu hình mẫu hoặc chỉnh sửa Mẫu mặc định dùng chung:",
                                                                        size="xs",
                                                                        c="dimmed",
                                                                    ),
                                                                    dmc.Stack(
                                                                        id="settings-tmpl-fn-list",
                                                                        children=render_fn_nav_list("GENERAL_EXPORT"),
                                                                        gap=4,
                                                                    ),
                                                                    dmc.Divider(my="xs"),
                                                                    dmc.Stack(
                                                                        [
                                                                            dmc.Group(
                                                                                [
                                                                                    DashIconify(icon="lucide:code", width=15, color="#495057"),
                                                                                    dmc.Text("Thẻ dữ liệu khả dụng:", fw=600, size="xs"),
                                                                                ],
                                                                                gap="xs",
                                                                            ),
                                                                            dmc.Text("Nhấp thẻ để chép hoặc chèn vào vị trí soạn thảo:", size="xs", c="dimmed"),
                                                                            html.Div(id="settings-tmpl-tokens-container"),
                                                                        ],
                                                                        gap=4,
                                                                    ),
                                                                ],
                                                                gap="xs",
                                                            ),
                                                            p="md",
                                                            withBorder=True,
                                                            radius="sm",
                                                            bg="var(--mantine-color-gray-0)",
                                                            h="100%",
                                                        ),
                                                        span={"base": 12, "lg": 3.5},
                                                    ),
                                                    # CARD 2: Detail Editor - Soạn thảo tiêu đề & HTML rộng rãi
                                                    dmc.GridCol(
                                                        dmc.Paper(
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Group(
                                                                        [
                                                                            DashIconify(icon="lucide:file-edit", width=18, color="#1971c2"),
                                                                            html.Div(id="settings-tmpl-header-info"),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                    dmc.TextInput(
                                                                        id="settings-tmpl-subject-input",
                                                                        label="Tiêu đề email",
                                                                        placeholder="Tiêu đề email (hỗ trợ {{token}})...",
                                                                        w="100%",
                                                                        size="sm",
                                                                    ),
                                                                    dmc.Textarea(
                                                                        id="settings-tmpl-body-input",
                                                                        label="Nội dung HTML email",
                                                                        placeholder="Soạn nội dung mã nguồn HTML...",
                                                                        minRows=20,
                                                                        autosize=True,
                                                                        maxRows=35,
                                                                        w="100%",
                                                                        styles={
                                                                            "input": {
                                                                                "fontFamily": "Consolas, 'Courier New', monospace",
                                                                                "fontSize": "13px",
                                                                                "lineHeight": "1.5",
                                                                                "padding": "12px",
                                                                            }
                                                                        },
                                                                    ),
                                                                    dmc.Group(
                                                                        [
                                                                            button_primary(
                                                                                "Lưu mẫu email",
                                                                                id="settings-tmpl-save-btn",
                                                                                icon="lucide:save",
                                                                                size="sm",
                                                                            ),
                                                                            dmc.Button(
                                                                                "Khôi phục mặc định",
                                                                                id="settings-tmpl-reset-btn",
                                                                                variant="light",
                                                                                color="gray",
                                                                                leftSection=DashIconify(icon="lucide:rotate-ccw", width=14),
                                                                                size="sm",
                                                                            ),
                                                                        ],
                                                                        gap="sm",
                                                                    ),
                                                                ],
                                                                gap="sm",
                                                            ),
                                                            p="md",
                                                            withBorder=True,
                                                            radius="sm",
                                                            bg="#ffffff",
                                                            h="100%",
                                                        ),
                                                        span={"base": 12, "lg": 4.5},
                                                    ),
                                                    # CARD 3: Detail Live Preview - Mô phỏng hộp thư người nhận
                                                    dmc.GridCol(
                                                        dmc.Paper(
                                                            dmc.Stack(
                                                                [
                                                                    dmc.Group(
                                                                        [
                                                                            DashIconify(icon="lucide:eye", width=18, color="#1971c2"),
                                                                            dmc.Text("Xem trước thời gian thực (Live Preview)", size="sm", fw=600),
                                                                        ],
                                                                        gap="xs",
                                                                    ),
                                                                    dmc.Text("Mô phỏng chính xác giao diện hộp thư người nhận:", size="xs", c="dimmed"),
                                                                    dmc.Paper(
                                                                        [
                                                                            dmc.Group(
                                                                                [
                                                                                    dmc.Text("Từ:", size="xs", c="dimmed", w=50),
                                                                                    dmc.Text("ReconHub <noreply@reconhub.local>", size="xs", fw=500),
                                                                                ],
                                                                                gap="xs",
                                                                                mb=4,
                                                                            ),
                                                                            dmc.Group(
                                                                                [
                                                                                    dmc.Text("Tiêu đề:", size="xs", c="dimmed", w=50),
                                                                                    dmc.Text(id="settings-tmpl-preview-subject", size="xs", fw=600, c="blue.8"),
                                                                                ],
                                                                                gap="xs",
                                                                                mb=4,
                                                                            ),
                                                                            dmc.Divider(my="xs"),
                                                                            html.Iframe(
                                                                                id="settings-tmpl-preview-frame",
                                                                                style={
                                                                                    "width": "100%",
                                                                                    "height": "480px",
                                                                                    "border": "none",
                                                                                    "borderRadius": "4px",
                                                                                    "backgroundColor": "#ffffff",
                                                                                },
                                                                            ),
                                                                        ],
                                                                        p="sm",
                                                                        withBorder=True,
                                                                        radius="sm",
                                                                        bg="#ffffff",
                                                                    ),
                                                                ],
                                                                gap="xs",
                                                            ),
                                                            p="md",
                                                            withBorder=True,
                                                            radius="sm",
                                                            bg="var(--mantine-color-gray-0)",
                                                            h="100%",
                                                        ),
                                                        span={"base": 12, "lg": 4},
                                                    ),
                                                ],
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    withBorder=True,
                                    radius="sm",
                                    p="lg",
                                    w="100%",
                                ),
                                value="email_template",
                            ),
                        ],
                        id="settings-tabs",
                        value="retention",
                        w="100%",
                        maw=1440,
                    ),
                ],
                style={
                    "flex": "1 1 0%",
                    "minHeight": 0,
                    "overflowY": "auto",
                    "padding": "4px 0 24px 0",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                },
            ),
        ],
        style={
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
        },
    )


@callback(
    Output("settings-alert", "children"),
    Input("settings-save-btn", "n_clicks"),
    State("settings-mode-select", "value"),
    State("settings-days-input", "value"),
    State("settings-concurrent-input", "value"),
    State("settings-count-timeout-input", "value"),
    State("settings-data-timeout-input", "value"),
    State("settings-telegram-token", "value"),
    State("settings-telegram-username", "value"),
    State("settings-smtp-host", "value"),
    State("settings-smtp-port", "value"),
    State("settings-smtp-security", "value"),
    State("settings-smtp-username", "value"),
    State("settings-smtp-password", "value"),
    State("settings-smtp-from-email", "value"),
    State("settings-smtp-from-name", "value"),
    prevent_initial_call=True,
)
def handle_settings_save(
    n_clicks: int | None,
    mode: str | None,
    days: int | float | None,
    max_concurrent: int | float | None,
    count_timeout: int | float | None,
    data_timeout: int | float | None,
    telegram_token: str | None,
    telegram_username: str | None,
    smtp_host: str | None,
    smtp_port: int | float | None,
    smtp_security: str | None,
    smtp_username: str | None,
    smtp_password: str | None,
    smtp_from_email: str | None,
    smtp_from_name: str | None,
) -> Any:
    """Lưu cài đặt dọn file + song song export + timeout báo cáo + Telegram + SMTP (task 52, 57, 71, 94, 96)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    try:
        days_int = int(days) if days is not None else 30
    except (TypeError, ValueError):
        return notify_error("Số ngày phải là số nguyên.")
    try:
        concurrent_int = int(max_concurrent) if max_concurrent is not None else 10
    except (TypeError, ValueError):
        return notify_error("Số export song song phải là số nguyên.")
    try:
        count_int = int(count_timeout) if count_timeout is not None else 300
    except (TypeError, ValueError):
        return notify_error("Timeout câu COUNT phải là số nguyên.")
    try:
        data_int = int(data_timeout) if data_timeout is not None else 300
    except (TypeError, ValueError):
        return notify_error("Timeout câu dữ liệu phải là số nguyên.")
    try:
        smtp_port_int = int(smtp_port) if smtp_port is not None else 587
    except (TypeError, ValueError):
        return notify_error("Cổng SMTP phải là số nguyên.")

    res = set_export_retention(ctx, mode or "manual", days_int)
    if not res.ok:
        return notify_error(res.message or "Không lưu được cài đặt.")
    c_res = set_export_concurrency(ctx, concurrent_int)
    if not c_res.ok:
        return notify_error(c_res.message or "Không lưu được cài đặt song song.")
    t_res = set_report_timeouts(ctx, count_int, data_int)
    if not t_res.ok:
        return notify_error(t_res.message or "Không lưu được timeout báo cáo.")
    tg_res = set_telegram_settings(ctx, telegram_token, telegram_username)
    if not tg_res.ok:
        return notify_error(tg_res.message or "Không lưu được cài đặt Telegram.")
    smtp_res = set_smtp_settings(
        ctx=ctx,
        host=smtp_host or "",
        port=smtp_port_int,
        security=smtp_security or "STARTTLS",
        username=smtp_username or "",
        password=smtp_password,
        from_email=smtp_from_email or "",
        from_name=smtp_from_name or "",
    )
    if not smtp_res.ok:
        return notify_error(smtp_res.message or "Không lưu được cấu hình SMTP.")

    data = res.data or {}
    c_data = c_res.data or {}
    t_data = t_res.data or {}
    tg_data = tg_res.data or {}
    smtp_data = smtp_res.data or {}
    return notify_success(
        f"Đã lưu: chế độ {data.get('mode')}, giữ file {data.get('days')} ngày, "
        f"tối đa {c_data.get('max_concurrent')} export chạy song song, "
        f"timeout COUNT {t_data.get('count_timeout_sec')}s, "
        f"timeout dữ liệu {t_data.get('data_timeout_sec')}s, "
        f"Telegram {'đã cấu hình' if tg_data.get('configured') else 'chưa cấu hình'}, "
        f"SMTP {'đã cấu hình' if smtp_data.get('configured') else 'chưa cấu hình'}."
    )


@callback(
    Output("settings-telegram-alert", "children"),
    Input("settings-telegram-test-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_settings_telegram_test(n_clicks: int | None) -> Any:
    """Gửi tin thử Telegram tới tài khoản đã liên kết của ADMIN (task 94)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = send_telegram_test(ctx)
    if not res.ok:
        return notify_error(res.message or "Không gửi được tin thử.")
    return notify_success("Đã gửi tin thử tới Telegram của bạn.")


@callback(
    Output("settings-smtp-alert", "children"),
    Input("settings-smtp-test-btn", "n_clicks"),
    State("settings-smtp-test-email", "value"),
    prevent_initial_call=True,
)
def handle_settings_smtp_test(n_clicks: int | None, test_email: str | None) -> Any:
    """Gửi email thử nghiệm từ cài đặt SMTP đã lưu (task 96)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    target_email = (test_email or "").strip()
    if not target_email:
        return notify_error("Vui lòng nhập địa chỉ email nhận thư thử nghiệm.")
    res = test_smtp_connection(ctx, target_email)
    if not res.ok:
        return notify_error(res.message or "Không gửi được email thử nghiệm.")
    return notify_success(res.message or "Đã gửi email thử nghiệm thành công.")


@callback(
    Output("settings-tmpl-selected-fn", "data"),
    Input({"type": "settings-tmpl-fn-nav", "code": ALL}, "n_clicks"),
    State("settings-tmpl-selected-fn", "data"),
    prevent_initial_call=True,
)
def handle_template_nav_click(n_clicks_list: list[int | None], current_code: str | None) -> str:
    """Xử lý chọn phân hệ / chức năng gửi email từ danh sách Card 1."""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict) and "code" in triggered_id:
        return str(triggered_id["code"])
    return current_code or "GENERAL_EXPORT"


@callback(
    Output("settings-tmpl-fn-list", "children"),
    Output("settings-tmpl-header-info", "children"),
    Output("settings-tmpl-subject-input", "value"),
    Output("settings-tmpl-body-input", "value"),
    Output("settings-tmpl-tokens-container", "children"),
    Output("settings-tmpl-alert", "children"),
    Input("settings-tmpl-selected-fn", "data"),
    Input("settings-tmpl-save-btn", "n_clicks"),
    Input("settings-tmpl-reset-btn", "n_clicks"),
    State("settings-tmpl-subject-input", "value"),
    State("settings-tmpl-body-input", "value"),
    prevent_initial_call=False,
)
def handle_template_editor_events(
    fn_code: str | None,
    save_clicks: int | None,
    reset_clicks: int | None,
    current_subject: str | None,
    current_body: str | None,
) -> tuple[list[Any], Any, str, str, Any, Any]:
    """Tải template khi đổi chức năng, lưu cấu hình hoặc khôi phục mặc định."""
    triggered_id = dash.callback_context.triggered_id
    code = fn_code or "GENERAL_EXPORT"
    ctx = get_current_ctx()
    fn_meta = get_email_function_meta(code)

    alert_node = None
    if triggered_id == "settings-tmpl-save-btn":
        if ctx is None:
            tmpl = get_email_template_internal(code)
            return (
                render_fn_nav_list(code),
                render_tmpl_header_info(tmpl, fn_meta),
                current_subject or "",
                current_body or "",
                dash.no_update,
                notify_error("Chưa đăng nhập."),
            )
        res = save_email_template(
            ctx,
            {
                "function_code": code,
                "name": fn_meta["label"] if fn_meta else f"Mẫu email {code}",
                "subject_pattern": current_subject or "",
                "body_html": current_body or "",
            },
        )
        if not res.ok:
            tmpl = get_email_template_internal(code)
            return (
                render_fn_nav_list(code),
                render_tmpl_header_info(tmpl, fn_meta),
                current_subject or "",
                current_body or "",
                dash.no_update,
                notify_error(res.message or "Lỗi lưu mẫu."),
            )
        tmpl = res.data or {}
        alert_node = notify_success(f"Đã lưu mẫu email cho chức năng '{fn_meta['label'] if fn_meta else code}' thành công.")
        tokens_badges = render_token_badges(tmpl.get("available_tokens", []))
        return (
            render_fn_nav_list(code),
            render_tmpl_header_info(tmpl, fn_meta),
            tmpl.get("subject_pattern") or "",
            tmpl.get("body_html") or "",
            tokens_badges,
            alert_node,
        )

    if triggered_id == "settings-tmpl-reset-btn":
        if ctx is None:
            tmpl = get_email_template_internal(code)
            return (
                render_fn_nav_list(code),
                render_tmpl_header_info(tmpl, fn_meta),
                current_subject or "",
                current_body or "",
                dash.no_update,
                notify_error("Chưa đăng nhập."),
            )
        res = reset_email_template_to_default(ctx, code)
        if not res.ok:
            tmpl = get_email_template_internal(code)
            return (
                render_fn_nav_list(code),
                render_tmpl_header_info(tmpl, fn_meta),
                current_subject or "",
                current_body or "",
                dash.no_update,
                notify_error(res.message or "Lỗi khôi phục mẫu."),
            )
        tmpl = res.data or {}
        alert_node = notify_success(f"Đã khôi phục mẫu mặc định cho chức năng '{fn_meta['label'] if fn_meta else code}'.")
        tokens_badges = render_token_badges(tmpl.get("available_tokens", []))
        return (
            render_fn_nav_list(code),
            render_tmpl_header_info(tmpl, fn_meta),
            tmpl.get("subject_pattern") or "",
            tmpl.get("body_html") or "",
            tokens_badges,
            alert_node,
        )

    # Trigger mặc định hoặc đổi function trong Card 1
    tmpl = get_email_template_internal(code)
    tokens_badges = render_token_badges(tmpl.get("available_tokens", []))
    return (
        render_fn_nav_list(code),
        render_tmpl_header_info(tmpl, fn_meta),
        tmpl.get("subject_pattern") or "",
        tmpl.get("body_html") or "",
        tokens_badges,
        alert_node,
    )


@callback(
    Output("settings-tmpl-preview-subject", "children"),
    Output("settings-tmpl-preview-frame", "srcDoc"),
    Input("settings-tmpl-subject-input", "value"),
    Input("settings-tmpl-body-input", "value"),
    Input("settings-tmpl-selected-fn", "data"),
    prevent_initial_call=False,
)
def handle_template_preview(
    subject_val: str | None,
    body_val: str | None,
    fn_code: str | None,
) -> tuple[str, str]:
    """Cập nhật Live Preview tức thì khi người dùng gõ phím."""
    code = fn_code or "GENERAL_EXPORT"
    builtin = get_builtin_default_template(code)
    mock_ctx = builtin.get("mock_context", {})

    rendered_subject = render_email_subject(subject_val or "", mock_ctx)
    rendered_body = render_email_body(body_val or "", mock_ctx)
    return rendered_subject, rendered_body
