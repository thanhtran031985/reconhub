"""Trang Xem báo cáo — task 27 bước 2, prototype Screen16 v-report.

Template dạng tab, form tham số động (grid 12 cột), bảng kết quả
server-side, export background.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

from app.core.session import get_current_ctx
from app.services.perm import page_gate
from app.services.report import get_report
from app.services.report_column import get_result_layout
from app.services.report_export import get_export, request_export
from app.services.report_param import preview_layout
from app.services.report_run import (
    create_report_run,
    execute_report_run,
    get_report_page,
    get_report_run,
)
from app.services.report_template import get_version, list_templates
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.page_header import page_header
from app.ui.components.report_widgets import (
    _format_cell,
    _lov_options,
    render_param_control,
    render_param_form,
    render_result_table,
)

__all__ = [
    "_format_cell",
    "_lov_options",
    "render_param_control",
    "render_param_form",
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
    # dmc.Select chỉ nhận value chuỗi (số gây lỗi Mantine ở trình duyệt).
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
    options_by_code: dict[str, list[dict[str, str]]] = {}
    for row in preview.get("rows", []):
        for entry in row.get("params", []):
            if entry.get("control_type") in ("SELECT", "MULTI_SELECT"):
                options_by_code[str(entry["code"])] = _lov_options(ctx, int(first["active_version_id"]), entry)
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
                        id="viewer-param-form",
                        children=render_param_form(preview, options_by_code),
                    ),
                    dmc.Group(
                        [
                            dmc.Button(
                                "Xem báo cáo",
                                id="viewer-run-btn",
                                variant="filled",
                                size="xs",
                            ),
                            html.Div(
                                id="viewer-run-error",
                                **{"aria-live": "polite"},  # type: ignore[arg-type]
                            ),
                        ],
                        mt="xs",
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
                            dmc.Group(
                                [
                                    dmc.Select(
                                        id="viewer-page-size",
                                        data=PAGE_SIZE_OPTIONS,
                                        value="50",
                                        w=140,
                                        size="xs",
                                        clearable=False,
                                        **{"aria-label": "Số dòng mỗi trang"},
                                    ),
                                    dmc.Button(
                                        "Xuất Excel",
                                        id="viewer-export-btn",
                                        variant="filled",
                                        size="xs",
                                        disabled=True,
                                    ),
                                ],
                                gap="xs",
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
                    dcc.Loading(
                        id="viewer-loading",
                        type="circle",
                        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
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


@callback(
    Output("viewer-run-store", "data"),
    Output("viewer-page-store", "data"),
    Output("viewer-run-error", "children"),
    Input("viewer-run-btn", "n_clicks"),
    State("viewer-report-store", "data"),
    State("viewer-tabs", "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def handle_run_click(
    n_clicks: int | None,
    report: dict[str, Any] | int | None,
    template_id: str | None,
    param_values: list[Any] | None,
    param_ids: list[dict[str, Any]] | None,
    page_size: int = 50,
) -> tuple[dict[str, Any], int, Any]:
    """Tạo + chạy run đồng bộ (task 25 Q2); render do handle_result_render.

    run-store mang sẵn total/total_pages (từ execute) để đồng bộ pagination
    mà không cần truy vấn thêm.
    """
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not report or not template_id:
        raise PreventUpdate
    report_id = int(report["id"]) if isinstance(report, dict) else int(report)
    values = _values_from_inputs(param_values, param_ids)
    created = create_report_run(ctx, report_id, template_id=int(template_id), values=values)
    if not created.ok or not isinstance(created.data, dict):
        return {}, 1, alert_box(created.message or "Không tạo được run.", tone="crit")
    run_id = int(created.data["id"])
    executed = execute_report_run(ctx, run_id)
    if not executed.ok or not isinstance(executed.data, dict):
        return {}, 1, alert_box(executed.message or "Chạy báo cáo lỗi.", tone="crit")
    # execute trả ok=True kể cả khi run FAILED (lỗi truy vấn là kết quả
    # nghiệp vụ, task 25): phải kiểm tra status, không render trang lỗi.
    run = executed.data.get("run") or {}
    if run.get("status") != "DONE":
        detail = run.get("error_message") or "Run lỗi, chưa rõ nguyên nhân."
        return {}, 1, alert_box(f"Chạy báo cáo lỗi: {detail}", tone="crit")
    total = int(executed.data.get("total") or 0)
    return (
        {
            "run_id": run_id,
            "template_id": int(template_id),
            "report_id": report_id,
            "version_id": int(created.data["version_id"]),
            "total": total,
            "total_pages": _total_pages(total, page_size),
        },
        1,
        "",
    )


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
    return int(page_no)


@callback(
    Output("viewer-sort-store", "data"),
    Output("viewer-page-store", "data", allow_duplicate=True),
    Input({"type": "viewer-sort", "index": dash.ALL}, "n_clicks"),
    State("viewer-sort-store", "data"),
    prevent_initial_call=True,
)
def handle_sort_click(
    n_clicks: list[int | None] | None, sorts: list[dict[str, str]] | None
) -> tuple[list[dict[str, str]], int]:
    """Bấm tiêu đề cột: ASC → DESC → bỏ sắp xếp."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    field = str(triggered_id["index"])
    current = list(sorts or [])
    existing = next((s for s in current if s["field"] == field), None)
    if existing is None:
        new_sorts = [{"field": field, "direction": "ASC"}]
    elif existing["direction"] == "ASC":
        new_sorts = [{"field": field, "direction": "DESC"}]
    else:
        new_sorts = []
    return new_sorts, 1


