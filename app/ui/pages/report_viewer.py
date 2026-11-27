"""Trang Xem báo cáo — task 27 bước 2, prototype Screen16 v-report.

Template dạng tab, form tham số động (grid 12 cột), bảng kết quả
server-side, export background.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, clientside_callback, dcc, html
from dash.exceptions import PreventUpdate

from app.core.session import get_current_ctx
from app.services.perm import is_admin, page_gate
from app.services.report import get_report
from app.services.report_column import get_result_layout
from app.services.report_export import download_export, get_export, request_export
from app.services.report_param import preview_layout
from app.services.report_run import (
    create_report_run,
    execute_report_run,
    get_report_page,
    get_report_run,
    get_run_sql,
)
from app.services.report_studio import list_version_visuals
from app.services.report_template import get_version, list_templates
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.notification import notify_error
from app.ui.components.page_header import page_header
from app.ui.components.report_widgets import (
    _format_cell,
    _lov_options,
    render_param_control,
    render_param_form,
    render_result_grid,
    render_result_table,
)
from app.ui.components.semantic_visuals import render_semantic_visual

__all__ = [
    "_format_cell",
    "_lov_options",
    "render_param_control",
    "render_param_form",
    "render_result_grid",
    "render_result_table",
]

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/reports/<report_id>",
        path="/reports/1",
        title="Xem báo cáo – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_center"
PAGE_SIZE_OPTIONS = [
    # Cỡ trang dùng value chuỗi (Select cũ và SegmentedControl đều chỉ
    # nhận chuỗi; số gây lỗi Mantine ở trình duyệt).
    {"label": "50 dòng/trang", "value": "50"},
    {"label": "100 dòng/trang", "value": "100"},
    {"label": "200 dòng/trang", "value": "200"},
]


# ─── Hàm thuần (test được) ──────────────────────────────────────────────────


# ─── Layout ────────────────────────────────────────────────────────────────


def layout(report_id: str | int | None = 1, **kwargs: Any) -> Any:
    """Layout chính màn hình Xem báo cáo."""
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            [
                dcc.Location(id="viewer-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn cần đăng nhập để xem báo cáo.", tone="crit"),
            ]
        )
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="viewer-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem báo cáo.", tone="crit"),
            ]
        )
    try:
        report_id_int = int(report_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return html.Div(alert_box("Báo cáo không hợp lệ.", tone="crit"))
    report_res = get_report(ctx, report_id_int)
    if not report_res.ok or not isinstance(report_res.data, dict):
        return html.Div(alert_box(report_res.message or "Không tìm thấy báo cáo.", tone="crit"))
    report = report_res.data
    tpl_res = list_templates(ctx, report_id_int)
    templates: list[dict[str, Any]] = tpl_res.data if tpl_res.ok and isinstance(tpl_res.data, list) else []
    active_templates = [t for t in templates if t.get("active_version_id")]
    if not active_templates:
        return html.Div(
            [
                dmc.Stack(
                    [
                        dmc.Title(str(report["name"]), order=1),
                        alert_box(
                            "Chưa có template ACTIVE cho báo cáo này.",
                            "Admin cần kích hoạt một version trước khi xem.",
                            tone="warn",
                        ),
                        dcc.Link("← Danh sách báo cáo", href="/reports"),
                    ],
                    gap="md",
                    p="lg",
                )
            ]
        )
    first = active_templates[0]
    version_res = get_version(ctx, int(first["active_version_id"]))
    version_detail: dict[str, Any] = version_res.data if version_res.ok and isinstance(version_res.data, dict) else {}
    preview_res = preview_layout(ctx, int(first["active_version_id"]))
    preview = preview_res.data if preview_res.ok and isinstance(preview_res.data, dict) else {"rows": []}
    # Task 43: ?rerun_from=<run_id> (từ Lịch sử: Chạy lại) — điền sẵn
    # tham số của run gốc vào form (khớp theo mã tham số ở version ACTIVE
    # hiện tại; mã lạ bỏ qua). Không tự chạy, không nạp kết quả cũ.
    rerun_alert: str | None = None
    rerun_from = kwargs.get("rerun_from")
    if rerun_from is not None:
        try:
            rerun_id = int(str(rerun_from))
        except (TypeError, ValueError):
            rerun_id = None
        if rerun_id is None:
            rerun_alert = "Không tải được tham số của run gốc."
        else:
            run_res = get_report_run(ctx, rerun_id)
            if (
                not run_res.ok
                or not isinstance(run_res.data, dict)
                or int(run_res.data.get("report_id", -1)) != report_id_int
            ):
                rerun_alert = "Không tải được tham số của run gốc."
            else:
                saved = dict(run_res.data.get("params") or {})
                for row in preview.get("rows", []):
                    for entry in row.get("params", []):
                        code = str(entry.get("code"))
                        if code in saved:
                            entry["value"] = saved[code]
    options_by_code: dict[str, list[dict[str, str]]] = {}
    for row in preview.get("rows", []):
        for entry in row.get("params", []):
            if entry.get("control_type") in ("SELECT", "MULTI_SELECT"):
                options_by_code[str(entry["code"])] = _lov_options(ctx, int(first["active_version_id"]), entry)
    # Task 40: tab SQL thực hiện chỉ ADMIN thấy (chặn ở server lúc dựng
    # layout, không chỉ ẩn bằng CSS).
    show_sql = is_admin(ctx)
    # Task 109 Bước 5: báo cáo Studio (SEMANTIC_MODEL) xem đa visual +
    # xuất từng visual; nút Xuất Excel cả báo cáo của luồng cổ điển bị ẩn
    # (không xóa khỏi layout để clientside callback vẫn hợp lệ).
    is_semantic = str(version_detail.get("source_type") or "") == "SEMANTIC_MODEL"
    result_tabs_list: list[Any] = [dmc.TabsTab("Kết quả", value="result")]
    result_panels: list[Any] = [
        dmc.TabsPanel(
            [
                dcc.Loading(
                    id="viewer-loading",
                    type="circle",
                    # style của Loading đi vào lớp phủ spinner; muốn khung
                    # ngoài co giãn theo Paper phải dùng parent_style
                    # (bài học layout /history: nếu không khung cao bằng
                    # nội dung, grid 0px nên không thấy dòng nào).
                    parent_style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
                    children=html.Div(
                        id="viewer-result-container",
                        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
                        children=empty_state(
                            "Nhập tham số và bấm Xem báo cáo.",
                            "Kết quả hiển thị theo từng trang từ máy chủ.",
                        ),
                    ),
                ),
                dmc.Group(
                    [
                        dmc.Pagination(
                            id="viewer-pagination",
                            total=1,
                            value=1,
                            size="xs",
                        ),
                    ],
                    justify="center",
                    mt="xs",
                ),
            ],
            value="result",
            style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
        )
    ]
    if show_sql:
        result_tabs_list.append(dmc.TabsTab("SQL thực hiện", value="sql", id="viewer-sql-tab"))
        result_panels.append(
            dmc.TabsPanel(
                html.Div(
                    id="viewer-sql-container",
                    children=empty_state(
                        "Chưa chạy báo cáo.",
                        "Bấm Xem báo cáo để xem SQL đã thực hiện.",
                    ),
                    style={"paddingTop": "8px", "overflowY": "auto"},
                ),
                value="sql",
                style={"flex": 1, "minHeight": 0, "overflow": "hidden"},
            )
        )
    result_tabs = dmc.Tabs(
        [dmc.TabsList(result_tabs_list), *result_panels],
        id="viewer-result-tabs",
        value="result",
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
    )
    return dmc.Box(
        [
            dcc.Location(id="viewer-location", refresh=False),
            dcc.Store(id="viewer-report-store", data=report),
            dcc.Store(id="viewer-templates-store", data=templates),
            dcc.Store(id="viewer-version-store", data=version_detail),
            dcc.Store(id="viewer-run-store", data={}),
            dcc.Store(id="viewer-page-store", data=1),
            dcc.Store(id="viewer-sort-store", data=[]),
            dcc.Store(id="viewer-export-store", data={}),
            dcc.Store(id="viewer-dark-mode-store", data=False),
            dcc.Download(id="viewer-download"),
            page_header(
                title=str(report["name"]),
                subtitle=str(report.get("description") or ""),
                actions=[
                    dcc.Link(button_subtle("← Danh sách", size="xs"), href="/reports"),
                ],
            ),
            dmc.Tabs(
                [
                    dmc.TabsList(
                        [
                            dmc.TabsTab(
                                t["name"],
                                value=str(t["id"]),
                                id=f"viewer-tab-{t['id']}",
                            )
                            for t in active_templates
                        ]
                    )
                ],
                id="viewer-tabs",
                value=str(first["id"]),
                style={"marginBottom": "4px"},
            ),
            dmc.Paper(
                [
                    dmc.Title("Tham số báo cáo", order=4, size="sm", mb="xs"),
                    html.Div(
                        alert_box(rerun_alert, tone="warn") if rerun_alert else None,
                        id="viewer-rerun-alert",
                    ),
                    html.Div(
                        id="viewer-param-form",
                        children=render_param_form(
                            preview,
                            options_by_code,
                            action=dmc.Button(
                                "Xem báo cáo",
                                id="viewer-run-btn",
                                variant="filled",
                                size="sm",
                            ),
                        ),
                    ),
                    html.Div(
                        id="viewer-run-error",
                        **{"aria-live": "polite"},  # type: ignore[arg-type]
                    ),
                ],
                withBorder=True,
                radius="sm",
                p="xs",
            ),
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Stack(
                                [
                                    dmc.Title("Kết quả", order=4, size="sm"),
                                    dmc.Text(
                                        "Chưa chạy",
                                        id="viewer-result-count",
                                        c="dimmed",
                                        size="xs",
                                        **{"aria-live": "polite"},
                                    ),
                                ],
                                gap=0,
                            ),
                            html.Div(
                                [
                                    dmc.Group(
                                        [
                                            dmc.SegmentedControl(
                                                id="viewer-page-size",
                                                data=PAGE_SIZE_OPTIONS,
                                                value="50",
                                                size="xs",
                                                radius="xl",
                                                **{"aria-label": "Số dòng mỗi trang"},
                                            ),
                                            # Task 70: chế độ xuất dạng Switch thay cho
                                            # Select — tắt = Xuất ngay (mặc định như cũ),
                                            # bật = Chạy ngầm (mẫu switch task 67).
                                            dmc.Switch(
                                                id="viewer-export-mode",
                                                label="Chạy ngầm",
                                                checked=False,
                                                size="xs",
                                                styles={"label": {"fontSize": "11px", "cursor": "pointer"}},
                                                **{"aria-label": "Chế độ xuất Excel"},
                                            ),
                                            dmc.Button(
                                                "Xuất Excel",
                                                id="viewer-export-btn",
                                                variant="filled",
                                                size="xs",
                                            ),
                                        ],
                                        gap="xs",
                                    )
                                ],
                                id="viewer-export-controls",
                                style={"display": "none"} if is_semantic else {},
                            ),
                        ],
                        justify="space-between",
                        align="center",
                        mb="xs",
                    ),
                    html.Div(
                        id="viewer-export-status",
                        style={"marginTop": 4},
                        **{"aria-live": "polite"},  # type: ignore[arg-type]
                    ),
                    result_tabs,
                ],
                withBorder=True,
                radius="sm",
                p="xs",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
            dcc.Interval(
                id="viewer-export-poll",
                interval=2000,
                n_intervals=0,
                disabled=True,
            ),
        ],
        style={
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "8px",
        },
    )


# ─── Callbacks ─────────────────────────────────────────────────────────────


def _values_from_inputs(param_values: list[Any] | None, param_ids: list[dict[str, Any]] | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for val, pid in zip(param_values or [], param_ids or [], strict=False):
        code = str(pid.get("index", ""))
        if code.endswith("__from") or code.endswith("__to"):
            base = code.rsplit("__", 1)[0]
            slot = "from" if code.endswith("__from") else "to"
            if val is not None and val != "":
                values.setdefault(base, {})[slot] = val
            continue
        if isinstance(val, list) and len(val) == 2:
            values[code] = {"from": val[0], "to": val[1]}
        elif val is not None and val != "":
            values[code] = val
    return values


def _total_pages(total: int, page_size: int) -> int:
    return max(1, (int(total) + int(page_size) - 1) // int(page_size))


# Task 40: nút Xem/Xuất sang dạng loading ngay khi bấm (mẫu Loading State
# trong tài liệu DMC Button: clientside đặt loading=True — nút tự disable
# khi loading nên không bấm trùng được; callback chính trả loading=False
# ở cuối mọi đường). Cần allow_duplicate vì callback chính cũng ghi cùng
# prop loading.
clientside_callback(
    """
    function(n_clicks) { return true; }
    """,
    Output("viewer-run-btn", "loading", allow_duplicate=True),
    Input("viewer-run-btn", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) { return true; }
    """,
    Output("viewer-export-btn", "loading", allow_duplicate=True),
    Input("viewer-export-btn", "n_clicks"),
    prevent_initial_call=True,
)


