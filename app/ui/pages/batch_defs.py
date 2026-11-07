"""Màn danh sách Bộ đối soát — Bước 8 task 18 (Screen13).

Danh sách bộ đối soát (/batches): tìm kiếm, lọc trạng thái, tạo bộ mới,
kích hoạt/lưu trữ.
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
    create_batch_def,
    list_batch_defs,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
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
    {"label": "Nháp", "value": "DRAFT"},
    {"label": "Đang hoạt động", "value": "ACTIVE"},
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
            [dmc.Skeleton(height=48, radius="md") for _ in range(5)],
            gap="sm",
        )
    if error:
        return alert_box(
            title="Không thể tải danh sách bộ đối soát",
            message=error,
            tone="crit",
            action=button_danger("Thử lại", id="bdef-retry-btn", size="xs"),
        )
    if items is None or len(items) == 0:
        return empty_state(
            title="Chưa có bộ đối soát nào",
            description="Tạo bộ đối soát để khai báo một lần nhóm template chạy chung mỗi kỳ.",
            action=(
                button_primary("Tạo bộ đối soát", icon="lucide:plus", id="bdef-empty-create-btn") if can_write else None
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
                "Mở",
                id={"type": "bdef-action-open", "index": def_id},
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
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(str(it.get("code", "")), className="rh-code", fw=700, size="sm"),
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
                    dmc.TableTd(status_chip(status), style={"verticalAlign": "middle"}),
                    dmc.TableTd(
                        dmc.Text(str(it.get("cnt_items", 0)), size="sm"),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(str(it.get("max_parallel_per_ds", 2)), size="sm"),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Anchor(
                                    button_subtle("Mở", icon="lucide:edit-3", size="xs"),
                                    href=f"/batches/{def_id}",
                                    underline=False,
                                ),
                                dmc.Menu(
                                    [
                                        dmc.MenuTarget(
                                            dmc.ActionIcon(
                                                DashIconify(icon="lucide:more-vertical", width=16),
                                                variant="subtle",
                                                color="gray",
                                                size="sm",
                                            )
                                        ),
                                        dmc.MenuDropdown(menu_items),
                                    ],
                                    position="bottom-start",
                                    withArrow=True,
                                ),
                            ],
                            gap="xs",
                            style={"flexWrap": "nowrap"},
                        ),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                ]
            )
        )

    th_base: dict[str, Any] = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--p2, #FAFAFA)",
        "zIndex": 1,
        "height": "34px",
        "fontSize": "12px",
        "fontWeight": 600,
        "borderBottom": "1px solid var(--line, #E0E0E0)",
        "whiteSpace": "nowrap",
    }

    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=800,
            style={"flex": 1, "minHeight": 0, "overflow": "auto"},
            children=dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Mã", style={**th_base, "minWidth": "160px"}),
                                dmc.TableTh("Tên", style={**th_base, "minWidth": "220px"}),
                                dmc.TableTh("Trạng thái", style={**th_base, "minWidth": "120px"}),
                                dmc.TableTh("Số mục", style={**th_base, "minWidth": "90px"}),
                                dmc.TableTh("Song song/DS", style={**th_base, "minWidth": "110px"}),
                                dmc.TableTh("Thao tác", style={**th_base, "minWidth": "160px", "textAlign": "right"}),
                            ]
                        )
                    ),
                    dmc.TableTbody(rows),
                ],
                striped=False,
                highlightOnHover=True,
                verticalSpacing=4,
                style={"fontSize": "13px"},
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
            "backgroundColor": "var(--p, #FFFFFF)",
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

    header_actions = [
        dmc.ActionIcon(
            DashIconify(icon="lucide:refresh-cw", width=16),
            id="bdef-refresh-btn",
            variant="subtle",
            color="gray",
            size="md",
        ),
    ]
    if can_write:
        header_actions.append(button_primary("Tạo bộ đối soát", icon="lucide:plus", id="bdef-create-btn", size="xs"))

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
        )
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
            html.Div(id="bdef-alert"),
            html.Div(
                id="bdef-content",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
                    dmc.Modal(
                        id="bdef-create-modal",
                        title="Tạo bộ đối soát",
                        opened=False,
                        centered=True,
                        children=[
                            dmc.Stack(
                                [
                                    dmc.TextInput(
                                        id="bdef-create-code",
                                        label="Mã bộ",
                                        placeholder="VD: DOANH_THU_CUOI_THANG",
                                        description="Chữ hoa, số và dấu gạch dưới, bắt đầu bằng chữ hoa.",
                                        required=True,
                                    ),
                                    dmc.TextInput(
                                        id="bdef-create-name",
                                        label="Tên bộ",
                                        placeholder="VD: Doanh thu cuối tháng",
                                        required=True,
                                    ),
                                    dmc.Textarea(
                                        id="bdef-create-desc",
                                        label="Mô tả",
                                        placeholder="Mô tả ngắn về bộ đối soát",
                                        autosize=True,
                                        minRows=2,
                                    ),
                                    dmc.NumberInput(
                                        id="bdef-create-max-parallel",
                                        label="Số run song song mỗi Data Source",
                                        value=2,
                                        min=1,
                                        max=4,
                                        step=1,
                                    ),
                                    html.Div(id="bdef-create-error"),
                                    dmc.Group(
                                        [
                                            button_subtle("Hủy", id="bdef-create-cancel"),
                                            button_primary("Tạo bộ", id="bdef-create-submit"),
                                        ],
                                        justify="flex-end",
                                        gap="sm",
                                    ),
                                ],
                                gap="sm",
                            )
                        ],
                    ),
            modal_confirm(
                id="bdef-archive-modal",
                title="Lưu trữ bộ đối soát",
                description="Bộ đối soát đã lưu trữ không thể tạo lần chạy mới. Các lần chạy cũ vẫn xem được.",
                confirm_label="Lưu trữ",
            ),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "8px",
        },
    )


@callback(
    Output("bdef-content", "children"),
    Output("bdef-alert", "children"),
    Input("bdef-store-list", "data"),
    Input("bdef-filter-search", "value"),
    Input("bdef-filter-status", "value"),
)
def _render_list(store_data: Any, search: str | None, status: str | None) -> tuple[Any, Any]:
    ctx = get_current_ctx()
    if store_data is None:
        return render_batch_defs_content(None, loading=True), None
    if isinstance(store_data, dict) and store_data.get("error"):
        return render_batch_defs_content(None, error=str(store_data["error"])), None
    return (
        render_batch_defs_content(
            store_data,
            search_term=search or "",
            status_filter=status or "",
            can_write=_can_write(ctx),
        ),
        None,
    )


@callback(
    Output("bdef-store-list", "data"),
    Input("bdef-refresh-btn", "n_clicks"),
    Input("bdef-retry-btn", "n_clicks"),
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
    Output("bdef-create-modal", "opened"),
    Input("bdef-create-btn", "n_clicks"),
    Input("bdef-empty-create-btn", "n_clicks"),
    Input("bdef-create-cancel", "n_clicks"),
    State("bdef-create-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_create_modal(_open: Any, _open_empty: Any, _cancel: Any, opened: bool) -> bool:
    return not opened


@callback(
    Output("bdef-create-error", "children"),
    Output("bdef-redirect", "href"),
    Output("bdef-create-modal", "opened", allow_duplicate=True),
    Input("bdef-create-submit", "n_clicks"),
    State("bdef-create-code", "value"),
    State("bdef-create-name", "value"),
    State("bdef-create-desc", "value"),
    State("bdef-create-max-parallel", "value"),
    prevent_initial_call=True,
)
def _submit_create(
    _n: Any, code: str | None, name: str | None, desc: str | None, max_parallel: Any
) -> tuple[Any, Any, bool]:
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập.", tone="crit"), dash.no_update, True
    res = create_batch_def(
        ctx,
        {
            "code": (code or "").strip(),
            "name": (name or "").strip(),
            "description": (desc or "").strip() or None,
            "max_parallel_per_ds": int(max_parallel or 2),
        },
    )
    if not res.ok:
        return alert_box(res.message or "Không tạo được bộ đối soát.", tone="crit"), dash.no_update, True
    data = res.data or {}
    return None, f"/batches/{data.get('id')}", False


@callback(
    Output("bdef-archive-modal", "opened"),
    Output("bdef-action-target", "data"),
    Input({"type": "bdef-action-archive", "index": ALL}, "n_clicks"),
    Input({"type": "bdef-action-activate", "index": ALL}, "n_clicks"),
    Input("bdef-archive-modal-cancel", "n_clicks"),
    State("bdef-archive-modal", "opened"),
    prevent_initial_call=True,
)
def _open_action_modal(archive_clicks: Any, activate_clicks: Any, _cancel: Any, opened: bool) -> tuple[bool, Any]:
    triggered = dash.callback_context.triggered_id
    if triggered is None or _cancel:
        return False, dash.no_update
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-archive":
        return True, {"action": "archive", "id": triggered["index"]}
    return False, dash.no_update


@callback(
    Output("bdef-store-list", "data", allow_duplicate=True),
    Output("bdef-alert", "children", allow_duplicate=True),
    Output("bdef-archive-modal", "opened", allow_duplicate=True),
    Input("bdef-archive-modal-confirm", "n_clicks"),
    Input({"type": "bdef-action-activate", "index": ALL}, "n_clicks"),
    State("bdef-action-target", "data"),
    prevent_initial_call=True,
)
def _run_list_action(_confirm: Any, _activate: Any, target: Any) -> tuple[Any, Any, bool]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, alert_box("Bạn cần đăng nhập.", tone="crit"), False
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-action-activate":
        def_id = int(triggered["index"])
        res = activate_batch_def(ctx, def_id)
        if not res.ok:
            return dash.no_update, alert_box(res.message or "Không kích hoạt được bộ.", tone="crit"), False
        return _load_list(None, None), None, False
    if target and target.get("action") == "archive":
        res = archive_batch_def(ctx, int(target["id"]))
        if not res.ok:
            return dash.no_update, alert_box(res.message or "Không lưu trữ được bộ.", tone="crit"), False
        return _load_list(None, None), None, False
    return dash.no_update, None, False
