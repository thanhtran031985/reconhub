"""Trang Thông báo (task 78) — danh sách lưu DB + cài đặt từng loại sự kiện.

Chuông ở header chỉ hiện 5 mục mới nhất; trang này xem tất cả
(phân trang server-side, mẫu task 60: Pagination ở footer ngoài
vùng vẽ lại), đánh dấu đã đọc / xóa từng mục, đánh dấu tất cả đã
đọc, và bật/tắt từng loại sự kiện theo user.
"""

from __future__ import annotations

import math
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.notification import (
    EVENT_GROUPS,
    EVENT_TYPES,
    delete_notification,
    get_prefs,
    list_notifications,
    mark_all_read,
    mark_read,
    set_prefs,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/notifications", title="Thông báo – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "notifications"
PAGE_SIZE = 20


def _format_dt(iso: str | None) -> str:
    if not iso:
        return ""
    return str(iso)[:16].replace("T", " ")


def _notif_row(item: dict[str, Any]) -> dmc.Paper:
    """1 dòng thông báo: badge loại + tiêu đề (bấm -> link + đã đọc) + hành động."""
    notif_id = int(item["id"])
    is_read = bool(item.get("is_read"))
    title = str(item.get("title") or "")
    link = str(item.get("link") or "")
    title_node: Any = dmc.Text(title, fw=600 if not is_read else 400, size="sm")
    if link:
        # html.A KHÔNG dùng href (cùng lý do panel chuông: href + n_clicks
        # thì click điều hướng ngay, n_clicks mất) — callback tự điều
        # hướng qua app-location.href sau khi đánh dấu đọc. (dmc.Anchor
        # bắt buộc có href nên không dùng được ở đây.)
        title_node = html.A(
            title_node,
            id={"type": "notif-item-open", "index": notif_id},
            style={"cursor": "pointer", "textDecoration": "none"},
        )
    actions: list[Any] = []
    if not is_read:
        actions.append(
            dmc.Button(
                "Đánh dấu đã đọc",
                id={"type": "notif-item-read", "index": notif_id},
                variant="subtle",
                size="xs",
            )
        )
    actions.append(
        dmc.ActionIcon(
            DashIconify(icon="lucide:trash-2", width=16),
            id={"type": "notif-item-delete", "index": notif_id},
            variant="subtle",
            color="gray",
            size="sm",
            **{"aria-label": "Xóa thông báo"},
        )
    )
    return dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Badge(
                        str(item.get("type_label") or ""),
                        variant="light",
                        size="sm",
                    ),
                    title_node,
                    dmc.Text(_format_dt(str(item.get("created_at") or "")), size="xs", c="dimmed"),
                ],
                gap="sm",
                align="center",
            ),
            dmc.Text(str(item.get("message") or ""), size="sm", c="dimmed") if item.get("message") else html.Div(),
            dmc.Group(actions, gap="xs", justify="flex-end"),
        ],
        withBorder=True,
        p="sm",
        radius="md",
        style={"opacity": 1 if not is_read else 0.7},
    )


def _list_body(ctx: Ctx, page: int) -> tuple[list[Any], str, int, str, int]:
    """(children, showing, max_page, unread_summary, total) của 1 trang."""
    res = list_notifications(ctx, page=page, page_size=PAGE_SIZE)
    if not res.ok or not isinstance(res.data, dict):
        return (
            [alert_box(res.message or "Không tải được thông báo.", tone="crit")],
            "",
            1,
            "",
            0,
        )
    items = res.data.get("items") or []
    total = int(res.data.get("total") or 0)
    unread = int(res.data.get("unread") or 0)
    max_page = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
    if not items:
        children: list[Any] = [dmc.Text("Chưa có thông báo.", size="sm", c="dimmed", p="sm")]
    else:
        children = [_notif_row(item) for item in items]
    start = (page - 1) * PAGE_SIZE + 1 if total else 0
    end = min(page * PAGE_SIZE, total)
    showing = f"Hiển thị {start} – {end} trong tổng số {total} thông báo" if total else ""
    summary = f"Có {unread} thông báo chưa đọc." if unread else "Đã đọc hết."
    return children, showing, max_page, summary, total


def _prefs_section(ctx: Ctx) -> dmc.Paper:
    """Khối cài đặt: 1 Switch cho mỗi loại sự kiện (mặc định lỗi BẬT, DONE TẮT)."""
    prefs: dict[str, bool] = {code: bool(info["default"]) for code, info in EVENT_TYPES.items()}
    res = get_prefs(ctx)
    if res.ok and isinstance(res.data, dict):
        saved = res.data.get("prefs") or {}
        for code in prefs:
            if code in saved:
                prefs[code] = bool(saved[code])
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
    return dmc.Paper(
        [
            dmc.Title("Cài đặt thông báo", order=5, size=16, fw=600),
            dmc.Text(
                "Tắt 1 loại thì sự kiện đó không tạo thông báo nữa. Thông báo lỗi mặc định bật; "
                "thông báo đã xong mặc định tắt (tự vào lịch xem).",
                size="sm",
                c="dimmed",
            ),
            dmc.SimpleGrid(cols={"base": 1, "sm": 2, "lg": 3}, spacing="md", children=groups),
            dmc.Group(
                [
                    dmc.Button("Lưu cài đặt", id="notif-prefs-save-btn", size="sm"),
                    html.Div(id="notif-prefs-alert"),
                ],
                gap="sm",
                align="center",
            ),
        ],
        withBorder=True,
        p="md",
        radius="md",
    )


