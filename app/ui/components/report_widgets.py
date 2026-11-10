"""Widget dùng chung cho trang Xem báo cáo và Wizard quản trị báo cáo.

Đặt ở components (không import chéo giữa các page): Dash đăng ký page theo
cả hai đường dẫn module `app.ui.pages.X` và `pages.X` nên một page import
từ page khác gây lỗi duplicate paths khi chạy server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash_mantine_components as dmc
from dash import html

from app.core.context import Ctx
from app.services.report_param import resolve_lov
from app.ui.components.data_grid import data_grid
from app.ui.components.empty_state import empty_state


def _format_cell(value: Any, column: dict[str, Any]) -> str:
    """Định dạng một ô theo metadata cột (mask + type)."""
    if value is None or value == "":
        return "—"
    dtype = column.get("data_type")
    mask = column.get("format_mask")
    if dtype == "NUMBER":
        try:
            num = float(value)
        except (TypeError, ValueError):
            return str(value)
        if mask == "#,##0%":
            return f"{num * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
        if mask == "#,##0.00":
            return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{num:,.0f}".replace(",", ".")
    if dtype in ("DATE", "DATETIME"):
        dt = None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                dt = None
        if dt is None:
            return str(value)
        if mask == "DD/MM/YYYY HH:mm":
            return dt.strftime("%d/%m/%Y %H:%M")
        if mask == "DD/MM/YYYY HH:mm:ss":
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        if mask == "MM/YYYY":
            return dt.strftime("%m/%Y")
        if mask == "YYYY-MM-DD":
            return dt.strftime("%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    return str(value)


def _lov_options(ctx: Ctx, version_id: int, param: dict[str, Any]) -> list[dict[str, str]]:
    """Options cho SELECT/MULTI_SELECT từ LOV (STATIC/LOOKUP/SQL không dep)."""
    lov = param.get("lov") or {}
    lov_type = lov.get("lov_type", "NONE")
    if lov_type == "STATIC":
        # Dạng thật từ service: static_json = [{"value","label"}];
        # dạng test: static_values = [[value, label], ...].
        items = lov.get("static_json") or lov.get("static_values") or []
        opts = []
        for item in items:
            if isinstance(item, dict):
                opts.append(
                    {
                        "label": str(item.get("label", item.get("value"))),
                        "value": str(item.get("value")),
                    }
                )
            else:
                opts.append({"label": str(item[1]), "value": str(item[0])})
        return opts
    if lov_type in ("SQL", "LOOKUP"):
        try:
            res = resolve_lov(ctx, version_id, int(param["id"]))
        except Exception:
            return []
        if res.ok and isinstance(res.data, list):
            return [{"label": str(o.get("label", o.get("value"))), "value": str(o.get("value"))} for o in res.data]
        return []
    return []


def render_param_control(param: dict[str, Any], options: list[dict[str, str]] | None) -> Any:
    """Một control tham số theo DATA_TYPE/CONTROL_TYPE + LOV."""
    code = str(param["code"])
    label = f"{param['label']}{' *' if param.get('required') else ''}"
    value = param.get("value")
    pid = {"type": "viewer-param", "index": code}
    ctype = param.get("control_type")
    dtype = param.get("data_type")
    if ctype == "DATE_RANGE":
        # dmc 2.8.1: DateInput không có type="range" — dùng 2 DateInput
        # (test đếm đúng 2 DateInput); callback gộp __from/__to thành dict.
        raw = value if isinstance(value, dict) else {}
        return dmc.Stack(
            [
                dmc.Text(label, size="sm", fw=500),
                dmc.Group(
                    [
                        dmc.DateInput(
                            id={"type": "viewer-param", "index": code + "__from"},
                            value=str(raw.get("from")) if raw.get("from") else None,
                            valueFormat="YYYY-MM-DD",
                            placeholder="Từ ngày…",
                            **{"aria-label": f"{label} từ ngày"},
                        ),
                        dmc.DateInput(
                            id={"type": "viewer-param", "index": code + "__to"},
                            value=str(raw.get("to")) if raw.get("to") else None,
                            valueFormat="YYYY-MM-DD",
                            placeholder="Đến ngày…",
                            **{"aria-label": f"{label} đến ngày"},
                        ),
                    ],
                    gap="sm",
                    grow=True,
                ),
            ],
            gap=2,
        )
    if ctype in ("SELECT", "MULTI_SELECT"):
        opts = options
        if opts is None:
            # Dự phòng: tự suy options từ LOV STATIC của param (test + render
            # độc lập); layout() thường truyền options đã resolve qua resolve_lov.
            lov = param.get("lov") or {}
            if lov.get("lov_type") == "STATIC":
                items = lov.get("static_json") or lov.get("static_values") or []
                opts = []
                for item in items:
                    if isinstance(item, dict):
                        opts.append(
                            {
                                "label": str(item.get("label", item.get("value"))),
                                "value": str(item.get("value")),
                            }
                        )
                    else:
                        opts.append({"label": str(item[1]), "value": str(item[0])})
            else:
                opts = []
        if ctype == "MULTI_SELECT":
            return dmc.MultiSelect(
                id=pid,
                label=label,
                data=opts,
                value=value if isinstance(value, list) else None,
                placeholder="Chọn giá trị…",
                searchable=True,
                clearable=True,
            )
        return dmc.Select(
            id=pid,
            label=label,
            data=opts,
            value=str(value) if value is not None else None,
            placeholder="Chọn giá trị…",
            searchable=True,
            clearable=not param.get("required"),
        )
    if ctype == "DATE" or dtype in ("DATE", "DATETIME"):
        return dmc.DateInput(
            id=pid,
            label=label,
            value=str(value) if value is not None else None,
            valueFormat="YYYY-MM-DD",
            placeholder="Chọn ngày…",
            **{"aria-label": label},
        )
    if ctype == "NUMBER" or dtype == "NUMBER":
        return dmc.NumberInput(
            id=pid,
            label=label,
            value=value,
            placeholder="Nhập số…",
            **{"aria-label": label},
        )
    return dmc.TextInput(
        id=pid,
        label=label,
        value=str(value) if value is not None else None,
        placeholder=f"Nhập {str(param['label']).lower()}…",
        **{"aria-label": label},
    )


def render_param_form(
    layout_detail: dict[str, Any],
    options_by_code: dict[str, list[dict[str, str]]],
    action: Any = None,
) -> Any:
    """Form tham số theo grid 12 cột (build_param_layout).

    action: nút hành động (vd "Xem báo cáo") — tổng span tham số < 12 thì
    đặt cùng dòng với tham số (ô span = phần còn lại, tối đa 3, tối thiểu
    2 cột; phần còn lại < 2 cột thì vẫn xuống dòng mới); >= 12 thì xuống
    dòng mới như trước.
    """
    rows = []
    row_spans: list[int] = []
    total_span = 0
    for row in layout_detail.get("rows", []):
        cells = []
        row_span = 0
        for entry in row.get("params", []):
            span = max(1, min(12, int(entry.get("grid_span") or 1)))
            row_span += span
            total_span += span
            cells.append(
                html.Div(
                    render_param_control(entry, options_by_code.get(str(entry["code"]))),
                    style={"gridColumn": f"span {span}"},
                )
            )
        row_spans.append(row_span)
        rows.append(
            html.Div(
                cells,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(12, minmax(0, 1fr))",
                    "gap": 10,
                    "marginBottom": 12,
                },
            )
        )
    if action is not None:
        placed = False
        if rows and total_span < 12:
            remaining = 12 - row_spans[-1]
            if remaining >= 2:
                rows[-1].children.append(
                    html.Div(
                        action,
                        style={
                            "gridColumn": f"span {min(remaining, 3)}",
                            "alignSelf": "end",
                        },
                    )
                )
                placed = True
        if not placed:
            rows.append(html.Div(action))
    return html.Div(rows)


def render_result_grid(layout: dict[str, Any], rows: list[dict[str, Any]]) -> Any:
    """Kết quả dạng AG Grid (data_grid): cột theo layout web, ô định dạng
    theo mask như bảng cũ, hàng Tổng ghim cuối (pinnedBottomRowData).

    Phân trang vẫn server-side (dmc.Pagination + select số dòng/trang ở
    viewer): grid chỉ hiển thị đúng trang đã fetch, không bật pagination
    nội bộ. Sort cũng server-side qua columnState → sort-store → refetch.

    rowData mang chuỗi ĐÃ ĐỊNH DẠNG (như bảng cũ) nên sort client-side
    mặc định của AG Grid sẽ sai (so chuỗi: "9.000" > "55.000"). Vì vậy
    cột NUMBER/DATE có comparator riêng parse ngược chuỗi định dạng về
    số/ngày — hàm JS nằm ở app/ui/assets/dashAgGridFunctions.js
    (namespace dashAgGridFunctions). Dạng inline
    {"function": "function(a, b) {...}"} đã thử ở dash-ag-grid 35.3.0 và
    KHÔNG chạy (rơi về sort chuỗi) — chỉ dạng tham chiếu tên mới chạy.
    """
    columns = layout.get("columns", [])
    if not rows:
        return empty_state(
            "Không có dòng nào.",
            "Thử đổi tham số hoặc khoảng thời gian rồi chạy lại.",
        )

    def _align(c_meta: dict[str, Any]) -> str:
        a = str(c_meta.get("alignment") or "LEFT").upper()
        if a in ("CENTER", "GIỮA", "GIUA"):
            return "center"
        if a in ("RIGHT", "PHẢI", "PHAI"):
            return "right"
        return "left"

    def _val(row_dict: dict[str, Any], f_name: str) -> Any:
        if f_name in row_dict:
            return row_dict[f_name]
        if f_name.upper() in row_dict:
            return row_dict[f_name.upper()]
        if f_name.lower() in row_dict:
            return row_dict[f_name.lower()]
        return None

    defs = []
    for c in columns:
        field = str(c["field_name"])
        width = c.get("width")
        col_def: dict[str, Any] = {
            "field": field,
            "colId": field,
            "headerName": str(c["label"]),
            "width": int(width) if width else 140,
            "minWidth": 80,
            "sortable": True,
            "filter": False,
            "cellStyle": {"textAlign": _align(c)},
        }
        if c.get("data_type") == "NUMBER":
            col_def["comparator"] = {"function": "reconViewerNumCompare"}
        elif c.get("data_type") in ("DATE", "DATETIME"):
            col_def["comparator"] = {"function": "reconViewerDateCompare"}
        defs.append(col_def)
    row_data = [
        {str(c["field_name"]): _format_cell(_val(row, str(c["field_name"])), c) for c in columns}
        for row in rows
    ]
    pinned = None
    if any(bool(c.get("is_total")) for c in columns):
        pinned_row: dict[str, Any] = {}
        is_first = True
        for c in columns:
            field = str(c["field_name"])
            if c.get("is_total") and c.get("data_type") == "NUMBER":
                total_val = 0.0
                for row in rows:
                    val = _val(row, field)
                    if val is not None:
                        try:
                            total_val += float(val)
                        except (TypeError, ValueError):
                            pass
                pinned_row[field] = _format_cell(total_val, c)
            else:
                pinned_row[field] = "Tổng cộng" if is_first else ""
            is_first = False
        pinned = [pinned_row]
    # pinnedBottomRowData không phải prop trực tiếp của dag.AgGrid 35.3.0
    # (truyền vào sẽ lỗi TypeError) — phải đi qua dashGridOptions.
    grid_options: dict[str, Any] = {
        "suppressMultiSort": True,
        "defaultColDef": {"sortable": True, "filter": False, "resizable": True, "minWidth": 80},
    }
    if pinned is not None:
        grid_options["pinnedBottomRowData"] = pinned
    return data_grid(
        id="viewer-result-grid",
        columnDefs=defs,
        rowData=row_data,
        dashGridOptions=grid_options,
        dangerously_allow_code=True,
    )


def render_result_table(layout: dict[str, Any], rows: list[dict[str, Any]]) -> Any:
    """Bảng kết quả theo layout web (header LABEL, format theo mask)."""
    columns = layout.get("columns", [])
    if not rows:
        return empty_state(
            "Không có dòng nào.",
            "Thử đổi tham số hoặc khoảng thời gian rồi chạy lại.",
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
    def _align(c_meta: dict[str, Any]) -> str:
        a = str(c_meta.get("alignment") or "LEFT").upper()
        if a in ("CENTER", "GIỮA", "GIUA"):
            return "center"
        if a in ("RIGHT", "PHẢI", "PHAI"):
            return "right"
        return "left"

    def _val(row_dict: dict[str, Any], f_name: str) -> Any:
        if f_name in row_dict:
            return row_dict[f_name]
        if f_name.upper() in row_dict:
            return row_dict[f_name.upper()]
        if f_name.lower() in row_dict:
            return row_dict[f_name.lower()]
        return None

    header = [
        dmc.TableTh(
            dmc.Button(
                c["label"],
                variant="subtle",
                size="xs",
                id={"type": "viewer-sort", "index": c["field_name"]},
                **{"aria-label": f"Sắp xếp theo {c['label']}"},
            ),
            style={**th_style, "textAlign": _align(c)},
        )
        for c in columns
    ]
    body = []
    for row in rows:
        body.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        _format_cell(_val(row, c["field_name"]), c),
                        style={"textAlign": _align(c), "height": "32px"},
                    )
                    for c in columns
                ]
            )
        )

    has_total = any(bool(c.get("is_total")) for c in columns)
    tfoot = None
    if has_total:
        tfoot_cells = []
        is_first = True
        for c in columns:
            if c.get("is_total") and c.get("data_type") == "NUMBER":
                total_val = 0.0
                for row in rows:
                    val = row.get(c["field_name"])
                    if val is not None:
                        try:
                            total_val += float(val)
                        except (TypeError, ValueError):
                            pass
                formatted = _format_cell(total_val, c)
                tfoot_cells.append(
                    dmc.TableTd(
                        dmc.Text(formatted, fw=700, size="xs"),
                        style={
                            "textAlign": _align(c),
                            "height": "34px",
                            "fontWeight": 700,
                            "backgroundColor": "var(--surface-2, #FAFAFA)",
                            "borderTop": "2px solid var(--line, #E0E0E0)",
                        },
                    )
                )
            else:
                label_text = "Tổng cộng" if is_first else ""
                tfoot_cells.append(
                    dmc.TableTd(
                        dmc.Text(label_text, fw=700, size="xs") if label_text else "",
                        style={
                            "textAlign": _align(c),
                            "height": "34px",
                            "fontWeight": 700,
                            "backgroundColor": "var(--surface-2, #FAFAFA)",
                            "borderTop": "2px solid var(--line, #E0E0E0)",
                        },
                    )
                )
            is_first = False
        tfoot = dmc.TableTfoot(dmc.TableTr(tfoot_cells))

    table_children = [dmc.TableThead(dmc.TableTr(header)), dmc.TableTbody(body)]
    if tfoot:
        table_children.append(tfoot)

    return dmc.Paper(
        dmc.TableScrollContainer(
            minWidth=800,
            style={"height": "100%", "overflow": "auto"},
            children=dmc.Table(
                table_children,
                striped=True,
                highlightOnHover=True,
                withTableBorder=False,
                withColumnBorders=False,
                style={"fontSize": "13px"},
            ),
        ),
        withBorder=True,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "overflow": "hidden", "display": "flex", "flexDirection": "column"},
    )
