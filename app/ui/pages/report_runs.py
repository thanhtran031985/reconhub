"""Trang Lịch sử báo cáo — task 27 bước 2, prototype Screen16 v-history.

Task 43: tên + nhóm báo cáo, cột tham số, bắt đầu/kết thúc/tổng (giây),
dòng format dấu phẩy, icon tải file, bỏ nút Xem, chạy lại qua viewer
(?rerun_from=), lọc theo ngày/nhóm/tên/người chạy, chọn cỡ trang.
Task 55: bảng chuyển sang AG Grid (getRowId + rowData) — tick chỉ cập
nhật dòng đổi tại chỗ, nút bấm trong cell đi qua cellClicked.
Task 57: các nút gom vào 1 cột "Hành động" (nút DMC có icon, bấm qua
cellRendererData); cột File giữ riêng (hiện tiến trình export).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, clientside_callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.services.perm import is_admin, page_gate
from app.services.report_export import (
    cancel_export,
    delete_export,
    list_exports_by_runs,
    rerun_and_export,
    retry_export,
)
from app.services.report_run import list_report_runs, list_run_creators
from app.ui.components.alert_box import alert_box
from app.ui.components.command_bar import command_bar
from app.ui.components.data_grid import data_grid
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header
from app.ui.components.saved_view_toolbar import saved_view_toolbar
from app.ui.formatters import format_datetime
from app.ui.layout_cache import cached_layout
from app.ui.swr import should_skip_swr_update

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

# Task 58: lọc theo trạng thái run (thứ tự theo vòng đời run).
_RUN_STATUS_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả trạng thái", "value": "all"},
    {"label": "Đang chờ", "value": "QUEUED"},
    {"label": "Đang chạy", "value": "RUNNING"},
    {"label": "Hoàn tất", "value": "DONE"},
    {"label": "Lỗi", "value": "FAILED"},
    {"label": "Đã hủy", "value": "CANCELLED"},
]


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

    ``field`` của cột File/Hành động là `_export` (dict export mới nhất):
    AG Grid chỉ vẽ lại cell khi giá trị của cột đổi — field "file" không
    có trong rowData nên cell không bao giờ đổi (task 55: đã kiểm chứng
    live, tick cập nhật rowData mà cell File vẫn "Đang chờ").
    Task 57: 5 cột nút riêng (cancel/retry/delete/rerun/rerun_link) gom
    thành 1 cột "Hành động" (renderer reconRunsActionsCell: nút DMC có
    icon, bấm gọi setData(action) → Dash đọc qua cellRendererData;
    "Chạy lại" chuyển trang trực tiếp bằng JS). Nút Xóa chỉ hiện khi
    can_delete (qua cellRendererParams). Width cột Hành động: 340 khi
    có Xóa (tối đa 4 nút: Thử lại+Xóa+Xuất lại+Chạy lại), 280 khi không.
    Cột Báo cáo/Tham số dùng flex để tổng chiều rộng vừa khung 1440px
    (nút hành động ở cuối vẫn thấy được, không phải cuộn ngang).
    Task 56: Tham số về cuối (sau Hành động); Bắt đầu/Kết thúc 140px
    (đủ "11/11/2026 13:09:56" ở font 12), Nhóm 80, Trạng thái 90.
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
        {
            "field": "_export",
            "colId": "actions",
            "headerName": "Hành động",
            "width": 340 if can_delete else 280,
            "cellRenderer": "reconRunsActionsCell",
            "cellRendererParams": {"canDelete": can_delete},
            **base,
        },
        {"field": "params", "headerName": "Tham số", "flex": 2, "minWidth": 140, **base},
    ]
    return cols


def _filters_to_kwargs(
    from_date: str | None,
    to_date: str | None,
    category: str | None,
    name: str | None,
    runner: str | None,
    status: str | None = None,
) -> dict[str, Any]:
    """Giá trị lọc từ form → tham số service ("all"/rỗng = không lọc)."""
    return {
        "from_date": from_date or None,
        "to_date": to_date or None,
        "category_code": None if category in (None, "", "all") else category,
        "report_name": (name or "").strip() or None,
        "created_by": None if runner in (None, "", "all") else runner,
        "status": None if status in (None, "", "all") else status,
    }


def _load_page_data(
    ctx: Any, page: int, page_size: int, filters: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, dict[int, list[dict[str, Any]]]]:
    """Nạp 1 trang lịch sử + exports theo lô nhiều run (tránh N+1 query)."""
    res = list_report_runs(ctx, page=page, page_size=page_size, **filters)
    if not res.ok or not isinstance(res.data, dict):
        raise ValueError(res.message or "Không tải được lịch sử.")
    runs = res.data.get("runs", [])
    total = int(res.data.get("total", 0))
    run_ids = [int(run["id"]) for run in runs]
    exports_by_run: dict[int, list[dict[str, Any]]] = {}
    if run_ids:
        e_res = list_exports_by_runs(ctx, run_ids)
        if e_res.ok and isinstance(e_res.data, dict):
            exports_by_run = e_res.data
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


def render_report_runs_view_toolbar() -> Any:
    """Thanh công cụ Quản lý Template / Saved Views cho AG Grid Lịch sử báo cáo."""
    return saved_view_toolbar("rruns")


def _build_report_runs_layout(can_delete: bool) -> Any:
    """Dựng khung Skeleton-first cho màn Lịch sử báo cáo (không query DB nặng)."""
    creators: list[dict[str, str]] = [{"label": "Tất cả người chạy", "value": "all"}]
    return dmc.Box(
        [
            dcc.Store(id="report-runs-page-store", data=1),
            dcc.Store(id="report-runs-refresh-store", data=0),
            dcc.Store(id="rruns-view-init-trigger", data=1),
            html.Div(id="rruns-view-init-dummy", style={"display": "none"}),
            # Task 53: vân tay dữ liệu đang hiện — tick tự động chỉ vẽ lại
            # bảng khi vân tay đổi, không thì giữ nguyên (khỏi mất vị trí cuộn).
            dcc.Store(id="report-runs-fingerprint", data=""),
            dcc.Store(id="report-runs-swr-store", storage_type="session"),
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
                        id="report-runs-filter-status",
                        data=_RUN_STATUS_OPTIONS,
                        value="all",
                        size="xs",
                        w=150,
                        **{"aria-label": "Lọc theo trạng thái"},
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
            render_report_runs_view_toolbar(),
            # Task 55: AG Grid thay dmc.Table — tick chỉ đưa rowData mới,
            # grid tự diff theo getRowId và cập nhật dòng đổi tại chỗ
            # (không vẽ lại toàn bảng, không spinner, giữ vị trí cuộn).
            # Bỏ dcc.Loading quanh bảng (task 52) vì lý do đó.
            data_grid(
                id="report-runs-grid",
                columnDefs=_runs_grid_column_defs(can_delete=can_delete),
                rowData=None,
                getRowId="params.data.id.toString()",
                # Task 61: grid truyền overlayNoRowsTemplate là chuỗi tĩnh
                # qua dashGridOptions; dash-ag-grid 35.3.1 chặn chuỗi ở vị
                # trí hàm khi thiếu cờ này (console.error mỗi lần mở trang).
                dangerously_allow_code=True,
                # Task 56: class rh-runs-grid → font 12px (pattern task 40).
                className="ag-theme-quartz-auto-dark rh-runs-grid",
                dashGridOptions={
                    "overlayLoadingTemplate": "Đang tải lịch sử báo cáo...",
                    "overlayNoRowsTemplate": "Chưa có run nào. Chạy một báo cáo ở Trung tâm báo cáo để xem lịch sử tại đây.",
                },
                container_style={"flex": 1, "minHeight": 0},
            ),
            dmc.Group(
                [
                    dmc.Text(
                        "Tổng 0 run",
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
                        total=1,
                        value=1,
                        size="xs",
                    ),
                ],
                justify="center",
                gap="md",
                mt=2,
            ),
            # Modal Lưu Template / View mới
            dmc.Modal(
                id="rruns-save-view-modal",
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
                            id="rruns-new-view-name",
                            label="Tên Template / View",
                            placeholder="Nhập tên template (vd: Theo dõi xuất file, Xem gọn...)",
                            withAsterisk=True,
                            size="sm",
                        ),
                        dmc.Checkbox(
                            id="rruns-new-view-default",
                            label="Đặt làm giao diện mặc định khi mở trang",
                            size="sm",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="rruns-cancel-save-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Lưu Template",
                                    id="rruns-confirm-save-view-btn",
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
            # Modal Xóa Template / View
            dmc.Modal(
                id="rruns-delete-view-modal",
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
                                    id="rruns-cancel-delete-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Xóa Template",
                                    id="rruns-confirm-delete-view-btn",
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
        ],
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
            "gap": "6px",
        },
    )


def layout() -> Any:
    """Giao diện chính màn hình Lịch sử báo cáo (Skeleton-first + Server Layout Cache)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="report-runs-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem lịch sử báo cáo.", tone="crit"),
            ]
        )
    engine = get_recon_engine()
    can_delete = bool(ctx and is_admin(ctx, engine))
    return cached_layout(
        engine,
        ("report_runs", can_delete),
        lambda: _build_report_runs_layout(can_delete),
    )


