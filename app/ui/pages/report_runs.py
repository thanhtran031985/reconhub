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
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.perm import page_gate
from app.services.report_export import list_exports
from app.services.report_run import list_report_runs, list_run_creators
from app.ui.components.alert_box import alert_box
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
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


def render_runs_table(runs: list[dict[str, Any]], exports_by_run: dict[int, list[dict[str, Any]]]) -> Any:
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
        done = [e for e in exports if e["status"] == "DONE"]
        file_cell: Any = "—"
        if done:
            latest = done[0]
            file_cell = dmc.Tooltip(
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
                        dcc.Link(
                            dmc.Button(
                                "Chạy lại",
                                size="xs",
                                variant="subtle",
                                leftSection=DashIconify(icon="lucide:play-circle", width=14),
                            ),
                            href=f"/reports/{run['report_id']}?rerun_from={run_id}",
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
                    children=render_runs_table(runs, exports_by_run),
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
    Input("report-runs-pagination", "value"),
    Input("report-runs-page-size", "value"),
    Input("report-runs-filter-from", "value"),
    Input("report-runs-filter-to", "value"),
    Input("report-runs-filter-category", "value"),
    Input("report-runs-filter-name", "value"),
    Input("report-runs-filter-runner", "value"),
    Input("report-runs-clear-btn", "n_clicks"),
    State("report-runs-page-store", "data"),
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
) -> tuple[Any, int, str, int, Any, Any, str, str, str]:
    """Chuyển trang / đổi cỡ trang / lọc lịch sử (đổi lọc → về trang 1)."""
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
        )
    return (
        render_runs_table(runs, exports_by_run),
        max(1, (total + size - 1) // size),
        f"Tổng {total} run",
        page,
        from_date or "",
        to_date or "",
        category or "all",
        name or "",
        runner or "all",
    )