def _run_semantic_report(
    ctx: Any,
    report_id: int,
    template_id: int,
    version_id: int,
    values: dict[str, Any],
) -> tuple[dict[str, Any], int, Any, bool]:
    """Chạy báo cáo Studio: 1 run cho mỗi visual của version ACTIVE.

    Trả (run_store, page, error, loading) khớp handle_run_click. Visual
    lỗi không chặn visual khác — visual đó hiện trạng thái lỗi trên lưới.
    """
    visuals_res = list_version_visuals(ctx, version_id)
    if not visuals_res.ok or not isinstance(visuals_res.data, list):
        return {}, 1, notify_error(visuals_res.message or "Không tải được danh sách visual."), False
    visuals = visuals_res.data
    if not visuals:
        return {}, 1, notify_error("Báo cáo chưa có visual nào."), False
    runs: list[dict[str, Any]] = []
    errors: list[str] = []
    for vis in visuals:
        code = str(vis.get("code") or "")
        created = create_report_run(
            ctx, report_id, template_id=template_id, values=values, visual_id=int(vis["id"])
        )
        if not created.ok or not isinstance(created.data, dict):
            errors.append(f"{code}: {created.message}")
            continue
        run_id = int(created.data["id"])
        executed = execute_report_run(ctx, run_id)
        if not executed.ok or not isinstance(executed.data, dict):
            errors.append(f"{code}: {executed.message}")
            continue
        run = executed.data.get("run") or {}
        entry: dict[str, Any] = {
            "visual_id": int(vis["id"]),
            "visual_code": code,
            "visual_type": str(vis.get("visual_type") or "TABLE"),
            "title": str(vis.get("title") or code),
            "grid_span": int(vis.get("grid_span") or 12),
            "height_size": str(vis.get("height_size") or "M"),
            "run_id": run_id,
            "status": str(run.get("status") or "FAILED"),
            "error": run.get("error_message") or "",
            "total": int(executed.data.get("total") or 0),
            "columns": executed.data.get("columns") or [],
            "rows": executed.data.get("rows") or [],
        }
        runs.append(entry)
        if entry["status"] != "DONE":
            errors.append(f"{code}: {entry['error'] or 'chạy lỗi'}")
    if not runs:
        return {}, 1, notify_error("Chạy báo cáo lỗi: " + "; ".join(errors)), False
    store = {
        "semantic": True,
        "report_id": report_id,
        "template_id": template_id,
        "version_id": version_id,
        "values": values,
        "runs": runs,
    }
    error = notify_error("Một số visual chạy lỗi: " + "; ".join(errors)) if errors else ""
    return store, 1, error, False


