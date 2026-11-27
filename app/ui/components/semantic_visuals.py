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
from app.ui.components.report_widgets import _format_cell

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


def _fmt_value(val: Any, *, format_mask: str | None = None, data_type: str | None = None) -> str:
    """Định dạng giá trị KPI theo format_mask (nếu có) hoặc mặc định dấu ','."""
    if val is None or val == "":
        return "—"
    if format_mask:
        return _format_cell(val, {"data_type": str(data_type or "NUMBER").upper(), "format_mask": format_mask})
    try:
        num = float(val)
        if num == 0:
            return "0"
        if num.is_integer():
            return f"{int(num):,}"
        return f"{num:,.2f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return str(val)


def _visual_value_mask(visual: dict[str, Any], columns: list[dict[str, Any]]) -> str | None:
    if columns and columns[-1].get("format_mask"):
        return str(columns[-1]["format_mask"])
    for f in visual.get("fields") or []:
        if str(f.get("well_role") or "") in ("VALUE", "VALUES", "Y") and f.get("format_mask"):
            return str(f["format_mask"])
    return None


def _attach_formatter(col_def: dict[str, Any], format_mask: str | None, data_type: str) -> dict[str, Any]:
    """Gắn valueFormatter JS theo context khi cột có format_mask."""
    if format_mask:
        col_def["valueFormatter"] = {"function": "reconSemanticFormat(params)"}
        col_def["context"] = {"formatMask": str(format_mask), "dataType": str(data_type or "STRING").upper()}
    return col_def


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
    *,
    visual: dict[str, Any] | None = None,
) -> dag.AgGrid:
    has_mask = False
    col_defs: list[dict[str, Any]] = []
    # Fallback lấy format_mask theo thứ tự cột nếu caller chưa enrich columns.
    vis_fields = list((visual or {}).get("fields") or [])
    for idx, c in enumerate(columns):
        dtype = str(c.get("data_type") or "").upper()
        mask = c.get("format_mask")
        if mask is None and idx < len(vis_fields):
            mask = vis_fields[idx].get("format_mask")
        cdef: dict[str, Any] = {
            "field": str(c.get("name")),
            "headerName": str(c.get("label") or c.get("name")),
            "filter": "agNumberColumnFilter" if dtype == "NUMBER" else "agTextColumnFilter",
        }
        if mask:
            has_mask = True
            _attach_formatter(cdef, str(mask), dtype)
        col_defs.append(cdef)
    grid_kwargs: dict[str, Any] = {}
    if has_mask:
        grid_kwargs["dangerously_allow_code"] = True
    return dag.AgGrid(
        columnDefs=col_defs,
        rowData=rows,
        dashGridOptions=GRID_DEFAULTS,
        className="ag-theme-quartz-auto-dark",
        style={"height": height},
        **grid_kwargs,
    )


def _render_table(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    rows = list(preview.get("rows") or [])
    return dmc.Stack(
        [
            _truncated_banner(preview),
            _warning_banner(preview),
            _table_grid(_columns_of(preview), rows, _height_px(visual), visual=visual),
        ],
        gap="xs",
    )


def _render_matrix(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    pivot = preview.get("pivot") or {}
    row_headers = list(pivot.get("row_headers") or [])
    col_headers = list(pivot.get("col_headers") or [])
    cells = list(pivot.get("cells") or [])
    cols = _columns_of(preview)
    row_label = str((cols[0].get("label") if cols else "") or "")
    val_mask = _visual_value_mask(visual, cols)
    col_defs: list[dict[str, Any]] = [
        {"field": "__row_key", "headerName": row_label, "filter": "agTextColumnFilter"}
    ]
    for h in col_headers:
        cdef: dict[str, Any] = {"field": str(h), "headerName": str(h), "filter": "agNumberColumnFilter"}
        if val_mask:
            _attach_formatter(cdef, val_mask, "NUMBER")
        col_defs.append(cdef)
    rows = [
        {"__row_key": rh, **{str(ch): (cells[i][j] if j < len(cells[i]) else None) for j, ch in enumerate(col_headers)}}
        for i, rh in enumerate(row_headers)
    ]
    grid_kwargs: dict[str, Any] = {}
    if val_mask:
        grid_kwargs["dangerously_allow_code"] = True
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
                **grid_kwargs,
            ),
        ],
        gap="xs",
    )


