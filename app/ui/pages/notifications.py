"""Trang Trung tâm thông báo (task 78 + task 79 theo thiết kế NOTIFICATION-01).

Master–Detail, không cuộn trang ở ≥1366×768 (chỉ list/panel cuộn
trong); dưới 900px xếp dọc, trang được cuộn (quy tắc ui-dash).

- Header 1 dòng + nút "Đánh dấu tất cả đã đọc" / "Cài đặt".
- Command bar: tìm kiếm + lọc loại / đã-chưa đọc / thời gian + Làm mới.
- List trái nhóm theo ngày (HÔM NAY/HÔM QUA), giờ tương đối, icon
  trạng thái, chấm xanh chưa đọc, dòng chọn highlight; bấm dòng chỉ
  chọn (không điều hướng).
- Panel phải rộng 320 (token --size-detail-panel): chi tiết entity
  + nút "Mở kết quả" (đánh dấu đã đọc trước, mẫu D18 task 78) +
  "Sao chép mã run" (clientside callback ghi clipboard) + "Xóa"
  (qua modal xác nhận).
- Footer: "N thông báo · M chưa đọc · Cập nhật HH:MM:SS" + Pagination.
- Cài đặt: dmc.Modal (công tắc tổng + đủ 12 loại, Hủy/Lưu).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, clientside_callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.notification import (
    EVENT_GROUPS,
    EVENT_TYPES,
    delete_notification,
    get_notification_detail,
    get_prefs,
    list_notifications,
    mark_all_read,
    mark_read,
    set_prefs,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/notifications", title="Thông báo – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "notifications"
PAGE_SIZE = 20

READ_OPTIONS = [
    {"value": "all", "label": "Tất cả"},
    {"value": "unread", "label": "Chưa đọc"},
    {"value": "read", "label": "Đã đọc"},
]
TIME_OPTIONS = [
    {"value": "7d", "label": "7 ngày qua"},
    {"value": "30d", "label": "30 ngày qua"},
    {"value": "all", "label": "Tất cả"},
]
DEFAULT_FILTERS = {"q": "", "event_type": "", "read": "all", "time_range": "7d"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    """datetime | chuỗi ISO | None -> datetime naive | None."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def format_relative_time(value: Any, now: datetime | None = None) -> str:
    """Giờ tương đối: 'Vừa xong' / '2 phút' / '1 giờ' /
    'Hôm qua 16:20' / '12/11/2026 16:20' (giờ UTC như trong DB)."""
    dt = _parse_dt(value)
    if dt is None:
        return ""
    now = now or _now()
    secs = int((now - dt).total_seconds())
    if secs < 0:
        secs = 0
    if secs < 60:
        return "Vừa xong"
    if secs < 3600:
        return f"{secs // 60} phút"
    if dt.date() == now.date():
        return f"{secs // 3600} giờ"
    if dt.date() == (now - timedelta(days=1)).date():
        return f"Hôm qua {dt.strftime('%H:%M')}"
    return dt.strftime("%d/%m/%Y %H:%M")


def day_group_label(value: Any, now: datetime | None = None) -> str:
    """Nhãn nhóm theo ngày: HÔM NAY / HÔM QUA / '12/11/2026'."""
    dt = _parse_dt(value)
    if dt is None:
        return ""
    now = now or _now()
    if dt.date() == now.date():
        return "HÔM NAY"
    if dt.date() == (now - timedelta(days=1)).date():
        return "HÔM QUA"
    return dt.strftime("%d/%m/%Y")


def _status_meta(event_type: str) -> dict[str, str]:
    """(nhãn, màu, icon) trạng thái theo loại sự kiện."""
    if event_type.endswith("_FAILED"):
        return {"label": "Lỗi", "color": "red", "icon": "lucide:x-circle"}
    if event_type in ("WORKER_DOWN", "QUEUE_STUCK"):
        return {"label": "Cảnh báo", "color": "orange", "icon": "lucide:alert-triangle"}
    if event_type.endswith("_DONE"):
        return {"label": "Hoàn tất", "color": "green", "icon": "lucide:check-circle"}
    return {"label": "Thông tin", "color": "blue", "icon": "lucide:info"}