@callback(
    Output("report-runs-filter-runner", "data"),
    Input("rruns-view-init-trigger", "data"),
    Input("report-runs-refresh-btn", "n_clicks"),
)
def load_runner_options(_trigger: Any, _refresh_clicks: Any) -> list[dict[str, str]]:
    """Nạp danh sách người chạy bất đồng bộ để layout() không truy vấn DB đồng bộ."""
    ctx = get_current_ctx()
    if ctx is None:
        return [{"label": "Tất cả người chạy", "value": "all"}]
    return _runner_options(ctx)


def _is_default_runs_view(
    page: int,
    size: int,
    from_date: str | None,
    to_date: str | None,
    category: str | None,
    name: str | None,
    runner: str | None,
    status: str | None,
) -> bool:
    """Trả True nếu bảng đang ở bộ lọc mặc định trang 1 (được phép dùng cache SWR)."""
    return (
        page == 1
        and size == DEFAULT_PAGE_SIZE
        and not from_date
        and not to_date
        and category in (None, "all")
        and not name
        and runner in (None, "all")
        and status in (None, "all")
    )


def _resolve_runs_swr_state(
    last_fingerprint: Any,
    page_store: Any,
    swr_cache: Any,
) -> tuple[str, Any]:
    """Chuẩn hóa fingerprint & swr_cache giữa runtime Dash và test gọi trực tiếp."""
    runtime_fp = (
        last_fingerprint
        if isinstance(last_fingerprint, str)
        else (page_store if isinstance(page_store, str) else "")
    )
    effective_swr = (
        swr_cache
        if isinstance(swr_cache, dict)
        else (last_fingerprint if isinstance(last_fingerprint, dict) else None)
    )
    return runtime_fp, effective_swr


