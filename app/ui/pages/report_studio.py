"""Trang Report Studio Designer (/report-studio/<report_id>) — Bước 3 task 109.

Khung 3 panel Fluent Compact, không cuộn cả trang (Trường & Chỉ số |
Report Canvas 12 cột | Thiết lập biểu đồ & dữ liệu), header (Xem trước,
Kiểm tra, Lưu nháp, Phát hành), Status Bar, tìm kiếm trường in-memory,
ẩn field HIDDEN, nhóm Dimensions / Ngày (phân cấp ảo) / Measures.

Route /report-studio/<id>/edit redirect 302 về /report-studio/<id> (xem
app/ui/app.py), giống mẫu Model Studio task 107: chế độ sửa hay chỉ đọc
phụ thuộc trạng thái version (DRAFT/DRY_RUN_OK sửa được, ACTIVE chỉ đọc).
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.schemas.errors import ErrorCode
from app.schemas.semantic_model import allowed_aggregations_for
from app.services.perm import page_gate
from app.services.report_studio import (
    get_studio_draft,
    list_studio_reports,
    open_or_create_studio_draft,
    preview_studio_visual,
    publish_studio_report,
    save_studio_draft,
    validate_studio_report,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.error_state import error_state
from app.ui.components.notification import toast_error, toast_success
from app.ui.components.page_header import page_header
from app.ui.components.semantic_visuals import render_semantic_visual
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/report-studio/<report_id>",
        path="/report-studio/1",
        title="Report Studio – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_studio"

_EDITABLE_STATUSES = ("DRAFT", "DRY_RUN_OK")
_DATE_TYPES = ("DATE", "DATETIME")

# Well cho phép theo loại visual (đồng bộ _VISUAL_WELLS ở service report_studio).
_VISUAL_WELLS_UI: dict[str, tuple[str, ...]] = {
    "TABLE": ("X", "Y"),
    "MATRIX": ("ROWS", "COLUMNS", "VALUES"),
    "KPI": ("VALUE",),
    "BAR": ("X", "Y", "SERIES"),
    "LINE": ("X", "Y", "SERIES"),
}
_DIMENSION_WELLS_UI = ("X", "ROWS", "COLUMNS", "SERIES")
_MEASURE_WELLS_UI = ("Y", "VALUES", "VALUE")
_SINGLE_SLOT_WELLS = ("ROWS", "COLUMNS", "VALUES", "VALUE")
_WELL_LABELS: dict[str, str] = {
    "X": "Trục X — Dimension",
    "Y": "Giá trị — Measure",
    "ROWS": "Hàng — Dimension",
    "COLUMNS": "Cột — Dimension",
    "VALUES": "Giá trị — Measure",
    "VALUE": "Giá trị — Measure",
    "SERIES": "Chuỗi — Dimension",
}
# Remap well khi đổi loại visual: (well cũ, loại mới) -> well mới.
_REMAP_WELL: dict[tuple[str, str], str] = {
    ("X", "MATRIX"): "ROWS",
    ("Y", "MATRIX"): "VALUES",
    ("SERIES", "MATRIX"): "COLUMNS",
    ("VALUE", "MATRIX"): "VALUES",
    ("Y", "KPI"): "VALUE",
    ("VALUES", "KPI"): "VALUE",
    ("ROWS", "TABLE"): "X",
    ("COLUMNS", "TABLE"): "X",
    ("VALUES", "TABLE"): "Y",
    ("VALUE", "TABLE"): "Y",
    ("ROWS", "BAR"): "X",
    ("COLUMNS", "BAR"): "SERIES",
    ("VALUES", "BAR"): "Y",
    ("VALUE", "BAR"): "Y",
    ("ROWS", "LINE"): "X",
    ("COLUMNS", "LINE"): "SERIES",
    ("VALUES", "LINE"): "Y",
    ("VALUE", "LINE"): "Y",
}
_FILTER_OPERATORS = ("=", ">=", "<=", "LIKE_PREFIX")
_FILTER_OPERATOR_LABELS: dict[str, str] = {
    "=": "Bằng (=)",
    ">=": "Lớn hơn hoặc bằng (>=)",
    "<=": "Nhỏ hơn hoặc bằng (<=)",
    "LIKE_PREFIX": "Bắt đầu bằng",
}


def _fmt_dt(val: Any) -> str:
    if not val:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", ""))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)


def load_designer_draft(
    ctx: Ctx, report_id: str | int | None
) -> tuple[dict[str, Any] | None, str | None, bool]:
    """Nạp bản nháp hiện tại (DRAFT) hoặc version mới nhất (ACTIVE: chỉ đọc).

    Không tự tạo bản nháp khi chỉ mở xem (mẫu Model Studio task 107).
    """
    try:
        rid = int(str(report_id or "0"))
    except ValueError:
        return None, "Mã báo cáo không hợp lệ.", False
    if rid <= 0:
        return None, "Mã báo cáo không hợp lệ.", False
    listed = list_studio_reports(ctx)
    if not listed.ok:
        return None, listed.message or "Không tải được báo cáo.", False
    target = next((r for r in (listed.data or []) if int(r["id"]) == rid), None)
    if target is None:
        return None, "Không tìm thấy báo cáo.", False
    detail_res = get_studio_draft(ctx, int(target["version_id"]))
    if not detail_res.ok or not detail_res.data:
        return None, detail_res.message or "Không mở được bản nháp.", False
    detail = detail_res.data
    is_editable = str(detail["version"]["status"]) in _EDITABLE_STATUSES
    return detail, None, is_editable


def _visible_fields(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Toàn bộ field đang hiển thị của bundle (ẩn HIDDEN + bảng ẩn)."""
    out: list[dict[str, Any]] = []
    for table in bundle.get("tables") or []:
        if table.get("is_hidden"):
            continue
        for f in table.get("fields") or []:
            if not f.get("is_visible") or str(f.get("field_role") or "").upper() == "HIDDEN":
                continue
            item = dict(f)
            item["table_alias"] = str(table.get("alias") or table.get("source_object") or "")
            item["table_id"] = int(table["id"])
            out.append(item)
    return out


def _is_detail_editable(detail: dict[str, Any] | None) -> bool:
    """Bản nháp DRAFT/DRY_RUN_OK mới sửa được; ACTIVE/ARCHIVED là chỉ đọc."""
    status = str(((detail or {}).get("version") or {}).get("status") or "DRAFT").upper()
    return status in _EDITABLE_STATUSES


def _field_hay(f: dict[str, Any]) -> str:
    return (
        f"{f.get('table_alias', '')} {f.get('source_column', '')} "
        f"{f.get('field_code', '')} {f.get('display_name', '')}"
    ).lower()


def _field_row(
    f: dict[str, Any],
    *,
    kind: str,
    matched: bool = False,
    is_editable: bool = True,
) -> Any:
    """Một dòng field: checkbox + tên/kiểu + nút + (thêm vào visual)."""
    fid = int(f["id"])
    row_cls = "rs-field-row rs-match" if matched else "rs-field-row"
    label = str(f.get("display_name") or f.get("field_code") or f.get("source_column"))
    code = str(f.get("field_code") or f.get("source_column") or "")
    dtype = str(f.get("data_type") or "")
    return html.Div(
        dmc.Group(
            [
                html.Span(
                    DashIconify(icon="lucide:grip-vertical", width=13),
                    className="rs-drag-handle",
                ),
                dmc.Checkbox(
                    id={"type": "rs-field-check", "kind": kind, "id": fid},
                    size="xs",
                    disabled=not is_editable,
                    **{"aria-label": f"Chọn trường {code}"},
                ),
                dmc.Stack(
                    [
                        dmc.Text(label, size="xs", fw=600 if matched else 500, className="rh-code"),
                        dmc.Text(f"{code} · {dtype}", size="xs", c="dimmed", className="rh-code"),
                    ],
                    gap=0,
                    style={"flex": 1, "minWidth": 0},
                ),
                dmc.ActionIcon(
                    DashIconify(icon="lucide:plus", width=14),
                    id={"type": "rs-field-add-btn", "kind": kind, "id": fid},
                    variant="subtle",
                    color="gray",
                    size="sm",
                    disabled=not is_editable,
                    **{"aria-label": f"Thêm trường {code} vào visual"},
                ),
            ],
            gap="xs",
            align="center",
            wrap="nowrap",
        ),
        className=row_cls,
        **{"data-kind": kind, "data-field-id": str(fid)},  # type: ignore[arg-type]
    )


def render_fields_panel(
    bundle: dict[str, Any],
    *,
    query: str = "",
    is_editable: bool = True,
) -> Any:
    """Panel trái: trường nhóm theo Dimensions / Ngày (phân cấp ảo) / Measures.

    Tìm kiếm lọc in-memory trên bundle đã tải (không query DB); field HIDDEN
    không bao giờ hiện; từ khóa khớp tên bảng cũng mở rộng nhóm liên quan.
    """
    q = (query or "").strip().lower()
    fields = _visible_fields(bundle)
    measures = [m for m in (bundle.get("measures") or [])]

    dim_fields = [
        f
        for f in fields
        if str(f.get("data_type") or "").upper() not in _DATE_TYPES
        and (not q or q in _field_hay(f))
    ]
    date_fields = [
        f
        for f in fields
        if str(f.get("data_type") or "").upper() in _DATE_TYPES
        and (not q or q in _field_hay(f))
    ]
    shown_measures = [
        m
        for m in measures
        if not q or q in str(m.get("code", "")).lower() or q in str(m.get("name", "")).lower()
    ]
    if q and not dim_fields and not date_fields and not shown_measures:
        return empty_state(
            title="Không tìm thấy trường",
            description="Thử từ khóa khác hoặc xóa bộ lọc tìm kiếm.",
        )

    group_nodes: list[Any] = []
    if dim_fields:
        group_nodes.append(dmc.Text("Dimensions", fw=700, size="xs", px="xs", pt="xs"))
        group_nodes.append(
            dmc.Stack(
                [
                    _field_row(f, kind="field", matched=bool(q and q in _field_hay(f)), is_editable=is_editable)
                    for f in dim_fields
                ],
                gap=2,
                px="xs",
                py=4,
            )
        )
    if date_fields:
        group_nodes.append(dmc.Text("Ngày (phân cấp ảo)", fw=700, size="xs", px="xs", pt="xs"))
        group_nodes.append(
            dmc.Stack(
                [
                    _field_row(f, kind="field", matched=bool(q and q in _field_hay(f)), is_editable=is_editable)
                    for f in date_fields
                ],
                gap=2,
                px="xs",
                py=4,
            )
        )
    if shown_measures:
        group_nodes.append(dmc.Text("Measures", fw=700, size="xs", px="xs", pt="xs"))
        group_nodes.append(
            dmc.Stack(
                [
                    _field_row(
                        {
                            "id": int(m["id"]),
                            "display_name": str(m.get("name") or m.get("code")),
                            "field_code": str(m.get("code")),
                            "source_column": str(m.get("code")),
                            "data_type": "MEASURE",
                        },
                        kind="measure",
                        matched=bool(q),
                        is_editable=is_editable,
                    )
                    for m in shown_measures
                ],
                gap=2,
                px="xs",
                py=4,
            )
        )
    if not group_nodes:
        return empty_state(
            title="Mô hình chưa có trường nào",
            description="Mô hình đã pin chưa có field hoặc measure hiển thị.",
        )
    return dmc.Stack(group_nodes, gap=0)


