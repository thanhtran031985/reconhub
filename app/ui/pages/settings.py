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
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
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
                        ],
                        id="settings-tabs",
                        value="retention",
                        w="100%",
                        maw=800,
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