@callback(
    Output("report-runs-grid", "rowData", allow_duplicate=True),
    Output("report-runs-pagination", "total", allow_duplicate=True),
    Output("report-runs-total-text", "children", allow_duplicate=True),
    Output("report-runs-pagination", "value"),
    Output("report-runs-filter-from", "value"),
    Output("report-runs-filter-to", "value"),
    Output("report-runs-filter-category", "value"),
    Output("report-runs-filter-name", "value"),
    Output("report-runs-filter-runner", "value"),
    Output("report-runs-filter-status", "value"),
    Output("report-runs-fingerprint", "data", allow_duplicate=True),
    # Task 55: alert cũng do handle_renderer_action ghi — cho phép trùng
    # output (Dash sẽ gọi callback nào trigger trước).
    Output("report-runs-alert", "children", allow_duplicate=True),
    Input("report-runs-pagination", "value"),
    Input("report-runs-page-size", "value"),
    Input("report-runs-filter-from", "value"),
    Input("report-runs-filter-to", "value"),
    Input("report-runs-filter-category", "value"),
    Input("report-runs-filter-name", "value"),
    Input("report-runs-filter-runner", "value"),
    Input("report-runs-filter-status", "value"),
    Input("report-runs-clear-btn", "n_clicks"),
    Input("report-runs-auto-refresh", "n_intervals"),
    Input("report-runs-refresh-btn", "n_clicks"),
    Input("report-runs-refresh-store", "data"),
    State("report-runs-page-store", "data"),
    State("report-runs-fingerprint", "data"),
    State("report-runs-swr-store", "data"),
    # Task 55: output alert trùng với handle_renderer_action nên phải
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
    status: str | None,
    _clear_clicks: int | None,
    _current: int | None,
    _auto_n: int | None = None,
    _refresh_clicks: int | None = None,
    _refresh_store: int | None = None,
    _page_store: Any = None,
    last_fingerprint: Any = None,
    swr_cache: Any = None,
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
        from_date, to_date, category, name, runner, status = None, None, "all", "", "all", "all"
        page = 1
    elif triggered in (
        "report-runs-page-size",
        "report-runs-filter-from",
        "report-runs-filter-to",
        "report-runs-filter-category",
        "report-runs-filter-name",
        "report-runs-filter-runner",
        "report-runs-filter-status",
    ):
        page = 1
    else:
        page = int(page_no or 1)
    size = int(page_size or DEFAULT_PAGE_SIZE)
    if size not in PAGE_SIZE_OPTIONS:
        size = DEFAULT_PAGE_SIZE
    filters = _filters_to_kwargs(from_date, to_date, category, name, runner, status=status)
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
            status or "all",
            dash.no_update,
            alert_box(str(exc), tone="crit"),
        )
    fingerprint = _runs_fingerprint(runs, exports_by_run, total, page)
    runtime_fp, effective_swr = _resolve_runs_swr_state(last_fingerprint, _page_store, swr_cache)
    swr_initial_hit = (
        triggered is None
        and _is_default_runs_view(page, size, from_date, to_date, category, name, runner, status)
        and should_skip_swr_update(effective_swr, getattr(ctx, "user_id", None), fingerprint)
    )
    if (triggered == "report-runs-auto-refresh" and fingerprint == (runtime_fp or "")) or swr_initial_hit:
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
        status or "all",
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