def _status_icon(event_type: str) -> Any:
    meta = _status_meta(event_type)
    return dmc.ThemeIcon(
        DashIconify(icon=meta["icon"], width=16),
        color=meta["color"],
        variant="filled",
        size="sm",
        radius="xl",
    )


def _notif_row(item: dict[str, Any], selected_id: int | None, now: datetime) -> Any:
    """1 dòng thông báo trong list (bấm để chọn, không điều hướng)."""
    nid = int(item["id"])
    is_read = bool(item.get("is_read"))
    title = str(item.get("title") or "")
    message = str(item.get("message") or "")
    return html.Div(
        dmc.Group(
            [
                _status_icon(str(item.get("type") or "")),
                dmc.Stack(
                    [
                        dmc.Text(title, size="sm", fw=600 if not is_read else 400, lineClamp=1),
                        dmc.Text(message, size="xs", c="dimmed", lineClamp=1) if message else html.Div(),
                    ],
                    gap=0,
                    style={"flex": "1", "minWidth": 0},
                ),
                dmc.Stack(
                    [
                        dmc.Text(format_relative_time(item.get("created_at"), now), size="xs", c="dimmed"),
                        html.Div(className="notif-unread-dot") if not is_read else html.Div(),
                    ],
                    gap="xs",
                    align="flex-end",
                ),
            ],
            gap="sm",
            align="flex-start",
            wrap="nowrap",
        ),
        id={"type": "notif-row", "index": nid},
        className="notif-row notif-row-selected" if nid == selected_id else "notif-row",
    )


def _grouped_rows(items: list[dict[str, Any]], selected_id: int | None, now: datetime) -> list[Any]:
    """List nhóm theo ngày (HÔM NAY/HÔM QUA/ngày cũ)."""
    if not items:
        return [dmc.Text("Chưa có thông báo.", size="sm", c="dimmed", p="sm")]
    children: list[Any] = []
    current_group: str | None = None
    for item in items:
        group = day_group_label(item.get("created_at"), now)
        if group != current_group:
            current_group = group
            children.append(dmc.Text(group, size="xs", fw=600, c="dimmed", px="sm", pt="xs", pb="xs"))
        children.append(_notif_row(item, selected_id, now))
    return children


