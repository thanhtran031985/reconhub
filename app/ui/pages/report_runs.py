"""Trang Lịch sử báo cáo — task 27 bước 2, prototype Screen16 v-history.

Task 43: tên + nhóm báo cáo, cột tham số, bắt đầu/kết thúc/tổng (giây),
dòng format dấu phẩy, icon tải file, bỏ nút Xem, chạy lại qua viewer
(?rerun_from=), lọc theo ngày/nhóm/tên/người chạy, chọn cỡ trang.
Task 55: bảng chuyển sang AG Grid (getRowId + rowData) — tick chỉ cập
nhật dòng đổi tại chỗ, nút bấm trong cell đi qua cellClicked.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate

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
from app.ui.components.data_grid import data_grid
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


_RUN_STATUS_LABELS: dict[str, str] = {
    "DONE": "Hoàn tất",
    "FAILED": "Lỗi",
    "RUNNING": "Đang chạy",
    "QUEUED": "Đang chờ",
    "CANCELLED": "Đã hủy",
}


def _runs_row_data(
    runs: list[dict[str, Any]],
    exports_by_run: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """1 run → 1 dòng rowData cho AG Grid (task 55).

    Các trường hiển thị đã format sẵn như bảng cũ (dấu phẩy, DD/MM/YYYY);
    `_export` là export mới nhất để renderer File/nút bấm đọc; `_report_id`
    để renderer link "Chạy lại" ghép URL.
    """
    rows: list[dict[str, Any]] = []
    for run in runs:
        run_id = int(run["id"])
        exports = exports_by_run.get(run_id, [])
        latest = exports[0] if exports else None
        rows.append(
            {
                "id": run_id,
                "run": f"#{run_id}",
                "report": str(run.get("report_name") or run.get("report_code") or run["report_id"]),
                "category": _category_label(run.get("category_code")),
                "runner": str(run.get("created_by", "")),
                "rows": _fmt_row_count(run.get("row_count")),
                "params": _fmt_params(run.get("params")),
                "status": _RUN_STATUS_LABELS.get(str(run["status"]), str(run["status"])),
                "status_code": str(run["status"]),
                "started": format_datetime(run.get("created_at")),
                "finished": format_datetime(run.get("finished_at")),
                "duration": _fmt_duration(run.get("created_at"), run.get("finished_at")),
                "_export": (
                    {
                        "id": int(latest["id"]),
                        "status": str(latest.get("status") or ""),
                        "progress_pct": int(latest.get("progress_pct") or 0),
                    }
                    if latest
                    else None
                ),
                "_report_id": int(run["report_id"]),
            }
        )
    return rows


def _runs_grid_column_defs(can_delete: bool) -> list[dict[str, Any]]:
    """columnDefs cho grid Lịch sử (task 55).

    ``field`` của cột File/nút bấm là `_export` (dict export mới nhất):
    AG Grid chỉ vẽ lại cell khi giá trị của cột đổi — field "file" không
    có trong rowData nên cell không bao giờ đổi (task 55: đã kiểm chứng
    live, tick cập nhật rowData mà cell File vẫn "Đang chờ"). `colId`
    giữ tên riêng để cellClicked phân biệt nút nào được bấm.
    Cột Báo cáo/Tham số dùng flex để tổng chiều rộng vừa khung 1440px
    (nút hành động ở cuối vẫn thấy được, không phải cuộn ngang).
    Task 56: Tham số về cuối (sau Chạy lại); Bắt đầu/Kết thúc 140px
    (đủ "11/11/2026 13:09:56" ở font 12), Nhóm 80, Trạng thái 90 —
    tổng các cột trước Tham số ~1160px, vừa khung nội dung ~1208px ở
    viewport 1440 (nút cuối thấy được không cần cuộn ngang).
    """
    base: dict[str, Any] = {"sortable": False, "filter": False, "resizable": True}
    cols: list[dict[str, Any]] = [
        {"field": "run", "headerName": "Run", "width": 60, **base},
        {"field": "report", "headerName": "Báo cáo", "flex": 1, "minWidth": 130, **base},
        {"field": "category", "headerName": "Nhóm", "width": 80, **base},
        {"field": "runner", "headerName": "Người chạy", "width": 70, **base},
        {"field": "rows", "headerName": "Dòng", "width": 60, "cellStyle": {"textAlign": "right"}, **base},
        {"field": "status", "headerName": "Trạng thái", "width": 90, "cellRenderer": "reconRunsStatusCell", **base},
        {"field": "started", "headerName": "Bắt đầu", "width": 140, **base},
        {"field": "finished", "headerName": "Kết thúc", "width": 140, **base},
        {"field": "duration", "headerName": "Tổng", "width": 70, "cellStyle": {"textAlign": "right"}, **base},
        {"field": "_export", "colId": "file", "headerName": "File", "width": 110, "cellRenderer": "reconRunsFileCell", **base},
        {"field": "_export", "colId": "cancel", "headerName": "", "width": 60, "cellRenderer": "reconRunsActionCell", "cellRendererParams": {"action": "cancel"}, **base},
        {"field": "_export", "colId": "retry", "headerName": "", "width": 70, "cellRenderer": "reconRunsActionCell", "cellRendererParams": {"action": "retry"}, **base},
    ]
    if can_delete:
        cols.append(
            {"field": "_export", "colId": "delete", "headerName": "", "width": 60, "cellRenderer": "reconRunsActionCell", "cellRendererParams": {"action": "delete"}, **base}
        )
    cols.extend(
        [
            {"field": "_export", "colId": "rerun", "headerName": "", "width": 70, "cellRenderer": "reconRunsActionCell", "cellRendererParams": {"action": "rerun"}, **base},
            {"field": "id", "colId": "rerun_link", "headerName": "", "width": 70, "cellRenderer": "reconRunsRerunLink", **base},
            {"field": "params", "headerName": "Tham số", "flex": 2, "minWidth": 140, **base},
        ]
    )
    return cols


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
            # Task 55: AG Grid thay dmc.Table — tick chỉ đưa rowData mới,
            # grid tự diff theo getRowId và cập nhật dòng đổi tại chỗ
            # (không vẽ lại toàn bảng, không spinner, giữ vị trí cuộn).
            # Bỏ dcc.Loading quanh bảng (task 52) vì lý do đó.
            data_grid(
                id="report-runs-grid",
                columnDefs=_runs_grid_column_defs(
                    can_delete=bool(ctx and is_admin(ctx, get_recon_engine()))
                ),
                rowData=_runs_row_data(runs, exports_by_run),
                getRowId="params.data.id.toString()",
                # Task 56: class rh-runs-grid → font 12px (pattern task 40).
                className="ag-theme-quartz-auto-dark rh-runs-grid",
                dashGridOptions={
                    "overlayNoRowsTemplate": "Chưa có run nào. Chạy một báo cáo ở Trung tâm báo cáo để xem lịch sử tại đây."
                },
                container_style={"flex": 1, "minHeight": 0},
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
    Output("report-runs-grid", "rowData"),
    Output("report-runs-pagination", "total"),
    Output("report-runs-total-text", "children"),
    Output("report-runs-pagination", "value"),
    Output("report-runs-filter-from", "value"),
    Output("report-runs-filter-to", "value"),
    Output("report-runs-filter-category", "value"),
    Output("report-runs-filter-name", "value"),
    Output("report-runs-filter-runner", "value"),
    Output("report-runs-fingerprint", "data"),
    # Task 55: alert cũng do handle_grid_cell_clicked ghi — cho phép trùng
    # output (Dash sẽ gọi callback nào trigger trước).
    Output("report-runs-alert", "children", allow_duplicate=True),
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
    # Task 55: output alert trùng với handle_grid_cell_clicked nên phải
    # cho phép duplicate; "initial_duplicate" giữ nguyên lần gọi đầu
    # (tải bảng lúc mở trang).
    prevent_initial_call="initial_duplicate",
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

    Task 53: tick tự động 10s chỉ cập nhật grid khi dữ liệu thật sự đổi
    (vân tay mới khác vân tay đã lưu) — không đổi thì trả no_update cho
    toàn bộ output, grid giữ nguyên, không mất vị trí cuộn. Mọi trigger
    khác (lọc, phân trang, "Làm mới", refresh-store sau hành động export)
    luôn tải lại như cũ.
    Task 55: output đầu là rowData của AG Grid — grid tự diff theo
    getRowId và chỉ cập nhật dòng đổi tại chỗ.
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
            [],
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
            alert_box(str(exc), tone="crit"),
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
            dash.no_update,
        )
    return (
        _runs_row_data(runs, exports_by_run),
        max(1, (total + size - 1) // size),
        f"Tổng {total} run",
        page,
        from_date or "",
        to_date or "",
        category or "all",
        name or "",
        runner or "all",
        fingerprint,
        dash.no_update,
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


_CELL_CLICK_ACTIONS: dict[str, str] = {
    "cancel": "report-runs-export-cancel",
    "retry": "report-runs-export-retry",
    "delete": "report-runs-export-delete",
    "rerun": "report-runs-rerun-export",
}


@callback(
    Output("report-runs-alert", "children", allow_duplicate=True),
    Output("report-runs-refresh-store", "data"),
    Input("report-runs-grid", "cellClicked"),
    State("report-runs-grid", "rowData"),
    State("report-runs-refresh-store", "data"),
    prevent_initial_call=True,
)
def handle_grid_cell_clicked(
    clicked: dict[str, Any] | None,
    row_data: list[dict[str, Any]] | None,
    refresh: int | None,
) -> tuple[Any, Any]:
    """Click vào nút trong cell AG Grid (task 55) → hành động export.

    Spike đã chứng minh: cellClicked về được Dash với colId + rowId;
    setData/rowData KHÔNG đồng bộ về nên không dùng. Nút trong cell chỉ
    là hình thức — click nổi bọt lên cell. Guard theo trạng thái export
    để bấm vào ô trống (nút không hiện) thì im lặng, không báo lỗi.
    """
    if not isinstance(clicked, dict):
        raise PreventUpdate
    kind = _CELL_CLICK_ACTIONS.get(str(clicked.get("colId") or ""))
    if kind is None:
        raise PreventUpdate
    try:
        run_id = int(clicked.get("rowId") or 0)
    except (TypeError, ValueError):
        raise PreventUpdate from None
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    if kind == "report-runs-rerun-export":
        return _do_export_action(ctx, kind, run_id, refresh)
    row = next((r for r in (row_data or []) if int(r.get("id") or -1) == run_id), None)
    export = (row or {}).get("_export") or {}
    export_id = export.get("id")
    status = str(export.get("status") or "")
    if export_id is None:
        raise PreventUpdate
    if kind == "report-runs-export-cancel" and status not in ("QUEUED", "RUNNING"):
        raise PreventUpdate
    if kind == "report-runs-export-retry" and status != "FAILED":
        raise PreventUpdate
    if kind == "report-runs-export-delete" and status not in ("DONE", "FAILED", "CANCELLED"):
        raise PreventUpdate
    return _do_export_action(ctx, kind, int(export_id), refresh)