_RENDERER_ACTIONS: dict[str, str] = {
    "cancel": "report-runs-export-cancel",
    "retry": "report-runs-export-retry",
    "delete": "report-runs-export-delete",
    "rerun": "report-runs-rerun-export",
}


@callback(
    Output("report-runs-alert", "children", allow_duplicate=True),
    Output("report-runs-refresh-store", "data"),
    Input("report-runs-grid", "cellRendererData"),
    State("report-runs-grid", "rowData"),
    State("report-runs-refresh-store", "data"),
    prevent_initial_call=True,
)
def handle_renderer_action(
    data: dict[str, Any] | None,
    row_data: list[dict[str, Any]] | None,
    refresh: int | None,
) -> tuple[Any, Any]:
    """Bấm nút trong cột Hành động (task 57) → hành động export.

    Renderer DMC gọi props.setData(action) → Dash nhận cellRendererData
    {"value": action, "colId": "actions", "rowId": run_id, "timestamp"}
    (spike ~/workspace/spike-aggrid-dmc/ đã chứng minh). "Chạy lại"
    không qua đây (renderer chuyển trang trực tiếp bằng JS). Guard theo
    trạng thái export để bấm vào nút không còn phù hợp thì im lặng.
    """
    if not isinstance(data, dict):
        raise PreventUpdate
    kind = _RENDERER_ACTIONS.get(str(data.get("value") or ""))
    if kind is None:
        raise PreventUpdate
    try:
        run_id = int(data.get("rowId") or 0)
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


