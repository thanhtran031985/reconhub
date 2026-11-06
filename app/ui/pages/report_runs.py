"""Trang Lịch sử báo cáo — task 27 bước 2, prototype Screen16 v-history."""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

from app.core.session import get_current_ctx
from app.services.perm import page_gate
from app.services.report_export import list_exports
from app.services.report_run import (
    create_report_run,
    execute_report_run,
    get_report_run,
    list_report_runs,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.empty_state import empty_state

try:
    dash.register_page(__name__, path="/report-runs", title="Lịch sử báo cáo – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "report_history"


def _status_badge(status: str) -> dmc.Badge:
    color = {
        "DONE": "green",
        "FAILED": "red",
        "RUNNING": "blue",
        "QUEUED": "gray",
        "CANCELLED": "gray",
    }.get(status, "gray")
    label = {
        "DONE": "Hoàn tất",
        "FAILED": "Lỗi",
        "RUNNING": "Đang chạy",
        "QUEUED": "Đang chờ",
        "CANCELLED": "Đã hủy",
    }.get(status, status)
    return dmc.Badge(label, color=color, variant="light")


def render_runs_table(
    runs: list[dict[str, Any]], exports_by_run: dict[int, list[dict[str, Any]]]
) -> Any:
    """Bảng lịch sử run + file export + hành động."""
    if not runs:
        return empty_state(
            "Chưa có run nào.",
            "Chạy một báo cáo ở Trung tâm báo cáo để xem lịch sử tại đây.",
        )
    header = dmc.TableTr(
        [
            dmc.TableTh("Run"),
            dmc.TableTh("Báo cáo"),
            dmc.TableTh("Người chạy"),
            dmc.TableTh("Dòng"),
            dmc.TableTh("Trạng thái"),
            dmc.TableTh("Thời gian"),
            dmc.TableTh("File"),
            dmc.TableTh(""),
        ]
    )
    body = []
    for run in runs:
        run_id = int(run["id"])
        exports = exports_by_run.get(run_id, [])
        done = [e for e in exports if e["status"] == "DONE"]
        file_cell: Any = "—"
        if done:
            latest = done[0]
            file_cell = dcc.Link(
                "Tải file",
                href=f"/download/report-export/{latest['id']}",
                target="_blank",
            )
        body.append(
            dmc.TableTr(
                [
                    dmc.TableTd(f"#{run_id}"),
                    dmc.TableTd(str(run.get("report_code") or run["report_id"])),
                    dmc.TableTd(str(run.get("created_by", ""))),
                    dmc.TableTd(
                        str(run.get("row_count") if run.get("row_count") is not None else "—"),
                        style={"textAlign": "right"},
                    ),
                    dmc.TableTd(_status_badge(str(run["status"]))),
                    dmc.TableTd(str(run.get("created_at") or "")),
                    dmc.TableTd(file_cell),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dcc.Link(
                                    dmc.Button("Xem", size="xs", variant="subtle"),
                                    href=f"/reports/{run['report_id']}?run={run_id}",
                                ),
                                dmc.Button(
                                    "Chạy lại",
                                    size="xs",
                                    variant="subtle",
                                    id={"type": "runs-rerun-btn", "index": run_id},
                                    **{"aria-label": f"Chạy lại run {run_id}"},
                                ),
                            ],
                            gap="xs",
                        )
                    ),
                ]
            )
        )
    return dmc.ScrollArea(
        dmc.Table(
            [dmc.TableThead(header), dmc.TableTbody(body)],
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
        ),
        h=520,
    )


def layout() -> html.Div:
    """Giao diện chính màn hình Lịch sử báo cáo."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="report-runs-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem lịch sử báo cáo.", tone="crit"),
            ]
        )
    runs: list[dict[str, Any]] = []
    total = 0
    exports_by_run: dict[int, list[dict[str, Any]]] = {}
    if ctx:
        try:
            res = list_report_runs(ctx, page=1, page_size=50)
            if res.ok and isinstance(res.data, dict):
                runs = res.data.get("runs", [])
                total = int(res.data.get("total", 0))
                for run in runs:
                    e_res = list_exports(ctx, run_id=int(run["id"]))
                    if e_res.ok and isinstance(e_res.data, dict):
                        exports_by_run[int(run["id"])] = e_res.data.get("exports", [])
        except Exception:
            runs = []
    return html.Div(
        [
            dcc.Store(id="report-runs-page-store", data=1),
            html.Div(id="report-runs-alert"),
            dmc.Stack(
                [
                    dmc.Title("Lịch sử báo cáo", order=1),
                    dmc.Text(
                        "Admin thấy tất cả; người dùng thường chỉ thấy run của mình.",
                        c="dimmed",
                    ),
                    dcc.Loading(
                        id="report-runs-loading",
                        type="circle",
                        children=html.Div(
                            id="report-runs-table-container",
                            children=render_runs_table(runs, exports_by_run),
                        ),
                    ),
                    dmc.Group(
                        [
                            dmc.Pagination(
                                id="report-runs-pagination",
                                total=max(1, (total + 49) // 50),
                                value=1,
                                size="sm",
                            ),
                        ],
                        justify="center",
                        mt="md",
                    ),
                ],
                gap="lg",
                p="lg",
            ),
        ]
    )


@callback(
    Output("report-runs-table-container", "children"),
    Output("report-runs-pagination", "total"),
    Input("report-runs-pagination", "value"),
    State("report-runs-page-store", "data"),
)
def handle_runs_page(
    page_no: int | None, _current: int | None
) -> tuple[Any, int]:
    """Chuyển trang lịch sử."""
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    page = int(page_no or 1)
    res = list_report_runs(ctx, page=page, page_size=50)
    if not res.ok or not isinstance(res.data, dict):
        return alert_box(res.message or "Không tải được lịch sử.", tone="crit"), 1
    runs = res.data.get("runs", [])
    total = int(res.data.get("total", 0))
    exports_by_run: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        e_res = list_exports(ctx, run_id=int(run["id"]))
        if e_res.ok and isinstance(e_res.data, dict):
            exports_by_run[int(run["id"])] = e_res.data.get("exports", [])
    return render_runs_table(runs, exports_by_run), max(1, (total + 49) // 50)


@callback(
    Output("report-runs-alert", "children"),
    Input({"type": "runs-rerun-btn", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_rerun(n_clicks: list[int | None] | None) -> Any:
    """Chạy lại với tham số cũ (Q4): tạo run mới rồi báo link xem."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    try:
        run_id = int(triggered_id["index"])
    except (TypeError, ValueError):
        raise PreventUpdate from None
    orig = get_report_run(ctx, run_id)
    if not orig.ok or not isinstance(orig.data, dict):
        return alert_box(orig.message or "Không tìm thấy run gốc.", tone="crit")
    created = create_report_run(
        ctx,
        int(orig.data["report_id"]),
        template_id=int(orig.data["template_id"]),
        values=dict(orig.data.get("params") or {}),
    )
    if not created.ok or not isinstance(created.data, dict):
        return alert_box(created.message or "Không tạo được run mới.", tone="crit")
    new_id = int(created.data["id"])
    executed = execute_report_run(ctx, new_id)
    if not executed.ok:
        return alert_box(executed.message or "Chạy lại lỗi.", tone="crit")
    return alert_box(
        "Đã chạy lại xong.",
        dcc.Link(
            "Xem kết quả",
            href=f"/reports/{orig.data['report_id']}?run={new_id}",
        ),
        tone="ok",
    )
