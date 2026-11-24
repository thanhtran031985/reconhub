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
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

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


def render_tabulator_toolbar() -> Any:
    """Thanh công cụ phong cách Oracle APEX Interactive Grid: Quản lý Template/Saved Views."""
    return dmc.Paper(
        dmc.Group(
            [
                dmc.Group(
                    [
                        DashIconify(icon="lucide:layout-grid", width=16, color="var(--ink-soft)"),
                        dmc.Text("Template/View:", size="xs", fw=600),
                        dmc.Select(
                            id="batches-view-select",
                            data=[{"label": "Mặc định hệ thống", "value": "default"}],
                            value="default",
                            size="xs",
                            w=190,
                            styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                        ),
                        dmc.Button(
                            "Lưu vị trí cột",
                            id="btn-save-view",
                            size="xs",
                            color="blue",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Lưu thành View mới...",
                            id="btn-save-as-view",
                            size="xs",
                            variant="default",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Đặt mặc định",
                            id="btn-set-default",
                            size="xs",
                            variant="subtle",
                            color="gray",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Khôi phục gốc",
                            id="btn-reset-default",
                            size="xs",
                            variant="subtle",
                            color="gray",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                        dmc.Button(
                            "Xóa View",
                            id="btn-delete-view",
                            size="xs",
                            variant="subtle",
                            color="red",
                            style={"height": "28px", "fontSize": "12px"},
                        ),
                    ],
                    gap="xs",
                    align="center",
                ),
                html.Span(
                    id="batches-grid-notification",
                    style={
                        "fontSize": "11px",
                        "color": "#2B8A3E",
                        "fontWeight": "600",
                        "transition": "opacity 0.3s ease",
                        "opacity": "0",
                    },
                ),
            ],
            justify="space-between",
            align="center",
            p="xs",
        ),
        withBorder=True,
        radius="sm",
        mb="xs",
        style={"backgroundColor": "var(--surface-2, #FAFAFA)"},
    )


def render_batch_defs_content(
    items: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
    search_term: str = "",
    status_filter: str = "",
    can_write: bool = False,
) -> Any:
    """Hàm thuần dựng nội dung danh sách bộ đối soát dạng Tabulator Interactive Grid."""
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

    enriched_items = []
    for it in (items or []):
        d = dict(it)
        d["detail_url"] = f"/batches/{it.get('id')}"
        enriched_items.append(d)

    return dmc.Box(
        [
            render_tabulator_toolbar(),
            html.Div(
                id="bdef-tabulator-table",
                style={
                    "flex": 1,
                    "minHeight": "480px",
                    "width": "100%",
                },
            ),
            dcc.Store(id="bdef-tabulator-ready-data", data=enriched_items),
            html.Div(id="bdef-tabulator-dummy-output", style={"display": "none"}),
        ],
        style={
            "flex": 1,
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
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

    return dmc.Box(
        [
            dcc.Store(id="bdef-store-list"),
            dcc.Store(id="bdef-action-target"),
            dcc.Location(id="bdef-redirect", refresh=True),
            header_node,
            html.Div(id="bdef-notifications"),
            html.Div(
                id="bdef-content",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
            dmc.Modal(
                id="bdef-save-view-modal",
                title=dmc.Group(
                    [
                        DashIconify(icon="lucide:layout-grid", width=18, color="var(--primary, #2563EB)"),
                        dmc.Text("Lưu Template / View mới", fw=600, size="sm"),
                    ],
                    gap="xs",
                ),
                children=dmc.Stack(
                    [
                        dmc.TextInput(
                            id="bdef-new-view-name",
                            label="Tên Template / View",
                            placeholder="Nhập tên template (vd: Xem nhanh, Báo cáo cá nhân...)",
                            withAsterisk=True,
                            size="sm",
                        ),
                        dmc.Checkbox(
                            id="bdef-new-view-default",
                            label="Đặt làm giao diện mặc định khi mở trang",
                            size="sm",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="bdef-cancel-save-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Lưu Template",
                                    id="bdef-confirm-save-view-btn",
                                    color="primary",
                                    size="xs",
                                ),
                            ],
                            justify="flex-end",
                            gap="xs",
                            mt="sm",
                        ),
                    ],
                    gap="md",
                ),
                opened=False,
                size="sm",
                centered=True,
            ),
            dmc.Modal(
                id="bdef-delete-view-modal",
                title=dmc.Group(
                    [
                        DashIconify(icon="lucide:trash-2", width=18, color="#DC2626"),
                        dmc.Text("Xóa Template / View", fw=600, size="sm", c="#DC2626"),
                    ],
                    gap="xs",
                ),
                children=dmc.Stack(
                    [
                        dmc.Text(
                            "Bạn có chắc chắn muốn xóa Template / View này? Thao tác này không thể hoàn tác.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="bdef-cancel-delete-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Xóa Template",
                                    id="bdef-confirm-delete-view-btn",
                                    color="red",
                                    size="xs",
                                ),
                            ],
                            justify="flex-end",
                            gap="xs",
                            mt="sm",
                        ),
                    ],
                    gap="md",
                ),
                opened=False,
                size="sm",
                centered=True,
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
                description="Bộ đối soát và các lần chạy của bộ sẽ bị xóa hoàn toàn khỏi hệ thống. "
                "Các lần chạy đối soát đã tạo vẫn còn trong Lịch sử. Thao tác này không thể hoàn tác.",
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
    Input("bdef-store-list", "data"),
)
def _render_list(store_data: Any) -> Any:
    ctx = get_current_ctx()
    if store_data is None:
        return render_batch_defs_content(None, loading=True)
    if isinstance(store_data, dict) and store_data.get("error"):
        return render_batch_defs_content(None, error=str(store_data["error"]))
    items = store_data if isinstance(store_data, list) else []
    return render_batch_defs_content(
        items,
        can_write=_can_write(ctx),
    )


dash.clientside_callback(
    """
    function(data) {
        if (!data || !Array.isArray(data)) return "";
        function mountTabulator() {
            var container = document.getElementById("bdef-tabulator-table");
            if (container && window.batchesTabulator && window.batchesTabulator.init) {
                window.batchesTabulator.init("bdef-tabulator-table", data, true);
            } else {
                setTimeout(mountTabulator, 100);
            }
        }
        setTimeout(mountTabulator, 50);
        return "";
    }
    """,
    Output("bdef-tabulator-dummy-output", "children"),
    Input("bdef-tabulator-ready-data", "data"),
)

dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.batchesTabulator) {
            window.batchesTabulator.saveCurrentView();
        }
        return "";
    }
    """,
    Output("batches-grid-notification", "children", allow_duplicate=True),
    Input("btn-save-view", "n_clicks"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
        return [true, "", false];
    }
    """,
    Output("bdef-save-view-modal", "opened"),
    Output("bdef-new-view-name", "value"),
    Output("bdef-new-view-default", "checked"),
    Input("btn-save-as-view", "n_clicks"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("bdef-save-view-modal", "opened", allow_duplicate=True),
    Input("bdef-cancel-save-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks, name, isDefault) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var vName = (name || "").trim();
        if (!vName) {
            alert("Vui lòng nhập tên cho Template / View.");
            return true;
        }
        if (window.batchesTabulator && window.batchesTabulator.saveNewView) {
            window.batchesTabulator.saveNewView(vName, !!isDefault);
        }
        return false;
    }
    """,
    Output("bdef-save-view-modal", "opened", allow_duplicate=True),
    Input("bdef-confirm-save-view-btn", "n_clicks"),
    State("bdef-new-view-name", "value"),
    State("bdef-new-view-default", "checked"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks, viewId) {
        if (n_clicks && window.batchesTabulator) {
            window.batchesTabulator.setDefaultView(viewId || "default");
        }
        return "";
    }
    """,
    Output("batches-grid-notification", "children", allow_duplicate=True),
    Input("btn-set-default", "n_clicks"),
    State("batches-view-select", "value"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.batchesTabulator) {
            window.batchesTabulator.resetToDefault();
        }
        return "";
    }
    """,
    Output("batches-grid-notification", "children", allow_duplicate=True),
    Input("btn-reset-default", "n_clicks"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.batchesTabulator && window.batchesTabulator.activeViewId) ? window.batchesTabulator.activeViewId : viewId;
        if (!activeId || activeId === "default") {
            if (window.batchesTabulator && window.batchesTabulator.showStatusNotification) {
                window.batchesTabulator.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            }
            return false;
        }
        return true;
    }
    """,
    Output("bdef-delete-view-modal", "opened"),
    Input("btn-delete-view", "n_clicks"),
    State("batches-view-select", "value"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("bdef-delete-view-modal", "opened", allow_duplicate=True),
    Input("bdef-cancel-delete-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.batchesTabulator && window.batchesTabulator.activeViewId) ? window.batchesTabulator.activeViewId : viewId;
        if (window.batchesTabulator && window.batchesTabulator.deleteView) {
            window.batchesTabulator.deleteView(activeId);
        }
        return false;
    }
    """,
    Output("bdef-delete-view-modal", "opened", allow_duplicate=True),
    Input("bdef-confirm-delete-view-btn", "n_clicks"),
    State("batches-view-select", "value"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(viewId) {
        if (viewId && window.batchesTabulator) {
            window.batchesTabulator.applyView(viewId);
        }
        return "";
    }
    """,
    Output("batches-grid-notification", "children", allow_duplicate=True),
    Input("batches-view-select", "value"),
    prevent_initial_call=True,
)


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
            # Task 86: báo rõ số lần chạy của bộ đã bị xóa cùng.
            data = res.data or {}
            n_runs = int(data.get("deleted_runs", 0) or 0)
            if n_runs > 0:
                msg = f"Đã xóa bộ đối soát {data.get('code', '')} cùng {n_runs} lần chạy."
            else:
                msg = "Đã xóa bộ đối soát thành công."
            return _load_list(None, None), notify_success(msg), False, False
    return dash.no_update, dash.no_update, False, False
