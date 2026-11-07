"""Kết quả lần chạy bộ — Bước 9 task 18 (Screen13).

`/batch-runs/<id>/result`: KPI, ma trận kết quả từ RECON_RUN_SUMMARY,
chạy lại run lỗi / chạy lại một mục, tải .zip, đánh dấu kiểm tra, xóa
dữ liệu tạm theo nhóm (gọi lại service hiện có).
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.batch_run import build_zip, matrix, rerun_item, retry_failed
from app.services.perm import is_admin, page_gate
from app.services.run_service import export_run
from app.services.temp_data import mark_checked, purge_runs
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
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
    return page_header(
        title=f"Kết quả lần chạy bộ #{run.get('id')}",
        subtitle=f"{matrix_data.get('def_code', '')} — {matrix_data.get('def_name', '')} · Kỳ {run.get('period', '')} · {run.get('name', '')} · Người chạy {run.get('created_by', '')} · {with_results}/{total} mục có kết quả",
        actions=[
            dmc.Anchor(
                button_subtle("Theo dõi tiến độ", icon="lucide:loader", size="xs"),
                href=f"/batch-runs/{run.get('id')}",
                underline=False,
            ),
            button_primary("Chạy lại run lỗi", icon="lucide:rotate-ccw", id="brr-retry-btn", size="xs"),
            button_primary("Tải tất cả (.zip)", icon="lucide:download", id="brr-zip-btn", size="xs"),
        ],
    )


def render_result_kpis(kpis: dict[str, Any]) -> Any:
    return dmc.Group(
        [
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Khớp hết", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("all_matched_items", 0)), fw=700, size="md"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                style={"minWidth": 120},
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Có lệch", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("mismatch_items", 0)), fw=700, size="md"),
                        dmc.Text(f"Tổng chênh {_fmt_num(kpis.get('mismatch_total_diff'))}", size="xs", c="dimmed"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                style={"minWidth": 140},
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Lỗi / chưa chạy", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("error_items", 0)), fw=700, size="md"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                style={"minWidth": 120},
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Bỏ qua", size="xs", c="dimmed"),
                        dmc.Text(str(kpis.get("skipped_items", 0)), fw=700, size="md"),
                    ],
                    gap=2,
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                style={"minWidth": 120},
            ),
        ],
        gap="xs",
    )


def render_matrix_table(matrix_data: dict[str, Any], selected_ids: set[int] | None = None) -> Any:
    rows_data = matrix_data.get("rows") or []
    selected_ids = selected_ids or set()
    if not rows_data:
        return empty_state(
            title="Chưa có mục nào",
            description="Lần chạy bộ chưa có mục nào để hiển thị.",
        )
    rows = []
    for row in rows_data:
        item_id = int(row["item_id"])
        run_id = row.get("current_run_id")
        can_select = run_id is not None
        checked_by = row.get("checked_by")
        check_cell = dmc.Text(
            f"Đã kiểm tra ({checked_by})" if checked_by else "Chưa kiểm tra",
            size="sm",
        )
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
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "brr-select-cb", "index": item_id},
                            checked=item_id in selected_ids,
                            disabled=not can_select,
                            size="sm",
                            **{"aria-label": f"Chọn mục {row.get('template_code')}"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(row.get("template_code")), className="rh-code", fw=600, size="sm"),
                                dmc.Text(str(row.get("template_name") or ""), size="xs", c="dimmed"),
                            ],
                            gap=0,
                        )
                    ),
                    dmc.TableTd(dmc.Text(str(row.get("file_count", 0)), size="sm")),
                    dmc.TableTd(item_status_badge(str(row.get("status")))),
                    dmc.TableTd(dmc.Text(_fmt_num(row.get("excel_total")), size="sm")),
                    dmc.TableTd(dmc.Text(_fmt_num(row.get("db_total")), size="sm")),
                    dmc.TableTd(dmc.Text(_fmt_num(row.get("diff_total")), size="sm")),
                    dmc.TableTd(
                        dmc.Text(str(row.get("cnt_matched")) if row.get("cnt_matched") is not None else "—", size="sm")
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            str(row.get("cnt_mismatch")) if row.get("cnt_mismatch") is not None else "—", size="sm"
                        )
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            str(row.get("cnt_missing_in_db")) if row.get("cnt_missing_in_db") is not None else "—",
                            size="sm",
                        )
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            str(row.get("cnt_missing_in_excel"))
                            if row.get("cnt_missing_in_excel") is not None
                            else "—",
                            size="sm",
                        )
                    ),
                    dmc.TableTd(dmc.Text(_fmt_pct(row.get("match_rate")), size="sm")),
                    dmc.TableTd(dmc.Text(_fmt_delta(row.get("match_rate_delta")), size="sm")),
                    dmc.TableTd(check_cell),
                    dmc.TableTd(dmc.Group(actions, gap="xs")),
                ]
            )
        )
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--p2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "12px",
        "fontWeight": 600,
    }
    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=1100,
            style={"height": "100%", "overflow": "auto"},
            children=dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("", style=th_style),
                                dmc.TableTh("Template", style=th_style),
                                dmc.TableTh("Số file", style=th_style),
                                dmc.TableTh("Trạng thái", style=th_style),
                                dmc.TableTh("Tổng Excel", style=th_style),
                                dmc.TableTh("Tổng DB", style=th_style),
                                dmc.TableTh("Chênh lệch", style=th_style),
                                dmc.TableTh("Khớp", style=th_style),
                                dmc.TableTh("Lệch", style=th_style),
                                dmc.TableTh("Thiếu DB", style=th_style),
                                dmc.TableTh("Thiếu Excel", style=th_style),
                                dmc.TableTh("Tỷ lệ khớp", style=th_style),
                                dmc.TableTh("So tháng trước", style=th_style),
                                dmc.TableTh("Kiểm tra", style=th_style),
                                dmc.TableTh("Thao tác", style=th_style),
                            ]
                        )
                    ),
                    dmc.TableTbody(rows),
                ],
                striped=True,
                highlightOnHover=True,
                style={"fontSize": "13px"},
            ),
        ),
        withBorder=True,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


def render_zip_file_list(names: list[str]) -> Any:
    if not names:
        return dmc.Text("")
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("File trong .zip", fw=600),
                dmc.List([dmc.ListItem(name, icon=DashIconify(icon="lucide:file-text", width=14)) for name in names]),
            ],
            gap="xs",
        ),
        p="md",
        withBorder=True,
    )


def _load_matrix_data(run_id: int) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem kết quả lần chạy bộ."}
    res = matrix(ctx, run_id)
    if not res.ok:
        return {"error": res.message or "Không tải được kết quả lần chạy bộ."}
    return res.data


def _selected_child_run_ids(store_data: Any, checked_values: Any) -> list[int]:
    if not isinstance(store_data, dict):
        return []
    rows = store_data.get("rows") or []
    by_item = {int(r["item_id"]): r for r in rows}
    ids: list[int] = []
    states = dash.callback_context.states_list or []
    for group in states:
        group_entries = group if isinstance(group, list) else [group]
        for entry in group_entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), dict):
                continue
            if entry.get("id", {}).get("type") != "brr-select-cb":
                continue
            if not entry.get("value"):
                continue
            row = by_item.get(int(entry["id"]["index"]))
            if row and row.get("current_run_id"):
                ids.append(int(row["current_run_id"]))
    return ids


def layout(run_id: str | int | None = None, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="brr-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Kết quả lần chạy bộ.", tone="crit"),
            ]
        )
    run_id_int = int(run_id) if run_id is not None and str(run_id).isdigit() else 0
    can_purge_bulk = bool(ctx is not None and is_admin(ctx))
    return dmc.Box(
        [
            dcc.Store(id="brr-run-id", data=run_id_int),
            dcc.Store(id="brr-store"),
            dcc.Store(id="brr-refresh-trigger", data=0),
            dcc.Download(id="brr-download"),
            html.Div(id="brr-header"),
            html.Div(id="brr-kpis"),
            html.Div(id="brr-alert"),
            dmc.Group(
                [
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
                gap="xs",
            ),
            html.Div(
                id="brr-content",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
            html.Div(id="brr-zip-list"),
            modal_confirm(
                id="brr-purge-modal",
                title="Xóa dữ liệu tạm các run đã chọn",
                description="Xóa dữ liệu tạm của các run con đã chọn. Chỉ Admin xóa hàng loạt.",
                confirm_text="XOA",
                confirm_label="Xóa dữ liệu tạm",
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


@callback(
    Output("brr-store", "data"),
    Input("brr-run-id", "data"),
    Input("brr-refresh-trigger", "data"),
)
def _load_result(run_id: Any, _refresh: Any) -> Any:
    if run_id is None or int(run_id) <= 0:
        return {"error": "Không xác định được lần chạy bộ."}
    return _load_matrix_data(int(run_id))


@callback(
    Output("brr-header", "children"),
    Output("brr-kpis", "children"),
    Output("brr-content", "children"),
    Input("brr-store", "data"),
)
def _render_result(store_data: Any) -> tuple[Any, Any, Any]:
    if store_data is None:
        return (
            dmc.Skeleton(height=48, radius="md"),
            dmc.Skeleton(height=48, radius="md"),
            dmc.Stack([dmc.Skeleton(height=48, radius="md") for _ in range(5)], gap="sm"),
        )
    if isinstance(store_data, dict) and store_data.get("error"):
        return (
            alert_box(title="Không thể tải kết quả", message=str(store_data["error"]), tone="crit"),
            dmc.Text(""),
            dmc.Text(""),
        )
    return (
        render_result_header(store_data),
        render_result_kpis(store_data.get("kpis") or {}),
        render_matrix_table(store_data),
    )


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-alert", "children", allow_duplicate=True),
    Input("brr-retry-btn", "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _retry_failed(_n: Any, run_id: Any) -> tuple[Any, Any]:
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = retry_failed(ctx, int(run_id))
    if not res.ok:
        return dash.no_update, alert_box(res.message or "Không chạy lại được.", tone="crit")
    started = (res.data or {}).get("started", 0)
    return _load_matrix_data(int(run_id)), alert_box(
        f"Đã chạy lại {started} mục lỗi. Theo dõi tiến độ ở trang chạy bộ.",
        tone="info",
    )


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-alert", "children", allow_duplicate=True),
    Input({"type": "brr-rerun-btn", "index": ALL}, "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _rerun_one(_n: Any, run_id: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = rerun_item(ctx, int(triggered["index"]))
    if not res.ok:
        return dash.no_update, alert_box(res.message or "Không chạy lại được mục.", tone="crit")
    return _load_matrix_data(int(run_id)), alert_box("Đã chạy lại mục. Theo dõi tiến độ ở trang chạy bộ.", tone="info")


@callback(
    Output("brr-download", "data", allow_duplicate=True),
    Output("brr-alert", "children", allow_duplicate=True),
    Input({"type": "brr-download-btn", "index": ALL}, "n_clicks"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _download_item_file(_n: Any, store_data: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None or not isinstance(store_data, dict):
        return dash.no_update, dash.no_update
    row = next(
        (r for r in (store_data.get("rows") or []) if int(r["item_id"]) == int(triggered["index"])),
        None,
    )
    if row is None or not row.get("current_run_id"):
        return dash.no_update, dash.no_update
    run_id = int(row["current_run_id"])
    res = export_run(ctx, run_id)
    if not res.ok or not res.data:
        return dash.no_update, alert_box(res.message or "Không xuất được file.", tone="crit")
    f_path = Path(str(res.data["export_path"])).resolve()
    return dcc.send_file(str(f_path), filename=f"ReconHub_Run_{run_id}.xlsx"), dash.no_update  # type: ignore[attr-defined,no-untyped-call]


@callback(
    Output("brr-download", "data", allow_duplicate=True),
    Output("brr-zip-list", "children"),
    Output("brr-alert", "children", allow_duplicate=True),
    Input("brr-zip-btn", "n_clicks"),
    State("brr-run-id", "data"),
    prevent_initial_call=True,
)
def _download_zip(_n: Any, run_id: Any) -> tuple[Any, Any, Any]:
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, dash.no_update
    res = build_zip(ctx, int(run_id))
    if not res.ok or not res.data:
        return dash.no_update, dash.no_update, alert_box(res.message or "Không tạo được file .zip.", tone="crit")
    zip_path = Path(str(res.data["zip_path"])).resolve()
    names: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
    except Exception:
        names = []
    return (
        dcc.send_file(str(zip_path), filename=str(res.data["file_name"])),  # type: ignore[attr-defined,no-untyped-call]
        render_zip_file_list(names),
        alert_box(
            "Đã tạo file .zip." + (" (dùng lại file đã tạo trước đó)" if res.data.get("cached") else ""), tone="info"
        ),
    )


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-alert", "children", allow_duplicate=True),
    Input("brr-mark-checked-btn", "n_clicks"),
    State({"type": "brr-select-cb", "index": ALL}, "checked"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _mark_checked_selected(_n: Any, _checked: Any, store_data: Any) -> tuple[Any, Any]:
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, dash.no_update
    run_ids = _selected_child_run_ids(store_data, _checked)
    if not run_ids:
        return dash.no_update, alert_box("Chọn ít nhất một mục có run để đánh dấu kiểm tra.", tone="warn")
    errors: list[str] = []
    done = 0
    for run_id in run_ids:
        res = mark_checked(ctx, run_id)
        if res.ok:
            done += 1
        else:
            errors.append(f"Run #{run_id}: {res.message or res.code}")
    run = (store_data or {}).get("run") or {}
    reloaded = _load_matrix_data(int(run.get("id", 0))) if run.get("id") else store_data
    if errors:
        return reloaded, alert_box(f"Đã đánh dấu {done} run. Lỗi: {'; '.join(errors)}", tone="warn")
    return reloaded, alert_box(f"Đã đánh dấu kiểm tra {done} run.", tone="info")


@callback(
    Output("brr-purge-modal", "opened"),
    Input("brr-purge-btn", "n_clicks"),
    Input("brr-purge-modal-cancel", "n_clicks"),
    State("brr-purge-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_purge_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    return not opened


@callback(
    Output("brr-store", "data", allow_duplicate=True),
    Output("brr-alert", "children", allow_duplicate=True),
    Output("brr-purge-modal", "opened", allow_duplicate=True),
    Input("brr-purge-modal-confirm", "n_clicks"),
    State("brr-purge-modal-input", "value"),
    State({"type": "brr-select-cb", "index": ALL}, "checked"),
    State("brr-store", "data"),
    prevent_initial_call=True,
)
def _purge_selected(_n: Any, confirm_text: Any, _checked: Any, store_data: Any) -> tuple[Any, Any, bool]:
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, dash.no_update, False
    if (confirm_text or "") != "XOA":
        return dash.no_update, alert_box("Gõ đúng XOA để xác nhận xóa dữ liệu tạm.", tone="warn"), True
    run_ids = _selected_child_run_ids(store_data, _checked)
    if not run_ids:
        return dash.no_update, alert_box("Chọn ít nhất một mục có run để xóa dữ liệu tạm.", tone="warn"), True
    res = purge_runs(ctx, run_ids)
    if not res.ok:
        return dash.no_update, alert_box(res.message or "Không xóa được dữ liệu tạm.", tone="crit"), True
    run = (store_data or {}).get("run") or {}
    reloaded = _load_matrix_data(int(run.get("id", 0))) if run.get("id") else store_data
    return reloaded, alert_box(f"Đã xóa dữ liệu tạm của {len(run_ids)} run.", tone="info"), False