def layout(**kwargs: Any) -> Any:
    """Trang Thông báo: danh sách + phân trang + cài đặt."""
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
    children, showing, max_page, summary, _total = _list_body(ctx, 1)
    return dmc.Box(
        [
            page_header(
                title="Thông báo",
                subtitle="Thông báo về run, báo cáo, export, chạy bộ và sức khỏe hệ thống. Bấm 1 mục để tới nơi liên quan.",
            ),
            dcc.Store(id="notif-page-store", data={"page": 1}),
            dmc.Group(
                [
                    dmc.Text(summary, id="notif-unread-summary", size="sm", fw=500),
                    dmc.Button(
                        "Đánh dấu tất cả đã đọc",
                        id="notif-mark-all-read-btn",
                        variant="light",
                        size="sm",
                    ),
                    dmc.Button("Làm mới", id="notif-refresh-btn", variant="light", size="sm"),
                ],
                gap="sm",
                align="center",
            ),
            html.Div(id="notif-list-toast"),
            html.Div(id="notif-list-container", children=children),
            dmc.Group(
                [
                    dmc.Text(showing, id="notif-showing", size="sm", c="dimmed"),
                    dmc.Pagination(id="notif-pagination", total=max_page, value=1, size="sm"),
                ],
                justify="space-between",
                align="center",
            ),
            _prefs_section(ctx),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "padding": "12px 16px",
            "gap": "10px",
        },
    )


@callback(
    Output("notif-list-container", "children"),
    Output("notif-showing", "children"),
    Output("notif-pagination", "max_value"),
    Output("notif-unread-summary", "children"),
    Output("notif-page-store", "data", allow_duplicate=True),
    Output("notif-list-toast", "children"),
    Output("app-location", "href", allow_duplicate=True),
    Input("notif-page-store", "data"),
    Input("notif-refresh-btn", "n_clicks"),
    Input("notif-mark-all-read-btn", "n_clicks"),
    Input({"type": "notif-item-open", "index": ALL}, "n_clicks"),
    Input({"type": "notif-item-read", "index": ALL}, "n_clicks"),
    Input({"type": "notif-item-delete", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_notif_list_actions(
    page_data: Any,
    _refresh_clicks: int | None,
    _mark_all_clicks: int | None,
    _open_clicks: list[int | None] | None,
    _read_clicks: list[int | None] | None,
    _delete_clicks: list[int | None] | None,
) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    """1 callback cho mọi hành động trên danh sách (mẫu task 66).

    Đổi trang (qua store) / Làm mới / Đánh dấu tất cả đã đọc /
    bấm mục (đánh dấu đọc) / xóa 1 mục.
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
    toast: Any = dash.no_update
    href: Any = dash.no_update
    if isinstance(triggered, dict):
        kind = str(triggered.get("type") or "")
        if not any(c for c in ((_open_clicks or []) + (_read_clicks or []) + (_delete_clicks or [])) if c):
            raise PreventUpdate
        try:
            notif_id = int(triggered["index"])
        except (TypeError, ValueError):
            raise PreventUpdate from None
        if kind == "notif-item-delete":
            res = delete_notification(ctx, notif_id)
            toast = notify_success("Đã xóa thông báo.") if res.ok else notify_error(res.message or "Không xóa được.")
        else:  # notif-item-open / notif-item-read: chỉ đánh dấu đọc, không toast
            mark_read(ctx, notif_id)
            if kind == "notif-item-open":
                # Tìm link của mục vừa bấm (đang ở trang hiện tại) để
                # điều hướng sau khi đã đánh dấu đọc.
                link_res = list_notifications(ctx, page=page, page_size=PAGE_SIZE)
                if link_res.ok and isinstance(link_res.data, dict):
                    for it in link_res.data.get("items") or []:
                        if int(it.get("id") or 0) == notif_id and it.get("link"):
                            href = str(it["link"])
                            break
    elif triggered == "notif-mark-all-read-btn":
        if not _mark_all_clicks:
            raise PreventUpdate
        res = mark_all_read(ctx)
        toast = (
            notify_success("Đã đánh dấu tất cả là đã đọc.")
            if res.ok
            else notify_error(res.message or "Không đánh dấu được.")
        )
    elif triggered == "notif-refresh-btn":
        if not _refresh_clicks:
            raise PreventUpdate
    elif triggered == "notif-page-store":
        pass  # Đổi trang: chỉ vẽ lại.
    else:
        raise PreventUpdate
    children, showing, max_page, summary, _total = _list_body(ctx, page)
    # Xóa mục cuối của trang cuối: lùi về trang còn dữ liệu.
    store_out: Any = dash.no_update
    if page > max_page:
        page = max_page
        children, showing, max_page, summary, _total = _list_body(ctx, page)
        store_out = {"page": page}
    return children, showing, max_page, summary, store_out, toast, href


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
    Output("notif-prefs-alert", "children"),
    Input("notif-prefs-save-btn", "n_clicks"),
    State({"type": "notif-pref-switch", "index": ALL}, "checked"),
    prevent_initial_call=True,
)
def handle_notif_prefs_save(_n_clicks: int | None, _checked: list[bool | None] | None) -> Any:
    """Lưu cài đặt bật/tắt từng loại sự kiện cho user hiện tại."""
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
    if not prefs:
        return alert_box("Không có cài đặt nào để lưu.", tone="warn")
    res = set_prefs(ctx, prefs)
    if not res.ok:
        return alert_box(res.message or "Không lưu được cài đặt.", tone="crit")
    return alert_box("Đã lưu cài đặt thông báo.", tone="ok")
