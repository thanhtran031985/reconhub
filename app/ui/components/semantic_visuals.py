"""Render 5 loại visual semantic (Table / Matrix / KPI / Bar / Line) — Bước 4 task 109.

Nhận visual (dict đã lưu) + kết quả preview từ service `preview_studio_visual`
và dựng component hiển thị, kèm 4 trạng thái: Loading / Empty / Error+Retry /
Data, banner khi kết quả bị cắt ngắn (truncated) và cảnh báo từ planner.

Màu biểu đồ lấy từ token Fluent (sáng `#0F6CBD`, tối `#479EF5`); chế độ tối
được truyền qua tham số `dark_mode` do designer đồng bộ từ
`data-mantine-color-scheme` (xem `studio_drag_drop.js`).
"""

from __future__ import annotations

from typing import Any

import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash import dcc

from app.ui.components.alert_box import alert_box
from app.ui.components.empty_state import empty_state
from app.ui.components.error_state import error_state
from app.ui.components.grid_defaults import GRID_DEFAULTS
from app.ui.components.kpi_card import kpi_card

HEIGHT_PX: dict[str, int] = {"S": 220, "M": 320, "L": 420}

_CHART_LIGHT = {
    "marker": "#0F6CBD",
    "marker_alt": "#62ABF5",
    "font": "#242424",
    "grid": "#E0E0E0",
    "paper": "#FFFFFF",
}
_CHART_DARK = {
    "marker": "#479EF5",
    "marker_alt": "#8EC9F8",
    "font": "#E5E5E5",
    "grid": "#3A3A3A",
    "paper": "#1A1B1E",
}
_CHART_SERIES = ("#0F6CBD", "#8764B8", "#038387", "#BC4B09", "#498205", "#C50F1F")
_CHART_SERIES_DARK = ("#479EF5", "#B29DE0", "#4CC2C7", "#F7A46B", "#8ED1A0", "#F1707B")


def _fmt_value(val: Any) -> str:
    """Định dạng số: hàng nghìn ',' , số lẻ '.' (giống fmt_num ở run_result)."""
    if val is None or val == "":
        return "—"
    try:
        num = float(val)
        if num == 0:
            return "0"
        if num.is_integer():
            return f"{int(num):,}"
        return f"{num:,.2f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return str(val)


def _height_px(visual: dict[str, Any]) -> int:
    return HEIGHT_PX.get(str(visual.get("height_size") or "M").upper(), 320)


def _truncated_banner(preview: dict[str, Any] | None, *, matrix: bool = False) -> Any:
    if not preview or not preview.get("truncated"):
        return None
    if matrix:
        message = (
            "Ma trận vượt giới hạn an toàn (50 hàng × 20 cột), chỉ hiển thị phần đầu. "
            "Thu hẹp bộ lọc để xem đủ dữ liệu."
        )
    else:
        message = (
            f"Kết quả đã bị cắt ngắn, chỉ hiển thị {int(preview.get('row_count') or 0)} dòng đầu. "
            "Thu hẹp bộ lọc để xem đủ dữ liệu."
        )
    return alert_box(title="Kết quả đã bị cắt ngắn", message=message, tone="warn")


def _warning_banner(preview: dict[str, Any] | None) -> Any:
    msg = (preview or {}).get("warning_message")
    if not msg:
        return None
    return alert_box(title="Lưu ý", message=str(msg), tone="info")


def _columns_of(preview: dict[str, Any]) -> list[dict[str, Any]]:
    return list(preview.get("columns") or [])


def _table_grid(
    columns: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    height: int,
) -> dag.AgGrid:
    col_defs = [
        {
            "field": str(c.get("name")),
            "headerName": str(c.get("label") or c.get("name")),
            "filter": "agNumberColumnFilter"
            if str(c.get("data_type") or "").upper() == "NUMBER"
            else "agTextColumnFilter",
        }
        for c in columns
    ]
    return dag.AgGrid(
        columnDefs=col_defs,
        rowData=rows,
        dashGridOptions=GRID_DEFAULTS,
        className="ag-theme-quartz-auto-dark",
        style={"height": height},
    )