def _filters_from(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return dict(DEFAULT_FILTERS)
    return {
        "q": str(data.get("q") or ""),
        "event_type": str(data.get("event_type") or ""),
        "read": str(data.get("read") or "all"),
        "time_range": str(data.get("time_range") or "7d"),
    }


def _updated_now() -> str:
    return f"Cập nhật {_now().strftime('%H:%M:%S')}"


def _list_body(
    ctx: Ctx, page: int, filters: dict[str, str], selected_id: int | None
) -> tuple[list[Any], str, str, int, int, int, int | None]:
    """(children, footer, updated, max_page, total, unread, selected_id)."""
    res = list_notifications(
        ctx,
        page=page,
        page_size=PAGE_SIZE,
        unread_only=filters.get("read") == "unread",
        read_only=filters.get("read") == "read",
        q=filters.get("q") or None,
        event_type=filters.get("event_type") or None,
        time_range=filters.get("time_range") or "7d",
    )
    if not res.ok or not isinstance(res.data, dict):
        return (
            [alert_box(res.message or "Không tải được thông báo.", tone="crit")],
            "0 thông báo · 0 chưa đọc",
            _updated_now(),
            1,
            0,
            0,
            None,
        )
    items = res.data.get("items") or []
    total = int(res.data.get("total") or 0)
    unread = int(res.data.get("unread") or 0)
    max_page = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
    if selected_id is not None and not any(int(i["id"]) == selected_id for i in items):
        selected_id = None
    if selected_id is None and items:
        selected_id = int(items[0]["id"])
    now = _now()
    children = _grouped_rows(items, selected_id, now)
    footer = f"{total} thông báo · {unread} chưa đọc"
    return children, footer, _updated_now(), max_page, total, unread, selected_id


def _action_buttons(link: Any, code: Any, open_label: Any, show_delete: bool = True) -> Any:
    """Nút Mở kết quả + Sao chép mã + Xóa: luôn render (ẩn khi không
    áp dụng) vì Dash yêu cầu Input của callback phải tồn tại trong
    layout — panel trống/SYSTEM không render nút làm callback
    list/copy chết, mọi bộ lọc sau đó kẹt (hồi quy live)."""
    return dmc.Group(
        [
            dmc.Button(
                str(open_label or "Mở kết quả"),
                id="notif-detail-open-btn",
                size="sm",
                leftSection=DashIconify(icon="lucide:external-link", width=16),
                style={} if link else {"display": "none"},
            ),
            dmc.Button(
                "Sao chép mã run",
                id="notif-detail-copy-btn",
                variant="light",
                size="sm",
                leftSection=DashIconify(icon="lucide:copy", width=16),
                style={} if code else {"display": "none"},
                **{"aria-label": "Sao chép mã run"},
            ),
            dmc.Button(
                "Xóa",
                id="notif-detail-delete-btn",
                variant="subtle",
                color="red",
                size="sm",
                leftSection=DashIconify(icon="lucide:trash-2", width=16),
                style={} if show_delete else {"display": "none"},
            ),
        ],
        gap="sm",
        align="center",
    )


def _detail_panel(ctx: Ctx, selected_id: int | None) -> list[Any]:
    """Nội dung panel chi tiết bên phải."""
    if not selected_id:
        return [
            dmc.Text("Chọn dòng để xem chi tiết.", size="sm", c="dimmed", p="sm"),
            _action_buttons(None, None, None, show_delete=False),
        ]
    res = get_notification_detail(ctx, selected_id)
    if not res.ok or not isinstance(res.data, dict):
        return [
            alert_box(res.message or "Không tải được chi tiết.", tone="crit"),
            _action_buttons(None, None, None, show_delete=True),
        ]
    d = res.data
    meta = _status_meta(str(d.get("type") or ""))
    nodes: list[Any] = [
        dmc.Title(str(d.get("title") or ""), order=5, size=16, fw=600),
        dmc.Group(
            [
                dmc.Badge(meta["label"], color=meta["color"], size="sm"),
                dmc.Badge(str(d.get("type") or ""), variant="outline", color="gray", size="sm"),
            ],
            gap="xs",
        ),
    ]
    created = _parse_dt(d.get("created_at"))
    if created:
        nodes.append(dmc.Text(created.strftime("%d/%m/%Y · %H:%M:%S"), size="xs", c="dimmed"))
    if d.get("message"):
        nodes.append(dmc.Text(str(d["message"]), size="sm", c="dimmed"))
    if d.get("code"):
        nodes.append(
            dmc.Group(
                [
                    dmc.Text(str(d.get("code_label") or "Mã"), size="sm", c="dimmed"),
                    dmc.Text(str(d["code"]), size="sm", fw=600, id="notif-detail-code"),
                ],
                gap="sm",
                align="center",
                justify="space-between",
            )
        )
    for field in d.get("fields") or []:
        nodes.append(
            dmc.Group(
                [
                    dmc.Text(str(field.get("label")), size="sm", c="dimmed"),
                    dmc.Text(str(field.get("value")), size="sm", fw=500),
                ],
                gap="sm",
                align="center",
                justify="space-between",
            )
        )
    if d.get("error"):
        nodes.append(
            dmc.Alert(
                str(d["error"]),
                title="Nguyên nhân",
                color="red",
                variant="light",
                icon=DashIconify(icon="lucide:x-circle", width=16),
            )
        )
    nodes.append(_action_buttons(d.get("link"), d.get("code"), d.get("open_label")))
    return nodes


def _prefs_modal_body(ctx: Ctx) -> list[Any]:
    """Nội dung modal cài đặt: công tắc tổng + đủ 12 loại theo nhóm."""
    prefs: dict[str, bool] = {code: bool(info["default"]) for code, info in EVENT_TYPES.items()}
    master = True
    res = get_prefs(ctx)
    if res.ok and isinstance(res.data, dict):
        saved = res.data.get("prefs") or {}
        for code in prefs:
            if code in saved:
                prefs[code] = bool(saved[code])
        master = bool(res.data.get("master", True))
    groups: list[Any] = []
    for group in EVENT_GROUPS:
        switches = [
            dmc.Switch(
                label=str(EVENT_TYPES[code]["label"]),
                id={"type": "notif-pref-switch", "index": code},
                checked=prefs[code],
                size="sm",
            )
            for code in group["types"]
            if code in EVENT_TYPES
        ]
        groups.append(
            dmc.Stack(
                [dmc.Text(str(group["label"]), size="sm", fw=600), *switches],
                gap="xs",
            )
        )
    return [
        dmc.Text("Chỉ áp dụng cho tài khoản của bạn.", size="sm", c="dimmed"),
        dmc.Switch(
            label="Nhận thông báo trong ứng dụng",
            id="notif-master-switch",
            checked=master,
            size="sm",
        ),
        dmc.SimpleGrid(cols={"base": 1, "sm": 2}, spacing="md", children=groups),
        html.Div(id="notif-settings-alert"),
        dmc.Group(
            [
                dmc.Button("Hủy", id="notif-settings-cancel-btn", variant="default", size="sm"),
                dmc.Button("Lưu thay đổi", id="notif-settings-save-btn", size="sm"),
            ],
            justify="flex-end",
            gap="sm",
        ),
    ]


def layout(**kwargs: Any) -> Any:
    """Trang Trung tâm thông báo: Master–Detail, không cuộn trang."""
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập để xem thông báo.", tone="crit")
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="notifications-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem thông báo.", tone="crit"),
            ]
        )
    filters = dict(DEFAULT_FILTERS)
    children, footer, updated, max_page, total, unread, selected = _list_body(ctx, 1, filters, None)
    type_options = [{"value": "", "label": "Tất cả sự kiện"}] + [
        {"value": code, "label": str(info["label"])} for code, info in EVENT_TYPES.items()
    ]
    return dmc.Box(
        [
            page_header(
                title="Trung tâm thông báo",
                subtitle="Theo dõi sự kiện đối soát, báo cáo và hệ thống.",
                actions=[
                    dmc.Button(
                        "Đánh dấu tất cả đã đọc",
                        id="notif-mark-all-read-btn",
                        variant="light",
                        size="sm",
                        leftSection=DashIconify(icon="lucide:check", width=16),
                    ),
                    dmc.Button(
                        "Cài đặt",
                        id="notif-settings-btn",
                        variant="light",
                        size="sm",
                        leftSection=DashIconify(icon="lucide:settings", width=16),
                    ),
                ],
            ),
            dcc.Store(id="notif-filter-store", data=filters),
            dcc.Store(id="notif-page-store", data={"page": 1}),
            dcc.Store(id="notif-selected-store", data={"id": selected}),
            dcc.Store(id="notif-copy-store", data={}),
            dmc.Paper(
                dmc.Group(
                    [
                        html.Div(
                            dmc.TextInput(
                                id="notif-search",
                                placeholder="Tìm thông báo...",
                                leftSection=DashIconify(icon="lucide:search", width=16),
                                debounce=500,
                                size="sm",
                            ),
                            className="notif-search-wrap",
                        ),
                        dmc.Select(
                            id="notif-type-filter",
                            data=type_options,
                            value="",
                            size="sm",
                            w=220,
                            **{"aria-label": "Lọc loại sự kiện"},
                        ),
                        dmc.Select(
                            id="notif-read-filter",
                            data=READ_OPTIONS,
                            value="all",
                            size="sm",
                            w=130,
                            **{"aria-label": "Lọc đã đọc"},
                        ),
                        dmc.Select(
                            id="notif-time-filter",
                            data=TIME_OPTIONS,
                            value="7d",
                            size="sm",
                            w=150,
                            **{"aria-label": "Lọc thời gian"},
                        ),
                        dmc.Button(
                            "Làm mới",
                            id="notif-refresh-btn",
                            variant="light",
                            size="sm",
                            leftSection=DashIconify(icon="lucide:refresh-cw", width=16),
                        ),
                    ],
                    gap="sm",
                    align="center",
                ),
                withBorder=True,
                p="sm",
                radius="md",
            ),
            html.Div(
                [
                    dmc.Paper(
                        [
                            dmc.Group(
                                [
                                    dmc.Title("Thông báo", order=5, size=16, fw=600),
                                    dmc.Badge(
                                        f"{unread} chưa đọc",
                                        id="notif-list-unread-badge",
                                        color="red",
                                        variant="filled",
                                        size="sm",
                                    ),
                                ],
                                gap="sm",
                                align="center",
                                p="sm",
                            ),
                            dmc.ScrollArea(
                                html.Div(id="notif-list-container", children=children),
                                className="notif-scroll",
                            ),
                        ],
                        withBorder=True,
                        radius="md",
                        className="notif-list",
                    ),
                    dmc.Paper(
                        dmc.ScrollArea(
                            html.Div(id="notif-detail-container", children=_detail_panel(ctx, selected)),
                            className="notif-detail-scroll",
                        ),
                        withBorder=True,
                        radius="md",
                        bg="var(--surface-2)",
                        w="var(--size-detail-panel)",
                        className="notif-detail",
                    ),
                ],
                className="notif-main",
            ),
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Text(footer, id="notif-footer-summary", size="sm", c="dimmed"),
                            dmc.Text(updated, id="notif-footer-updated", size="sm", c="dimmed"),
                        ],
                        gap="md",
                    ),
                    dmc.Pagination(id="notif-pagination", total=max_page, value=1, size="sm"),
                ],
                justify="space-between",
                align="center",
            ),
            html.Div(id="notif-list-toast"),
            html.Div(id="notif-copy-sink", hidden=True),
            dmc.Modal(
                title="Cài đặt thông báo",
                id="notif-settings-modal",
                size="lg",
                opened=False,
                children=_prefs_modal_body(ctx),
            ),
            modal_confirm(
                "notif-delete-modal",
                "Xóa thông báo",
                "Thông báo đang chọn sẽ bị xóa vĩnh viễn và không thể khôi phục.",
                confirm_label="Xóa",
            ),
        ],
        className="notif-page",
        p="md",
    )