# Clientside callbacks cho Saved Views / Templates trên AG Grid Lịch sử báo cáo
clientside_callback(
    """
    function(trigger) {
        if (!trigger) return "";
        function initViews() {
            if (window.reportRunsViews && window.reportRunsViews.init) {
                window.reportRunsViews.init();
            } else {
                setTimeout(initViews, 100);
            }
        }
        setTimeout(initViews, 50);
        return "";
    }
    """,
    Output("rruns-view-init-dummy", "children"),
    Input("rruns-view-init-trigger", "data"),
)

clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.reportRunsViews) {
            window.reportRunsViews.saveCurrentView();
        }
        return "";
    }
    """,
    Output("rruns-grid-notification", "children", allow_duplicate=True),
    Input("rruns-btn-save-view", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) {
            return [
                window.dash_clientside.no_update,
                window.dash_clientside.no_update,
                window.dash_clientside.no_update,
                window.dash_clientside.no_update
            ];
        }
        return [true, "", null, false];
    }
    """,
    Output("rruns-save-view-modal", "opened"),
    Output("rruns-new-view-name", "value"),
    Output("rruns-new-view-name", "error"),
    Output("rruns-new-view-default", "checked"),
    Input("rruns-btn-save-as-view", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("rruns-save-view-modal", "opened", allow_duplicate=True),
    Input("rruns-cancel-save-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, name, isDefault) {
        if (!n_clicks) {
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        var vName = (name || "").trim();
        if (!vName) {
            return [true, "Vui lòng nhập tên cho Template / View."];
        }
        if (window.reportRunsViews && window.reportRunsViews.saveNewView) {
            window.reportRunsViews.saveNewView(vName, !!isDefault);
        }
        return [false, null];
    }
    """,
    Output("rruns-save-view-modal", "opened", allow_duplicate=True),
    Output("rruns-new-view-name", "error", allow_duplicate=True),
    Input("rruns-confirm-save-view-btn", "n_clicks"),
    State("rruns-new-view-name", "value"),
    State("rruns-new-view-default", "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (n_clicks && window.reportRunsViews) {
            window.reportRunsViews.setDefaultView(viewId || "default");
        }
        return "";
    }
    """,
    Output("rruns-grid-notification", "children", allow_duplicate=True),
    Input("rruns-btn-set-default", "n_clicks"),
    State("rruns-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.reportRunsViews) {
            window.reportRunsViews.resetToDefault();
        }
        return "";
    }
    """,
    Output("rruns-grid-notification", "children", allow_duplicate=True),
    Input("rruns-btn-reset-default", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.reportRunsViews && window.reportRunsViews.activeViewId)
            ? window.reportRunsViews.activeViewId
            : viewId;
        if (!activeId || activeId === "default") {
            if (window.reportRunsViews && window.reportRunsViews.showStatusNotification) {
                window.reportRunsViews.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            }
            return false;
        }
        return true;
    }
    """,
    Output("rruns-delete-view-modal", "opened"),
    Input("rruns-btn-delete-view", "n_clicks"),
    State("rruns-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("rruns-delete-view-modal", "opened", allow_duplicate=True),
    Input("rruns-cancel-delete-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.reportRunsViews && window.reportRunsViews.activeViewId)
            ? window.reportRunsViews.activeViewId
            : viewId;
        if (window.reportRunsViews && window.reportRunsViews.deleteView) {
            window.reportRunsViews.deleteView(activeId);
        }
        return false;
    }
    """,
    Output("rruns-delete-view-modal", "opened", allow_duplicate=True),
    Input("rruns-confirm-delete-view-btn", "n_clicks"),
    State("rruns-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(viewId) {
        if (viewId && window.reportRunsViews) {
            window.reportRunsViews.applyView(viewId);
        }
        return "";
    }
    """,
    Output("rruns-grid-notification", "children", allow_duplicate=True),
    Input("rruns-view-select", "value"),
    prevent_initial_call=True,
)

# Client-side SWR: nạp ngay rowData từ sessionStorage khi quay lại /report-runs
clientside_callback(
    """
    function(swrData, gridRowData, shellMode, currentPage, pageSize, fromDate, toDate, cat, name, runner, status) {
        var noUp = window.dash_clientside.no_update;
        if (gridRowData !== null && gridRowData !== undefined) {
            return [noUp, noUp, noUp, noUp];
        }
        if (!swrData || typeof swrData !== "object" || !Array.isArray(swrData.rowData)) {
            return [noUp, noUp, noUp, noUp];
        }
        var uid = shellMode && shellMode.user_id !== undefined ? shellMode.user_id : null;
        if (uid === null || swrData.user_id !== uid) {
            return [noUp, noUp, noUp, noUp];
        }
        var isDefault = (
            (currentPage === null || currentPage === undefined || currentPage === 1) &&
            (!pageSize || String(pageSize) === "50") &&
            !fromDate && !toDate &&
            (!cat || cat === "all") &&
            !name &&
            (!runner || runner === "all") &&
            (!status || status === "all")
        );
        if (!isDefault) {
            return [noUp, noUp, noUp, noUp];
        }
        return [
            swrData.rowData,
            swrData.total || 1,
            swrData.totalText || ("Tổng " + swrData.rowData.length + " run"),
            swrData.fingerprint || ""
        ];
    }
    """,
    Output("report-runs-grid", "rowData", allow_duplicate=True),
    Output("report-runs-pagination", "total", allow_duplicate=True),
    Output("report-runs-total-text", "children", allow_duplicate=True),
    Output("report-runs-fingerprint", "data", allow_duplicate=True),
    Input("report-runs-swr-store", "data"),
    State("report-runs-grid", "rowData"),
    State("app-shell-mode", "data"),
    State("report-runs-pagination", "value"),
    State("report-runs-page-size", "value"),
    State("report-runs-filter-from", "value"),
    State("report-runs-filter-to", "value"),
    State("report-runs-filter-category", "value"),
    State("report-runs-filter-name", "value"),
    State("report-runs-filter-runner", "value"),
    State("report-runs-filter-status", "value"),
    prevent_initial_call="initial_duplicate",
)

# Client-side SWR: lưu snapshot trang 1 mặc định vào sessionStorage khi vân tay đổi
clientside_callback(
    """
    function(fp, rowData, total, totalText, currentPage, pageSize, fromDate, toDate, cat, name, runner, status, shellMode, prevSwr) {
        var noUp = window.dash_clientside.no_update;
        if (!fp || !Array.isArray(rowData)) {
            return noUp;
        }
        var uid = shellMode && shellMode.user_id !== undefined ? shellMode.user_id : null;
        if (uid === null) {
            return noUp;
        }
        var isDefault = (
            (currentPage === null || currentPage === undefined || currentPage === 1) &&
            (!pageSize || String(pageSize) === "50") &&
            !fromDate && !toDate &&
            (!cat || cat === "all") &&
            !name &&
            (!runner || runner === "all") &&
            (!status || status === "all")
        );
        if (!isDefault) {
            return noUp;
        }
        if (prevSwr && prevSwr.user_id === uid && prevSwr.fingerprint === fp) {
            return noUp;
        }
        return {
            user_id: uid,
            rowData: rowData,
            total: total || 1,
            totalText: totalText || ("Tổng " + rowData.length + " run"),
            fingerprint: fp
        };
    }
    """,
    Output("report-runs-swr-store", "data"),
    Input("report-runs-fingerprint", "data"),
    State("report-runs-grid", "rowData"),
    State("report-runs-pagination", "total"),
    State("report-runs-total-text", "children"),
    State("report-runs-pagination", "value"),
    State("report-runs-page-size", "value"),
    State("report-runs-filter-from", "value"),
    State("report-runs-filter-to", "value"),
    State("report-runs-filter-category", "value"),
    State("report-runs-filter-name", "value"),
    State("report-runs-filter-runner", "value"),
    State("report-runs-filter-status", "value"),
    State("app-shell-mode", "data"),
    State("report-runs-swr-store", "data"),
    prevent_initial_call=True,
)