def _render_kpi(visual: dict[str, Any], preview: dict[str, Any]) -> Any:
    rows = list(preview.get("rows") or [])
    columns = _columns_of(preview)
    value_col = str(columns[-1].get("name")) if columns else ""
    label = str(columns[-1].get("label") or value_col) if columns else ""
    dtype = str(columns[-1].get("data_type") or "NUMBER") if columns else "NUMBER"
    mask = _visual_value_mask(visual, columns)
    value = rows[0].get(value_col) if rows and value_col else None
    meta = f"{label} · {int(preview.get('row_count') or 0)} dòng" if label else None
    return dmc.Stack(
        [
            _truncated_banner(preview),
            _warning_banner(preview),
            kpi_card(
                label=str(visual.get("title") or visual.get("code") or "KPI"),
                value=_fmt_value(value, format_mask=mask, data_type=dtype),
                meta=meta,
                icon="lucide:gauge",
            ),
        ],
        gap="xs",
    )


def _chart_roles(
    visual: dict[str, Any], columns: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    """Xác định cột X, SERIES (nếu có) và các cột Y measure cho Bar/Line."""
    if any(c.get("well_role") for c in columns):
        x_col = next((c for c in columns if str(c.get("well_role")) == "X"), columns[0])
        series_col = next((c for c in columns if str(c.get("well_role")) == "SERIES"), None)
        y_cols = [c for c in columns if str(c.get("well_role")) in ("Y", "VALUES", "VALUE")]
        if not y_cols:
            y_cols = [c for c in columns if c is not x_col and c is not series_col]
        return x_col, series_col, y_cols
    fields = list(visual.get("fields") or [])
    has_series = any(str(f.get("well_role") or "") == "SERIES" for f in fields)
    if has_series and len(columns) >= 3:
        x_count = max(1, sum(1 for f in fields if str(f.get("well_role") or "") == "X"))
        if x_count < len(columns) - 1:
            return columns[0], columns[x_count], columns[x_count + 1 :]
    return columns[0], None, columns[1:]


def _build_trace(
    kind: str,
    x_vals: list[Any],
    y_vals: list[Any],
    name: str,
    color: str,
) -> dict[str, Any]:
    if kind == "BAR":
        return {"type": "bar", "x": x_vals, "y": y_vals, "name": name, "marker": {"color": color}}
    return {
        "type": "scatter",
        "mode": "lines+markers",
        "x": x_vals,
        "y": y_vals,
        "name": name,
        "line": {"color": color},
        "marker": {"color": color},
    }


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
    x_col, series_col, y_cols = _chart_roles(visual, columns)
    x_name = str(x_col.get("name"))
    traces: list[dict[str, Any]] = []
    if series_col is not None and y_cols:
        s_name = str(series_col.get("name"))
        x_vals = list(dict.fromkeys(r.get(x_name) for r in rows))
        s_vals = list(dict.fromkeys(r.get(s_name) if r.get(s_name) is not None else "—" for r in rows))
        t_idx = 0
        for y_col in y_cols:
            y_name = str(y_col.get("name"))
            y_label = str(y_col.get("label") or y_name)
            lookup: dict[tuple[Any, Any], Any] = {}
            for r in rows:
                s_key = r.get(s_name) if r.get(s_name) is not None else "—"
                lookup[(r.get(x_name), s_key)] = r.get(y_name)
            for sv in s_vals:
                trace_label = str(sv) if len(y_cols) == 1 else f"{sv} · {y_label}"
                color = series_colors[t_idx % len(series_colors)]
                traces.append(
                    _build_trace(kind, x_vals, [lookup.get((xv, sv)) for xv in x_vals], trace_label, color)
                )
                t_idx += 1
    else:
        x_vals = [r.get(x_name) for r in rows]
        for idx, col in enumerate(y_cols):
            name = str(col.get("name"))
            color = series_colors[idx % len(series_colors)]
            traces.append(
                _build_trace(kind, x_vals, [r.get(name) for r in rows], str(col.get("label") or name), color)
            )
    layout_cfg: dict[str, Any] = {
        "height": height,
        "margin": {"l": 48, "r": 16, "t": 16, "b": 48},
        "paper_bgcolor": palette["paper"],
        "plot_bgcolor": palette["paper"],
        "font": {"color": palette["font"], "size": 12},
        "xaxis": {"gridcolor": palette["grid"], "title": str(x_col.get("label") or x_name)},
        "yaxis": {"gridcolor": palette["grid"]},
        "showlegend": len(traces) > 1 or series_col is not None,
        "legend": {"orientation": "h", "y": -0.18},
    }
    if kind == "BAR" and len(traces) > 1:
        layout_cfg["barmode"] = "group"
    figure = {"data": traces, "layout": layout_cfg}
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