@callback(
    Output("notif-filter-store", "data"),
    Output("notif-page-store", "data", allow_duplicate=True),
    Input("notif-search", "value"),
    Input("notif-type-filter", "value"),
    Input("notif-read-filter", "value"),
    Input("notif-time-filter", "value"),
    State("notif-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_notif_filters(
    q: str | None,
    event_type: str | None,
    read: str | None,
    time_range: str | None,
    current: Any,
) -> tuple[dict[str, str], dict[str, int]]:
    """Đổi bộ lọc -> lưu filter store + về trang 1."""
    new = {
        "q": q or "",
        "event_type": event_type or "",
        "read": read or "all",
        "time_range": time_range or "7d",
    }
    if isinstance(current, dict) and all(current.get(k) == v for k, v in new.items()):
        raise PreventUpdate
    return new, {"page": 1}


@callback(
    Output("notif-list-container", "children"),
    Output("notif-footer-summary", "children"),
    Output("notif-footer-updated", "children"),
    Output("notif-list-unread-badge", "children"),
    Output("notif-pagination", "max_value"),
    Output("notif-page-store", "data", allow_duplicate=True),
    Output("notif-list-toast", "children"),
    Output("app-location", "href", allow_duplicate=True),
    Output("notif-detail-container", "children"),
    Output("notif-selected-store", "data"),
    Output("app-notif-indicator", "label", allow_duplicate=True),
    Output("app-notif-indicator", "disabled", allow_duplicate=True),
    Input("notif-page-store", "data"),
    Input("notif-filter-store", "data"),
    Input("notif-refresh-btn", "n_clicks"),
    Input("notif-mark-all-read-btn", "n_clicks"),
    Input({"type": "notif-row", "index": ALL}, "n_clicks"),
    Input("notif-detail-open-btn", "n_clicks"),
    Input("notif-delete-modal-confirm", "n_clicks"),
    State("notif-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_notif_list_actions(
    page_data: Any,
    filter_data: Any,
    _refresh_clicks: int | None,
    _mark_all_clicks: int | None,
    _row_clicks: list[int | None] | None,
    _open_clicks: int | None,
    _delete_confirm_clicks: int | None,
    selected_data: Any,
) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any, Any, Any, Any, Any]:
    """1 callback cho mọi hành động trên danh sách (mẫu task 66).

    Đổi trang / đổi lọc / Làm mới / Đánh dấu tất cả đã đọc /
    bấm dòng (chỉ chọn, vẽ panel) / nút "Mở kết quả" trong panel
    (đánh dấu đã đọc rồi mới điều hướng, mẫu D18 task 78) /
    xác nhận xóa trong modal (xóa dòng đang chọn, bỏ chọn).
    """
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered is None:
        raise PreventUpdate
    page = 1
    if isinstance(page_data, dict):
        try:
            page = max(1, int(page_data.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
    filters = _filters_from(filter_data)
    selected: int | None = None
    if isinstance(selected_data, dict):
        raw_id = selected_data.get("id")
        try:
            selected = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            selected = None
    toast: Any = dash.no_update
    href: Any = dash.no_update
    store_out: Any = dash.no_update
    if isinstance(triggered, dict):
        if not any(c for c in (_row_clicks or []) if c):
            raise PreventUpdate
        try:
            selected = int(triggered["index"])
        except (TypeError, ValueError):
            raise PreventUpdate from None
    elif triggered == "notif-mark-all-read-btn":
        if not _mark_all_clicks:
            raise PreventUpdate
        res = mark_all_read(ctx)
        toast = (
            notify_success("Đã đánh dấu tất cả là đã đọc.")
            if res.ok
            else notify_error(res.message or "Không đánh dấu được.")
        )
    elif triggered == "notif-detail-open-btn":
        if not _open_clicks:
            raise PreventUpdate
        if selected is None:
            raise PreventUpdate
        mark_read(ctx, selected)
        detail = get_notification_detail(ctx, selected)
        if detail.ok and isinstance(detail.data, dict) and detail.data.get("link"):
            href = str(detail.data["link"])
    elif triggered == "notif-delete-modal-confirm":
        if not _delete_confirm_clicks:
            raise PreventUpdate
        if selected is None:
            raise PreventUpdate
        res = delete_notification(ctx, selected)
        toast = notify_success("Đã xóa thông báo.") if res.ok else notify_error(res.message or "Không xóa được.")
        selected = None
    elif triggered in ("notif-refresh-btn", "notif-page-store", "notif-filter-store"):
        if triggered == "notif-refresh-btn" and not _refresh_clicks:
            raise PreventUpdate
    else:
        raise PreventUpdate
    children, footer, updated, max_page, total, unread, selected = _list_body(ctx, page, filters, selected)
    # Trang hiện tại rỗng (vd xóa mục cuối): lùi về trang còn dữ liệu.
    if page > max_page:
        page = max_page
        children, footer, updated, max_page, total, unread, selected = _list_body(ctx, page, filters, selected)
        store_out = {"page": page}
    detail_nodes = _detail_panel(ctx, selected)
    # Đồng bộ badge chuông ở header ngay (như bấm mục trong popover) —
    # không chờ tick Interval 60s.
    bell_label = str(unread) if unread > 0 else ""
    bell_disabled = unread == 0
    return (
        children,
        footer,
        updated,
        f"{unread} chưa đọc",
        max_page,
        store_out,
        toast,
        href,
        detail_nodes,
        {"id": selected},
        bell_label,
        bell_disabled,
    )


@callback(
    Output("notif-delete-modal", "opened"),
    Input("notif-detail-delete-btn", "n_clicks"),
    Input("notif-delete-modal-cancel", "n_clicks"),
    Input("notif-delete-modal-confirm", "n_clicks"),
    prevent_initial_call=True,
)
def handle_notif_delete_modal(
    _delete_clicks: int | None, _cancel_clicks: int | None, _confirm_clicks: int | None
) -> bool:
    """Mở modal xác nhận xóa (nút Xóa); Hủy/Xác nhận đều đóng modal
    (xác nhận xóa chạy ở callback danh sách).

    Guard `_delete_clicks`: nút Xóa nằm trong panel chi tiết, bị
    vẽ lại (remount) mỗi lần danh sách đổi — Dash bắn callback với
    n_clicks=None và triggered_id là nút Xóa; không guard thì modal
    tự mở sau mỗi lần lọc/phân trang (hồi quy live).
    """
    triggered = dash.callback_context.triggered_id
    if triggered == "notif-detail-delete-btn" and _delete_clicks:
        return True
    if triggered in ("notif-delete-modal-cancel", "notif-delete-modal-confirm"):
        return False
    raise PreventUpdate


@callback(
    Output("notif-page-store", "data"),
    Input("notif-pagination", "value"),
    State("notif-page-store", "data"),
    prevent_initial_call=True,
)
def handle_notif_pagination(value: Any, page_data: Any) -> Any:
    """Đổi trang qua Pagination (footer ngoài vùng vẽ lại — mẫu task 60)."""
    if value is None:
        raise PreventUpdate
    try:
        new_page = max(1, int(value))
    except (TypeError, ValueError):
        raise PreventUpdate from None
    current = 1
    if isinstance(page_data, dict):
        try:
            current = max(1, int(page_data.get("page") or 1))
        except (TypeError, ValueError):
            current = 1
    if new_page == current:
        raise PreventUpdate
    return {"page": new_page}


@callback(
    Output("notif-settings-modal", "opened"),
    Output("notif-settings-modal", "children"),
    Input("notif-settings-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_notif_settings_open(_n_clicks: int | None) -> tuple[bool, Any]:
    """Mở modal cài đặt: vẽ lại từ pref đã lưu."""
    if not _n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    return True, _prefs_modal_body(ctx)


@callback(
    Output("notif-settings-alert", "children"),
    Output("notif-settings-modal", "opened", allow_duplicate=True),
    Output("notif-settings-modal", "children", allow_duplicate=True),
    Output("notif-list-toast", "children", allow_duplicate=True),
    Input("notif-settings-save-btn", "n_clicks"),
    State("notif-master-switch", "checked"),
    State({"type": "notif-pref-switch", "index": ALL}, "checked"),
    prevent_initial_call=True,
)
def handle_notif_settings_save(
    _n_clicks: int | None,
    master_checked: bool | None,
    _checked: list[bool | None] | None,
) -> tuple[Any, bool, Any, Any]:
    """Lưu cài đặt (công tắc tổng + từng loại) rồi đóng modal."""
    if not _n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    prefs: dict[str, bool] = {}
    states = dash.callback_context.states_list or []
    for group in states:
        entries = group if isinstance(group, list) else [group]
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("id"), dict):
                code = str(entry["id"].get("index") or "")
                if code in EVENT_TYPES:
                    prefs[code] = bool(entry.get("value"))
    if not prefs and master_checked is None:
        return alert_box("Không có cài đặt nào để lưu.", tone="warn"), False, dash.no_update, dash.no_update
    res = set_prefs(ctx, prefs, master=bool(master_checked) if master_checked is not None else None)
    if not res.ok:
        return (
            alert_box(res.message or "Không lưu được cài đặt.", tone="crit"),
            True,
            dash.no_update,
            dash.no_update,
        )
    return (
        dash.no_update,
        False,
        _prefs_modal_body(ctx),
        notify_success("Đã lưu cài đặt thông báo."),
    )


@callback(
    Output("notif-settings-modal", "opened", allow_duplicate=True),
    Input("notif-settings-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_notif_settings_cancel(_n_clicks: int | None) -> bool:
    """Hủy: đóng modal, không lưu."""
    if not _n_clicks:
        raise PreventUpdate
    return False


@callback(
    Output("notif-copy-store", "data"),
    Output("notif-list-toast", "children", allow_duplicate=True),
    Input("notif-detail-copy-btn", "n_clicks"),
    State("notif-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_notif_copy(_n_clicks: int | None, selected_data: Any) -> tuple[Any, Any]:
    """Bấm sao chép mã: ghi mã vào copy-store (clientside ghi clipboard)."""
    if not _n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    selected: int | None = None
    if isinstance(selected_data, dict):
        raw_id = selected_data.get("id")
        try:
            selected = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            selected = None
    if selected is None:
        raise PreventUpdate
    detail = get_notification_detail(ctx, selected)
    code = str(detail.data.get("code")) if detail.ok and isinstance(detail.data, dict) else ""
    if not code:
        raise PreventUpdate
    return {"text": code}, notify_success(f"Đã sao chép mã {code}.")


# Sao chép mã run: clientside ghi clipboard khi copy-store đổi (theo mẫu
# data_model.py; dùng dcc.Clipboard sẽ log cảnh báo React defaultProps
# của FontAwesomeIcon vào console nên không dùng ở đây — D13 sửa đổi).
clientside_callback(
    """
    function(copyData) {
        if (copyData && copyData.text && navigator.clipboard) {
            navigator.clipboard.writeText(copyData.text).catch(function() {});
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("notif-copy-sink", "children"),
    Input("notif-copy-store", "data"),
    prevent_initial_call=True,
)
