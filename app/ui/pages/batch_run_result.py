"""Kết quả lần chạy bộ — Bước 9 task 18 (Screen13).

`/batch-runs/<id>/result`: KPI, ma trận kết quả từ RECON_RUN_SUMMARY,
chạy lại run lỗi / chạy lại một mục, tải .zip, đánh dấu kiểm tra, xóa
dữ liệu tạm theo nhóm. Phong cách Fluent Compact theo Screen13.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html

from app.core.session import get_current_ctx
from app.services.batch_run import build_zip, matrix, rerun_item, retry_failed
from app.services.perm import is_admin, page_gate
from app.services.run_service import export_run
from app.services.temp_data import mark_checked, purge_runs
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import (
    notify_error,
    notify_info,
    notify_success,
    notify_warning,
)
from app.ui.components.page_header import page_header
from app.ui.components.status_chip import item_status_badge

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path_template="/batch-runs/<run_id>/result",
        path="/batch-runs/1/result",
        title="Kết quả lần chạy bộ — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "batch_run"


def _fmt_num(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_delta(value: Any) -> str:
    if value is None:
        return "—"
    try:
        delta = float(value) * 100
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.1f} điểm %"
    except (TypeError, ValueError):
        return "—"


def render_result_header(matrix_data: dict[str, Any]) -> Any:
    run = matrix_data.get("run") or {}
    total = int(matrix_data.get("total_items", 0))
    with_results = int((matrix_data.get("kpis") or {}).get("items_with_results", 0))
    p_from = (run.get("period_from") or "")[:10]
    p_to = (run.get("period_to") or "")[:10]
    created_at = (run.get("created_at") or "")[:16].replace("T", " ")

    return page_header(
        title=f"Lần chạy bộ: {run.get('name') or matrix_data.get('def_name')}",
        subtitle=f"{matrix_data.get('def_name', '')} · {p_from} → {p_to} · {run.get('created_by', '')} lúc {created_at} · {with_results}/{total} mục có kết quả",
        actions=[
            dmc.Anchor(
                button_subtle("Theo dõi tiến độ", icon="lucide:loader", size="xs"),
                href=f"/batch-runs/{run.get('id')}",
                underline=False,
            ),
            button_subtle("Chạy lại run lỗi", icon="lucide:rotate-ccw", id="brr-retry-btn", size="xs"),
            button_primary(f"Tải tất cả (.zip, {with_results} file riêng)", icon="lucide:download", id="brr-zip-btn", size="xs"),
        ],
    )


def render_result_kpis(kpis: dict[str, Any]) -> Any:
    mismatch_diff = kpis.get("mismatch_total_diff")
    diff_text = f"Tổng chênh {_fmt_num(mismatch_diff)}" if mismatch_diff else "Không có chênh lệch"
    err_count = int(kpis.get("error_items", 0))

    return dmc.SimpleGrid(
        cols={"base": 2, "sm": 4},
        spacing="xs",
        children=[
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Khớp hết", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("all_matched_items", 0)), fw=700, size="lg", c="teal"),
                        dmc.Text("100% khớp giá trị và số lượng", size="xs", c="dimmed"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Có lệch", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("mismatch_items", 0)), fw=700, size="lg", c="orange"),
                        dmc.Text(diff_text, size="xs", c="dimmed"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Lỗi / chưa chạy", size="xs", c="dimmed"),
                        dmc.Text(str(err_count), fw=700, size="lg", c="red"),
                        dmc.Text("Bấm 'Chạy lại run lỗi'" if err_count else "Không có lỗi", size="xs", c="dimmed"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Bỏ qua", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("skipped_items", 0)), fw=700, size="lg", c="gray"),
                        dmc.Text("Không có file hoặc đã Archive", size="xs", c="dimmed"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
        ],
    )


def render_matrix_table(
    matrix_data: dict[str, Any],
    selected_ids: set[int] | None = None,
    search_q: str = "",
    status_filter: str = "all",
) -> Any:
    rows_data = matrix_data.get("rows") or []
    selected_ids = selected_ids or set()
    if not rows_data:
        return empty_state(
            title="Chưa có mục nào",
            description="Lần chạy bộ chưa có mục nào để hiển thị.",
        )

    # Lọc client-side
    q = search_q.strip().lower()
    filtered = rows_data
    if q:
        filtered = [
            r for r in filtered
            if q in str(r.get("template_code", "")).lower() or q in str(r.get("template_name", "")).lower()
        ]
    if status_filter != "all":
        if status_filter == "diff":
            filtered = [r for r in filtered if str(r.get("status")) in ("DONE", "PARTIAL") and float(r.get("diff_total") or 0) != 0]
        elif status_filter == "ok":
            filtered = [r for r in filtered if str(r.get("status")) == "DONE" and float(r.get("diff_total") or 0) == 0]
        elif status_filter == "fail":
            filtered = [r for r in filtered if str(r.get("status")) in ("FAILED", "NOT_RUN")]
        elif status_filter == "skip":
            filtered = [r for r in filtered if str(r.get("status")) == "SKIPPED"]

    if not filtered:
        return empty_state(
            title="Không có template khớp bộ lọc",
            description="Hãy thử thay đổi từ khóa hoặc điều kiện lọc kết quả.",
        )

    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    rows = []
    for row in filtered:
        item_id = int(row["item_id"])
        run_id = row.get("current_run_id")
        can_select = run_id is not None
        checked_by = row.get("checked_by")
        purged = bool(row.get("purged_at"))

        check_chips: list[Any] = []
        if checked_by:
            check_chips.append(dmc.Badge(f"Đã kiểm tra ({checked_by})", color="teal", variant="light", size="xs"))
        else:
            check_chips.append(dmc.Badge("Chưa kiểm tra", color="gray", variant="light", size="xs"))
        if purged:
            check_chips.append(dmc.Badge("Đã xóa dữ liệu tạm", color="gray", variant="outline", size="xs"))

        actions: list[Any] = []
        if run_id is not None:
            actions.append(
                dmc.Anchor(
                    button_subtle("Mở run", size="xs"),
                    href=f"/runs/{run_id}",
                    underline=False,
                )
            )
            actions.append(
                button_subtle(
                    "Tải file",
                    id={"type": "brr-download-btn", "index": item_id},
                    size="xs",
                )
            )
        if str(row.get("status")) in ("DONE", "FAILED", "NOT_RUN"):
            actions.append(
                button_subtle(
                    "Chạy lại",
                    id={"type": "brr-rerun-btn", "index": item_id},
                    size="xs",
                )
            )

        diff_val = row.get("diff_total")
        diff_color = "var(--crit, #C50F1F)" if diff_val and float(diff_val) != 0 else None

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "brr-select-cb", "index": item_id},
                            checked=item_id in selected_ids,
                            disabled=not can_select,
                            size="xs",
                            **{"aria-label": f"Chọn mục {row.get('template_code')}"},
                        ),
                        style={"textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(row.get("template_name") or ""), fw=600, size="xs"),
                                dmc.Text(
                                    f"{row.get('template_code')} · {row.get('file_count', 0)} file",
                                    size="xs",
                                    className="rh-code",
                                    c="dimmed",
                                ),
                            ],
                            gap=2,
                        )
                    ),
                    dmc.TableTd(item_status_badge(str(row.get("status"))), style={"textAlign": "center"}),
                    dmc.TableTd(dmc.Text(_fmt_num(row.get("excel_total")), size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(_fmt_num(row.get("db_total")), size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(_fmt_num(diff_val), size="xs", ta="right", fw=700 if diff_color else 400, style={"color": diff_color})),
                    dmc.TableTd(dmc.Text(str(row.get("cnt_matched")) if row.get("cnt_matched") is not None else "—", size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(str(row.get("cnt_mismatch")) if row.get("cnt_mismatch") is not None else "—", size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(str(row.get("cnt_missing_in_db")) if row.get("cnt_missing_in_db") is not None else "—", size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(str(row.get("cnt_missing_in_excel")) if row.get("cnt_missing_in_excel") is not None else "—", size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(_fmt_pct(row.get("match_rate")), size="xs", ta="right")),
                    dmc.TableTd(dmc.Text(_fmt_delta(row.get("match_rate_delta")), size="xs", ta="center", c="dimmed")),
                    dmc.TableTd(dmc.Group(check_chips, gap=4)),
                    dmc.TableTd(dmc.Group(actions, gap=4)),
                ]
            )
        )

    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=1100,
            style={"height": "100%", "overflow": "auto"},
            children=dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh(
                                    dmc.Checkbox(id="brr-select-all", size="xs", **{"aria-label": "Chọn tất cả"}),
                                    style={**th_style, "width": "40px"},
                                ),
                                dmc.TableTh("Template / hệ thống", style={**th_style, "minWidth": "220px", "textAlign": "left"}),
                                dmc.TableTh("Trạng thái", style={**th_style, "width": "110px"}),
                                dmc.TableTh("Tổng Excel", style={**th_style, "width": "110px"}),
                                dmc.TableTh("Tổng DB", style={**th_style, "width": "110px"}),
                                dmc.TableTh("Chênh lệch", style={**th_style, "width": "110px"}),
                                dmc.TableTh("Khớp", style={**th_style, "width": "60px"}),
                                dmc.TableTh("Lệch", style={**th_style, "width": "60px"}),
                                dmc.TableTh("Thiếu DB", style={**th_style, "width": "75px"}),
                                dmc.TableTh("Thiếu Excel", style={**th_style, "width": "80px"}),
                                dmc.TableTh("Tỷ lệ khớp", style={**th_style, "width": "80px"}),
                                dmc.TableTh("So tháng trước", style={**th_style, "width": "100px"}),
                                dmc.TableTh("Kiểm tra", style={**th_style, "minWidth": "140px"}),
                                dmc.TableTh("Thao tác", style={**th_style, "minWidth": "160px"}),
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
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


def layout(run_id: str | int | None = None, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="brr-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Kết quả lần chạy bộ.", tone="crit"),
            ],
            p="md",
        )
    run_id_int = int(run_id) if run_id is not None and str(run_id).isdigit() else 0
    can_purge_bulk = bool(ctx is not None and is_admin(ctx))

    return dmc.Box(
        [
            dcc.Store(id="brr-run-id", data=run_id_int),
            dcc.Store(id="brr-store"),
            dcc.Store(id="brr-selected-store", data=[]),
            dcc.Store(id="brr-refresh-trigger", data=0),
            dcc.Download(id="brr-download"),
            html.Div(id="brr-notifications"),

            # Header
            html.Div(id="brr-header", style={"flexShrink": 0}),

            # 4 KPIs
            html.Div(id="brr-kpis", style={"flexShrink": 0}),

            # Toolbar lọc & thao tác chọn nhiều
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Group(
                            [
                                dmc.TextInput(
                                    id="brr-search-input",
                                    placeholder="Tìm template (mã, tên)...",
                                    size="xs",
                                    w=220,
                                    styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "11px"}},
                                ),
                                dmc.Select(
                                    id="brr-filter-status",
                                    data=[
                                        {"label": "Tất cả kết quả", "value": "all"},
                                        {"label": "Có lệch", "value": "diff"},
                                        {"label": "Khớp hết", "value": "ok"},
                                        {"label": "Lỗi", "value": "fail"},
                                        {"label": "Bỏ qua", "value": "skip"},
                                    ],
                                    value="all",
                                    size="xs",
                                    w=160,
                                    styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "11px"}},
                                ),
                            ],
                            gap="xs",
                        ),
                        dmc.Group(
                            [
                                html.Span(id="brr-selected-count", style={"fontSize": "11px", "color": "var(--ink-soft)"}),
                                button_primary(
                                    "Đánh dấu đã kiểm tra", icon="lucide:check-check", id="brr-mark-checked-btn", size="xs"
                                ),
                                button_danger(
                                    "Xóa dữ liệu tạm",
                                    id="brr-purge-btn",
                                    disabled=not can_purge_bulk,
                                    size="xs",
                                ),
                            ],
                            id="brr-bulk-actions",
                            gap="xs",
                            style={"display": "none"},
                        ),
                    ],
                    justify="space-between",
                    align="center",
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                style={"flexShrink": 0, "backgroundColor": "var(--surface-2, #FAFAFA)"},
            ),

            # Content Table
            html.Div(
                id="brr-content",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),

            modal_confirm(
                id="brr-purge-modal",
                title="Xóa dữ liệu tạm các run đã chọn",
                description="Xóa dòng Excel đã nạp, file gốc và cache. Giữ lại kết quả, tổng hợp và export. Chỉ Admin xóa hàng loạt.",
                confirm_text="XOA",
                confirm_label="Xóa dữ liệu tạm",
            ),
            modal_confirm(
                id="brr-check-modal",
                title="Đánh dấu đã kiểm tra",
                description="Đánh dấu đã kiểm tra cho các mục đã chọn trong lần chạy bộ.",
                confirm_label="Xác nhận",
            ),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 14px",
            "gap": "6px",
        },
    )


@callback(
    Output("brr-store", "data"),
    Input("brr-run-id", "data"),
    Input("brr-refresh-trigger", "data"),
)
def _load_result(run_id: Any, _refresh: Any) -> Any:
    if run_id is None or int(run_id) <= 0:
        return {"error": "Không xác định được lần chạy bộ."}
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem kết quả lần chạy bộ."}
    res = matrix(ctx, int(run_id))
    if not res.ok:
        return {"error": res.message or "Không tải được kết quả lần chạy bộ."}
    return res.data


@callback(
    Output("brr-header", "children"),
    Output("brr-kpis", "children"),
    Output("brr-content", "children"),
    Input("brr-store", "data"),
    Input("brr-search-input", "value"),
    Input("brr-filter-status", "value"),
    Input("brr-selected-store", "data"),
)
def _render_result(store_data: Any, search: str | None, status: str | None, selected_ids: Any) -> tuple[Any, Any, Any]:
    if store_data is None:
        return (
            dmc.Skeleton(height=36, radius="sm"),
            dmc.Skeleton(height=48, radius="sm"),
            dmc.Stack([dmc.Skeleton(height=36, radius="sm") for _ in range(5)], gap="xs"),
        )
    if isinstance(store_data, dict) and store_data.get("error"):
        return (
            alert_box(title="Không thể tải kết quả", message=str(store_data["error"]), tone="crit"),
            dmc.Text(""),
            dmc.Text(""),
        )
    sel_set = set(int(x) for x in (selected_ids or []))
    return (
        render_result_header(store_data),
        render_result_kpis(store_data.get("kpis") or {}),
        render_matrix_table(store_data, selected_ids=sel_set, search_q=search or "", status_filter=status or "all"),
    )


@callback(
    Output("brr-selected-store", "data"),
    Output("brr-selected-count", "children"),
    Output("brr-bulk-actions", "style"),
    Input({"type": "brr-select-cb", "index": ALL}, "checked"),
    Input("brr-select-all", "checked"),
    State("brr-store", "data"),
    State("brr-selected-store", "data"),
    prevent_initial_call=True,
)
def _track_selection(checked_list: Any, select_all: bool | None, store_data: Any, curr_selected: Any) -> tuple[Any, str, dict[str, Any]]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not isinstance(store_data, dict):
        return dash.no_update, "", {"display": "none"}
    trig = ctx_dash.triggered_id
    rows = store_data.get("rows") or []

    if trig == "brr-select-all":
        if select_all:
            selected = [int(r["item_id"]) for r in rows if r.get("current_run_id")]
        else:
            selected = []
    else:
        # Collect checkboxes
        states = ctx_dash.inputs_list or []
        selected = []
        for group in states:
            entries = group if isinstance(group, list) else [group]
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("id"), dict) and entry.get("id", {}).get("type") == "brr-select-cb":
                    if entry.get("value"):
                        selected.append(int(entry["id"]["index"]))

    count = len(selected)
    style = {"display": "flex"} if count > 0 else {"display": "none"}
    return selected, f"Đã chọn {count} template", style


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Input("brr-retry-btn", "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _retry_failed(_n: Any, run_id: Any) -> tuple[Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = retry_failed(ctx, int(run_id))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không chạy lại được.")
    started = (res.data or {}).get("started", 0)
    refreshed = matrix(ctx, int(run_id))
    return refreshed.data, notify_info(f"Đã chạy lại {started} mục lỗi. Theo dõi tiến độ ở trang chạy bộ.")


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Input({"type": "brr-rerun-btn", "index": ALL}, "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _rerun_one(_n: Any, run_id: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or not any(c for c in (_n or []) if c) or ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = rerun_item(ctx, int(triggered["index"]))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không chạy lại được mục.")
    refreshed = matrix(ctx, int(run_id))
    return refreshed.data, notify_info("Đã chạy lại mục. Theo dõi tiến độ ở trang chạy bộ.")


@callback(
    Output("brr-download", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Input({"type": "brr-download-btn", "index": ALL}, "n_clicks"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _download_one(_n: Any, store_data: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or not any(c for c in (_n or []) if c) or ctx is None or not isinstance(store_data, dict):
        return dash.no_update, dash.no_update
    item_id = int(triggered["index"])
    rows = store_data.get("rows") or []
    target = next((r for r in rows if int(r["item_id"]) == item_id), None)
    if not target or not target.get("current_run_id"):
        return dash.no_update, notify_error("Mục chưa có kết quả để xuất.")
    res = export_run(ctx, int(target["current_run_id"]))
    if not res.ok or not res.data:
        return dash.no_update, notify_error(res.message or "Không xuất được file.")
    path = Path(res.data["path"])
    return dcc.send_file(str(path)), notify_success(f"Bắt đầu tải {path.name}.")  # type: ignore[attr-defined,no-untyped-call]


@callback(
    Output("brr-download", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Input("brr-zip-btn", "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _download_zip(_n: Any, run_id: Any) -> tuple[Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = build_zip(ctx, int(run_id))
    if not res.ok or not res.data:
        return dash.no_update, notify_error(res.message or "Không tạo được file .zip.")
    zip_path = Path(res.data["zip_path"])
    return dcc.send_file(str(zip_path)), notify_success(f"Bắt đầu tải {zip_path.name}.")  # type: ignore[attr-defined,no-untyped-call]


@callback(
    Output("brr-check-modal", "opened"),
    Input("brr-mark-checked-btn", "n_clicks"),
    Input("brr-check-modal-cancel", "n_clicks"),
    State("brr-check-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_check_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trig = ctx_dash.triggered_id
    if trig == "brr-check-modal-cancel":
        return False
    if trig == "brr-mark-checked-btn" and bool(_open):
        return True
    return False


@callback(
    Output("brr-purge-modal", "opened"),
    Input("brr-purge-btn", "n_clicks"),
    Input("brr-purge-modal-cancel", "n_clicks"),
    State("brr-purge-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_purge_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trig = ctx_dash.triggered_id
    if trig == "brr-purge-modal-cancel":
        return False
    if trig == "brr-purge-btn" and bool(_open):
        return True
    return False


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Output("brr-check-modal", "opened", allow_duplicate=True),
    Input("brr-check-modal-confirm", "n_clicks"),
    State("brr-run-id", "data"),
    State("brr-selected-store", "data"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _confirm_mark_checked(_n: Any, run_id: Any, selected_ids: Any, store_data: Any) -> tuple[Any, Any, bool]:
    if not _n:
        return dash.no_update, dash.no_update, False
    ctx = get_current_ctx()
    if ctx is None or not isinstance(store_data, dict):
        return dash.no_update, notify_error("Bạn cần đăng nhập."), False
    rows = store_data.get("rows") or []
    wanted = set(int(x) for x in (selected_ids or []))
    child_ids = [int(r["current_run_id"]) for r in rows if int(r["item_id"]) in wanted and r.get("current_run_id")]
    if not child_ids:
        return dash.no_update, notify_warning("Chưa chọn run nào hợp lệ."), False

    for cid in child_ids:
        res = mark_checked(ctx, cid)
        if not res.ok:
            return dash.no_update, notify_error(res.message or f"Không đánh dấu được run #{cid}."), False

    refreshed = matrix(ctx, int(run_id))
    return refreshed.data, notify_success(f"Đã đánh dấu kiểm tra {len(child_ids)} run con."), False


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-notifications", "children", allow_duplicate=True),
    Output("brr-purge-modal", "opened", allow_duplicate=True),
    Input("brr-purge-modal-confirm", "n_clicks"),
    State("brr-run-id", "data"),
    State("brr-selected-store", "data"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _confirm_purge(_n: Any, run_id: Any, selected_ids: Any, store_data: Any) -> tuple[Any, Any, bool]:
    if not _n:
        return dash.no_update, dash.no_update, False
    ctx = get_current_ctx()
    if ctx is None or not isinstance(store_data, dict):
        return dash.no_update, notify_error("Bạn cần đăng nhập."), False
    rows = store_data.get("rows") or []
    wanted = set(int(x) for x in (selected_ids or []))
    child_ids = [int(r["current_run_id"]) for r in rows if int(r["item_id"]) in wanted and r.get("current_run_id")]
    if not child_ids:
        return dash.no_update, notify_warning("Chưa chọn run nào hợp lệ."), False

    res = purge_runs(ctx, child_ids)
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không xóa được dữ liệu tạm."), False

    refreshed = matrix(ctx, int(run_id))
    return refreshed.data, notify_success(f"Đã xóa dữ liệu tạm của {len(child_ids)} run con."), False