def _visual_wells_summary(visual: dict[str, Any], bundle: dict[str, Any]) -> str:
    """Tóm tắt wells của visual: 'X: CUSTOMER_NAME · Y: REV_SUM (SUM)'."""
    by_role: dict[str, list[dict[str, Any]]] = {}
    for f in visual.get("fields") or []:
        by_role.setdefault(str(f.get("well_role") or ""), []).append(f)
    parts: list[str] = []
    for role in _VISUAL_WELLS_UI.get(str(visual.get("visual_type") or ""), ()):
        items = by_role.get(role, [])
        if not items:
            continue
        labels = [
            _field_label(bundle, field_id=f.get("field_id"), measure_id=f.get("measure_id"))
            for f in items
        ]
        parts.append(f"{role}: {', '.join(labels)}")
    return " · ".join(parts) if parts else "Chưa có trường"


def render_preview_filter_bar(detail: dict[str, Any]) -> Any:
    """Thanh lọc xem thử trên canvas (chế độ Xem trước): 1 bộ lọc report-level."""
    bundle = detail.get("model") or {}
    options = [
        {
            "label": str(f.get("display_name") or f.get("field_code")),
            "value": str(f["id"]),
        }
        for f in _visible_fields(bundle)
        if str(f.get("data_type") or "").upper() not in _DATE_TYPES
    ]
    return dmc.Group(
        [
            dmc.Select(
                id="rs-preview-filter-field",
                data=options,
                placeholder="Trường lọc",
                value=None,
                size="xs",
                w=200,
                clearable=True,
                **{"aria-label": "Trường lọc xem trước"},
            ),
            dmc.Select(
                id="rs-preview-filter-op",
                data=[
                    {"label": _FILTER_OPERATOR_LABELS[o], "value": o}
                    for o in _FILTER_OPERATORS
                ],
                value="=",
                size="xs",
                w=150,
                **{"aria-label": "Toán tử lọc xem trước"},
            ),
            dmc.TextInput(
                id="rs-preview-filter-value",
                placeholder="Giá trị lọc...",
                value="",
                size="xs",
                debounce=300,
                style={"flex": 1},
                **{"aria-label": "Giá trị lọc xem trước"},
            ),
            dmc.ActionIcon(
                DashIconify(icon="lucide:x", width=14),
                id="rs-preview-filter-clear",
                variant="subtle",
                color="gray",
                size="sm",
                **{"aria-label": "Xóa bộ lọc xem trước"},
            ),
        ],
        gap="xs",
        className="rs-preview-filter-bar",
    )


def render_canvas_panel(
    detail: dict[str, Any],
    *,
    preview_mode: bool = False,
    previews: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    dark_mode: bool = False,
    is_editable: bool | None = None,
) -> Any:
    """Panel giữa: lưới 12 cột chứa các visual (thiết kế hoặc xem trước dữ liệu)."""
    editable = _is_detail_editable(detail) if is_editable is None else bool(is_editable)
    visuals = sorted(detail.get("visuals") or [], key=lambda v: int(v.get("display_order") or 0))
    sel_code = (selection or {}).get("visual_code")
    bundle = detail.get("model") or {}
    nodes: list[Any] = []
    if preview_mode:
        nodes.append(
            alert_box(
                title="Chế độ xem trước",
                message="Đang xem báo cáo như người đọc. Bấm Quay lại thiết kế để chỉnh sửa.",
                tone="info",
            )
        )
    if not visuals:
        nodes.append(
            empty_state(
                title="Chưa có visual",
                description="Chọn trường ở panel trái rồi bấm + để thêm visual đầu tiên.",
                icon="lucide:bar-chart-2",
            )
        )
    elif preview_mode:
        preview_results = (previews or {}).get("results") or {}
        for vis in visuals:
            code = str(vis.get("code"))
            nodes.append(
                dmc.Stack(
                    [
                        dmc.Text(str(vis.get("title") or code), fw=600, size="sm"),
                        _preview_visual_node(vis, preview_results.get(code), dark_mode=dark_mode),
                    ],
                    gap="xs",
                )
            )
    else:
        cols: list[Any] = []
        for vis in visuals:
            code = str(vis.get("code"))
            is_sel = str(sel_code) == code
            # Nút hành động (lên/xuống/nhân bản/xóa) KHÔNG được nằm trong div
            # clickable chọn visual: click nút sẽ bubble lên n_clicks của
            # card, bắn thêm handle_visual_select và vẽ lại canvas từ
            # store cũ — đè kết quả của action (visual mới nhân bản biến
            # mất khỏi canvas dù store đã có; xóa xong visual hiện lại).
            card_body = html.Div(
                [
                    dmc.Group(
                        [
                            html.Span(
                                DashIconify(icon="lucide:grip-vertical", width=13),
                                className="rs-drag-handle",
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text(str(vis.get("title") or code), fw=600, size="sm"),
                                    dmc.Text(
                                        f"{vis.get('visual_type')} · {vis.get('grid_span')} cột · {vis.get('height_size')}",
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ],
                                gap=2,
                                style={"flex": 1, "minWidth": 0},
                            ),
                            dmc.Badge(str(vis.get("visual_type") or ""), size="xs", variant="light"),
                        ],
                        gap="xs",
                        align="flex-start",
                        wrap="nowrap",
                    ),
                    dmc.Text(
                        _visual_wells_summary(vis, bundle),
                        size="xs",
                        c="dimmed",
                        className="rh-code",
                    ),
                ],
                id={"type": "rs-visual-card", "code": code},
                n_clicks=0,
                className="rs-visual-card-body",
                **{"data-visual-code": code, "role": "button", "tabIndex": "0"},  # type: ignore[arg-type]
            )
            card = html.Div(
                [
                    card_body,
                    dmc.Group(
                        [
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:arrow-up", width=14),
                                id={"type": "rs-visual-move-up", "code": code},
                                variant="subtle",
                                color="gray",
                                size="sm",
                                disabled=not editable,
                                **{"aria-label": f"Di chuyển visual {code} lên"},
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:arrow-down", width=14),
                                id={"type": "rs-visual-move-down", "code": code},
                                variant="subtle",
                                color="gray",
                                size="sm",
                                disabled=not editable,
                                **{"aria-label": f"Di chuyển visual {code} xuống"},
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:copy", width=14),
                                id={"type": "rs-visual-duplicate", "code": code},
                                variant="subtle",
                                color="gray",
                                size="sm",
                                disabled=not editable,
                                **{"aria-label": f"Nhân bản visual {code}"},
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:trash-2", width=14),
                                id={"type": "rs-visual-delete", "code": code},
                                variant="subtle",
                                color="red",
                                size="sm",
                                disabled=not editable,
                                **{"aria-label": f"Xóa visual {code}"},
                            ),
                        ],
                        gap=4,
                        justify="flex-end",
                    ),
                ],
                className="rs-visual-card rs-selected" if is_sel else "rs-visual-card",
                **{"data-visual-code": code},  # type: ignore[arg-type]
            )
            cols.append(dmc.GridCol(card, span=int(vis.get("grid_span") or 12)))
        nodes.append(dmc.Grid(cols, gutter="sm"))
    return dmc.Stack(nodes, gap="sm")


def _preview_visual_node(
    visual: dict[str, Any], item: dict[str, Any] | None, *, dark_mode: bool = False
) -> Any:
    """Một visual trong chế độ Xem trước: loading / error+retry / data."""
    if item is None:
        return render_semantic_visual(visual, None, state="loading")
    if item.get("state") == "error":
        return render_semantic_visual(
            visual, None, state="error", error_message=str(item.get("error") or "")
        )
    return render_semantic_visual(
        visual, item.get("data"), state="data", dark_mode=dark_mode
    )


def _well_field_row(
    visual: dict[str, Any],
    f: dict[str, Any],
    idx: int,
    bundle: dict[str, Any],
    *,
    is_editable: bool = True,
) -> Any:
    """Một dòng field trong Data Well: nhãn + Aggregation / Date part / Sort / Format / Xóa."""
    code = str(visual.get("code"))
    label = _field_label(bundle, field_id=f.get("field_id"), measure_id=f.get("measure_id"))
    well_role = str(f.get("well_role") or "")
    field_meta = (
        next((x for x in _visible_fields(bundle) if int(x["id"]) == int(f.get("field_id") or 0)), None)
        if f.get("measure_id") is None
        else None
    )
    controls: list[Any] = [
        dmc.Text(label, size="xs", fw=500, className="rh-code", style={"flex": 1, "minWidth": 0}),
    ]
    if f.get("measure_id") is not None:
        controls.append(dmc.Text("NONE", size="xs", c="dimmed"))
    elif well_role in _MEASURE_WELLS_UI:
        options = [
            a
            for a in allowed_aggregations_for(str((field_meta or {}).get("data_type") or ""))
            if a != "NONE"
        ]
        controls.append(
            dmc.Select(
                id={"type": "rs-well-agg", "code": code, "idx": idx},
                data=[{"label": a, "value": a} for a in options],
                value=str(f.get("aggregation") or "NONE"),
                size="xs",
                w=96,
                disabled=not is_editable,
                **{"aria-label": f"Aggregation của {label}"},
            )
        )
    elif (
        well_role in _DIMENSION_WELLS_UI
        and str((field_meta or {}).get("data_type") or "").upper() in _DATE_TYPES
    ):
        controls.append(
            dmc.Select(
                id={"type": "rs-well-datepart", "code": code, "idx": idx},
                data=[
                    {"label": "Nguyên gốc", "value": ""},
                    {"label": "Ngày", "value": "DAY"},
                    {"label": "Tháng", "value": "MONTH"},
                    {"label": "Quý", "value": "QUARTER"},
                    {"label": "Năm", "value": "YEAR"},
                ],
                value=str(f.get("date_part") or ""),
                size="xs",
                w=96,
                disabled=not is_editable,
                **{"aria-label": f"Phân cấp ngày của {label}"},
            )
        )
    controls.append(
        dmc.Select(
            id={"type": "rs-well-sort", "code": code, "idx": idx},
            data=[
                {"label": "Không sắp xếp", "value": ""},
                {"label": "Tăng dần", "value": "ASC"},
                {"label": "Giảm dần", "value": "DESC"},
            ],
            value=str(f.get("sort_direction") or ""),
            size="xs",
            w=110,
            disabled=not is_editable,
            **{"aria-label": f"Sắp xếp của {label}"},
        )
    )
    controls.append(
        dmc.TextInput(
            id={"type": "rs-well-format", "code": code, "idx": idx},
            value=str(f.get("format_mask") or ""),
            placeholder="#,##0.00",
            size="xs",
            w=90,
            debounce=300,
            disabled=not is_editable,
            **{"aria-label": f"Định dạng của {label}"},
        )
    )
    controls.append(
        dmc.ActionIcon(
            DashIconify(icon="lucide:x", width=13),
            id={"type": "rs-well-remove", "code": code, "idx": idx},
            variant="subtle",
            color="gray",
            size="xs",
            disabled=not is_editable,
            **{"aria-label": f"Gỡ {label} khỏi visual"},
        )
    )
    return dmc.Group(controls, gap="xs", align="center", wrap="nowrap")


