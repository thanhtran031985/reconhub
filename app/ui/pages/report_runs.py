"""Trang Lịch sử báo cáo — task 27 bước 2, prototype Screen16 v-history.

Task 43: tên + nhóm báo cáo, cột tham số, bắt đầu/kết thúc/tổng (giây),
dòng format dấu phẩy, icon tải file, bỏ nút Xem, chạy lại qua viewer
(?rerun_from=), lọc theo ngày/nhóm/tên/người chạy, chọn cỡ trang.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.services.perm import is_admin, page_gate
from app.services.report_export import (
    cancel_export,
    delete_export,
    list_exports,
    rerun_and_export,
    retry_export,
)
from app.services.report_run import list_report_runs, list_run_creators
from app.ui.components.alert_box import alert_box
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header
from app.ui.formatters import format_datetime

try:
    dash.register_page(__name__, path="/report-runs", title="Lịch sử báo cáo – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "report_history"
PAGE_SIZE_OPTIONS = [20, 50, 100]
DEFAULT_PAGE_SIZE = 50

# Nhãn nhóm — cùng map với CATEGORY_LABELS ở /report-admin; mã không có
# trong map (vd "FIN") hiện nguyên mã.
CATEGORY_LABELS: dict[str, str] = {
    "FINANCE": "Tài chính",
    "ACCOUNTING": "Kế toán",
    "OPERATIONS": "Vận hành",
}


def _category_label(code: Any) -> str:
    if code is None or str(code) == "":
        return "—"
    return CATEGORY_LABELS.get(str(code), str(code))


def _fmt_row_count(value: Any) -> str:
    """Dòng format dấu phẩy theo yêu cầu task 43: 14585 → 14,585."""
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _fmt_duration(created: Any, finished: Any) -> str:
    """Tổng thời gian chạy (cả chờ + chạy) theo giây, 1 chữ số thập phân."""
    start = _as_datetime(created)
    end = _as_datetime(finished)
    if start is None or end is None:
        return "—"
    seconds = (end - start).total_seconds()
    return f"{seconds:.1f}".replace(".", ",") + " giây"


def _fmt_param_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return str(value)
    text = str(value)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return text


def _fmt_params(params: Any) -> str:
    """Tham số đã chạy dạng gọn `mã=giá trị`, nối bằng ' · '."""
    if not isinstance(params, dict) or not params:
        return "—"
    return " · ".join(f"{code}={_fmt_param_value(value)}" for code, value in params.items())


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


def _export_action_cell(
    label: str,
    export: dict[str, Any],
    retry: bool = False,
    cancel: bool = False,
    can_delete: bool = False,
) -> Any:
    """Ô File khi export chưa xong (task 52): trạng thái + nút Thử lại/Hủy/Xóa."""
    children: list[Any] = [dmc.Text(label, size="xs", c="red" if retry else "dimmed")]
    if retry:
        children.append(
            dmc.Button(
                "Thử lại",
                id={"type": "report-runs-export-retry", "index": int(export["id"])},
                size="xs",
                variant="subtle",
            )
        )
    if cancel:
        children.append(
            dmc.Button(
                "Hủy",
                id={"type": "report-runs-export-cancel", "index": int(export["id"])},
                size="xs",
                variant="subtle",
            )
        )
    if can_delete:
        children.append(
            dmc.Button(
                "Xóa",
                id={"type": "report-runs-export-delete", "index": int(export["id"])},
                size="xs",
                variant="subtle",
                color="red",
            )
        )
    return dmc.Group(children, gap=4)


def _export_delete_button(export_id: int) -> Any:
    """Nút Xóa file export (chỉ ADMIN, task 52)."""
    return dmc.Button(
        "Xóa",
        id={"type": "report-runs-export-delete", "index": int(export_id)},
        size="xs",
        variant="subtle",
        color="red",
    )


def render_runs_table(
    runs: list[dict[str, Any]],
    exports_by_run: dict[int, list[dict[str, Any]]],
    can_delete: bool = False,
) -> Any:
    """Bảng lịch sử run + file export + hành động."""
    if not runs:
        return empty_state(
            "Chưa có run nào.",
            "Chạy một báo cáo ở Trung tâm báo cáo để xem lịch sử tại đây.",
        )
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--p2, #FAFAFA)",
        "zIndex": 1,
        "height": "34px",
        "fontSize": "12px",
        "fontWeight": 600,
    }
    header = dmc.TableTr(
        [
            dmc.TableTh("Run", style=th_style),
            dmc.TableTh("Báo cáo", style=th_style),
            dmc.TableTh("Nhóm", style=th_style),
            dmc.TableTh("Người chạy", style=th_style),
            dmc.TableTh("Dòng", style=th_style),
            dmc.TableTh("Tham số", style=th_style),
            dmc.TableTh("Trạng thái", style=th_style),
            dmc.TableTh("Bắt đầu", style=th_style),
            dmc.TableTh("Kết thúc", style=th_style),
            dmc.TableTh("Tổng", style=th_style),
            dmc.TableTh("File", style=th_style),
            dmc.TableTh("", style=th_style),
        ]
    )
    body = []
    for run in runs:
        run_id = int(run["id"])
        exports = exports_by_run.get(run_id, [])
        # Task 52: hiện trạng thái export mới nhất (không chỉ file DONE).
        file_cell: Any = "—"
        if exports:
            latest = exports[0]
            latest_status = str(latest.get("status") or "")
            if latest_status == "DONE":
                download = dmc.Tooltip(
                    label="Tải file Excel",
                    children=dcc.Link(
                        dmc.Group(
                            [
                                DashIconify(icon="lucide:file-spreadsheet", width=18, color="green"),
                                DashIconify(icon="lucide:arrow-down", width=14),
                            ],
                            gap=2,
                        ),
                        href=f"/download/report-export/{latest['id']}",
                        target="_blank",
                        # Giữ vùng bấm tối thiểu khi icon chưa tải xong (CDN chậm).
                        style={"display": "inline-flex", "minWidth": "36px", "minHeight": "28px", "alignItems": "center"},
                    ),
                )
                file_cell = (
                    dmc.Group([download, _export_delete_button(int(latest["id"]))], gap=4)
                    if can_delete
                    else download
                )
            elif latest_status == "QUEUED":
                file_cell = _export_action_cell("Đang chờ", latest, cancel=True)
            elif latest_status == "RUNNING":
                file_cell = _export_action_cell(
                    f"Đang xuất {int(latest.get('progress_pct') or 0)}%", latest, cancel=True
                )
            elif latest_status == "FAILED":
                file_cell = _export_action_cell("Lỗi", latest, retry=True, can_delete=can_delete)
            elif latest_status == "CANCELLED":
                file_cell = dmc.Text("Đã hủy", size="xs", c="dimmed")
        params_text = _fmt_params(run.get("params"))
        body.append(
            dmc.TableTr(
                [
                    dmc.TableTd(f"#{run_id}", style={"height": "34px"}),
                    dmc.TableTd(
                        str(run.get("report_name") or run.get("report_code") or run["report_id"]),
                        style={"height": "34px"},
                    ),
                    dmc.TableTd(_category_label(run.get("category_code")), style={"height": "34px"}),
                    dmc.TableTd(str(run.get("created_by", "")), style={"height": "34px"}),
                    dmc.TableTd(
                        _fmt_row_count(run.get("row_count")),
                        style={"textAlign": "right", "height": "34px"},
                    ),
                    dmc.TableTd(
                        html.Div(
                            params_text,
                            title=params_text,
                            style={
                                "maxWidth": "260px",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "whiteSpace": "nowrap",
                                "fontSize": "12px",
                            },
                        ),
                        style={"height": "34px"},
                    ),
                    dmc.TableTd(_status_badge(str(run["status"])), style={"height": "34px"}),
                    dmc.TableTd(format_datetime(run.get("created_at")), style={"height": "34px"}),
                    dmc.TableTd(format_datetime(run.get("finished_at")), style={"height": "34px"}),
                    dmc.TableTd(
                        _fmt_duration(run.get("created_at"), run.get("finished_at")),
                        style={"textAlign": "right", "height": "34px"},
                    ),
                    dmc.TableTd(file_cell, style={"height": "34px"}),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dcc.Link(
                                    dmc.Button(
                                        "Chạy lại",
                                        size="xs",
                                        variant="subtle",
                                        leftSection=DashIconify(icon="lucide:play-circle", width=14),
                                    ),
                                    href=f"/reports/{run['report_id']}?rerun_from={run_id}",
                                ),
                                dmc.Button(
                                    "Xuất lại",
                                    id={"type": "report-runs-rerun-export", "index": run_id},
                                    size="xs",
                                    variant="subtle",
                                    leftSection=DashIconify(icon="lucide:download", width=14),
                                ),
                            ],
                            gap=4,
                        ),
                        style={"height": "34px"},
                    ),
                ]
            )
        )
    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=1100,
            style={"height": "100%", "overflow": "auto"},
            children=dmc.Table(
                [dmc.TableThead(header), dmc.TableTbody(body)],
                striped=True,
                highlightOnHover=True,
                withTableBorder=False,
                style={"fontSize": "13px"},
            ),
        ),
        withBorder=True,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "overflow": "hidden", "display": "flex", "flexDirection": "column"},
    )


def _filters_to_kwargs(
    from_date: str | None,
    to_date: str | None,
    category: str | None,
    name: str | None,
    runner: str | None,
) -> dict[str, Any]:
    """Giá trị lọc từ form → tham số service ("all"/rỗng = không lọc)."""
    return {
        "from_date": from_date or None,
        "to_date": to_date or None,
        "category_code": None if category in (None, "", "all") else category,
        "report_name": (name or "").strip() or None,
        "created_by": None if runner in (None, "", "all") else runner,
    }


def _load_page_data(
    ctx: Any, page: int, page_size: int, filters: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, dict[int, list[dict[str, Any]]]]:
    """Nạp 1 trang lịch sử + exports theo run (dùng chung layout/callback)."""
    res = list_report_runs(ctx, page=page, page_size=page_size, **filters)
    if not res.ok or not isinstance(res.data, dict):
        raise ValueError(res.message or "Không tải được lịch sử.")
    runs = res.data.get("runs", [])
    total = int(res.data.get("total", 0))
    exports_by_run: dict[int, list[dict[str, Any]]] = {}
    for run in runs:
        e_res = list_exports(ctx, run_id=int(run["id"]))
        if e_res.ok and isinstance(e_res.data, dict):
            exports_by_run[int(run["id"])] = e_res.data.get("exports", [])
    return runs, total, exports_by_run


def _runs_fingerprint(
    runs: list[dict[str, Any]],
    exports_by_run: dict[int, list[dict[str, Any]]],
    total: int,
    page: int,
) -> str:
    """Dấu vân tay của dữ liệu đang hiện trên bảng Lịch sử (task 53).

    Chỉ gồm những gì bảng hiện: tổng số run, trang, mỗi run
    (id/trạng thái/số dòng/bắt đầu/kết thúc) và mỗi export của run
    (id/trạng thái/% tiến trình). Tên/nhóm/tham số không đổi sau khi tạo
    nên không cần đưa vào. Hai lần tải giống nhau cho cùng một chuỗi.
    """
    parts = [f"total={total}", f"page={page}"]
    for run in runs:
        parts.append(
            f"r{run.get('id')}:{run.get('status')}:{run.get('row_count')}:"
            f"{run.get('created_at')}:{run.get('finished_at')}"
        )
        for exp in exports_by_run.get(int(run["id"]), []):
            parts.append(
                f"e{exp.get('id')}:{exp.get('status')}:{exp.get('progress_pct')}"
            )
    return "|".join(parts)


def _category_options() -> list[dict[str, str]]:
    return [{"label": "Tất cả nhóm", "value": "all"}] + [
        {"label": label, "value": code} for code, label in CATEGORY_LABELS.items()
    ]


def _runner_options(ctx: Any) -> list[dict[str, str]]:
    try:
        res = list_run_creators(ctx)
    except Exception:
        return [{"label": "Tất cả người chạy", "value": "all"}]
    if not res.ok or not isinstance(res.data, list):
        return [{"label": "Tất cả người chạy", "value": "all"}]
    return [{"label": "Tất cả người chạy", "value": "all"}] + [
        {"label": str(name), "value": str(name)} for name in res.data
    ]


def layout() -> Any:
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
    creators: list[dict[str, str]] = [{"label": "Tất cả người chạy", "value": "all"}]
    if ctx:
        try:
            creators = _runner_options(ctx)
            runs, total, exports_by_run = _load_page_data(ctx, 1, DEFAULT_PAGE_SIZE, {})
        except Exception:
            runs = []
    return dmc.Box(
        [
            dcc.Store(id="report-runs-page-store", data=1),
            dcc.Store(id="report-runs-refresh-store", data=0),
            dcc.Store(id="report-runs-action-clicks", data={}),
            # Task 53: vân tay dữ liệu đang hiện — tick tự động chỉ vẽ lại
            # bảng khi vân tay đổi, không thì giữ nguyên (khỏi mất vị trí cuộn).
            dcc.Store(id="report-runs-fingerprint", data=""),
            # Task 52: tự làm mới mỗi 10s để thấy export chạy ngầm xong.
            dcc.Interval(id="report-runs-auto-refresh", interval=10000, n_intervals=0),
            html.Div(id="report-runs-alert", **{"aria-live": "polite"}),  # type: ignore[arg-type]
            page_header(
                title="Lịch sử báo cáo",
                subtitle="Admin thấy tất cả; người dùng thường chỉ thấy run của mình.",
            ),
            command_bar(
                search_id="report-runs-filter-name",
                search_placeholder="Tìm tên báo cáo...",
                filters=[
                    dmc.DateInput(
                        id="report-runs-filter-from",
                        placeholder="Từ ngày",
                        # Task 45: value "" ngay từ đầu — không có value
                        # thì ô là uncontrolled, callback trả "" sẽ thành
                        # controlled và React cảnh báo.
                        value="",
                        valueFormat="YYYY-MM-DD",
                        size="xs",
                        w=140,
                        styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                    ),
                    dmc.DateInput(
                        id="report-runs-filter-to",
                        placeholder="Đến ngày",
                        value="",
                        valueFormat="YYYY-MM-DD",
                        size="xs",
                        w=140,
                        styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                    ),
                    dmc.Select(
                        id="report-runs-filter-category",
                        data=_category_options(),
                        value="all",
                        size="xs",
                        w=150,
                        styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                    ),
                    dmc.Select(
                        id="report-runs-filter-runner",
                        data=creators,
                        value="all",
                        size="xs",
                        w=150,
                        styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                    ),
                ],
                actions=[
                    dmc.Button(
                        "Làm mới",
                        id="report-runs-refresh-btn",
                        size="xs",
                        variant="subtle",
                    ),
                    dmc.Button(
                        "Xóa lọc",
                        id="report-runs-clear-btn",
                        size="xs",
                        variant="subtle",
                    ),
                ],
            ),
            dcc.Loading(
                id="report-runs-loading",
                type="circle",
                # Như viewer (task 39): style của Loading đi vào lớp phủ
                # spinner, khung ngoài co giãn phải dùng parent_style —
                # nếu không khối Loading cao theo nội dung và đẩy phân
                # trang ra khỏi khung, bị overflow:hidden cắt mất.
                parent_style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
                children=html.Div(
                    id="report-runs-table-container",
                    style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
                    children=render_runs_table(
                        runs,
                        exports_by_run,
                        can_delete=bool(ctx and is_admin(ctx, get_recon_engine())),
                    ),
                ),
            ),
            dmc.Group(
                [
                    dmc.Text(
                        f"Tổng {total} run",
                        id="report-runs-total-text",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Select(
                        id="report-runs-page-size",
                        data=[{"label": f"{n} dòng/trang", "value": str(n)} for n in PAGE_SIZE_OPTIONS],
                        value=str(DEFAULT_PAGE_SIZE),
                        size="xs",
                        w=130,
                    ),
                    dmc.Pagination(
                        id="report-runs-pagination",
                        total=max(1, (total + DEFAULT_PAGE_SIZE - 1) // DEFAULT_PAGE_SIZE),
                        value=1,
                        size="xs",
                    ),
                ],
                justify="center",
                gap="md",
                mt="xs",
            ),
        ],
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "10px",
        },
    )


@callback(
    Output("report-runs-table-container", "children"),
    Output("report-runs-pagination", "total"),
    Output("report-runs-total-text", "children"),
    Output("report-runs-pagination", "value"),
    Output("report-runs-filter-from", "value"),
    Output("report-runs-filter-to", "value"),
    Output("report-runs-filter-category", "value"),
    Output("report-runs-filter-name", "value"),
    Output("report-runs-filter-runner", "value"),
    Output("report-runs-fingerprint", "data"),
    Input("report-runs-pagination", "value"),
    Input("report-runs-page-size", "value"),
    Input("report-runs-filter-from", "value"),
    Input("report-runs-filter-to", "value"),
    Input("report-runs-filter-category", "value"),
    Input("report-runs-filter-name", "value"),
    Input("report-runs-filter-runner", "value"),
    Input("report-runs-clear-btn", "n_clicks"),
    Input("report-runs-auto-refresh", "n_intervals"),
    Input("report-runs-refresh-btn", "n_clicks"),
    Input("report-runs-refresh-store", "data"),
    State("report-runs-page-store", "data"),
    State("report-runs-fingerprint", "data"),
)
def handle_runs_refresh(
    page_no: int | None,
    page_size: str | None,
    from_date: str | None,
    to_date: str | None,
    category: str | None,
    name: str | None,
    runner: str | None,
    _clear_clicks: int | None,
    _current: int | None,
    _auto_n: int | None = None,
    _refresh_clicks: int | None = None,
    _refresh_store: int | None = None,
    _page_store: int | None = None,
    last_fingerprint: str | None = None,
) -> tuple[Any, ...]:
    """Chuyển trang / đổi cỡ trang / lọc lịch sử (đổi lọc → về trang 1).

    Task 53: tick tự động 10s chỉ vẽ lại bảng khi dữ liệu thật sự đổi
    (vân tay mới khác vân tay đã lưu) — không đổi thì trả no_update cho
    toàn bộ output, bảng giữ nguyên, không mất vị trí cuộn. Mọi trigger
    khác (lọc, phân trang, "Làm mới", refresh-store sau hành động export)
    luôn vẽ lại như cũ.
    """
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    triggered = dash.callback_context.triggered_id
    if triggered == "report-runs-clear-btn":
        from_date, to_date, category, name, runner = None, None, "all", "", "all"
        page = 1
    elif triggered in (
        "report-runs-page-size",
        "report-runs-filter-from",
        "report-runs-filter-to",
        "report-runs-filter-category",
        "report-runs-filter-name",
        "report-runs-filter-runner",
    ):
        page = 1
    else:
        page = int(page_no or 1)
    size = int(page_size or DEFAULT_PAGE_SIZE)
    if size not in PAGE_SIZE_OPTIONS:
        size = DEFAULT_PAGE_SIZE
    filters = _filters_to_kwargs(from_date, to_date, category, name, runner)
    try:
        runs, total, exports_by_run = _load_page_data(ctx, page, size, filters)
    except ValueError as exc:
        return (
            alert_box(str(exc), tone="crit"),
            1,
            "Tổng 0 run",
            page,
            # Task 45: "" thay vì None — None gây cảnh báo React
            # "value should not be null" ở ô lọc ngày.
            from_date or "",
            to_date or "",
            category or "all",
            name or "",
            runner or "all",
            dash.no_update,
        )
    fingerprint = _runs_fingerprint(runs, exports_by_run, total, page)
    if triggered == "report-runs-auto-refresh" and fingerprint == (last_fingerprint or ""):
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    return (
        render_runs_table(
            runs,
            exports_by_run,
            can_delete=is_admin(ctx, get_recon_engine()),
        ),
        max(1, (total + size - 1) // size),
        f"Tổng {total} run",
        page,
        from_date or "",
        to_date or "",
        category or "all",
        name or "",
        runner or "all",
        fingerprint,
    )


def _do_export_action(ctx: Any, kind: str, item_id: int, refresh: int | None) -> tuple[Any, Any]:
    """Logic thuần cho 4 nút hành động export (task 52) — không phụ thuộc
    callback context nên test gọi trực tiếp được."""
    if kind == "report-runs-export-retry":
        res = retry_export(ctx, item_id)
        ok_msg, err_msg = "Đã đưa export vào hàng đợi.", "Không thử lại được export."
    elif kind == "report-runs-export-cancel":
        res = cancel_export(ctx, item_id)
        ok_msg, err_msg = "Đã hủy export.", "Không hủy được export."
    elif kind == "report-runs-export-delete":
        res = delete_export(ctx, item_id)
        ok_msg, err_msg = "Đã xóa file export.", "Không xóa được file export."
    elif kind == "report-runs-rerun-export":
        res = rerun_and_export(ctx, item_id)
        if res.ok and isinstance(res.data, dict):
            ok_msg = (
                f"Đã tạo run mới #{res.data['run_id']} và đưa export vào hàng đợi chạy ngầm."
            )
        else:
            ok_msg = "Đã tạo run mới và đưa export vào hàng đợi chạy ngầm."
        err_msg = "Không xuất lại được."
    else:
        raise PreventUpdate
    if not res.ok:
        return notify_error(res.message or err_msg), dash.no_update
    return notify_success(ok_msg), (refresh or 0) + 1


def _action_click_map() -> dict[str, int]:
    """Map nút hành động → số lần bấm hiện tại (đọc từ inputs_list).

    Dùng để phân biệt bấm thật với callback bị kích lại do bảng render lại
    (ALL inputs đổi khi tập nút thay đổi): chỉ bấm thật mới tăng count.
    Ngoài callback context thì trả map rỗng.
    """
    current: dict[str, int] = {}
    try:
        groups = dash.callback_context.inputs_list
    except Exception:
        return current
    for group in groups or []:
        items = group if isinstance(group, list) else [group]
        for item in items:
            btn_id = (item or {}).get("id")
            if isinstance(btn_id, dict):
                key = f"{btn_id.get('type')}:{btn_id.get('index')}"
                current[key] = int((item or {}).get("value") or 0)
    return current


@callback(
    Output("report-runs-alert", "children"),
    Output("report-runs-refresh-store", "data"),
    Output("report-runs-action-clicks", "data"),
    Input({"type": "report-runs-export-retry", "index": ALL}, "n_clicks"),
    Input({"type": "report-runs-export-cancel", "index": ALL}, "n_clicks"),
    Input({"type": "report-runs-export-delete", "index": ALL}, "n_clicks"),
    Input({"type": "report-runs-rerun-export", "index": ALL}, "n_clicks"),
    State("report-runs-refresh-store", "data"),
    State("report-runs-action-clicks", "data"),
    prevent_initial_call=True,
)
def handle_export_action(
    _retry_clicks: list[int | None] | None,
    _cancel_clicks: list[int | None] | None,
    _delete_clicks: list[int | None] | None,
    _rerun_clicks: list[int | None] | None,
    refresh: int | None,
    last_clicks: dict[str, int] | None,
) -> tuple[Any, Any, dict[str, int]]:
    """Một callback duy nhất cho 4 nút hành động export (task 52, D8).

    Dùng ALL + triggered_id thay vì 4 callback MATCH riêng: Dash không cho
    nhiều callback MATCH cùng ghi 1 output ("Overlapping wildcard callback
    outputs" khiến cả app không mount được). Guard bằng map số lần bấm:
    ALL inputs đổi mỗi khi bảng render lại (tập nút thay đổi) nên callback
    bị kích lại mà không có bấm thật — chỉ hành động khi nút trigger tăng
    count so với lần trước; lần kích lại chỉ reset map về count hiện tại.
    """
    current_map = _action_click_map()
    triggered = dash.callback_context.triggered_id
    if isinstance(triggered, dict):
        key = f"{triggered.get('type')}:{triggered.get('index')}"
        prev = (last_clicks or {}).get(key, 0)
        if current_map.get(key, 0) > prev:
            ctx = get_current_ctx()
            if ctx is not None:
                alert, new_refresh = _do_export_action(
                    ctx, str(triggered.get("type")), int(triggered["index"]), refresh
                )
                return alert, new_refresh, current_map
    return dash.no_update, dash.no_update, current_map