@callback(
    Output("viewer-run-store", "data"),
    Output("viewer-page-store", "data"),
    Output("viewer-run-error", "children"),
    Output("viewer-run-btn", "loading"),
    Input("viewer-run-btn", "n_clicks"),
    State("viewer-report-store", "data"),
    State("viewer-tabs", "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "id"),
    State("viewer-version-store", "data"),
    prevent_initial_call=True,
)
def handle_run_click(
    n_clicks: int | None,
    report: dict[str, Any] | int | None,
    template_id: str | None,
    param_values: list[Any] | None,
    param_ids: list[dict[str, Any]] | None,
    version_store: dict[str, Any] | None,
    page_size: int = 50,
) -> tuple[dict[str, Any], int, Any, bool]:
    """Tạo + chạy run đồng bộ (task 25 Q2); render do handle_result_render.

    run-store mang sẵn total/total_pages (từ execute) để đồng bộ pagination
    mà không cần truy vấn thêm. Báo cáo Studio chạy 1 run cho mỗi visual.
    """
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not report or not template_id:
        raise PreventUpdate
    report_id = int(report["id"]) if isinstance(report, dict) else int(report)
    values = _values_from_inputs(param_values, param_ids)
    if isinstance(version_store, dict) and str(version_store.get("source_type") or "") == "SEMANTIC_MODEL":
        return _run_semantic_report(ctx, report_id, int(template_id), int(version_store.get("id") or 0), values)
    created = create_report_run(ctx, report_id, template_id=int(template_id), values=values)
    if not created.ok or not isinstance(created.data, dict):
        return {}, 1, notify_error(created.message or "Không tạo được run."), False
    run_id = int(created.data["id"])
    executed = execute_report_run(ctx, run_id)
    if not executed.ok or not isinstance(executed.data, dict):
        return {}, 1, notify_error(executed.message or "Chạy báo cáo lỗi."), False
    # execute trả ok=True kể cả khi run FAILED (lỗi truy vấn là kết quả
    # nghiệp vụ, task 25): phải kiểm tra status, không render trang lỗi.
    run = executed.data.get("run") or {}
    if run.get("status") != "DONE":
        detail = run.get("error_message") or "Run lỗi, chưa rõ nguyên nhân."
        return {}, 1, notify_error(f"Chạy báo cáo lỗi: {detail}"), False
    total = int(executed.data.get("total") or 0)
    return (
        {
            "run_id": run_id,
            "template_id": int(template_id),
            "report_id": report_id,
            "version_id": int(created.data["version_id"]),
            "total": total,
            "total_pages": _total_pages(total, page_size),
            "values": values,
        },
        1,
        "",
        False,
    )


@callback(
    Output("viewer-param-form", "children"),
    Output("viewer-version-store", "data"),
    Output("viewer-run-store", "data", allow_duplicate=True),
    Output("viewer-page-store", "data", allow_duplicate=True),
    Output("viewer-run-error", "children", allow_duplicate=True),
    Input("viewer-tabs", "value"),
    State("viewer-version-store", "data"),
    State("viewer-templates-store", "data"),
    State("viewer-run-store", "data"),
    prevent_initial_call=True,
)
def handle_viewer_tab_switch_click(
    tab_value: str | None,
    version_store: dict[str, Any] | None,
    templates_store: list[dict[str, Any]] | None,
    run_store: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Task 77: chọn tab template khác -> vẽ lại form tham số + xóa kết quả cũ."""
    form, version_detail, new_run, page, error = handle_viewer_tab_switch(
        tab_value, version_store, templates_store, run_store
    )
    return (
        form if form is not None else dash.no_update,
        version_detail if version_detail is not None else dash.no_update,
        new_run if new_run is not None else dash.no_update,
        page if page is not None else dash.no_update,
        error,
    )


def handle_viewer_tab_switch(
    tab_value: str | int | None,
    version_store: dict[str, Any] | None,
    templates_store: list[dict[str, Any]] | None,
    run_store: dict[str, Any] | None,
) -> tuple[Any, dict[str, Any] | None, dict[str, Any] | None, int | None, Any]:
    """Task 77: chọn tab template khác -> vẽ lại form tham số theo version
    ACTIVE của template đó, xóa kết quả cũ. Không tự chạy báo cáo.

    Trả (form, version_detail, run_store_mới, page, error); None ở một
    slot nghĩa là giữ nguyên (callback map sang dash.no_update).
    """
    if tab_value is None or str(tab_value) == "":
        raise PreventUpdate
    try:
        template_id = int(str(tab_value))
    except (TypeError, ValueError):
        raise PreventUpdate from None
    current_id: int | None = None
    if isinstance(version_store, dict):
        try:
            current_id = int(version_store.get("template_id") or 0) or None
        except (TypeError, ValueError):
            current_id = None
    if current_id is not None and template_id == current_id:
        raise PreventUpdate
    target: dict[str, Any] | None = None
    for t in templates_store or []:
        if isinstance(t, dict) and int(t.get("id") or 0) == template_id:
            target = t
            break
    if target is None:
        raise PreventUpdate
    active_version_id = target.get("active_version_id")
    if not active_version_id:
        return (
            None,
            None,
            None,
            None,
            notify_error(f"Template {target.get('code') or template_id} chưa có version ACTIVE."),
        )
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    version_res = get_version(ctx, int(active_version_id))
    if not version_res.ok or not isinstance(version_res.data, dict):
        return None, None, None, None, notify_error(version_res.message or "Không tải được version.")
    version_detail = version_res.data
    preview_res = preview_layout(ctx, int(active_version_id))
    if not preview_res.ok or not isinstance(preview_res.data, dict):
        return None, None, None, None, notify_error(preview_res.message or "Không tải được form tham số.")
    preview = preview_res.data
    options_by_code: dict[str, list[dict[str, str]]] = {}
    for row in preview.get("rows", []):
        for entry in row.get("params", []):
            if entry.get("control_type") in ("SELECT", "MULTI_SELECT"):
                options_by_code[str(entry["code"])] = _lov_options(ctx, int(active_version_id), entry)
    form = render_param_form(
        preview,
        options_by_code,
        action=dmc.Button(
            "Xem báo cáo",
            id="viewer-run-btn",
            variant="filled",
            size="sm",
        ),
    )
    return form, version_detail, {}, 1, ""


@callback(
    Output("viewer-page-store", "data", allow_duplicate=True),
    Input("viewer-pagination", "value"),
    State("viewer-run-store", "data"),
    prevent_initial_call=True,
)
def handle_page_change(page_no: int | None, run_store: dict[str, Any] | None) -> int:
    """Chuyển trang kết quả (server-side, T27-06)."""
    if not page_no or not run_store or not run_store.get("run_id"):
        raise PreventUpdate
    if run_store.get("semantic"):
        raise PreventUpdate
    return int(page_no)


@callback(
    Output("viewer-sort-store", "data"),
    Output("viewer-page-store", "data", allow_duplicate=True),
    Input("viewer-result-grid", "columnState"),
    State("viewer-sort-store", "data"),
    prevent_initial_call=True,
)
def handle_grid_sort_change(
    column_state: list[dict[str, Any]] | None,
    sorts: list[dict[str, str]] | None,
) -> tuple[list[dict[str, str]], int]:
    """Sort từ header AG Grid (server-side): columnState → sort-store.

    Grid tự sort client-side trong trang hiện tại khi bấm header; callback
    này dịch thành sorts rồi refetch từ server nên kết quả cuối luôn đúng
    toàn cục. Không đổi → PreventUpdate (tránh vòng lặp khi resize cột
    cũng làm columnState đổi).
    """
    if not column_state:
        raise PreventUpdate
    new_sorts: list[dict[str, str]] = []
    for entry in column_state:
        if not isinstance(entry, dict):
            continue
        direction = str(entry.get("sort") or "").upper()
        if direction in ("ASC", "DESC"):
            new_sorts.append({"field": str(entry.get("colId", "")).upper(), "direction": direction})
    new_sorts = new_sorts[:1]  # single-sort (suppressMultiSort)
    if new_sorts == list(sorts or []):
        raise PreventUpdate
    return new_sorts, 1


def _render_semantic_results(run_store: dict[str, Any] | None, dark_mode: bool | None) -> tuple[Any, str]:
    """Lưới 12 cột đa visual cho báo cáo Studio + nút xuất từng visual."""
    runs = (run_store or {}).get("runs") or []
    if not runs:
        return (
            empty_state(
                "Nhập tham số và bấm Xem báo cáo.",
                "Mỗi visual chạy 1 lần và hiển thị trên lưới 12 cột.",
            ),
            "Chưa chạy",
        )
    cards: list[Any] = []
    for entry in runs:
        code = str(entry.get("visual_code") or "")
        visual = {
            "code": code,
            "visual_type": str(entry.get("visual_type") or "TABLE"),
            "title": str(entry.get("title") or code),
            "grid_span": int(entry.get("grid_span") or 12),
            "height_size": str(entry.get("height_size") or "M"),
        }
        if str(entry.get("status") or "") != "DONE":
            body: Any = alert_box(
                f"Visual {code} chạy lỗi.",
                str(entry.get("error") or "Không rõ nguyên nhân."),
                tone="crit",
            )
            export_row: Any = None
            total_text = "Lỗi"
        else:
            rows = entry.get("rows") or []
            total = int(entry.get("total") or 0)
            preview = {
                "columns": entry.get("columns") or [],
                "rows": rows,
                "row_count": len(rows),
                "truncated": total > len(rows),
                "warning_message": None,
            }
            body = render_semantic_visual(
                visual,
                preview,
                state="data" if rows else "empty",
                dark_mode=bool(dark_mode),
            )
            export_row = dmc.Group(
                [
                    dmc.Button(
                        "Xuất XLSX",
                        id={"type": "viewer-visual-export", "code": code, "format": "XLSX"},
                        variant="outline",
                        size="xs",
                        **{"data-visual-code": code, "data-export-format": "XLSX"},
                    ),
                    dmc.Button(
                        "Xuất CSV",
                        id={"type": "viewer-visual-export", "code": code, "format": "CSV"},
                        variant="outline",
                        size="xs",
                        **{"data-visual-code": code, "data-export-format": "CSV"},
                    ),
                ],
                gap="xs",
                mt="xs",
            )
            total_text = f"{total} dòng" + (" (hiển thị 50 dòng đầu)" if total > len(rows) else "")
        cards.append(
            dmc.GridCol(
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                dmc.Text(str(entry.get("title") or code), fw=600, size="sm"),
                                dmc.Text(total_text, c="dimmed", size="xs"),
                            ],
                            justify="space-between",
                        ),
                        body,
                        export_row,
                    ],
                    withBorder=True,
                    radius="sm",
                    p="xs",
                ),
                span=int(entry.get("grid_span") or 12),
            )
        )
    return dmc.Grid(cards, gutter="sm"), f"{len(runs)} visual"


@callback(
    Output("viewer-result-container", "children"),
    Output("viewer-result-count", "children"),
    Input("viewer-run-store", "data"),
    Input("viewer-page-store", "data"),
    Input("viewer-sort-store", "data"),
    Input("viewer-dark-mode-store", "data"),
    State("viewer-page-size", "value"),
    State("viewer-result-container", "children"),
)
def handle_result_render(
    run_store: dict[str, Any] | None,
    page_no: int | None,
    sorts: list[dict[str, str]] | None,
    dark_mode: bool | None,
    page_size: int | None,
    prev_children: Any = None,
) -> tuple[Any, str]:
    """Render kết quả từ run/page/sort hiện tại (một nơi duy nhất).

    Thứ tự tham số khớp thứ tự khai báo của decorator (run-store,
    page-store, sort-store, page-size): trước đây chữ ký là
    (run_store, page_no, page_size, sorts) nên Dash gán nhầm sort-store
    vào page_size và page-size vào sorts — sort trên trình duyệt thật
    không có tác dụng, còn test gọi trực tiếp thì vẫn xanh.

    Lỗi tải trang: giữ dữ liệu cũ + nút Thử lại (tải lại trang, theo mẫu
    lookups.py — nút Thử lại không phải Input của callback).
    """
    if not run_store or not run_store.get("run_id"):
        if run_store and run_store.get("semantic"):
            return _render_semantic_results(run_store, dark_mode)
        return (
            empty_state(
                "Nhập tham số và bấm Xem báo cáo.",
                "Kết quả hiển thị theo từng trang từ máy chủ.",
            ),
            "Chưa chạy",
        )
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    size = int(page_size or 50)
    page = int(page_no or 1)
    res = get_report_page(ctx, int(run_store["run_id"]), page=page, page_size=size, sorts=sorts or [])
    if not res.ok or not isinstance(res.data, dict):
        retry_href = f"/reports/{run_store.get('report_id')}" if run_store.get("report_id") else "/reports"
        error_view = alert_box(
            "Không tải được kết quả.",
            res.message,
            tone="crit",
            action=dmc.Anchor("Thử lại", href=retry_href, size="sm"),
        )
        if prev_children is None:
            return error_view, "Lỗi tải kết quả"
        return html.Div([error_view, prev_children]), "Lỗi tải kết quả"
    data = res.data
    total = int(data.get("total", 0))
    version_id = int(run_store.get("version_id") or 0)
    if not version_id:
        run_res = get_report_run(ctx, int(run_store["run_id"]))
        if run_res.ok and isinstance(run_res.data, dict):
            version_id = int(run_res.data["version_id"])
    layout_res = get_result_layout(ctx, version_id, "web")
    layout = layout_res.data if layout_res.ok and isinstance(layout_res.data, dict) else {"columns": []}
    return (
        render_result_grid(layout, data.get("rows", [])),
        f"{total} dòng",
    )


@callback(
    Output("viewer-pagination", "total"),
    Output("viewer-pagination", "value"),
    Input("viewer-run-store", "data"),
    Input("viewer-page-size", "value"),
    State("viewer-page-store", "data"),
)
def handle_pagination_sync(
    run_store: dict[str, Any] | None,
    page_size: int | None,
    page_no: int | None,
) -> tuple[int, int]:
    """Đồng bộ Pagination từ run-store (total có sẵn, không query).

    Nút Xuất Excel luôn mở (task 39) nên không còn điều khiển disabled ở đây.
    Báo cáo Studio hiển thị 50 dòng đầu mỗi visual, không phân trang chung.
    """
    if run_store and run_store.get("semantic"):
        return 1, 1
    if not run_store or not run_store.get("run_id"):
        return 1, 1
    total = int(run_store.get("total") or 0)
    total_pages = _total_pages(total, int(page_size or 50))
    return total_pages, min(int(page_no or 1), total_pages)


@callback(
    Output("viewer-page-store", "data", allow_duplicate=True),
    Input("viewer-page-size", "value"),
    prevent_initial_call=True,
)
def handle_page_size_change(page_size: int | None) -> int:
    """Đổi số dòng/trang → về trang 1."""
    return 1


@callback(
    Output("viewer-run-store", "data", allow_duplicate=True),
    Output("viewer-page-store", "data", allow_duplicate=True),
    Input("viewer-location", "href"),
    State("viewer-run-store", "data"),
    prevent_initial_call=True,
)
def handle_location_run(href: str | None, run_store: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
    """Mở Viewer với ?run=<id> (từ Lịch sử: Xem / Chạy lại)."""
    if not href or run_store:
        raise PreventUpdate
    qs = parse_qs(urlparse(href).query)
    run_ids = qs.get("run")
    if not run_ids:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    try:
        run_id = int(run_ids[0])
    except ValueError:
        raise PreventUpdate from None
    res = get_report_run(ctx, run_id)
    if not res.ok or not isinstance(res.data, dict):
        raise PreventUpdate
    data = res.data
    # Task 109 Bước 5: run Studio mở lại bằng tham số snapshot của nó và
    # chạy mới từng visual (dữ liệu hiện tại; snapshot là version + params).
    version_res = get_version(ctx, int(data["version_id"]))
    if version_res.ok and isinstance(version_res.data, dict):
        if str(version_res.data.get("source_type") or "") == "SEMANTIC_MODEL":
            values = dict(data.get("params") or {})
            store, _page, _err, _loading = _run_semantic_report(
                ctx,
                int(data["report_id"]),
                int(data["template_id"]),
                int(data["version_id"]),
                values,
            )
            return store, 1
    total = int(data.get("row_count") or 0)
    return (
        {
            "run_id": run_id,
            "template_id": int(data["template_id"]),
            "report_id": int(data["report_id"]),
            "version_id": int(data["version_id"]),
            "total": total,
            "total_pages": _total_pages(total, 50),
        },
        1,
    )


def _export_progress(pct: int = 0, step: str = "") -> Any:
    """Thanh tiến trình export theo % thật (task 40): worker ghi
    PROGRESS_PCT/PROGRESS_STEP xuống DB, poll đọc qua get_export.

    Trước task 40 là indeterminate (value=100, animated) vì service export
    không báo % số.
    """
    pct = max(0, min(100, int(pct or 0)))
    label = step or "Đang xuất file…"
    return dmc.Stack(
        [
            dmc.Progress(value=pct, size="sm", color="blue"),
            dmc.Text(f"{label} — {pct}%", c="dimmed", size="sm"),
        ],
        gap=4,
    )


def _background_status(export: dict[str, Any]) -> Any:
    """Trạng thái sau khi submit chạy ngầm (task 52): không poll, không tự tải.

    File đã DONE sẵn thì hiện link tải; còn lại hiện link tới Lịch sử báo
    cáo để user theo dõi tiến trình và tải khi xong.
    """
    if str(export.get("status") or "") == "DONE":
        return dmc.Group(
            [
                dmc.Text("File Excel đã có sẵn.", size="sm"),
                dcc.Link(
                    "Tải file Excel",
                    href=f"/download/report-export/{int(export['id'])}",
                    target="_blank",
                ),
            ],
            gap="xs",
        )
    return dmc.Group(
        [
            dmc.Text("Đã đưa export vào hàng đợi chạy ngầm.", size="sm"),
            dcc.Link("Mở Lịch sử báo cáo", href="/report-runs"),
        ],
        gap="xs",
    )


def _auto_download(ctx: Any, export_id: int) -> tuple[Any, Any]:
    """Tải file export tự động khi DONE (task 40, bỏ link "Tải file Excel").

    Qua service download_export nên vẫn giữ kiểm quyền owner/ADMIN + audit
    DOWNLOAD_EXPORT như route /download/report-export/<id>. Trả
    (dcc.send_file, dòng trạng thái) hoặc (no_update, notification lỗi).
    """
    res = download_export(ctx, export_id)
    if not res.ok or not isinstance(res.data, dict):
        return dash.no_update, notify_error(res.message or "Không tải được file.")
    file_name = str(res.data["file_name"])
    return (
        dcc.send_file(str(res.data["file_path"]), filename=file_name),  # type: ignore[attr-defined,no-untyped-call]
        dmc.Text(f"Đã tải {file_name}.", size="sm"),
    )


def _queued_run_id_from_export_store(
    export_store: dict[str, Any] | None, values: dict[str, Any]
) -> int | None:
    """Run đã nộp chạy ngầm trước đó với cùng tham số (task 54, D3).

    Chống bấm Xuất 2 lần sinh 2 run: export-store lưu run_id + values
    của lần nộp trước; khớp thì dùng lại run đó, request_export dedup
    trả export đang chờ sẵn.
    """
    if not isinstance(export_store, dict):
        return None
    run_id = export_store.get("run_id")
    if run_id is None or export_store.get("values") != values:
        return None
    return int(run_id)


@callback(
    Output("viewer-export-store", "data", allow_duplicate=True),
    Output("viewer-export-status", "children", allow_duplicate=True),
    Output("viewer-export-poll", "disabled", allow_duplicate=True),
    Output("viewer-download", "data", allow_duplicate=True),
    Output("viewer-run-store", "data", allow_duplicate=True),
    Output("viewer-page-store", "data", allow_duplicate=True),
    Output("viewer-export-btn", "loading"),
    Input("viewer-export-btn", "n_clicks"),
    State("viewer-run-store", "data"),
    State("viewer-report-store", "data"),
    State("viewer-tabs", "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "id"),
    State("viewer-page-store", "data"),
    State("viewer-export-mode", "checked"),
    State("viewer-export-store", "data"),
    State("viewer-version-store", "data"),
    prevent_initial_call=True,
)
def handle_export_click(
    n_clicks: int | None,
    run_store: dict[str, Any] | None,
    report: dict[str, Any] | int | None,
    template_id: str | None,
    param_values: list[Any] | None,
    param_ids: list[dict[str, Any]] | None,
    page_no: int | None,
    run_bg: bool | None = False,
    export_store: dict[str, Any] | None = None,
    version_store: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Any, bool, Any, dict[str, Any], int, bool]:
    """Xuất Excel theo điều kiện tìm kiếm hiện tại (không cần xem trước).

    Run hiện tại đúng điều kiện thì xuất lại run đó; khác (hoặc chưa có
    run, hoặc mở từ ?run=) thì tạo run mới từ form rồi xuất.
    - Chế độ "Xuất ngay": tạo + chạy run mới (đếm tổng + tải trang 1)
      rồi xuất — vì vậy bấm Xuất cũng query dữ liệu và grid hiện dữ liệu
      sẽ xuất (task 39).
    - Chế độ "Chạy ngầm" (task 54): chỉ tạo run QUEUED rồi đưa export
      vào hàng đợi luôn — KHÔNG chạy báo cáo trước (worker tự chạy query
      ở nền), grid và run-store giữ nguyên. Bấm lại cùng tham số thì
      dùng lại run đã nộp (export-store lưu run_id + values).
    Giai đoạn chạy báo cáo chưa có % thật (chưa biết tổng dòng) nên chỉ
    hiện loading trên nút; % thật bắt đầu khi worker export chạy.
    """
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not report or not template_id:
        raise PreventUpdate
    # Task 70: switch "Chạy ngầm" (checked) thay cho Select mode.
    mode = "background" if run_bg else "now"
    report_id = int(report["id"]) if isinstance(report, dict) else int(report)
    values = _values_from_inputs(param_values, param_ids)
    current = dict(run_store or {})
    page = int(page_no or 1)
    if isinstance(version_store, dict) and str(version_store.get("source_type") or "") == "SEMANTIC_MODEL":
        return (
            {},
            notify_error("Báo cáo Studio xuất theo từng visual ở từng thẻ kết quả."),
            True,
            dash.no_update,
            current,
            page,
            False,
        )
    run_id = current.get("run_id")
    if not run_id or current.get("values") != values:
        if (mode or "now") == "background":
            # Task 54: chạy ngầm — vào hàng đợi luôn, không chạy báo cáo
            # trước (không đếm tổng, không tải trang 1). Bấm lại cùng tham
            # số thì dùng lại run đã nộp (export-store, D3).
            run_id = _queued_run_id_from_export_store(export_store, values)
            if run_id is None:
                created = create_report_run(ctx, report_id, template_id=int(template_id), values=values)
                if not created.ok or not isinstance(created.data, dict):
                    return (
                        {},
                        notify_error(created.message or "Không tạo được run."),
                        True,
                        dash.no_update,
                        current,
                        page,
                        False,
                    )
                run_id = int(created.data["id"])
            res = request_export(ctx, int(run_id), "XLSX")
            if not res.ok or not isinstance(res.data, dict):
                return {}, notify_error(res.message or "Không tạo được export."), True, dash.no_update, current, page, False
            export = res.data
            return (
                {"export_id": export["id"], "run_id": int(run_id), "values": values},
                _background_status(export),
                True,
                dash.no_update,
                current,
                page,
                False,
            )
        created = create_report_run(ctx, report_id, template_id=int(template_id), values=values)
        if not created.ok or not isinstance(created.data, dict):
            return (
                {},
                notify_error(created.message or "Không tạo được run."),
                True,
                dash.no_update,
                current,
                page,
                False,
            )
        run_id = int(created.data["id"])
        executed = execute_report_run(ctx, run_id)
        if not executed.ok or not isinstance(executed.data, dict):
            return {}, notify_error(executed.message or "Chạy báo cáo lỗi."), True, dash.no_update, current, page, False
        run = executed.data.get("run") or {}
        if run.get("status") != "DONE":
            detail = run.get("error_message") or "Run lỗi, chưa rõ nguyên nhân."
            return {}, notify_error(f"Chạy báo cáo lỗi: {detail}"), True, dash.no_update, current, page, False
        total = int(executed.data.get("total") or 0)
        current = {
            "run_id": run_id,
            "template_id": int(template_id),
            "report_id": report_id,
            "version_id": int(created.data["version_id"]),
            "total": total,
            "total_pages": _total_pages(total, 50),
            "values": values,
        }
        page = 1
    res = request_export(ctx, int(run_id), "XLSX")
    if not res.ok or not isinstance(res.data, dict):
        return {}, notify_error(res.message or "Không tạo được export."), True, dash.no_update, current, page, False
    export = res.data
    if (mode or "now") == "background":
        return (
            {"export_id": export["id"], "run_id": int(run_id), "values": values},
            _background_status(export),
            True,
            dash.no_update,
            current,
            page,
            False,
        )
    if export["status"] == "DONE":
        download, status = _auto_download(ctx, int(export["id"]))
        return (
            {"export_id": export["id"]},
            status,
            True,
            download,
            current,
            page,
            False,
        )
    return (
        {"export_id": export["id"]},
        _export_progress(
            int(export.get("progress_pct") or 0), str(export.get("progress_step") or "Đã đưa vào hàng đợi export…")
        ),
        False,
        dash.no_update,
        current,
        page,
        False,
    )


@callback(
    Output("viewer-export-store", "data", allow_duplicate=True),
    Output("viewer-export-status", "children", allow_duplicate=True),
    Output("viewer-export-poll", "disabled", allow_duplicate=True),
    Output("viewer-download", "data", allow_duplicate=True),
    Input({"type": "viewer-visual-export", "code": dash.ALL, "format": dash.ALL}, "n_clicks"),
    State("viewer-run-store", "data"),
    State("viewer-report-store", "data"),
    State("viewer-tabs", "value"),
    prevent_initial_call=True,
)
def handle_visual_export_click(
    clicks: list[int | None] | None,
    run_store: dict[str, Any] | None,
    report: dict[str, Any] | int | None,
    template_id: str | None,
) -> tuple[dict[str, Any], Any, bool, Any]:
    """Xuất XLSX/CSV của 1 visual (task 109 Bước 5): 1 run + 1 export/visual.

    Visual chưa có run DONE thì chạy mới rồi xuất (luôn qua worker để
    dùng chung poll + tự tải như nút Xuất Excel cổ điển).
    """
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict) or not any(clicks or []):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not report or not template_id:
        raise PreventUpdate
    if not run_store or not run_store.get("semantic"):
        raise PreventUpdate
    code = str(trig.get("code") or "")
    fmt = str(trig.get("format") or "XLSX").upper()
    if fmt not in ("XLSX", "CSV"):
        raise PreventUpdate
    entry = next(
        (r for r in (run_store.get("runs") or []) if str(r.get("visual_code")) == code),
        None,
    )
    if entry is None:
        raise PreventUpdate
    report_id = int(report["id"]) if isinstance(report, dict) else int(report)
    values = dict(run_store.get("values") or {})
    run_id = entry.get("run_id")
    if not run_id or str(entry.get("status") or "") != "DONE":
        created = create_report_run(
            ctx,
            report_id,
            template_id=int(template_id),
            values=values,
            visual_id=int(entry.get("visual_id") or 0),
        )
        if not created.ok or not isinstance(created.data, dict):
            return {}, notify_error(created.message or "Không tạo được run."), True, dash.no_update
        run_id = int(created.data["id"])
        executed = execute_report_run(ctx, run_id)
        if not executed.ok or not isinstance(executed.data, dict):
            return {}, notify_error(executed.message or "Chạy báo cáo lỗi."), True, dash.no_update
        run = executed.data.get("run") or {}
        if run.get("status") != "DONE":
            detail = run.get("error_message") or "Run lỗi, chưa rõ nguyên nhân."
            return {}, notify_error(f"Chạy báo cáo lỗi: {detail}"), True, dash.no_update
    res = request_export(ctx, int(run_id), fmt)
    if not res.ok or not isinstance(res.data, dict):
        return {}, notify_error(res.message or "Không tạo được export."), True, dash.no_update
    export = res.data
    if export["status"] == "DONE":
        download, status = _auto_download(ctx, int(export["id"]))
        return (
            {"export_id": export["id"], "visual_code": code},
            status,
            True,
            download,
        )
    return (
        {"export_id": export["id"], "visual_code": code},
        _export_progress(
            int(export.get("progress_pct") or 0),
            str(export.get("progress_step") or "Đã đưa vào hàng đợi export…"),
        ),
        False,
        dash.no_update,
    )


@callback(
    Output("viewer-export-status", "children", allow_duplicate=True),
    Output("viewer-export-poll", "disabled", allow_duplicate=True),
    Output("viewer-download", "data", allow_duplicate=True),
    Input("viewer-export-poll", "n_intervals"),
    State("viewer-export-store", "data"),
    prevent_initial_call=True,
)
def handle_export_poll(_n: int | None, export_store: dict[str, Any] | None) -> tuple[Any, bool, Any]:
    """Poll trạng thái export mỗi 2s: % thật + bước, DONE thì tự tải file."""
    if not export_store or not export_store.get("export_id"):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = get_export(ctx, int(export_store["export_id"]))
    if not res.ok or not isinstance(res.data, dict):
        return notify_error(res.message or "Không kiểm tra được export."), True, dash.no_update
    status = res.data["status"]
    if status == "DONE":
        download, status_text = _auto_download(ctx, int(export_store["export_id"]))
        return status_text, True, download
    if status == "FAILED":
        return (
            notify_error(res.data.get("error_message") or "Export lỗi."),
            True,
            dash.no_update,
        )
    return (
        _export_progress(
            int(res.data.get("progress_pct") or 0),
            str(res.data.get("progress_step") or "Đang xuất file…"),
        ),
        False,
        dash.no_update,
    )


def _render_sql_field(label: str, text: str) -> Any:
    """Một mục trong tab SQL thực hiện: tiêu đề + khối mono (theo mẫu
    nhánh cổ điển của handle_sql_tab_render)."""
    return html.Div(
        [
            dmc.Title(label, order=5, size="sm", mt="sm"),
            html.Pre(
                text,
                style={"fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap", "marginTop": "4px"},
            ),
        ]
    )


@callback(
    Output("viewer-sql-container", "children"),
    Input("viewer-run-store", "data"),
    prevent_initial_call=True,
)
def handle_sql_tab_render(run_store: dict[str, Any] | None) -> Any:
    """Render tab SQL thực hiện (chỉ ADMIN — service get_run_sql chặn).

    Tab chỉ xuất hiện trong layout khi ADMIN nên đường thường không tới
    đây; callback vẫn chặn lại để không rò rỉ SQL qua store.

    Báo cáo Studio: 1 mục cho mỗi visual (SQL đã biên dịch + tên bind +
    RLS/tables — không lộ giá trị bind).
    """
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    if run_store and run_store.get("semantic"):
        sections: list[Any] = []
        for entry in run_store.get("runs") or []:
            code = str(entry.get("visual_code") or "")
            if not entry.get("run_id"):
                continue
            res = get_run_sql(ctx, int(entry["run_id"]))
            if not res.ok or not isinstance(res.data, dict):
                sections.append(
                    alert_box(
                        f"Visual {code}: không lấy được SQL.",
                        res.message or "",
                        tone="crit",
                    )
                )
                continue
            d = res.data
            sections.append(
                dmc.Paper(
                    [
                        dmc.Text(f"Visual {code} — {entry.get('title') or ''}", fw=600, size="sm"),
                        _render_sql_field("Câu truy vấn đã biên dịch", str(d.get("sql_text") or "")),
                        _render_sql_field(
                            "Binds (chỉ tên, không lộ giá trị)",
                            ", ".join(str(b) for b in d.get("bind_names") or []) or "(không có)",
                        ),
                        _render_sql_field(
                            "RLS áp dụng / Bảng dùng",
                            f"RLS: {'có' if d.get('rls_applied') else 'không'} — "
                            f"{', '.join(str(t) for t in d.get('tables_used') or [])}",
                        ),
                    ],
                    withBorder=True,
                    radius="sm",
                    p="sm",
                )
            )
        if not sections:
            return empty_state(
                "Chưa chạy báo cáo.",
                "Bấm Xem báo cáo để xem SQL đã thực hiện.",
            )
        if len(sections) == 1:
            return sections[0]
        return dmc.Stack(sections, gap="md")
    if not run_store or not run_store.get("run_id"):
        return empty_state(
            "Chưa chạy báo cáo.",
            "Bấm Xem báo cáo để xem SQL đã thực hiện.",
        )
        raise PreventUpdate
    res = get_run_sql(ctx, int(run_store["run_id"]))
    if not res.ok or not isinstance(res.data, dict):
        return alert_box(res.message or "Không xem được SQL.", tone="crit")
    data = res.data
    binds_text = (
        "\n".join(f"{key} = {value!r}" for key, value in (data.get("binds") or {}).items()) or "(không có bind)"
    )
    children: list[Any] = [
        dmc.Title("Câu truy vấn", order=5, size="sm"),
        html.Pre(
            str(data.get("sql_text") or ""),
            style={"fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap", "marginTop": "4px"},
        ),
        dmc.Title("Binds", order=5, size="sm", mt="sm"),
        html.Pre(
            binds_text,
            style={"fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap", "marginTop": "4px"},
        ),
    ]
    if data.get("warning"):
        children.append(alert_box(str(data["warning"]), tone="warn"))
    children.extend(
        [
            dmc.Title("Câu COUNT", order=5, size="sm", mt="sm"),
            html.Pre(
                str(data.get("count_sql") or ""),
                style={"fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap", "marginTop": "4px"},
            ),
            dmc.Title("Câu phân trang (trang 1, 50 dòng)", order=5, size="sm", mt="sm"),
            html.Pre(
                str(data.get("paged_sql") or ""),
                style={"fontFamily": "monospace", "fontSize": "12px", "whiteSpace": "pre-wrap", "marginTop": "4px"},
            ),
        ]
    )
    return dmc.Stack(children, gap="xs")