def _render_report_params_section(detail: dict[str, Any], *, is_editable: bool) -> list[Any]:
    """Khối cấu hình tham số báo cáo (RECON_RPT_PARAM) hiển thị trên Viewer."""
    bundle = detail.get("model") or {}
    params = list(detail.get("params") or [])
    nodes: list[Any] = [
        dmc.Divider(),
        dmc.Text("Tham số / Bộ lọc báo cáo (Viewer)", fw=700, size="xs"),
    ]
    for p in params:
        pcode = str(p.get("code") or "")
        nodes.append(
            dmc.Group(
                [
                    dmc.Text(
                        f"{p.get('label') or pcode} ({p.get('filter_column') or pcode} {p.get('filter_operator') or '='})",
                        size="xs",
                        className="rh-code",
                        style={"flex": 1, "minWidth": 0},
                    ),
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:x", width=13),
                        id={"type": "rs-param-remove", "code": pcode},
                        variant="subtle",
                        color="gray",
                        size="xs",
                        disabled=not is_editable,
                        **{"aria-label": f"Xóa tham số {pcode}"},
                    ),
                ],
                gap="xs",
                justify="space-between",
                wrap="nowrap",
            )
        )
    if not params:
        nodes.append(dmc.Text("Chưa có tham số báo cáo nào.", size="xs", c="dimmed"))
    field_options = [
        {
            "label": str(f.get("display_name") or f.get("field_code")),
            "value": str(f["id"]),
        }
        for f in _visible_fields(bundle)
    ]
    nodes.append(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Select(
                            id={"type": "rs-param-field", "k": "main"},
                            data=field_options,
                            placeholder="Trường lọc",
                            size="xs",
                            clearable=True,
                            disabled=not is_editable,
                            style={"flex": 1},
                        ),
                        dmc.Select(
                            id={"type": "rs-param-op", "k": "main"},
                            data=[
                                {"label": _FILTER_OPERATOR_LABELS[o], "value": o}
                                for o in _FILTER_OPERATORS
                            ],
                            value="=",
                            size="xs",
                            w=110,
                            disabled=not is_editable,
                        ),
                    ],
                    gap="xs",
                    wrap="nowrap",
                ),
                dmc.Group(
                    [
                        dmc.TextInput(
                            id={"type": "rs-param-label", "k": "main"},
                            placeholder="Nhãn hiển thị ở Viewer...",
                            size="xs",
                            disabled=not is_editable,
                            style={"flex": 1},
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:plus", width=14),
                            id={"type": "rs-param-add-btn", "k": "main"},
                            variant="light",
                            size="sm",
                            disabled=not is_editable,
                            **{"aria-label": "Thêm tham số báo cáo"},
                        ),
                    ],
                    gap="xs",
                    wrap="nowrap",
                ),
            ],
            gap="xs",
        )
    )
    return nodes


def render_settings_panel(
    detail: dict[str, Any],
    selection: dict[str, Any] | None = None,
    *,
    is_editable: bool | None = None,
) -> Any:
    """Panel phải: thiết lập visual đang chọn (loại, lưới, Data Wells, bộ lọc) hoặc tham số báo cáo."""
    editable = _is_detail_editable(detail) if is_editable is None else bool(is_editable)
    visuals = list(detail.get("visuals") or [])
    sel_code = (selection or {}).get("visual_code")
    selected = next((v for v in visuals if str(v.get("code")) == str(sel_code)), None) if sel_code else None
    if selected is None:
        return dmc.Stack(
            [
                dmc.Text("Thiết lập biểu đồ & dữ liệu", fw=700, size="xs"),
                dmc.Text(
                    "Chọn một visual trên canvas để thiết lập loại biểu đồ, Data Wells, format và bộ lọc.",
                    size="xs",
                    c="dimmed",
                ),
                dmc.Divider(),
                dmc.Text("Báo cáo", fw=700, size="xs"),
                dmc.Text(f"Mô hình: {(detail.get('model') or {}).get('model', {}).get('code', '—')}", size="xs"),
                dmc.Text(f"Phiên bản: v{detail['version']['version_no']} ({detail['version']['status']})", size="xs"),
                *_render_report_params_section(detail, is_editable=editable),
            ],
            gap="xs",
            p="xs",
        )
    bundle = detail.get("model") or {}
    code = str(selected.get("code"))
    vtype = str(selected.get("visual_type") or "TABLE")
    nodes: list[Any] = [
        dmc.Text("Thiết lập biểu đồ & dữ liệu", fw=700, size="xs"),
        dmc.TextInput(
            id="rs-set-title",
            label="Tiêu đề biểu đồ",
            value=str(selected.get("title") or ""),
            size="xs",
            debounce=300,
            disabled=not editable,
        ),
        dmc.Select(
            id="rs-set-type",
            label="Loại visual",
            data=[{"label": t, "value": t} for t in ("TABLE", "MATRIX", "KPI", "BAR", "LINE")],
            value=vtype,
            size="xs",
            disabled=not editable,
        ),
        dmc.Group(
            [
                dmc.Select(
                    id="rs-set-grid-span",
                    label="Rộng (cột)",
                    data=[{"label": str(s), "value": str(s)} for s in (3, 4, 6, 8, 12)],
                    value=str(selected.get("grid_span") or 12),
                    size="xs",
                    disabled=not editable,
                    style={"flex": 1},
                ),
                dmc.Select(
                    id="rs-set-height-size",
                    label="Cao",
                    data=[{"label": s, "value": s} for s in ("S", "M", "L")],
                    value=str(selected.get("height_size") or "M"),
                    size="xs",
                    disabled=not editable,
                    style={"flex": 1},
                ),
            ],
            gap="xs",
            grow=True,
        ),
        dmc.Divider(),
    ]
    fields = list(selected.get("fields") or [])
    for role in _VISUAL_WELLS_UI.get(vtype, ()):
        nodes.append(dmc.Text(_WELL_LABELS.get(role, role), fw=600, size="xs"))
        well_rows: list[Any] = []
        for idx, f in enumerate(fields):
            if str(f.get("well_role")) == role:
                well_rows.append(_well_field_row(selected, f, idx, bundle, is_editable=editable))
        nodes.append(
            html.Div(
                well_rows
                + [
                    dmc.Text(
                        "Kéo field vào đây hoặc bấm + ở panel trái.",
                        size="xs",
                        c="dimmed",
                    )
                ],
                className="rs-well-drop",
                **{"data-visual-code": code, "data-well-role": role},  # type: ignore[arg-type]
            )
        )
    filters = list((selected.get("config") or {}).get("filters") or [])
    nodes.append(dmc.Divider())
    nodes.append(dmc.Text("Bộ lọc visual", fw=600, size="xs"))
    for i, flt in enumerate(filters):
        label = _field_label(bundle, field_id=flt.get("field_id"), measure_id=None)
        nodes.append(
            dmc.Group(
                [
                    dmc.Text(
                        f"{label} {flt.get('operator')} {flt.get('value')}",
                        size="xs",
                        className="rh-code",
                        style={"flex": 1, "minWidth": 0},
                    ),
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:x", width=13),
                        id={"type": "rs-visual-filter-remove", "code": code, "idx": i},
                        variant="subtle",
                        color="gray",
                        size="xs",
                        disabled=not editable,
                        **{"aria-label": "Xóa bộ lọc visual"},
                    ),
                ],
                gap="xs",
                justify="space-between",
                wrap="nowrap",
            )
        )
    field_options = [
        {
            "label": str(f.get("display_name") or f.get("field_code")),
            "value": str(f["id"]),
        }
        for f in _visible_fields(bundle)
    ]
    nodes.append(
        dmc.Group(
            [
                dmc.Select(
                    id="rs-filter-field",
                    data=field_options,
                    placeholder="Trường",
                    size="xs",
                    style={"flex": 1},
                    clearable=True,
                    disabled=not editable,
                ),
                dmc.Select(
                    id="rs-filter-op",
                    data=[
                        {"label": _FILTER_OPERATOR_LABELS[o], "value": o}
                        for o in _FILTER_OPERATORS
                    ],
                    value="=",
                    size="xs",
                    w=110,
                    disabled=not editable,
                ),
                dmc.TextInput(
                    id="rs-filter-value",
                    placeholder="Giá trị",
                    size="xs",
                    disabled=not editable,
                    style={"flex": 1},
                ),
                dmc.ActionIcon(
                    DashIconify(icon="lucide:plus", width=14),
                    id="rs-filter-add-btn",
                    variant="light",
                    size="sm",
                    disabled=not editable,
                    **{"aria-label": "Thêm bộ lọc visual"},
                ),
            ],
            gap="xs",
            wrap="nowrap",
        )
    )
    nodes.append(dmc.Divider())
    nodes.append(
        dmc.Button(
            "Xóa visual",
            id={"type": "rs-visual-delete-btn", "code": code},
            size="xs",
            variant="outline",
            color="red",
            disabled=not editable,
            leftSection=DashIconify(icon="lucide:trash-2", width=14),
        )
    )
    return dmc.Stack(nodes, gap="xs", p="xs")


def render_status_bar(detail: dict[str, Any], *, dirty: bool = False) -> Any:
    """Thanh trạng thái dưới cùng: version, model, số visual, trạng thái lưu."""
    version = detail["version"]
    model = (detail.get("model") or {}).get("model") or {}
    status = str(version.get("status") or "DRAFT")
    return dmc.Group(
        [
            status_chip(status, size="xs"),
            dmc.Text(
                f"{detail['report']['code']} · v{version.get('version_no')} · Model {model.get('code', '—')}",
                size="xs",
                className="rh-code",
            ),
            dmc.Text(f"{len(detail.get('visuals') or [])} visual", size="xs", c="dimmed"),
            dmc.Text(
                "Chưa lưu thay đổi" if dirty else "Đã lưu",
                size="xs",
                c="orange" if dirty else "dimmed",
                fw=600 if dirty else 400,
            ),
        ],
        gap="md",
        justify="space-between",
        id="rs-status-bar",
        className="rs-status-bar",
    )


def render_designer_header(
    detail: dict[str, Any], *, is_editable: bool, preview_mode: bool = False
) -> Any:
    """Header designer: tiêu đề báo cáo + Xem trước / Kiểm tra / Lưu nháp / Phát hành."""
    report = detail["report"]
    version = detail["version"]
    status = str(version.get("status") or "DRAFT")
    title_group = dmc.Group(
        [
            dmc.Text(str(report.get("name") or ""), fw=700, size="md"),
            dmc.Badge(str(report.get("code") or ""), size="xs", variant="light", className="rh-code"),
            status_chip(status, size="xs"),
        ],
        gap="xs",
    )
    more_menu = dmc.Menu(
        [
            dmc.MenuTarget(
                dmc.ActionIcon(
                    DashIconify(icon="lucide:ellipsis", width=16),
                    id="rs-more-btn",
                    variant="subtle",
                    color="gray",
                    size="sm",
                    **{"aria-label": "Thêm thao tác"},
                )
            ),
            dmc.MenuDropdown(
                [
                    dmc.MenuItem(
                        "Xem ở /reports",
                        id="rs-menu-view-report",
                        leftSection=DashIconify(icon="lucide:eye", width=13),
                    ),
                    dmc.MenuItem(
                        "Quay lại Report Studio",
                        id="rs-menu-back-center",
                        leftSection=DashIconify(icon="lucide:arrow-left", width=13),
                    ),
                ]
            ),
        ],
        position="bottom-end",
    )
    actions: list[Any] = [
        dmc.Button(
            "Quay lại thiết kế" if preview_mode else "Xem trước",
            id="rs-preview-btn",
            size="xs",
            radius="xl",
            variant="outline",
            color="gray",
            leftSection=DashIconify(icon="lucide:eye" if not preview_mode else "lucide:pen-line", width=14),
            **{"aria-label": "Xem trước báo cáo"},
        ),
        dmc.Button(
            "Kiểm tra",
            id="rs-validate-btn",
            size="xs",
            radius="xl",
            variant="outline",
            color="gray",
            disabled=not is_editable,
            leftSection=DashIconify(icon="lucide:shield-check", width=14),
            **{"aria-label": "Kiểm tra báo cáo"},
        ),
        dmc.Button(
            "Lưu nháp",
            id="rs-save-btn",
            size="xs",
            radius="xl",
            variant="outline",
            color="gray",
            disabled=not is_editable,
            leftSection=DashIconify(icon="lucide:save", width=14),
            **{"aria-label": "Lưu nháp báo cáo"},
        ),
        button_primary(
            "Phát hành",
            id="rs-publish-btn",
            icon="lucide:upload-cloud",
            size="xs",
            radius="xl",
            disabled=not is_editable,
            **{"aria-label": "Phát hành báo cáo"},  # type: ignore[arg-type]
        ),
    ]
    if not is_editable:
        actions.append(
            button_primary(
                "Tạo bản nháp mới",
                id="rs-new-draft-btn",
                icon="lucide:git-branch-plus",
                size="xs",
                radius="xl",
                **{"aria-label": "Tạo bản nháp mới từ phiên bản ACTIVE"},  # type: ignore[arg-type]
            )
        )
    actions.append(more_menu)
    return page_header(title=title_group, subtitle=None, actions=actions, mb=0)