def _render_table(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    rows = list(preview.get("rows") or [])
    return dmc.Stack(
        [
            _truncated_banner(preview),
            _warning_banner(preview),
            _table_grid(_columns_of(preview), rows, _height_px(visual)),
        ],
        gap="xs",
    )


def _render_matrix(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    pivot = preview.get("pivot") or {}
    row_headers = list(pivot.get("row_headers") or [])
    col_headers = list(pivot.get("col_headers") or [])
    cells = list(pivot.get("cells") or [])
    row_label = str((_columns_of(preview)[0].get("label") if _columns_of(preview) else "") or "")
    col_defs: list[dict[str, Any]] = [
        {"field": "", "headerName": row_label, "filter": "agTextColumnFilter"}
    ]
    col_defs.extend(
        {"field": str(h), "headerName": str(h), "filter": "agNumberColumnFilter"}
        for h in col_headers
    )
    rows = [
        {"": rh, **{str(ch): (cells[i][j] if j < len(cells[i]) else None) for j, ch in enumerate(col_headers)}}
        for i, rh in enumerate(row_headers)
    ]
    return dmc.Stack(
        [
            _truncated_banner(preview, matrix=True),
            _warning_banner(preview),
            dag.AgGrid(
                columnDefs=col_defs,
                rowData=rows,
                dashGridOptions=GRID_DEFAULTS,
                className="ag-theme-quartz-auto-dark",
                style={"height": _height_px(visual)},
            ),
        ],
        gap="xs",
    )


def _render_kpi(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    rows = list(preview.get("rows") or [])
    columns = _columns_of(preview)
    value_col = str(columns[-1].get("name")) if columns else ""
    label = str(columns[-1].get("label") or value_col) if columns else ""
    value = rows[0].get(value_col) if rows and value_col else None
    meta = f"{label} · {int(preview.get('row_count') or 0)} dòng" if label else None
    return dmc.Stack(
        [
            _truncated_banner(preview),
            _warning_banner(preview),
            kpi_card(
                label=str(visual.get("title") or visual.get("code") or "KPI"),
                value=_fmt_value(value),
                meta=meta,
                icon="lucide:gauge",
            ),
        ],
        gap="xs",
    )


def _render_chart(
    visual: dict[str, Any],
    preview: dict[str, Any],
    *,
    kind: str,
    dark_mode: bool,
) -> Any:
    rows = list(preview.get("rows") or [])
    columns = _columns_of(preview)
    palette = _CHART_DARK if dark_mode else _CHART_LIGHT
    series_colors = _CHART_SERIES_DARK if dark_mode else _CHART_SERIES
    height = _height_px(visual)
    if not columns:
        return empty_state(
            title="Chưa có dữ liệu",
            description="Visual chưa trả về cột nào với bộ lọc hiện tại.",
        )
    x_name = str(columns[0].get("name"))
    x_vals = [r.get(x_name) for r in rows]
    traces: list[dict[str, Any]] = []
    for idx, col in enumerate(columns[1:]):
        name = str(col.get("name"))
        color = series_colors[idx % len(series_colors)]
        if kind == "BAR":
            traces.append(
                {
                    "type": "bar",
                    "x": x_vals,
                    "y": [r.get(name) for r in rows],
                    "name": str(col.get("label") or name),
                    "marker": {"color": color},
                }
            )
        else:
            traces.append(
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": x_vals,
                    "y": [r.get(name) for r in rows],
                    "name": str(col.get("label") or name),
                    "line": {"color": color},
                    "marker": {"color": color},
                }
            )
    figure = {
        "data": traces,
        "layout": {
            "height": height,
            "margin": {"l": 48, "r": 16, "t": 16, "b": 48},
            "paper_bgcolor": palette["paper"],
            "plot_bgcolor": palette["paper"],
            "font": {"color": palette["font"], "size": 12},
            "xaxis": {"gridcolor": palette["grid"], "title": str(columns[0].get("label") or x_name)},
            "yaxis": {"gridcolor": palette["grid"]},
            "showlegend": len(traces) > 1,
            "legend": {"orientation": "h", "y": -0.18},
        },
    }
    return dmc.Stack(
        [
            _truncated_banner(preview),
            _warning_banner(preview),
            dcc.Graph(
                figure=figure,
                config={"displayModeBar": False, "responsive": True},
                style={"height": height},
            ),
        ],
        gap="xs",
    )


def render_semantic_visual(
    visual: dict[str, Any],
    preview: dict[str, Any] | None,
    *,
    state: str = "data",
    error_message: str | None = None,
    dark_mode: bool = False,
) -> Any:
    """Render một visual semantic theo loại + trạng thái.

    state: "loading" | "empty" | "error" | "data". Khi state="data" nhưng
    preview không có dòng thì hiển thị trạng thái trống.
    """
    vtype = str(visual.get("visual_type") or "TABLE").upper()
    code = str(visual.get("code") or "")
    height = _height_px(visual)
    if state == "loading":
        return dmc.Skeleton(height=height, radius="sm")
    if state == "error":
        return error_state(
            title="Không xem trước được visual",
            message=error_message or "Vui lòng thử lại.",
            action=dmc.Button(
                "Thử lại",
                id={"type": "rs-visual-retry", "code": code},
                size="xs",
                variant="outline",
            ),
        )
    if state == "empty" or preview is None:
        return empty_state(
            title="Chưa có dữ liệu",
            description="Visual chưa trả về dòng nào với bộ lọc hiện tại.",
        )
    rows = list(preview.get("rows") or [])
    if vtype == "MATRIX":
        pivot = preview.get("pivot") or {}
        if not rows and not (pivot.get("row_headers") or []):
            return empty_state(
                title="Chưa có dữ liệu",
                description="Visual chưa trả về dòng nào với bộ lọc hiện tại.",
            )
        return _render_matrix(visual, preview)
    if not rows:
        return empty_state(
            title="Chưa có dữ liệu",
            description="Visual chưa trả về dòng nào với bộ lọc hiện tại.",
        )
    if vtype == "KPI":
        return _render_kpi(visual, preview)
    if vtype == "BAR":
        return _render_chart(visual, preview, kind="BAR", dark_mode=dark_mode)
    if vtype == "LINE":
        return _render_chart(visual, preview, kind="LINE", dark_mode=dark_mode)
    return _render_table(visual, preview)
