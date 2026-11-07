"""Màn danh sách Bộ đối soát — Bước 8 task 18 (Screen13).

Danh sách bộ đối soát (/batches): tìm kiếm, lọc trạng thái, tạo bộ mới,
kích hoạt/lưu trữ theo phong cách Fluent Compact + Master–Detail.
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Role
from app.core.session import get_current_ctx
from app.services.batch_def import (
    activate_batch_def,
    archive_batch_def,
    delete_batch_def,
    list_batch_defs,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/batches",
        title="Bộ đối soát — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "batch_def"
STATUS_OPTIONS = [
    {"label": "Tất cả trạng thái", "value": ""},
    {"label": "Hoạt động", "value": "ACTIVE"},
    {"label": "Bản nháp", "value": "DRAFT"},
    {"label": "Đã lưu trữ", "value": "ARCHIVED"},
]


def _can_write(ctx: Any) -> bool:
    if ctx is None:
        return False
    return Role.ADMIN in ctx.roles or Role.TEMPLATE_OWNER in ctx.roles


def render_batch_defs_content(
    items: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
    search_term: str = "",
    status_filter: str = "",
    can_write: bool = False,
) -> Any:
    """Hàm thuần dựng nội dung danh sách bộ đối soát."""
    if loading:
        return dmc.Stack(
            [dmc.Skeleton(height=40, radius="sm") for _ in range(5)],
            gap="xs",
        )
    if error:
        return alert_box(
            title="Không thể tải danh sách bộ đối soát",
            message=error,
            tone="crit",
            action=button_danger("Thử lại", id={"type": "bdef-retry-btn", "index": 0}, size="xs"),
        )
    if items is None or len(items) == 0:
        return empty_state(
            title="Chưa có bộ đối soát nào",
            description="Tạo bộ đối soát để khai báo một lần nhóm template chạy chung mỗi kỳ: mẫu tên file, gộp file, tham số ghi đè.",
            action=(
                dmc.Anchor(
                    button_primary("Tạo bộ đối soát", icon="lucide:plus", id={"type": "bdef-empty-create-btn", "index": 0}, size="xs"),
                    href="/batches/new",
                    underline=False,
                )
                if can_write
                else None
            ),
        )

    filtered = items
    if search_term:
        term = search_term.strip().lower()
        filtered = [
            it for it in filtered if term in str(it.get("code", "")).lower() or term in str(it.get("name", "")).lower()
        ]
    if status_filter:
        filtered = [it for it in filtered if it.get("status") == status_filter]
    if len(filtered) == 0:
        return empty_state(
            title="Không có bộ đối soát khớp bộ lọc",
            description="Hãy thử thay đổi từ khóa tìm kiếm hoặc bỏ bộ lọc trạng thái.",
        )

    rows = []
    for it in filtered:
        def_id = int(it.get("id") or 0)
        status = str(it.get("status", "DRAFT"))
        menu_items: list[Any] = [
            dmc.MenuItem(
                "Mở chi tiết",
                id={"type": "bdef-action-open", "index": def_id},
                href=f"/batches/{def_id}",
                leftSection=DashIconify(icon="lucide:external-link", width=14),
            ),
        ]
        if can_write and status == "DRAFT":
            menu_items.append(
                dmc.MenuItem(
                    "Kích hoạt",
                    id={"type": "bdef-action-activate", "index": def_id},
                    leftSection=DashIconify(icon="lucide:play", width=14),
                )
            )
        if can_write and status != "ARCHIVED":
            menu_items.append(
                dmc.MenuItem(
                    "Lưu trữ",
                    id={"type": "bdef-action-archive", "index": def_id},
                    color="orange",
                    leftSection=DashIconify(icon="lucide:archive", width=14),
                )
            )
        if can_write:
            menu_items.append(
                dmc.MenuItem(
                    "Xóa",
                    id={"type": "bdef-action-delete", "index": def_id},
                    color="red",
                    leftSection=DashIconify(icon="lucide:trash-2", width=14),
                )
            )
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Anchor(
                            dmc.Text(str(it.get("code", "")), className="rh-code", fw=700, size="sm"),
                            href=f"/batches/{def_id}",
                            underline=False,
                        ),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(it.get("name", "")), fw=600, size="sm"),
                                dmc.Text(
                                    str(it.get("description") or ""),
                                    size="xs",
                                    c="dimmed",
                                )
                                if it.get("description")
                                else dmc.Text("", size="xs"),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Group([status_chip(status)], justify="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Text(str(it.get("cnt_items", 0)), size="sm", ta="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Text(str(it.get("max_parallel_per_ds", 2)), size="sm", ta="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Anchor(
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:edit-3", width=14),
                                        variant="subtle",
                                        color="gray",
                                        size="sm",
                                        **{"aria-label": f"Mở {it.get('code')}"},
                                    ),
                                    href=f"/batches/{def_id}",
                                    underline=False,
                                ),
                                dmc.Menu(
                                    [
                                        dmc.MenuTarget(
                                            dmc.ActionIcon(
                                                DashIconify(icon="lucide:more-vertical", width=14),
                                                variant="subtle",
                                                color="gray",
                                                size="sm",
                                                **{"aria-label": "Thao tác khác"},
                                            )
                                        ),
                                        dmc.MenuDropdown(menu_items),
                                    ],
                                    position="bottom-end",
                                    withArrow=True,
                                ),
                            ],
                            gap="xs",
                            justify="center",
                            style={"flexWrap": "nowrap"},
                        ),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle", "textAlign": "center"},
                    ),
                ]
            )
        )

    th_base: dict[str, Any] = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "34px",
        "fontSize": "11px",
        "fontWeight": 600,
        "borderBottom": "1px solid var(--line, #E0E0E0)",
        "whiteSpace": "nowrap",
        "textAlign": "center",
    }

    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=820,
            style={"flex": 1, "minHeight": 0, "overflow": "auto"},
            children=dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Mã", style={**th_base, "minWidth": "160px"}),
                                dmc.TableTh("Tên", style={**th_base, "minWidth": "220px", "textAlign": "left"}),
                                dmc.TableTh("Trạng thái", style={**th_base, "minWidth": "120px"}),
                                dmc.TableTh("Số mục", style={**th_base, "minWidth": "80px"}),
                                dmc.TableTh("Song song/DS", style={**th_base, "minWidth": "100px"}),
                                dmc.TableTh("Thao tác", style={**th_base, "minWidth": "120px"}),
                            ]
                        )
                    ),
                    dmc.TableTbody(rows),
                ],
                striped=False,
                highlightOnHover=True,
                verticalSpacing=4,
                style={"fontSize": "12px"},
            ),
        ),
        withBorder=True,
        radius="sm",
        style={
            "flex": 1,
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "var(--surface, #FFFFFF)",
            "border": "1px solid var(--line, #E0E0E0)",
        },
    )


def layout() -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="bdef-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Bộ đối soát.", tone="crit"),
            ],
            p="md",
        )
    can_write = _can_write(ctx)

    header_actions: list[Any] = [
        dmc.ActionIcon(
            DashIconify(icon="lucide:refresh-cw", width=14),
            id="bdef-refresh-btn",
            variant="subtle",
            color="gray",
            size="sm",
            **{"aria-label": "Làm mới danh sách"},
        ),
    ]
    if can_write:
        header_actions.append(
            dmc.Anchor(
                button_primary("Tạo bộ đối soát", icon="lucide:plus", id="bdef-create-btn", size="xs"),
                href="/batches/new",
                underline=False,
            )
        )

    header_node = page_header(
        title="Bộ đối soát",
        subtitle="Khai báo một lần nhóm template chạy chung mỗi kỳ: mẫu tên file, gộp file, tham số ghi đè.",
        actions=header_actions,
    )

    filters = [
        dmc.Select(
            id="bdef-filter-status",
            data=STATUS_OPTIONS,
            value="",
            w=180,
            size="xs",
            styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
        ),
        html.Span(id="bdef-count-text", style={"fontSize": "11px", "color": "var(--ink-soft, #616161)", "marginLeft": "auto"}),
    ]
    cmd_bar = command_bar(
        search_id="bdef-filter-search",
        search_placeholder="Tìm theo mã hoặc tên bộ...",
        filters=filters,
    )

    return dmc.Box(
        [
            dcc.Store(id="bdef-store-list"),
            dcc.Store(id="bdef-action-target"),
            dcc.Location(id="bdef-redirect", refresh=True),
            header_node,
            cmd_bar,
            html.Div(id="bdef-notifications"),
            html.Div(
                id="bdef-content",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
            modal_confirm(
                id="bdef-archive-modal",
                title="Lưu trữ bộ đối soát",
                description="Bộ đối soát đã lưu trữ không thể tạo lần chạy mới. Các lần chạy cũ vẫn xem được.",
                confirm_label="Lưu trữ",
            ),
            modal_confirm(
                id="bdef-delete-modal",
                title="Xóa bộ đối soát",
                description="Bộ đối soát sẽ bị xóa hoàn toàn khỏi hệ thống (chỉ xóa được khi chưa có lần chạy nào). Thao tác này không thể hoàn tác.",
                confirm_label="Xóa bộ",
                danger=True,
            ),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
            "gap": "6px",
        },
    )


@callback(
    Output("bdef-content", "children"),
    Output("bdef-count-text", "children"),
    Input("bdef-store-list", "data"),
    Input("bdef-filter-search", "value"),
    Input("bdef-filter-status", "value"),
)
def _render_list(store_data: Any, search: str | None, status: str | None) -> tuple[Any, str]:
    ctx = get_current_ctx()
    if store_data is None:
        return render_batch_defs_content(None, loading=True), ""
    if isinstance(store_data, dict) and store_data.get("error"):
        return render_batch_defs_content(None, error=str(store_data["error"])), ""
    items = store_data if isinstance(store_data, list) else []
    filtered = items
    if search:
        term = search.strip().lower()
        filtered = [
            it for it in filtered if term in str(it.get("code", "")).lower() or term in str(it.get("name", "")).lower()
        ]
    if status:
        filtered = [it for it in filtered if it.get("status") == status]
    content = render_batch_defs_content(
        store_data,
        search_term=search or "",
        status_filter=status or "",
        can_write=_can_write(ctx),
    )
    return content, f"{len(filtered)} bộ"


@callback(
    Output("bdef-store-list", "data"),
    Input("bdef-refresh-btn", "n_clicks"),
    Input({"type": "bdef-retry-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=False,
)
def _load_list(_refresh: Any, _retry: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem bộ đối soát."}
    res = list_batch_defs(ctx)
    if not res.ok:
        return {"error": res.message or "Không tải được danh sách."}
    return res.data


@callback(
    Output("bdef-archive-modal", "opened"),
    Output("bdef-delete-modal", "opened"),
    Output("bdef-action-target", "data"),
    Output("bdef-redirect", "href", allow_duplicate=True),
    Input({"type": "bdef-action-archive", "index": ALL}, "n_clicks"),
    Input("bdef-archive-modal-cancel", "n_clicks"),
    Input({"type": "bdef-action-delete", "index": ALL}, "n_clicks"),
    Input("bdef-delete-modal-cancel", "n_clicks"),
    Input({"type": "bdef-action-open", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def _open_action_modal(
    archive_clicks: Any, cancel_arch: Any, delete_clicks: Any, cancel_del: Any, open_clicks: Any
) -> tuple[bool, bool, Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, False, dash.no_update, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered in ("bdef-archive-modal-cancel", "bdef-delete-modal-cancel"):
        return False, False, dash.no_update, dash.no_update
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-open":
        if any(c for c in (open_clicks or []) if c):
            return False, False, dash.no_update, f"/batches/{triggered['index']}"
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-archive":
        if any(c for c in (archive_clicks or []) if c):
            return True, False, {"action": "archive", "id": triggered["index"]}, dash.no_update
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-delete":
        if any(c for c in (delete_clicks or []) if c):
            return False, True, {"action": "delete", "id": triggered["index"]}, dash.no_update
    return False, False, dash.no_update, dash.no_update


@callback(
    Output("bdef-store-list", "data", allow_duplicate=True),
    Output("bdef-notifications", "children"),
    Output("bdef-archive-modal", "opened", allow_duplicate=True),
    Output("bdef-delete-modal", "opened", allow_duplicate=True),
    Input("bdef-archive-modal-confirm", "n_clicks"),
    Input("bdef-delete-modal-confirm", "n_clicks"),
    Input({"type": "bdef-action-activate", "index": ALL}, "n_clicks"),
    State("bdef-action-target", "data"),
    prevent_initial_call=True,
)
def _run_list_action(
    confirm_arch: Any, confirm_del: Any, activate_clicks: Any, target: Any
) -> tuple[Any, Any, bool, bool]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, False, False
    triggered = ctx_dash.triggered_id
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, notify_error("Bạn cần đăng nhập."), False, False
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-activate":
        if not any(c for c in (activate_clicks or []) if c):
            return dash.no_update, dash.no_update, False, False
        def_id = int(triggered["index"])
        res = activate_batch_def(ctx, def_id)
        if not res.ok:
            return dash.no_update, notify_error(res.message or "Không kích hoạt được bộ."), False, False
        return _load_list(None, None), notify_success("Đã kích hoạt bộ đối soát thành công."), False, False
    if triggered == "bdef-archive-modal-confirm" and confirm_arch:
        if target and target.get("action") == "archive":
            res = archive_batch_def(ctx, int(target["id"]))
            if not res.ok:
                return dash.no_update, notify_error(res.message or "Không lưu trữ được bộ."), False, False
            return _load_list(None, None), notify_success("Đã lưu trữ bộ đối soát thành công."), False, False
    if triggered == "bdef-delete-modal-confirm" and confirm_del:
        if target and target.get("action") == "delete":
            res = delete_batch_def(ctx, int(target["id"]))
            if not res.ok:
                return dash.no_update, notify_error(res.message or "Không xóa được bộ đối soát."), False, False
            return _load_list(None, None), notify_success("Đã xóa bộ đối soát thành công."), False, False
    return dash.no_update, dash.no_update, False, False