def _visual_payload_from_store(visual: dict[str, Any]) -> dict[str, Any]:
    """Chuyển visual trong Store về payload DTO (bỏ khóa phụ như id)."""
    return {
        "code": visual.get("code"),
        "title": visual.get("title"),
        "visual_type": visual.get("visual_type"),
        "display_order": visual.get("display_order", 0),
        "grid_span": visual.get("grid_span", 12),
        "height_size": visual.get("height_size", "M"),
        "config": visual.get("config") or {},
        "fields": [
            {
                "well_role": f.get("well_role"),
                "field_id": f.get("field_id"),
                "measure_id": f.get("measure_id"),
                "aggregation": f.get("aggregation", "NONE"),
                "date_part": f.get("date_part"),
                "alias": f.get("alias"),
                "label_override": f.get("label_override"),
                "format_mask": f.get("format_mask"),
                "sort_direction": f.get("sort_direction"),
                "display_order": f.get("display_order", 0),
            }
            for f in (visual.get("fields") or [])
        ],
    }


def _next_visual_code(visuals: list[dict[str, Any]]) -> str:
    used = {str(v.get("code") or "") for v in visuals}
    n = 1
    while f"V_{n:03d}" in used:
        n += 1
    return f"V_{n:03d}"


def _field_label(bundle: dict[str, Any], *, field_id: int | None, measure_id: int | None) -> str:
    """Nhãn dùng trong danh sách field bị loại: mã field/measure (ổn định, rõ ràng)."""
    if measure_id is not None:
        for m in bundle.get("measures") or []:
            if int(m["id"]) == int(measure_id):
                return str(m.get("code"))
        return f"Measure #{measure_id}"
    for f in _visible_fields(bundle):
        if int(f["id"]) == int(field_id or 0):
            return str(f.get("field_code") or f.get("source_column"))
    return f"Field #{field_id}"


def _default_aggregation(data_type: str) -> str | None:
    """Aggregation mặc định cho field khi thả vào well measure (bỏ NONE)."""
    for agg in allowed_aggregations_for(data_type):
        if agg != "NONE":
            return agg
    return None


def apply_field_drop(
    detail: dict[str, Any],
    *,
    kind: str,
    field_id: int,
    visual_code: str,
    well_role: str,
) -> tuple[dict[str, Any], str | None]:
    """Thả field/measure vào Data Well của visual (kéo-thả hoặc nút +).

    Trả (detail_mới, None) khi hợp lệ; (detail_cũ, lý_do) khi drop không hợp
    lệ — visual giữ nguyên, không đổi gì (TC-FN-03).
    """
    bundle = detail.get("model") or {}
    visuals = list(detail.get("visuals") or [])
    visual = next((v for v in visuals if str(v.get("code")) == str(visual_code)), None)
    if visual is None:
        return detail, f"Không tìm thấy visual {visual_code}."
    vtype = str(visual.get("visual_type") or "TABLE")
    allowed = _VISUAL_WELLS_UI.get(vtype, ())
    if well_role not in allowed:
        return detail, f"Visual {vtype} không dùng well {well_role}."
    fields = list(visual.get("fields") or [])
    if kind == "measure":
        if well_role not in _MEASURE_WELLS_UI:
            return (
                detail,
                f"Measure chỉ đặt được ở well giá trị (Y / VALUES / VALUE), "
                f"không đặt được ở well {well_role}.",
            )
        measure = next(
            (m for m in (bundle.get("measures") or []) if int(m["id"]) == int(field_id)),
            None,
        )
        if measure is None:
            return detail, "Không tìm thấy measure trong mô hình."
        if any(int(f.get("measure_id") or 0) == int(field_id) for f in fields if f.get("well_role") == well_role):
            return detail, "Measure này đã có trong well."
        if well_role in _SINGLE_SLOT_WELLS and any(f.get("well_role") == well_role for f in fields):
            return detail, f"Well {well_role} chỉ chứa một measure."
        entry = {
            "well_role": well_role,
            "field_id": None,
            "measure_id": int(field_id),
            "aggregation": "NONE",
            "date_part": None,
            "alias": None,
            "label_override": None,
            "format_mask": None,
            "sort_direction": None,
            "display_order": (max([int(f.get("display_order") or 0) for f in fields], default=0) + 10),
        }
    else:
        field = next(
            (f for f in _visible_fields(bundle) if int(f["id"]) == int(field_id)),
            None,
        )
        if field is None:
            return detail, "Không tìm thấy trường trong mô hình."
        if any(int(f.get("field_id") or 0) == int(field_id) for f in fields if f.get("well_role") == well_role):
            return detail, "Trường này đã có trong well."
        if well_role in _SINGLE_SLOT_WELLS and any(f.get("well_role") == well_role for f in fields):
            return detail, f"Well {well_role} chỉ chứa một trường."
        if well_role in _MEASURE_WELLS_UI:
            agg = _default_aggregation(str(field.get("data_type") or ""))
            if agg is None:
                return (
                    detail,
                    f"Trường {field.get('field_code')} không tổng hợp được ở well {well_role}.",
                )
        else:
            agg = "NONE"
        entry = {
            "well_role": well_role,
            "field_id": int(field_id),
            "measure_id": None,
            "aggregation": agg,
            "date_part": None,
            "alias": None,
            "label_override": None,
            "format_mask": None,
            "sort_direction": None,
            "display_order": (max([int(f.get("display_order") or 0) for f in fields], default=0) + 10),
        }
    new_detail = copy.deepcopy(detail)
    new_visual = next(v for v in new_detail["visuals"] if str(v.get("code")) == str(visual_code))
    new_visual["fields"] = [*fields, entry]
    return new_detail, None


