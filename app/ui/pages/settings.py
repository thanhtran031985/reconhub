"""Trang Cài đặt hệ thống (task 52) — chỉ ADMIN.

Cài đặt dọn file export chạy ngầm: chế độ manual (mặc định, không tự
xóa) hoặc scheduler (worker tự xóa file export đã kết thúc quá N ngày).
Task 57: số export chạy song song tối đa (mặc định 10).
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

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
from app.ui.components.alert_box import alert_box
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/settings", title="Cài đặt hệ thống – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "system_settings"


def layout(**kwargs: Any) -> Any:
    """Form cài đặt dọn file export (ADMIN-only qua menu)."""
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
    return dmc.Box(
        [
            html.Div(
                id="settings-alert",
                style={"width": "100%", "maxWidth": 640},
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            page_header(
                title="Cài đặt hệ thống",
                subtitle="Chỉ ADMIN. Áp dụng cho file export chạy ngầm và timeout truy vấn báo cáo.",
                style={"width": "fit-content"},
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Dọn file export", order=4, size="sm"),
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
                            w=320,
                            clearable=False,
                        ),
                        dmc.NumberInput(
                            id="settings-days-input",
                            label="Giữ file (ngày)",
                            value=days,
                            min=1,
                            max=365,
                            step=1,
                            w=320,
                            description="Chỉ dùng khi chế độ là Scheduler.",
                        ),
                    ],
                    gap="md",
                ),
                withBorder=True,
                radius="sm",
                p="md",
                w="100%",
                maw=640,
            ),
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
                            w=320,
                        ),
                    ],
                    gap="md",
                ),
                withBorder=True,
                radius="sm",
                p="md",
                w="100%",
                maw=640,
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Timeout truy vấn báo cáo", order=4, size="sm"),
                        dmc.Text(
                            "Khi xem báo cáo, app chạy câu COUNT để đếm tổng số dòng "
                            "rồi mới lấy 1 trang dữ liệu. Câu COUNT quét toàn bộ dữ "
                            "liệu trong khoảng ngày nên với khoảng rộng có thể chạy "
                            "lâu hơn câu lấy dữ liệu. Hai timeout này (giây) áp dụng "
                            "cho mọi báo cáo khi xem và xem trước; đổi xong có hiệu "
                            "lực ngay, không cần khởi động lại.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.NumberInput(
                            id="settings-count-timeout-input",
                            label="Timeout câu COUNT (giây)",
                            value=count_timeout,
                            min=1,
                            max=3600,
                            step=1,
                            w=320,
                        ),
                        dmc.NumberInput(
                            id="settings-data-timeout-input",
                            label="Timeout câu dữ liệu (giây)",
                            value=data_timeout,
                            min=1,
                            max=3600,
                            step=1,
                            w=320,
                        ),
                    ],
                    gap="md",
                ),
                withBorder=True,
                radius="sm",
                p="md",
                w="100%",
                maw=640,
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Lưu cài đặt",
                        id="settings-save-btn",
                        variant="filled",
                        size="sm",
                    ),
                ],
                justify="center",
                w="100%",
                maw=640,
            ),
        ],
        style={
            "padding": "12px 16px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "gap": "10px",
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
    prevent_initial_call=True,
)
def handle_settings_save(
    n_clicks: int | None,
    mode: str | None,
    days: int | float | None,
    max_concurrent: int | float | None,
    count_timeout: int | float | None,
    data_timeout: int | float | None,
) -> Any:
    """Lưu cài đặt dọn file + song song export + timeout báo cáo (task 52, 57, 71)."""
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
    res = set_export_retention(ctx, mode or "manual", days_int)
    if not res.ok:
        return notify_error(res.message or "Không lưu được cài đặt.")
    c_res = set_export_concurrency(ctx, concurrent_int)
    if not c_res.ok:
        return notify_error(c_res.message or "Không lưu được cài đặt song song.")
    t_res = set_report_timeouts(ctx, count_int, data_int)
    if not t_res.ok:
        return notify_error(t_res.message or "Không lưu được timeout báo cáo.")
    data = res.data or {}
    c_data = c_res.data or {}
    t_data = t_res.data or {}
    return notify_success(
        f"Đã lưu: chế độ {data.get('mode')}, giữ file {data.get('days')} ngày, "
        f"tối đa {c_data.get('max_concurrent')} export chạy song song, "
        f"timeout COUNT {t_data.get('count_timeout_sec')}s, "
        f"timeout dữ liệu {t_data.get('data_timeout_sec')}s."
    )