@callback(
    Output("viewer-result-container", "children"),
    Output("viewer-result-count", "children"),
    Input("viewer-run-store", "data"),
    Input("viewer-page-store", "data"),
    Input("viewer-sort-store", "data"),
    State("viewer-page-size", "value"),
    State("viewer-result-container", "children"),
)
def handle_result_render(
    run_store: dict[str, Any] | None,
    page_no: int | None,
    sorts: list[dict[str, str]] | None,
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
        render_result_table(layout, data.get("rows", [])),
        f"{total} dòng",
    )


@callback(
    Output("viewer-pagination", "total"),
    Output("viewer-pagination", "value"),
    Output("viewer-export-btn", "disabled"),
    Input("viewer-run-store", "data"),
    Input("viewer-page-size", "value"),
    State("viewer-page-store", "data"),
)
def handle_pagination_sync(
    run_store: dict[str, Any] | None,
    page_size: int | None,
    page_no: int | None,
) -> tuple[int, int, bool]:
    """Đồng bộ Pagination + nút Xuất từ run-store (total có sẵn, không query)."""
    if not run_store or not run_store.get("run_id"):
        return 1, 1, True
    total = int(run_store.get("total") or 0)
    total_pages = _total_pages(total, int(page_size or 50))
    return total_pages, min(int(page_no or 1), total_pages), False


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
    total = int(res.data.get("row_count") or 0)
    return (
        {
            "run_id": run_id,
            "template_id": int(res.data["template_id"]),
            "report_id": int(res.data["report_id"]),
            "version_id": int(res.data["version_id"]),
            "total": total,
            "total_pages": _total_pages(total, 50),
        },
        1,
    )


@callback(
    Output("viewer-export-store", "data"),
    Output("viewer-export-status", "children"),
    Output("viewer-export-poll", "disabled"),
    Input("viewer-export-btn", "n_clicks"),
    State("viewer-run-store", "data"),
    prevent_initial_call=True,
)
def handle_export_click(n_clicks: int | None, run_store: dict[str, Any] | None) -> tuple[dict[str, Any], Any, bool]:
    """Yêu cầu export XLSX rồi poll tới DONE (task 26)."""
    if not n_clicks or not run_store or not run_store.get("run_id"):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = request_export(ctx, int(run_store["run_id"]), "XLSX")
    if not res.ok or not isinstance(res.data, dict):
        return {}, alert_box(res.message or "Không tạo được export.", tone="crit"), True
    export = res.data
    if export["status"] == "DONE":
        return (
            {"export_id": export["id"]},
            dcc.Link(
                "Tải file Excel",
                href=f"/download/report-export/{export['id']}",
                target="_blank",
            ),
            True,
        )
    return (
        {"export_id": export["id"]},
        dmc.Text("Đang xuất file…", c="dimmed", size="sm"),
        False,
    )


@callback(
    Output("viewer-export-status", "children", allow_duplicate=True),
    Output("viewer-export-poll", "disabled", allow_duplicate=True),
    Input("viewer-export-poll", "n_intervals"),
    State("viewer-export-store", "data"),
    prevent_initial_call=True,
)
def handle_export_poll(_n: int | None, export_store: dict[str, Any] | None) -> tuple[Any, bool]:
    """Poll trạng thái export mỗi 2s."""
    if not export_store or not export_store.get("export_id"):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = get_export(ctx, int(export_store["export_id"]))
    if not res.ok or not isinstance(res.data, dict):
        return alert_box(res.message or "Không kiểm tra được export.", tone="crit"), True
    status = res.data["status"]
    if status == "DONE":
        return (
            dcc.Link(
                "Tải file Excel",
                href=f"/download/report-export/{export_store['export_id']}",
                target="_blank",
            ),
            True,
        )
    if status == "FAILED":
        return (
            alert_box(res.data.get("error_message") or "Export lỗi.", tone="crit"),
            True,
        )
    return dmc.Text("Đang xuất file…", c="dimmed", size="sm"), False