def remap_visual_fields(
    visual: dict[str, Any], new_type: str, bundle: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Tính lại fields khi đổi loại visual: (fields_giữ_lại, nhãn_field_bị_loại).

    Well cùng tên giữ nguyên; well khác tên được remap theo _REMAP_WELL;
    well đơn (ROWS/COLUMNS/VALUES/VALUE) chỉ giữ field đầu tiên.
    """
    new_type = str(new_type).upper()
    allowed = _VISUAL_WELLS_UI.get(new_type, ())
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    seen_single: set[str] = set()
    for f in visual.get("fields") or []:
        old_role = str(f.get("well_role") or "")
        new_role = old_role if old_role in allowed else _REMAP_WELL.get((old_role, new_type))
        if new_role is None or new_role not in allowed:
            dropped.append(
                _field_label(bundle, field_id=f.get("field_id"), measure_id=f.get("measure_id"))
            )
            continue
        if new_role in _SINGLE_SLOT_WELLS:
            if new_role in seen_single:
                dropped.append(
                    _field_label(bundle, field_id=f.get("field_id"), measure_id=f.get("measure_id"))
                )
                continue
            seen_single.add(new_role)
        item = dict(f)
        item["well_role"] = new_role
        kept.append(item)
    return kept, dropped


def move_visual(
    detail: dict[str, Any], code: str, direction: str
) -> tuple[dict[str, Any], bool]:
    """Đổi thứ tự visual: lên/xuống một bậc (đổi display_order với visual kề)."""
    ordered = sorted(detail.get("visuals") or [], key=lambda v: int(v.get("display_order") or 0))
    idx = next((i for i, v in enumerate(ordered) if str(v.get("code")) == str(code)), None)
    if idx is None:
        return detail, False
    swap = idx - 1 if direction == "up" else idx + 1
    if swap < 0 or swap >= len(ordered):
        return detail, False
    new_detail = copy.deepcopy(detail)
    by_code = {str(v.get("code")): v for v in new_detail["visuals"]}
    a, b = by_code[str(ordered[idx]["code"])], by_code[str(ordered[swap]["code"])]
    a["display_order"], b["display_order"] = b.get("display_order"), a.get("display_order")
    return new_detail, True


def reorder_visual(
    detail: dict[str, Any], from_code: str, to_code: str
) -> tuple[dict[str, Any], bool]:
    """Kéo-thả đổi thứ tự: đưa visual from_code tới vị trí của to_code."""
    ordered = sorted(detail.get("visuals") or [], key=lambda v: int(v.get("display_order") or 0))
    from_idx = next((i for i, v in enumerate(ordered) if str(v.get("code")) == str(from_code)), None)
    to_idx = next((i for i, v in enumerate(ordered) if str(v.get("code")) == str(to_code)), None)
    if from_idx is None or to_idx is None or from_idx == to_idx:
        return detail, False
    new_detail = copy.deepcopy(detail)
    by_code = {str(v.get("code")): v for v in new_detail["visuals"]}
    moved = by_code[str(from_code)]
    rest = [by_code[str(v["code"])] for v in ordered if str(v.get("code")) != str(from_code)]
    rest.insert(to_idx, moved)
    for i, v in enumerate(rest):
        v["display_order"] = (i + 1) * 10
    return new_detail, True


def duplicate_visual(detail: dict[str, Any], code: str) -> dict[str, Any]:
    """Nhân bản visual: giữ bindings, mã mới, tiêu đề thêm '(bản sao)'."""
    visuals = list(detail.get("visuals") or [])
    src = next((v for v in visuals if str(v.get("code")) == str(code)), None)
    if src is None:
        return detail
    new_detail = copy.deepcopy(detail)
    clone = copy.deepcopy(src)
    clone["code"] = _next_visual_code(visuals)
    clone["title"] = f"{str(src.get('title') or src.get('code'))} (bản sao)"
    clone["display_order"] = (max([int(v.get("display_order") or 0) for v in visuals], default=0) + 10)
    new_detail["visuals"] = [*visuals, clone]
    return new_detail


def delete_visual(detail: dict[str, Any], code: str) -> dict[str, Any]:
    """Xóa visual khỏi bản nháp (chỉ trên Draft, chưa chạm DB)."""
    new_detail = copy.deepcopy(detail)
    new_detail["visuals"] = [v for v in (detail.get("visuals") or []) if str(v.get("code")) != str(code)]
    return new_detail


def apply_preview_result(
    store: dict[str, Any] | None,
    visual_code: str,
    result: dict[str, Any],
    request_seq: int | None,
) -> tuple[dict[str, Any], bool]:
    """Chống stale response: chỉ nhận kết quả có request_seq >= seq hiện tại."""
    current = int((store or {}).get("seq") or 0)
    if request_seq is None or int(request_seq) < current:
        return dict(store or {}), False
    new_store: dict[str, Any] = dict(store or {})
    new_store["seq"] = int(request_seq)
    results = dict(new_store.get("results") or {})
    results[str(visual_code)] = result
    new_store["results"] = results
    return new_store, True


def add_field_to_draft(
    detail: dict[str, Any],
    *,
    kind: str,
    field_id: int,
    selection: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Thêm field/measure vào bản nháp trong Store (chưa lưu DB).

    Chưa chọn visual -> tạo visual TABLE mới; đã chọn visual TABLE/BAR/LINE ->
    thêm field vào well X (measure vào well Y); MATRIX/KPI không suy ra được
    well nên tạo visual TABLE mới.
    """
    bundle = detail.get("model") or {}
    visuals = list(detail.get("visuals") or [])
    sel_code = (selection or {}).get("visual_code")
    selected = next((v for v in visuals if str(v.get("code")) == str(sel_code)), None) if sel_code else None
    if kind == "measure":
        entry: dict[str, Any] = {
            "well_role": "Y",
            "field_id": None,
            "measure_id": int(field_id),
            "aggregation": "NONE",
            "date_part": None,
            "alias": None,
            "label_override": None,
            "format_mask": None,
            "sort_direction": None,
            "display_order": 0,
        }
        label = next(
            (str(m.get("code")) for m in (bundle.get("measures") or []) if int(m["id"]) == int(field_id)),
            f"#{field_id}",
        )
    else:
        field = next(
            (f for f in _visible_fields(bundle) if int(f["id"]) == int(field_id)),
            None,
        )
        if field is None:
            return detail, "Không tìm thấy trường trong mô hình."
        entry = {
            "well_role": "X",
            "field_id": int(field_id),
            "measure_id": None,
            "aggregation": "NONE",
            "date_part": None,
            "alias": None,
            "label_override": None,
            "format_mask": None,
            "sort_direction": None,
            "display_order": 0,
        }
        label = str(field.get("field_code") or field.get("source_column"))
    if selected is not None and str(selected.get("visual_type")) in ("TABLE", "BAR", "LINE"):
        fields = list(selected.get("fields") or [])
        if kind == "measure":
            if any(int(f.get("measure_id") or 0) == int(field_id) for f in fields if f.get("well_role") == "Y"):
                return detail, "Measure này đã có trong visual."
        elif any(int(f.get("field_id") or 0) == int(field_id) for f in fields if f.get("well_role") == "X"):
            return detail, "Trường này đã có trong visual."
        if kind == "measure":
            entry["display_order"] = (max([int(f.get("display_order") or 0) for f in fields], default=0) + 10)
            fields.append(entry)
            selected["fields"] = fields
            detail["visuals"] = visuals
            return detail, f"Đã thêm {label} vào visual {selected.get('code')}."
        entry["aggregation"] = "NONE"
        entry["display_order"] = (max([int(f.get("display_order") or 0) for f in fields], default=0) + 10)
        fields.append(entry)
        selected["fields"] = fields
        detail["visuals"] = visuals
        return detail, f"Đã thêm {label} vào visual {selected.get('code')}."
    code = _next_visual_code(visuals)
    entry["display_order"] = 10
    visuals.append(
        {
            "code": code,
            "title": f"Visual {label}",
            "visual_type": "TABLE",
            "display_order": (max([int(v.get("display_order") or 0) for v in visuals], default=0) + 10),
            "grid_span": 12,
            "height_size": "M",
            "config": {},
            "fields": [entry],
        }
    )
    detail["visuals"] = visuals
    return detail, f"Đã tạo visual {code} với trường {label}."


def add_checked_fields_to_draft(
    detail: dict[str, Any],
    checked_items: list[dict[str, Any]],
    selection: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Thêm hàng loạt các field/measure đã tick vào visual đang chọn hoặc tạo visual mới."""
    if not checked_items:
        return detail, None
    cur_detail = copy.deepcopy(detail)
    cur_sel = dict(selection) if selection else None
    added = 0
    for item in checked_items:
        kind = str(item.get("kind") or "field")
        fid = int(item.get("id") or 0)
        if fid <= 0:
            continue
        before = {str(v.get("code")) for v in (cur_detail.get("visuals") or [])}
        cur_detail, msg = add_field_to_draft(cur_detail, kind=kind, field_id=fid, selection=cur_sel)
        after_new = [str(v.get("code")) for v in (cur_detail.get("visuals") or []) if str(v.get("code")) not in before]
        if after_new:
            cur_sel = {"visual_code": after_new[-1]}
            added += 1
        elif msg and msg.startswith("Đã thêm"):
            added += 1
    if added == 0:
        return detail, "Không có trường mới nào phù hợp để thêm."
    return cur_detail, f"Đã thêm {added} trường đã chọn."


def _param_payload_from_store(p: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa param trong Store về payload ParamCreate cho save_studio_draft."""
    return {
        "code": str(p.get("code") or ""),
        "label": str(p.get("label") or p.get("code") or ""),
        "data_type": str(p.get("data_type") or "STRING"),
        "control_type": str(p.get("control_type") or "TEXT"),
        "required": bool(p.get("required", False)),
        "default_type": str(p.get("default_type") or "NONE"),
        "default_value": p.get("default_value"),
        "display_row": p.get("display_row"),
        "display_order": p.get("display_order"),
        "grid_span": int(p.get("grid_span") or 6),
        "filter_column": p.get("filter_column"),
        "filter_operator": p.get("filter_operator") or "=",
        "is_visible": bool(p.get("is_visible", True)),
        "lov": p.get("lov"),
    }


def add_studio_param(
    detail: dict[str, Any],
    *,
    field_id: int,
    operator: str = "=",
    label: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Thêm 1 tham số lọc báo cáo (RECON_RPT_PARAM) vào bản nháp Studio."""
    bundle = detail.get("model") or {}
    field = next((f for f in _visible_fields(bundle) if int(f["id"]) == int(field_id)), None)
    if field is None:
        return detail, "Không tìm thấy trường lọc trong mô hình."
    op = str(operator or "=").upper()
    if op not in _FILTER_OPERATORS:
        return detail, f"Toán tử {op} không được hỗ trợ cho tham số Studio."
    fcode = str(field.get("field_code") or field.get("source_column") or "PARAM").upper()
    dtype = str(field.get("data_type") or "STRING").upper()
    if dtype not in ("STRING", "NUMBER", "DATE", "DATETIME", "BOOLEAN"):
        dtype = "STRING"
    if dtype in ("DATE", "DATETIME"):
        ctype = "DATE_RANGE" if op == "BETWEEN" else "DATE"
    elif dtype == "NUMBER":
        ctype = "NUMBER"
    else:
        ctype = "TEXT"
    existing_codes = {str(p.get("code") or "").upper() for p in (detail.get("params") or [])}
    base_code = f"P_{fcode}"[:56]
    pcode = base_code
    n = 2
    while pcode in existing_codes:
        pcode = f"{base_code}_{n}"
        n += 1
    new_detail = copy.deepcopy(detail)
    params = list(new_detail.get("params") or [])
    params.append(
        {
            "code": pcode,
            "label": (label or str(field.get("display_name") or fcode)).strip(),
            "data_type": dtype,
            "control_type": ctype,
            "required": False,
            "default_type": "NONE",
            "default_value": None,
            "grid_span": 6,
            "filter_column": fcode,
            "filter_operator": op,
            "is_visible": True,
            "lov": None,
        }
    )
    new_detail["params"] = params
    return new_detail, None


def remove_studio_param(detail: dict[str, Any], param_code: str) -> tuple[dict[str, Any], bool]:
    """Xóa tham số báo cáo theo mã khỏi bản nháp."""
    params = list(detail.get("params") or [])
    kept = [p for p in params if str(p.get("code") or "") != str(param_code)]
    if len(kept) == len(params):
        return detail, False
    new_detail = copy.deepcopy(detail)
    new_detail["params"] = kept
    return new_detail, True


def layout(report_id: str | None = None) -> Any:
    """Layout chính của Report Studio Designer (/report-studio/<report_id>)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate is not None:
        return gate
    assert ctx is not None

    try:
        rid = int(str(report_id or "0"))
    except ValueError:
        rid = 0
    if rid <= 0:
        return dmc.Box(
            error_state(
                title="Mã báo cáo không hợp lệ",
                message="Vui lòng mở báo cáo từ danh sách Report Studio.",
                action=dcc.Link(button_primary("Về Report Studio", icon="lucide:arrow-left", size="xs"), href="/report-studio"),
            ),
            p="md",
        )

    detail, err, is_editable = load_designer_draft(ctx, rid)
    if err or detail is None:
        return dmc.Box(
            error_state(
                title="Không mở được Report Studio",
                message=err or "Không tìm thấy báo cáo.",
                action=dcc.Link(button_subtle("Về Report Studio", icon="lucide:arrow-left", size="xs"), href="/report-studio"),
            ),
            p="md",
        )

    bundle = detail.get("model") or {}
    publish_modal = dmc.Modal(
        id="rs-publish-modal",
        title=dmc.Text("Phát hành báo cáo Studio", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-publish-alert"),
                dmc.Textarea(
                    id="rs-publish-note",
                    label="Change note",
                    placeholder="Mô tả thay đổi trong phiên bản phát hành...",
                    minRows=2,
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rs-publish-cancel", size="xs"),
                        button_primary("Phát hành", id="rs-publish-submit", icon="lucide:upload-cloud", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    stale_modal = dmc.Modal(
        id="rs-stale-modal",
        title=dmc.Text("Xung đột phiên bản bản nháp (STALE_DATA)", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-stale-modal-body"),
                dmc.Group(
                    [
                        button_subtle("Giữ phiên bản đang sửa", id="rs-stale-keep-btn", size="xs"),
                        button_primary("Tải lại bản mới", id="rs-stale-reload-btn", icon="lucide:refresh-cw", size="xs"),
                    ],
                    justify="flex-end",
                    gap="md",
                ),
            ],
            gap="md",
        ),
    )

    type_confirm_modal = dmc.Modal(
        id="rs-type-confirm-modal",
        title=dmc.Text("Đổi loại visual", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-type-confirm-body"),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rs-type-confirm-no", size="xs"),
                        button_primary("Xác nhận đổi loại", id="rs-type-confirm-yes", icon="lucide:check", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    return dmc.Box(
        [
            dcc.Location(id="rs-redirect", refresh=True),
            dcc.Store(id="rs-draft-store", data=detail),
            dcc.Store(id="rs-selection-store", data=None),
            dcc.Store(id="rs-preview-store", data=False),
            dcc.Store(id="rs-dirty-store", data=False),
            dcc.Store(id="rs-checked-fields-store", data=[]),
            dcc.Store(id="rs-dnd-store", data=None),
            dcc.Store(id="rs-preview-data-store", data={"seq": 0, "results": {}}),
            dcc.Store(id="rs-preview-seq-store", data=0),
            dcc.Store(id="rs-preview-filters-store", data=[]),
            dcc.Store(id="rs-dark-mode-store", data=False),
            dcc.Store(id="rs-type-pending-store", data=None),
            dmc.NotificationContainer(id="rs-studio-notif", position="top-right", **{"aria-live": "polite"}),
            html.Div(render_designer_header(detail, is_editable=is_editable), id="rs-header-wrap"),
            html.Div(
                alert_box(
                    title="Chỉ đọc — phiên bản đã phát hành",
                    message="Báo cáo đang ở trạng thái ACTIVE. Bấm Tạo bản nháp mới để chỉnh sửa.",
                    tone="info",
                )
                if not is_editable
                else None,
                id="rs-readonly-banner",
            ),
            html.Div(
                alert_box(
                    title="Chế độ xem trên màn hình nhỏ",
                    message="Thiết kế báo cáo yêu cầu màn hình máy tính (≥ 1280px).",
                    tone="info",
                ),
                className="rs-mobile-notice",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dmc.Group(
                                [
                                    dmc.Text("Trường & Chỉ số", fw=700, size="xs"),
                                    dmc.Button(
                                        "+ Đã chọn",
                                        id="rs-field-add-checked-btn",
                                        size="xs",
                                        variant="light",
                                        disabled=True,
                                        **{"aria-label": "Thêm các trường đã chọn"},
                                    ),
                                ],
                                justify="space-between",
                                p="xs",
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            dmc.Box(
                                dmc.TextInput(
                                    id="rs-fields-search",
                                    placeholder="Tìm trường hoặc chỉ số...",
                                    value="",
                                    leftSection=DashIconify(icon="lucide:search", width=13),
                                    size="xs",
                                    debounce=200,
                                    **{"aria-label": "Tìm trường hoặc chỉ số"},
                                ),
                                px="xs",
                                py=6,
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            html.Div(
                                render_fields_panel(bundle, query="", is_editable=is_editable),
                                id="rs-fields-body",
                                className="rs-fields-scroll",
                            ),
                        ],
                        id="rs-fields-panel",
                        className="rs-fields-panel",
                    ),
                    html.Div(
                        [
                            dmc.Group(
                                [dmc.Text("Report Canvas", fw=700, size="xs")],
                                p="xs",
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            # Thanh lọc xem trước nằm NGOÀI rs-canvas-body: vẽ lại
                            # canvas khi fetch xong không được remount thanh lọc
                            # (kẻo xóa bộ lọc user đang nhập + mất focus).
                            html.Div(id="rs-preview-filter-wrap"),
                            html.Div(
                                render_canvas_panel(detail, is_editable=is_editable),
                                id="rs-canvas-body",
                                className="rs-canvas-scroll",
                            ),
                        ],
                        id="rs-canvas",
                        className="rs-canvas-col",
                    ),
                    html.Div(
                        [
                            dmc.Group(
                                [dmc.Text("Thiết lập", fw=700, size="xs")],
                                p="xs",
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            html.Div(
                                render_settings_panel(detail, None, is_editable=is_editable),
                                id="rs-settings-body",
                                className="rs-settings-scroll",
                            ),
                        ],
                        id="rs-settings-panel",
                        className="rs-settings-panel",
                    ),
                ],
                className="rs-workspace",
            ),
            html.Div(render_status_bar(detail, dirty=False), id="rs-status-wrap"),
            drawer_right(
                id="rs-validate-drawer",
                title="Kiểm tra báo cáo",
                opened=False,
                size=520,
                children=html.Div(id="rs-validate-drawer-body"),
            ),
            publish_modal,
            stale_modal,
            type_confirm_modal,
        ],
        id="rs-page",
        className="rs-page",
        **{"data-editable": "true" if is_editable else "false"},
    )


@callback(
    Output("rs-fields-body", "children"),
    Input("rs-fields-search", "value"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_fields_search(
    query: str | None,
    detail: dict[str, Any] | None,
) -> Any:
    """Tìm kiếm trường in-memory trên bundle đã tải (không query DB)."""
    if not detail:
        raise PreventUpdate
    bundle = detail.get("model") or {}
    return render_fields_panel(bundle, query=query or "", is_editable=_is_detail_editable(detail))


@callback(
    Output("rs-draft-store", "data"),
    Output("rs-canvas-body", "children"),
    Output("rs-status-wrap", "children"),
    Output("rs-dirty-store", "data"),
    Output("rs-studio-notif", "sendNotifications"),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Input({"type": "rs-field-add-btn", "kind": ALL, "id": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_field_add(
    add_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    dirty: bool | None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Nút +: thêm field/measure vào visual đang chọn hoặc tạo visual TABLE mới."""
    if not detail or not _is_detail_editable(detail) or not any(add_clicks or []):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    kind = str(trig.get("kind") or "field")
    fid = int(trig.get("id") or 0)
    if fid <= 0:
        raise PreventUpdate
    new_detail, msg = add_field_to_draft(detail, kind=kind, field_id=fid, selection=selection)
    if msg is None:
        raise PreventUpdate
    return (
        new_detail,
        render_canvas_panel(new_detail, selection=selection),
        render_status_bar(new_detail, dirty=True),
        True,
        [toast_success(msg)],
        render_settings_panel(new_detail, selection),
    )


@callback(
    Output("rs-checked-fields-store", "data"),
    Output("rs-field-add-checked-btn", "disabled"),
    Output("rs-field-add-checked-btn", "children"),
    Input({"type": "rs-field-check", "kind": ALL, "id": ALL}, "checked"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_field_check(
    checked_list: list[bool | None] | None,
    detail: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Theo dõi field đã tick và cập nhật trạng thái nút '+ Đã chọn'."""
    items = (dash.callback_context.inputs_list[0] if dash.callback_context.inputs_list else []) or []
    out: list[dict[str, Any]] = []
    for item, val in zip(items, checked_list or [], strict=False):
        if not val:
            continue
        ident = (item or {}).get("id") or {}
        out.append({"kind": str(ident.get("kind") or "field"), "id": int(ident.get("id") or 0)})
    editable = _is_detail_editable(detail) if detail else True
    btn_label = f"+ Đã chọn ({len(out)})" if out else "+ Đã chọn"
    return out, (len(out) == 0 or not editable), btn_label


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-fields-body", "children", allow_duplicate=True),
    Output("rs-checked-fields-store", "data", allow_duplicate=True),
    Input("rs-field-add-checked-btn", "n_clicks"),
    State("rs-checked-fields-store", "data"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-fields-search", "value"),
    prevent_initial_call=True,
)
def handle_bulk_field_add(
    n_clicks: int | None,
    checked_items: list[dict[str, Any]] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    search_query: str | None,
) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any]:
    """Thêm hàng loạt các trường đã tick rồi bỏ tick danh sách chọn."""
    if not n_clicks or not detail or not _is_detail_editable(detail) or not checked_items:
        raise PreventUpdate
    new_detail, msg = add_checked_fields_to_draft(detail, checked_items, selection=selection)
    bundle = new_detail.get("model") or {}
    return (
        new_detail,
        render_canvas_panel(new_detail, selection=selection),
        render_status_bar(new_detail, dirty=True),
        True,
        [toast_success(msg or "Đã thêm trường đã chọn.")],
        render_settings_panel(new_detail, selection),
        render_fields_panel(bundle, query=search_query or "", is_editable=True),
        [],
    )


@callback(
    Output("rs-selection-store", "data"),
    Output("rs-settings-body", "children"),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Input({"type": "rs-visual-card", "code": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_visual_select(
    card_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Bấm card visual trên canvas -> chọn visual, hiện panel phải."""
    if not detail or not any(card_clicks or []):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    selection = {"visual_code": str(trig.get("code") or "")}
    return (
        selection,
        render_settings_panel(detail, selection),
        render_canvas_panel(detail, selection=selection),
    )


@callback(
    Output("rs-validate-drawer", "opened"),
    Output("rs-validate-drawer-body", "children"),
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Input("rs-validate-btn", "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_validate(
    n_clicks: int | None,
    detail: dict[str, Any] | None,
) -> tuple[bool, Any, Any, Any]:
    """Kiểm tra: gọi validate_studio_report, lỗi liệt kê theo từng visual."""
    if not n_clicks or not detail:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    version_id = int(detail["version"]["id"])
    res = validate_studio_report(ctx, version_id)
    if not res.ok or not res.data:
        body = error_state(title="Không kiểm tra được báo cáo", message=res.message or "Vui lòng thử lại.")
        return True, body, dash.no_update, dash.no_update
    data = res.data
    errors = list(data.get("errors") or [])
    warnings = list(data.get("warnings") or [])
    if not errors:
        body = alert_box(
            title="Báo cáo hợp lệ",
            message=f"Đã kiểm tra {len(detail.get('visuals') or [])} visual, không có lỗi. Trạng thái: {data.get('status')}.",
            tone="ok",
        )
    else:
        body = dmc.Stack(
            [
                alert_box(
                    title=f"Phát hiện {len(errors)} lỗi",
                    message="Bấm vào từng lỗi để nhảy tới visual liên quan.",
                    tone="warn",
                ),
                dmc.Stack(
                    [
                        html.Button(
                            dmc.Stack(
                                [
                                    dmc.Text(str(e.get("visual_title") or e.get("visual_code")), fw=600, size="xs"),
                                    dmc.Text(str(e.get("message") or ""), size="xs", c="dimmed"),
                                ],
                                gap=2,
                            ),
                            id={"type": "rs-val-issue", "code": str(e.get("visual_code") or "")},
                            className="rms-val-issue-btn",
                        )
                        for e in errors
                    ],
                    gap="xs",
                ),
            ],
            gap="sm",
        )
    if warnings:
        body = dmc.Stack([body, dmc.Text(f"Có {len(warnings)} cảnh báo.", size="xs", c="dimmed")], gap="sm")
    new_detail = dict(detail)
    new_detail["version"] = dict(detail["version"])
    new_detail["version"]["status"] = str(data.get("status") or detail["version"]["status"])
    new_detail["version"]["row_version"] = int(data.get("row_version") or detail["version"]["row_version"])
    return True, body, new_detail, render_status_bar(new_detail, dirty=False)


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Output("rs-stale-modal", "opened"),
    Output("rs-stale-modal-body", "children"),
    Input("rs-save-btn", "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_save_draft(
    n_clicks: int | None,
    detail: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, bool, Any]:
    """Lưu nháp: ghi visuals trong Store xuống DB kèm kiểm tra ROW_VERSION."""
    if not n_clicks or not detail:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    version_id = int(detail["version"]["id"])
    row_version = int(detail["version"]["row_version"])
    visuals = [_visual_payload_from_store(v) for v in (detail.get("visuals") or [])]
    save_payload: dict[str, Any] = {"row_version": row_version, "visuals": visuals}
    if detail.get("params") is not None:
        save_payload["params"] = [_param_payload_from_store(p) for p in detail["params"]]
    res = save_studio_draft(ctx, version_id, save_payload)
    if not res.ok:
        if res.code == ErrorCode.STALE_DATA:
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                True,
                dmc.Text(
                    "Bản nháp đã bị thay đổi bởi người khác. Bấm Tải lại bản mới để lấy phiên bản mới nhất (thay đổi chưa lưu sẽ mất).",
                    size="sm",
                ),
            )
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            [toast_error(res.message or "Không lưu được bản nháp.")],
            False,
            dash.no_update,
        )
    new_detail = dict(detail)
    new_detail["version"] = dict(detail["version"])
    new_detail["version"]["status"] = "DRAFT"
    new_detail["version"]["row_version"] = int((res.data or {}).get("row_version") or row_version + 1)
    return (
        new_detail,
        render_status_bar(new_detail, dirty=False),
        False,
        [toast_success("Đã lưu bản nháp.")],
        False,
        dash.no_update,
    )


@callback(
    Output("rs-publish-modal", "opened"),
    Output("rs-publish-alert", "children"),
    Input("rs-publish-btn", "n_clicks"),
    Input("rs-publish-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_publish_modal_toggle(
    btn_clicks: int | None,
    cancel_clicks: int | None,
) -> tuple[bool, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rs-publish-cancel" and cancel_clicks:
        return False, None
    if trig == "rs-publish-btn" and btn_clicks:
        return True, None
    raise PreventUpdate


@callback(
    Output("rs-publish-modal", "opened", allow_duplicate=True),
    Output("rs-publish-alert", "children", allow_duplicate=True),
    Output("rs-redirect", "href", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-publish-submit", "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-publish-note", "value"),
    prevent_initial_call=True,
)
def handle_publish_submit(
    n_clicks: int | None,
    detail: dict[str, Any] | None,
    note: str | None,
) -> tuple[bool, Any, Any, Any]:
    """Phát hành: yêu cầu Change Note, gọi publish_studio_report rồi tải lại trang."""
    if not n_clicks or not detail:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    version_id = int(detail["version"]["id"])
    report_id = int(detail["report"]["id"])
    res = publish_studio_report(ctx, version_id, {"change_note": note or ""})
    if not res.ok:
        return True, alert_box(message=res.message or "Không thể phát hành.", tone="crit"), dash.no_update, dash.no_update
    return False, None, f"/report-studio/{report_id}", [toast_success("Đã phát hành báo cáo Studio.")]


@callback(
    Output("rs-redirect", "href", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-new-draft-btn", "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_new_draft(
    n_clicks: int | None,
    detail: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Tạo bản nháp mới từ phiên bản ACTIVE rồi tải lại trang."""
    if not n_clicks or not detail:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    report_id = int(detail["report"]["id"])
    res = open_or_create_studio_draft(ctx, report_id)
    if not res.ok:
        return dash.no_update, [toast_error(res.message or "Không tạo được bản nháp.")]
    return f"/report-studio/{report_id}", [toast_success("Đã tạo bản nháp mới.")]


@callback(
    Output("rs-preview-store", "data"),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-header-wrap", "children"),
    Output("rs-preview-filter-wrap", "children"),
    Output("rs-preview-filters-store", "data", allow_duplicate=True),
    Input("rs-preview-btn", "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-preview-store", "data"),
    State("rs-preview-data-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-dark-mode-store", "data"),
    prevent_initial_call=True,
)
def handle_preview_toggle(
    n_clicks: int | None,
    detail: dict[str, Any] | None,
    preview: bool | None,
    previews: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    dark_mode: bool | None,
) -> tuple[bool, Any, Any, Any, Any]:
    """Chuyển đổi chế độ Xem trước / Quay lại thiết kế (dữ liệu qua fetch callback)."""
    if not n_clicks or not detail:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    new_preview = not bool(preview)
    is_editable = str(detail["version"]["status"]) in _EDITABLE_STATUSES
    return (
        new_preview,
        render_canvas_panel(
            detail,
            preview_mode=new_preview,
            previews=previews if new_preview else None,
            selection=selection,
            dark_mode=bool(dark_mode),
        ),
        render_designer_header(detail, is_editable=is_editable, preview_mode=new_preview),
        render_preview_filter_bar(detail) if new_preview else None,
        [],
    )


@callback(
    Output("rs-redirect", "href", allow_duplicate=True),
    Input("rs-menu-view-report", "n_clicks"),
    Input("rs-menu-back-center", "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_header_menu(
    view_clicks: int | None,
    back_clicks: int | None,
    detail: dict[str, Any] | None,
) -> Any:
    """Menu ... : Xem ở /reports hoặc quay lại Report Studio."""
    if not detail:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    report_id = int(detail["report"]["id"])
    if trig == "rs-menu-view-report" and view_clicks:
        return f"/reports/{report_id}"
    if trig == "rs-menu-back-center" and back_clicks:
        return "/report-studio"
    raise PreventUpdate


@callback(
    Output("rs-redirect", "href", allow_duplicate=True),
    Output("rs-stale-modal", "opened", allow_duplicate=True),
    Input("rs-stale-reload-btn", "n_clicks"),
    Input("rs-stale-keep-btn", "n_clicks"),
    State("rs-draft-store", "data"),
    prevent_initial_call=True,
)
def handle_stale_modal(
    reload_clicks: int | None,
    keep_clicks: int | None,
    detail: dict[str, Any] | None,
) -> tuple[Any, bool]:
    """Modal STALE_DATA: tải lại bản mới hoặc giữ phiên bản đang sửa."""
    trig = dash.callback_context.triggered_id
    if trig == "rs-stale-keep-btn" and keep_clicks:
        return dash.no_update, False
    if trig == "rs-stale-reload-btn" and reload_clicks and detail:
        return f"/report-studio/{int(detail['report']['id'])}", False
    raise PreventUpdate


# ─── Bước 4: Canvas 12 cột, Data Wells, Filters & Preview ───────────────────


def _triggered_input_value(group_idx: int, code: str, idx: int) -> Any:
    """Giá trị của input pattern-matching vừa bắn (theo inputs_list)."""
    groups = dash.callback_context.inputs_list or []
    if group_idx < 0 or group_idx >= len(groups):
        return None
    for item in groups[group_idx] or []:
        ident = (item or {}).get("id") or {}
        if str(ident.get("code") or "") == code and int(ident.get("idx") or -1) == idx:
            return (item or {}).get("value")
    return None


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-dnd-store", "data"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_dnd_drop(
    payload: dict[str, Any] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Nhận sự kiện kéo-thả từ studio_drag_drop.js (field vào well / đổi thứ tự)."""
    if not detail or not _is_detail_editable(detail) or not payload or not isinstance(payload, dict):
        raise PreventUpdate
    kind = str(payload.get("kind") or "")
    if kind == "field-drop":
        new_detail, err = apply_field_drop(
            detail,
            kind=str(payload.get("field_kind") or "field"),
            field_id=int(payload.get("field_id") or 0),
            visual_code=str(payload.get("visual_code") or ""),
            well_role=str(payload.get("well_role") or ""),
        )
        if err:
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                [toast_error(err)],
            )
        return (
            new_detail,
            render_canvas_panel(new_detail, selection=selection),
            render_status_bar(new_detail, dirty=True),
            True,
            render_settings_panel(new_detail, selection),
            [toast_success(f"Đã thêm trường vào visual {payload.get('visual_code')}.")],
        )
    if kind == "visual-reorder":
        new_detail, ok = reorder_visual(
            detail,
            str(payload.get("from_code") or ""),
            str(payload.get("to_code") or ""),
        )
        if not ok:
            raise PreventUpdate
        return (
            new_detail,
            render_canvas_panel(new_detail, selection=selection),
            render_status_bar(new_detail, dirty=True),
            True,
            render_settings_panel(new_detail, selection),
            [toast_success("Đã đổi thứ tự visual.")],
        )
    raise PreventUpdate


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Output("rs-selection-store", "data", allow_duplicate=True),
    Input({"type": "rs-visual-move-up", "code": ALL}, "n_clicks"),
    Input({"type": "rs-visual-move-down", "code": ALL}, "n_clicks"),
    Input({"type": "rs-visual-duplicate", "code": ALL}, "n_clicks"),
    Input({"type": "rs-visual-delete", "code": ALL}, "n_clicks"),
    Input({"type": "rs-visual-delete-btn", "code": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_visual_actions(
    up_clicks: list[int | None] | None,
    down_clicks: list[int | None] | None,
    dup_clicks: list[int | None] | None,
    delete_clicks: list[int | None] | None,
    delete_btn_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    """Nút lên/xuống, nhân bản, xóa visual trên canvas và panel phải."""
    if not detail or not _is_detail_editable(detail):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if isinstance(trig, dict):
        code = str(trig.get("code") or "")
        kind = str(trig.get("type") or "")
        clicks = {
            "rs-visual-move-up": up_clicks,
            "rs-visual-move-down": down_clicks,
            "rs-visual-duplicate": dup_clicks,
            "rs-visual-delete": delete_clicks,
            "rs-visual-delete-btn": delete_btn_clicks,
        }.get(kind)
        if not any(clicks or []):
            raise PreventUpdate
        if kind == "rs-visual-move-up":
            new_detail, ok = move_visual(detail, code, "up")
            msg = "Đã di chuyển visual lên." if ok else None
        elif kind == "rs-visual-move-down":
            new_detail, ok = move_visual(detail, code, "down")
            msg = "Đã di chuyển visual xuống." if ok else None
        elif kind == "rs-visual-duplicate":
            new_detail = duplicate_visual(detail, code)
            msg = f"Đã nhân bản visual {code}."
        else:
            new_detail = delete_visual(detail, code)
            msg = f"Đã xóa visual {code} khỏi bản nháp."
        new_selection = selection
        if kind in ("rs-visual-delete", "rs-visual-delete-btn") and (
            selection or {}
        ).get("visual_code") == code:
            new_selection = None
        return (
            new_detail,
            render_canvas_panel(new_detail, selection=new_selection),
            render_status_bar(new_detail, dirty=True),
            True,
            render_settings_panel(new_detail, new_selection),
            [toast_success(msg)] if msg else dash.no_update,
            new_selection,
        )
    raise PreventUpdate


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-type-confirm-modal", "opened"),
    Output("rs-type-confirm-body", "children"),
    Output("rs-type-pending-store", "data"),
    Input("rs-set-title", "value"),
    Input("rs-set-type", "value"),
    Input("rs-set-grid-span", "value"),
    Input("rs-set-height-size", "value"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_settings_change(
    title: str | None,
    vtype: str | None,
    grid_span: str | None,
    height_size: str | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, bool, Any, Any]:
    """Tiêu đề / loại / rộng / cao của visual đang chọn (guard mount-firing).

    Đổi loại visual có field bị loại -> mở modal xác nhận thay vì áp ngay.
    """
    if not detail or not _is_detail_editable(detail):
        raise PreventUpdate
    sel_code = (selection or {}).get("visual_code")
    visual = next(
        (v for v in (detail.get("visuals") or []) if str(v.get("code")) == str(sel_code)),
        None,
    )
    if visual is None:
        raise PreventUpdate
    new_title = str(title or "")
    new_type = str(vtype or visual.get("visual_type"))
    try:
        new_span = int(grid_span or 12)
    except (TypeError, ValueError):
        new_span = 12
    new_height = str(height_size or "M")
    changed = (
        new_title != str(visual.get("title") or "")
        or new_type != str(visual.get("visual_type"))
        or new_span != int(visual.get("grid_span") or 12)
        or new_height != str(visual.get("height_size") or "M")
    )
    if not changed:
        raise PreventUpdate
    type_changed = False
    if new_type != str(visual.get("visual_type")):
        bundle = detail.get("model") or {}
        kept, dropped = remap_visual_fields(visual, new_type, bundle)
        if dropped:
            pending = {
                "visual_code": str(visual.get("code")),
                "new_type": new_type,
                "kept": kept,
                "dropped": dropped,
            }
            body = dmc.Stack(
                [
                    dmc.Text(
                        "Đổi loại visual sẽ loại bỏ các trường sau vì không tương thích:",
                        size="sm",
                    ),
                    dmc.List([dmc.ListItem(d) for d in dropped]),
                    dmc.Text(
                        "Bấm Xác nhận để đổi loại và loại các trường trên.",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                gap="xs",
            )
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                True,
                body,
                pending,
            )
        visual["visual_type"] = new_type
        visual["fields"] = kept
        type_changed = True
    visual["title"] = new_title
    visual["grid_span"] = new_span
    visual["height_size"] = new_height
    return (
        detail,
        render_canvas_panel(detail, selection=selection),
        render_status_bar(detail, dirty=True),
        True,
        # Chỉ vẽ lại panel phải khi đổi loại visual (wells đổi cấu trúc).
        # Đổi tiêu đề/span/height: control đã hiển thị giá trị mới, vẽ lại
        # chỉ làm mất focus khi user đang gõ tiêu đề (debounce 300ms).
        render_settings_panel(detail, selection) if type_changed else dash.no_update,
        False,
        dash.no_update,
        dash.no_update,
    )


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-type-confirm-modal", "opened", allow_duplicate=True),
    Output("rs-type-pending-store", "data", allow_duplicate=True),
    Input("rs-type-confirm-yes", "n_clicks"),
    Input("rs-type-confirm-no", "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-type-pending-store", "data"),
    prevent_initial_call=True,
)
def handle_type_confirm(
    yes_clicks: int | None,
    no_clicks: int | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    pending: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, bool, Any]:
    """Modal xác nhận đổi loại visual: áp remap hoặc hủy (vẽ lại panel)."""
    trig = dash.callback_context.triggered_id
    if not _is_detail_editable(detail):
        raise PreventUpdate
    if trig == "rs-type-confirm-no" and no_clicks:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            render_settings_panel(detail, selection) if detail else dash.no_update,
            False,
            None,
        )
    if trig == "rs-type-confirm-yes" and yes_clicks and detail and pending:
        code = str(pending.get("visual_code") or "")
        visual = next(
            (v for v in (detail.get("visuals") or []) if str(v.get("code")) == code),
            None,
        )
        if visual is None:
            raise PreventUpdate
        visual["visual_type"] = str(pending.get("new_type"))
        visual["fields"] = list(pending.get("kept") or [])
        return (
            detail,
            render_canvas_panel(detail, selection=selection),
            render_status_bar(detail, dirty=True),
            True,
            render_settings_panel(detail, selection),
            False,
            None,
        )
    raise PreventUpdate


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Input({"type": "rs-well-agg", "code": ALL, "idx": ALL}, "value"),
    Input({"type": "rs-well-sort", "code": ALL, "idx": ALL}, "value"),
    Input({"type": "rs-well-remove", "code": ALL, "idx": ALL}, "n_clicks"),
    Input({"type": "rs-well-format", "code": ALL, "idx": ALL}, "value"),
    Input({"type": "rs-well-datepart", "code": ALL, "idx": ALL}, "value"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_well_change(
    agg_vals: list[str | None] | None,
    sort_vals: list[str | None] | None,
    remove_clicks: list[int | None] | None,
    format_vals: list[str | None] | None,
    datepart_vals: list[str | None] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Aggregation / DatePart / Sort / Format / Gỡ field trong Data Well (guard mount-firing)."""
    if not detail or not _is_detail_editable(detail):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    code = str(trig.get("code") or "")
    idx = int(trig.get("idx") or -1)
    visual = next(
        (v for v in (detail.get("visuals") or []) if str(v.get("code")) == code),
        None,
    )
    if visual is None or idx < 0 or idx >= len(visual.get("fields") or []):
        raise PreventUpdate
    kind = str(trig.get("type") or "")
    field = visual["fields"][idx]
    if kind == "rs-well-remove":
        if not any(remove_clicks or []):
            raise PreventUpdate
        visual["fields"] = [f for i, f in enumerate(visual["fields"]) if i != idx]
    elif kind == "rs-well-agg":
        new_val = _triggered_input_value(0, code, idx)
        if new_val is None or str(new_val) == str(field.get("aggregation") or ""):
            raise PreventUpdate
        field["aggregation"] = str(new_val)
    elif kind == "rs-well-sort":
        new_val = _triggered_input_value(1, code, idx)
        if new_val is None or str(new_val) == str(field.get("sort_direction") or ""):
            raise PreventUpdate
        field["sort_direction"] = str(new_val) or None
    elif kind == "rs-well-format":
        new_val = _triggered_input_value(3, code, idx)
        if new_val is None or str(new_val) == str(field.get("format_mask") or ""):
            raise PreventUpdate
        field["format_mask"] = str(new_val) or None
    elif kind == "rs-well-datepart":
        new_val = _triggered_input_value(4, code, idx)
        if new_val is None or str(new_val) == str(field.get("date_part") or ""):
            raise PreventUpdate
        field["date_part"] = str(new_val) or None
    else:
        raise PreventUpdate
    return (
        detail,
        render_canvas_panel(detail, selection=selection),
        render_status_bar(detail, dirty=True),
        True,
        # Chỉ vẽ lại panel phải khi gỡ field (hàng biến mất). Đổi
        # agg/sort/format/datepart: control đã hiển thị giá trị mới,
        # vẽ lại chỉ làm mất focus khi user đang gõ format (debounce 300ms).
        render_settings_panel(detail, selection)
        if kind == "rs-well-remove"
        else dash.no_update,
    )


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-filter-add-btn", "n_clicks"),
    Input({"type": "rs-visual-filter-remove", "code": ALL, "idx": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-filter-field", "value"),
    State("rs-filter-op", "value"),
    State("rs-filter-value", "value"),
    prevent_initial_call=True,
)
def handle_visual_filter(
    add_clicks: int | None,
    remove_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    field_id: str | None,
    op: str | None,
    value: str | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Thêm / xóa bộ lọc của visual đang chọn (lưu trong config.filters)."""
    if not detail or not _is_detail_editable(detail):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    sel_code = str((selection or {}).get("visual_code") or "")
    visual = next(
        (v for v in (detail.get("visuals") or []) if str(v.get("code")) == sel_code),
        None,
    )
    if visual is None:
        raise PreventUpdate
    config = dict(visual.get("config") or {})
    filters = list(config.get("filters") or [])
    if trig == "rs-filter-add-btn" and add_clicks:
        if not field_id or value is None or str(value).strip() == "":
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                [toast_error("Chọn trường và nhập giá trị lọc.")],
            )
        filters.append(
            {
                "field_id": int(field_id),
                "operator": str(op or "="),
                "value": str(value).strip(),
            }
        )
        config["filters"] = filters
        visual["config"] = config
    elif isinstance(trig, dict) and trig.get("type") == "rs-visual-filter-remove":
        if not any(remove_clicks or []):
            raise PreventUpdate
        idx = int(trig.get("idx") or -1)
        if idx < 0 or idx >= len(filters):
            raise PreventUpdate
        filters = [f for i, f in enumerate(filters) if i != idx]
        config["filters"] = filters
        visual["config"] = config
    else:
        raise PreventUpdate
    return (
        detail,
        render_settings_panel(detail, selection),
        render_status_bar(detail, dirty=True),
        True,
        dash.no_update,
    )


@callback(
    Output("rs-preview-filters-store", "data"),
    Output("rs-preview-filter-field", "value"),
    Output("rs-preview-filter-op", "value"),
    Output("rs-preview-filter-value", "value"),
    Input("rs-preview-filter-field", "value"),
    Input("rs-preview-filter-op", "value"),
    Input("rs-preview-filter-value", "value"),
    Input("rs-preview-filter-clear", "n_clicks"),
    prevent_initial_call=True,
)
def handle_preview_filter_change(
    field_id: str | None,
    op: str | None,
    value: str | None,
    clear_clicks: int | None,
) -> tuple[Any, Any, Any, Any]:
    """Thanh lọc xem thử: giá trị debounce 300ms rồi ghi Store -> fetch lại."""
    trig = dash.callback_context.triggered_id
    if trig == "rs-preview-filter-clear" and clear_clicks:
        return [], None, "=", ""
    if not field_id or value is None or str(value).strip() == "":
        return [], dash.no_update, dash.no_update, dash.no_update
    return (
        [{"field_id": int(field_id), "operator": str(op or "="), "value": str(value).strip()}],
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )


@callback(
    Output("rs-preview-data-store", "data"),
    Input("rs-preview-store", "data"),
    Input("rs-preview-filters-store", "data"),
    Input("rs-draft-store", "data"),
    Input({"type": "rs-visual-retry", "code": ALL}, "n_clicks"),
    State("rs-preview-seq-store", "data"),
    prevent_initial_call=True,
)
def handle_preview_fetch(
    preview_on: bool | None,
    filters: list[dict[str, Any]] | None,
    detail: dict[str, Any] | None,
    retry_clicks: list[int | None] | None,
    seq: int | None,
) -> dict[str, Any]:
    """Lấy dữ liệu xem trước cho mọi visual (visual chưa lưu qua override).

    request_seq tăng mỗi lần fetch; render chỉ nhận seq mới nhất.
    """
    if not preview_on or not detail:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if isinstance(trig, dict) and trig.get("type") == "rs-visual-retry":
        if not any(retry_clicks or []):
            raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    new_seq = int(seq or 0) + 1
    version_id = int(detail["version"]["id"])
    results: dict[str, Any] = {}
    report_filters = list(filters or [])
    for vis in detail.get("visuals") or []:
        code = str(vis.get("code"))
        res = preview_studio_visual(
            ctx,
            version_id,
            code,
            {"request_seq": new_seq, "filters": report_filters},
            visual=_visual_payload_from_store(vis),
        )
        if not res.ok:
            results[code] = {
                "state": "error",
                "error": res.message or "Không xem trước được visual.",
            }
        else:
            results[code] = {"state": "data", "data": res.data}
    return {"seq": new_seq, "results": results}


@callback(
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Output("rs-preview-seq-store", "data"),
    Input("rs-preview-data-store", "data"),
    State("rs-draft-store", "data"),
    State("rs-preview-store", "data"),
    State("rs-selection-store", "data"),
    State("rs-dark-mode-store", "data"),
    State("rs-preview-seq-store", "data"),
    prevent_initial_call=True,
)
def handle_preview_render(
    previews: dict[str, Any] | None,
    detail: dict[str, Any] | None,
    preview_on: bool | None,
    selection: dict[str, Any] | None,
    dark_mode: bool | None,
    applied_seq: int | None,
) -> tuple[Any, int]:
    """Vẽ canvas xem trước; bỏ qua response có request_seq cũ hơn đã nhận."""
    if not detail or not preview_on or not previews:
        raise PreventUpdate
    incoming_seq = int(previews.get("seq") or 0)
    if incoming_seq < int(applied_seq or 0):
        raise PreventUpdate
    return (
        render_canvas_panel(
            detail,
            preview_mode=True,
            previews=previews,
            selection=selection,
            dark_mode=bool(dark_mode),
        ),
        incoming_seq,
    )


@callback(
    Output("rs-selection-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-canvas-body", "children", allow_duplicate=True),
    Input({"type": "rs-val-issue", "code": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-preview-store", "data"),
    prevent_initial_call=True,
)
def handle_validation_issue_click(
    issue_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
    preview_on: bool | None,
) -> tuple[Any, Any, Any]:
    """Bấm lỗi trong Validation Drawer -> nhảy đúng visual (chọn + highlight)."""
    if not detail or not any(issue_clicks or []):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    selection = {"visual_code": str(trig.get("code") or "")}
    return (
        selection,
        render_settings_panel(detail, selection),
        render_canvas_panel(
            detail, preview_mode=bool(preview_on), selection=selection
        ),
    )


@callback(
    Output("rs-draft-store", "data", allow_duplicate=True),
    Output("rs-settings-body", "children", allow_duplicate=True),
    Output("rs-status-wrap", "children", allow_duplicate=True),
    Output("rs-dirty-store", "data", allow_duplicate=True),
    Output("rs-studio-notif", "sendNotifications", allow_duplicate=True),
    Input({"type": "rs-param-add-btn", "k": ALL}, "n_clicks"),
    Input({"type": "rs-param-remove", "code": ALL}, "n_clicks"),
    State("rs-draft-store", "data"),
    State("rs-selection-store", "data"),
    State({"type": "rs-param-field", "k": ALL}, "value"),
    State({"type": "rs-param-op", "k": ALL}, "value"),
    State({"type": "rs-param-label", "k": ALL}, "value"),
    prevent_initial_call=True,
)
def handle_report_param_action(
    add_clicks: list[int | None] | None,
    remove_clicks: list[int | None] | None,
    detail: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    field_vals: list[str | None] | None,
    op_vals: list[str | None] | None,
    label_vals: list[str | None] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Thêm / xóa tham số báo cáo (RECON_RPT_PARAM) trong panel phải."""
    if not detail or not _is_detail_editable(detail):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    kind = str(trig.get("type") or "")
    if kind == "rs-param-add-btn":
        if not any(add_clicks or []):
            raise PreventUpdate
        fid_raw = next((v for v in (field_vals or []) if v not in (None, "")), None)
        if not fid_raw:
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                [toast_error("Vui lòng chọn trường lọc cho tham số.")],
            )
        op = str(next((v for v in (op_vals or []) if v), "="))
        lbl = next((v for v in (label_vals or []) if v is not None), None)
        new_detail, err = add_studio_param(detail, field_id=int(fid_raw), operator=op, label=lbl)
        if err:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, [toast_error(err)]
        msg = "Đã thêm tham số báo cáo."
    elif kind == "rs-param-remove":
        if not any(remove_clicks or []):
            raise PreventUpdate
        pcode = str(trig.get("code") or "")
        new_detail, ok = remove_studio_param(detail, pcode)
        if not ok:
            raise PreventUpdate
        msg = f"Đã xóa tham số {pcode}."
    else:
        raise PreventUpdate
    return (
        new_detail,
        render_settings_panel(new_detail, selection),
        render_status_bar(new_detail, dirty=True),
        True,
        [toast_success(msg)],
    )
