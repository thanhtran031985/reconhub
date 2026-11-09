"""Page Mô hình dữ liệu — Data Model Explorer (task 31, DATA-MODEL-01).

Route /data-model, menu code data_model (nhóm QUẢN TRỊ). Layout Fluent
Compact, trang vừa viewport (Box calc(100vh - 88px), 3 panel cuộn trong).
Dữ liệu từ service app.services.data_model (manifest/history đã commit +
drift live); page chỉ đọc metadata, không đọc dữ liệu dòng.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, clientside_callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.data_model import get_data_model, sync_schema
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.command_bar import command_bar
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.page_header import page_header
from app.ui.components.search_utils import matches_query, strip_accents

try:
    dash.register_page(__name__, path="/data-model", title="Mô hình dữ liệu – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "data_model"

DOMAIN_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả phân hệ", "value": "all"},
    {"label": "Core", "value": "core"},
    {"label": "Đối soát", "value": "recon"},
    {"label": "Báo cáo", "value": "report"},
    {"label": "Quản trị", "value": "admin"},
    {"label": "Khác", "value": "other"},
]

MODE_OPTIONS: list[dict[str, str]] = [
    {"label": "Hiển thị quan hệ", "value": "relations"},
    {"label": "Chỉ tên table", "value": "compact"},
]

# Giờ hiển thị "Cập nhật" theo giờ Việt Nam (quy ước của app: p_from/p_to
# nhập theo giờ Việt Nam). Manifest lưu generated_at theo UTC.
_VN_TZ = timezone(timedelta(hours=7))

HEALTH_TEXT: dict[str, str] = {
    "SYNCED": "✓ Schema đồng bộ",
    "DRIFT": "⚠ Schema drift",
    "UNKNOWN": "? Không xác định",
    "ERROR": "✕ Lỗi metadata",
    "CHECKING": "Đang kiểm tra schema…",
}

HEALTH_COLOR: dict[str, str] = {
    "SYNCED": "teal",
    "DRIFT": "yellow",
    "UNKNOWN": "gray",
    "ERROR": "red",
    "CHECKING": "blue",
}


def format_last_sync(generated_at: str | None) -> str:
    """Định dạng generated_at (ISO, UTC) thành DD/MM/YYYY HH:mm:ss giờ VN."""
    if not generated_at:
        return "Cập nhật: —"
    try:
        dt = datetime.fromisoformat(generated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(_VN_TZ)
        return f"Cập nhật: {local.strftime('%d/%m/%Y %H:%M:%S')}"
    except Exception:
        return "Cập nhật: —"


def health_badge(status: str) -> dmc.Badge:
    """Badge read-only trạng thái schema health (không phải button)."""
    label = HEALTH_TEXT.get(status, HEALTH_TEXT["UNKNOWN"])
    color = HEALTH_COLOR.get(status, "gray")
    icon = {
        "SYNCED": "lucide:check",
        "DRIFT": "lucide:alert-triangle",
        "UNKNOWN": "lucide:help-circle",
        "ERROR": "lucide:x-circle",
        "CHECKING": "lucide:loader",
    }.get(status, "lucide:help-circle")
    return dmc.Badge(
        label,
        id="data-model-health-badge",
        color=color,
        variant="light",
        size="sm",
        leftSection=DashIconify(icon=icon, width=14),
        **{"aria-label": f"Trạng thái schema: {label}"},
    )


def render_command_bar(domain: str, mode: str, health_status: str, generated_at: str | None) -> Any:
    """Thanh command bar: search + domain + mode + health + last sync."""
    return command_bar(
        search_id="data-model-search",
        search_placeholder="Tìm table hoặc column…",
        filters=[
            dmc.Select(
                id="data-model-domain-filter",
                data=DOMAIN_OPTIONS,
                value=domain,
                size="xs",
                w=150,
                clearable=False,
                **{"aria-label": "Lọc theo phân hệ"},
            ),
            dmc.Select(
                id="data-model-mode-select",
                data=MODE_OPTIONS,
                value=mode,
                size="xs",
                w=160,
                clearable=False,
                **{"aria-label": "Chế độ hiển thị"},
            ),
            html.Div(
                id="data-model-health-container",
                children=health_badge(health_status),
                style={"display": "flex", "alignItems": "center"},
            ),
            dmc.Text(
                format_last_sync(generated_at),
                id="data-model-last-sync",
                size="xs",
                c="dimmed",
            ),
        ],
        actions=[
            html.Div(id="data-model-drift-action-container"),
        ],
        id="data-model-command-bar",
    )


def render_panel_skeleton() -> Any:
    """Skeleton lúc load đầu cho một panel."""
    return dmc.Stack(
        [dmc.Skeleton(height=28), dmc.Skeleton(height=28), dmc.Skeleton(height=28)],
        gap="xs",
        p="sm",
    )


# --- Bước 4: Schema Explorer + command bar (helper thuần) ---

DOMAIN_ORDER: list[str] = ["core", "recon", "report", "admin", "other"]

DOMAIN_LABELS: dict[str, str] = {
    "core": "Core",
    "recon": "Đối soát",
    "report": "Báo cáo",
    "admin": "Quản trị",
    "other": "Khác",
}

HISTORY_TYPE_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả", "value": "all"},
    {"label": "TABLE_CREATED", "value": "TABLE_CREATED"},
    {"label": "TABLE_DROPPED", "value": "TABLE_DROPPED"},
    {"label": "COLUMN_ADDED", "value": "COLUMN_ADDED"},
    {"label": "COLUMN_REMOVED", "value": "COLUMN_REMOVED"},
    {"label": "COLUMN_CHANGED", "value": "COLUMN_CHANGED"},
    {"label": "PK_CHANGED", "value": "PK_CHANGED"},
    {"label": "FK_CHANGED", "value": "FK_CHANGED"},
    {"label": "INDEX_CHANGED", "value": "INDEX_CHANGED"},
    {"label": "CONSTRAINT_CHANGED", "value": "CONSTRAINT_CHANGED"},
]


def filter_tables(tables: list[dict[str, Any]], query: str, domain: str) -> list[dict[str, Any]]:
    """Lọc bảng theo query (tên bảng/cột/mô tả/index/constraint, không dấu được)
    và theo phân hệ. Query rỗng + domain all trả toàn bộ."""
    q = strip_accents((query or "").strip())
    result: list[dict[str, Any]] = []
    for table in tables:
        if domain and domain != "all" and table.get("domain") != domain:
            continue
        if not q:
            result.append(table)
            continue
        haystacks = [table.get("name", ""), table.get("description", "")]
        haystacks.extend(c.get("name", "") for c in table.get("columns", []))
        haystacks.extend(fk.get("constraint_name") or "" for fk in table.get("foreign_keys", []))
        haystacks.extend(ix.get("name") or "" for ix in table.get("indexes", []))
        haystacks.extend(uc.get("name") or "" for uc in table.get("unique_constraints", []))
        if any(q in strip_accents(h) for h in haystacks):
            result.append(table)
    return result


def group_tables(
    tables: list[dict[str, Any]],
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Nhóm bảng theo phân hệ, thứ tự Core, Đối soát, Báo cáo, Quản trị, Khác."""
    grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in DOMAIN_ORDER}
    for table in tables:
        grouped.setdefault(str(table.get("domain") or "other"), []).append(table)
    return [(code, DOMAIN_LABELS.get(code, code), grouped[code]) for code in DOMAIN_ORDER if grouped.get(code)]


def matching_columns(table: dict[str, Any], query: str) -> list[str]:
    """Tên các cột của bảng khớp query (không dấu được)."""
    q = strip_accents((query or "").strip())
    if not q:
        return []
    return [c["name"] for c in table.get("columns", []) if q in strip_accents(c.get("name", ""))]


def _parse_triggered_id(prop_id: str) -> dict[str, Any]:
    """Tách id pattern-matching (dạng JSON + '.n_clicks') từ prop_id."""
    try:
        raw = prop_id.rsplit(".n_clicks", 1)[0]
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _triggered_clicks(ctx_dash: Any) -> int | None:
    """Giá trị kích hoạt (n_clicks) của trigger hiện tại.

    Dash phát lại callback pattern-matching lúc load với n_clicks = 0/None;
    chỉ xử lý khi > 0 (quy tắc dash_callback_safety, tránh tạo side effect
    giả như vụ run trùng ở /runs/new).
    """
    triggered = getattr(ctx_dash, "triggered", None) or []
    if not triggered:
        return None
    value = triggered[0].get("value")
    return value if isinstance(value, int) else None


def _group_expanded(ui: dict[str, Any] | None, domain: str, has_match: bool, query: str) -> bool:
    """Group mở khi: đang search và có match, hoặc state đã lưu là mở.
    Mặc định (chưa bấm gì) group mở."""
    if query.strip() and has_match:
        return True
    expanded = (ui or {}).get("expanded") or {}
    if domain in expanded:
        return bool(expanded[domain])
    return True


def _render_table_row(
    table: dict[str, Any],
    selection: dict[str, Any] | None,
    query: str,
) -> Any:
    """Một dòng table compact: dot trạng thái + tên mono + số cột + menu 3 chấm."""
    name = str(table["name"])
    is_selected = selection is not None and selection.get("kind") == "table" and selection.get("table") == name
    matched = matching_columns(table, query)
    label_children: list[Any] = [
        html.Span(className="dm-dot"),
        dmc.Text(name, className="rh-code", size="sm", fw=600 if is_selected else 500),
        dmc.Text(f"{len(table.get('columns', []))} cột", size="xs", c="dimmed"),
    ]
    if matched:
        label_children.append(
            dmc.Text(
                " · ".join(matched[:3]),
                size="xs",
                className="dm-match",
            )
        )
    row_button = html.Button(
        dmc.Group(label_children, gap="xs", align="center", style={"minWidth": 0, "flexWrap": "nowrap"}),
        id={"type": "dm-table-item", "table": name},
        className="dm-table-item active" if is_selected else "dm-table-item",
        **{"aria-selected": "true" if is_selected else "false"},  # type: ignore[arg-type]
    )
    menu_items: list[Any] = [
        dmc.MenuItem(
            "Center trong ER Diagram",
            id={"type": "dm-table-menu", "table": name, "action": "center"},
            leftSection=DashIconify(icon="lucide:crosshair", width=14),
        ),
        dmc.MenuItem(
            "Xem columns",
            id={"type": "dm-table-menu", "table": name, "action": "columns"},
            leftSection=DashIconify(icon="lucide:columns-3", width=14),
        ),
        dmc.MenuItem(
            "Xem relationships",
            id={"type": "dm-table-menu", "table": name, "action": "relationships"},
            leftSection=DashIconify(icon="lucide:share-2", width=14),
        ),
        dmc.MenuItem(
            "Xem lịch sử thay đổi",
            id={"type": "dm-table-menu", "table": name, "action": "history"},
            leftSection=DashIconify(icon="lucide:history", width=14),
        ),
        dmc.MenuItem(
            "Copy table name",
            id={"type": "dm-table-menu", "table": name, "action": "copy"},
            leftSection=DashIconify(icon="lucide:copy", width=14),
        ),
    ]
    row_menu = dmc.Menu(
        [
            dmc.MenuTarget(
                dmc.ActionIcon(
                    DashIconify(icon="lucide:more-vertical", width=14),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    **{"aria-label": f"Thao tác {name}"},
                )
            ),
            dmc.MenuDropdown(menu_items),
        ],
        position="bottom-end",
        withArrow=True,
    )
    description = str(table.get("description") or name)
    return html.Div(
        [
            dmc.Tooltip(label=description, children=row_button, multiline=True, withArrow=True),
            row_menu,
        ],
        className="dm-table-row",
    )


def render_explorer(
    tables: list[dict[str, Any]],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
    query: str,
) -> Any:
    """Explorer: group theo domain (chevron + tên + count), click collapse/expand.

    Khi search, group có match tự expand. Hết kết quả -> empty state + nút
    Xóa bộ lọc.
    """
    if not tables:
        return dmc.Stack(
            [
                empty_state(
                    title="Không tìm thấy table hoặc column phù hợp.",
                    description="Thử từ khóa khác hoặc xóa bộ lọc để xem toàn bộ schema.",
                    action=button_subtle("Xóa bộ lọc", id="data-model-clear-filter-btn", icon="lucide:x"),
                )
            ],
            p="sm",
        )
    groups = group_tables(tables)
    children: list[Any] = []
    for code, label, group_tables_list in groups:
        expanded = _group_expanded(ui, code, has_match=True, query=query)
        chevron = "lucide:chevron-down" if expanded else "lucide:chevron-right"
        children.append(
            html.Button(
                dmc.Group(
                    [
                        DashIconify(icon=chevron, width=14),
                        dmc.Text(f"{label} ({len(group_tables_list)})", fw=600, size="sm"),
                    ],
                    gap="xs",
                    align="center",
                ),
                id={"type": "dm-group-toggle", "domain": code},
                className="dm-group-header",
                **{"aria-expanded": "true" if expanded else "false"},  # type: ignore[arg-type]
            )
        )
        if expanded:
            for table in group_tables_list:
                children.append(_render_table_row(table, selection, query))
    return dmc.Stack(children, gap=0, p="xs")


def render_canvas(
    tables: list[dict[str, Any]],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
    zoom: float,
    query: str,
) -> Any:
    """ER Canvas: entity card + relationship lines (div xoay) từ FK metadata.

    Layout deterministic theo domain (cột) + tên bảng (hàng), không hardcode
    tọa độ từng bảng. Pan bằng scroll native, zoom qua transform scale().
    """
    mode = str((ui or {}).get("mode") or "relations")
    if not tables:
        return empty_state(
            title="Không tìm thấy table hoặc column phù hợp.",
            description="Thử từ khóa khác hoặc xóa bộ lọc để xem toàn bộ schema.",
        )
    layout = layout_entities(tables, mode)
    canvas_w, canvas_h = canvas_size(layout)
    lines = relationship_lines(tables, layout)
    selected_table = (
        str(selection.get("table"))
        if selection and selection.get("kind") == "table" and selection.get("table")
        else None
    )
    selected_rel = selection if selection and selection.get("kind") == "relationship" else None
    related_tables: set[str] = set()
    related_lines: set[int] = set()
    if selected_table:
        related_tables.add(selected_table)
        for idx, line in enumerate(lines):
            if line["source"] == selected_table or line["target"] == selected_table:
                related_lines.add(idx)
                related_tables.add(line["source"])
                related_tables.add(line["target"])
    if selected_rel:
        for idx, line in enumerate(lines):
            if (
                line["source"] == selected_rel.get("source")
                and line["target"] == selected_rel.get("target")
                and line["column"] == selected_rel.get("column")
            ):
                related_lines.add(idx)
                related_tables.add(line["source"])
                related_tables.add(line["target"])

    line_nodes: list[Any] = []
    for idx, line in enumerate(lines):
        if selected_table or selected_rel:
            cls = "dm-rel-line related" if idx in related_lines else "dm-rel-line dimmed"
        else:
            cls = "dm-rel-line"
        line_nodes.append(
            html.Div(
                id={"type": "dm-rel-line", "index": idx},
                className=cls,
                title=f"{line['source']}.{line['column']} → {line['target']}.{line['references_column']}",
                style={
                    "position": "absolute",
                    "left": line["x1"],
                    "top": line["y1"],
                    "width": line["length"],
                    "height": 2,
                    "transform": f"rotate({line['angle_deg']:.2f}deg)",
                    "transformOrigin": "left center",
                    "zIndex": 1,
                },
            )
        )

    entity_nodes: list[Any] = []
    table_by_name = {t["name"]: t for t in tables}
    for name in sorted(layout):
        box = layout[name]
        table = table_by_name[name]
        columns = table.get("columns", [])
        if selected_table or selected_rel:
            if name == selected_table:
                cls = "dm-entity selected"
            elif name in related_tables:
                cls = "dm-entity related"
            else:
                cls = "dm-entity dimmed"
        else:
            cls = "dm-entity"
        header = dmc.Group(
            [
                html.Span(className="dm-dot"),
                dmc.Text(name, className="rh-code", size="sm", fw=600),
                dmc.Text(f"{len(columns)} cột", size="xs", c="dimmed"),
            ],
            gap="xs",
            align="center",
            style={"minWidth": 0, "flexWrap": "nowrap"},
        )
        body: list[Any] = [header]
        if mode == "relations":
            matched = set(matching_columns(table, query))
            for col in columns:
                if col.get("primary_key") and col.get("foreign_key"):
                    marker = "◆↗"
                elif col.get("primary_key"):
                    marker = "◆"
                elif col.get("foreign_key"):
                    marker = "↗"
                elif col.get("unique"):
                    marker = "U"
                else:
                    marker = ""
                body.append(
                    html.Div(
                        [
                            html.Span(marker, className="dm-col-marker"),
                            dmc.Text(col["name"], className="rh-code", size="xs"),
                            dmc.Text(str(col.get("type", "")), size="xs", c="dimmed"),
                        ],
                        className="dm-col-row dm-match" if col["name"] in matched else "dm-col-row",
                    )
                )
        entity_nodes.append(
            html.Button(
                dmc.Stack(body, gap=2),
                id={"type": "dm-entity", "table": name},
                className=cls,
                style={
                    "position": "absolute",
                    "left": box["x"],
                    "top": box["y"],
                    "width": box["w"],
                    "height": box["h"],
                    "zIndex": 2,
                },
                **{"data-table": name},  # type: ignore[arg-type]
            )
        )

    # Div canvas trong trả trực tiếp, KHÔNG bọc thêm div scroll: khung ngoài
    # #data-model-canvas-container (layout, overflow auto, flex 1) mới là
    # scroller — bọc thêm một div flex:1 trong parent block sẽ cao bằng nội
    # dung (7054px) khiến clientHeight sai, fit tính sai và center không cuộn.
    return html.Div(
        [*line_nodes, *entity_nodes],
        id="data-model-canvas-inner",
        style={
            "position": "relative",
            "width": canvas_w,
            "height": canvas_h,
            "transform": f"scale({zoom})",
            "transformOrigin": "0 0",
        },
        **{  # type: ignore[arg-type]
            "data-w": str(canvas_w),
            "data-h": str(canvas_h),
            "data-zoom": str(zoom),
        },
    )


# --- Bước 5: ER Canvas (helper thuần) ---

ENTITY_W = 205
GAP_X = 40
GAP_Y = 24


def layout_entities(tables: list[dict[str, Any]], mode: str) -> dict[str, dict[str, int]]:
    """Layout deterministic: cột theo domain, hàng theo tên bảng alphabet.

    Compact cao cố định 40; relations cao 34 + 24 * số cột. Trả
    {tên bảng: {x, y, w, h}}.
    """
    groups = group_tables(tables)
    layout: dict[str, dict[str, int]] = {}
    for col_idx, (_code, _label, group) in enumerate(groups):
        x = col_idx * (ENTITY_W + GAP_X)
        y = 0
        for table in sorted(group, key=lambda t: str(t["name"])):
            n_cols = len(table.get("columns", []))
            h = 40 if mode == "compact" else 34 + 24 * n_cols
            layout[str(table["name"])] = {"x": x, "y": y, "w": ENTITY_W, "h": h}
            y += h + GAP_Y
    return layout


def canvas_size(layout: dict[str, dict[str, int]]) -> tuple[int, int]:
    """Kích thước canvas vừa đủ chứa mọi entity."""
    if not layout:
        return (0, 0)
    width = max(box["x"] + box["w"] for box in layout.values())
    height = max(box["y"] + box["h"] for box in layout.values())
    return (width, height)


def relationship_lines(tables: list[dict[str, Any]], layout: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    """Relationship lines từ FK metadata: div xoay từ mép phải entity nguồn
    tới mép trái entity đích. Bỏ line khi đích bị lọc khỏi canvas."""
    lines: list[dict[str, Any]] = []
    for table in sorted(tables, key=lambda t: str(t["name"])):
        source = str(table["name"])
        if source not in layout:
            continue
        src = layout[source]
        x1 = src["x"] + src["w"]
        y1 = src["y"] + src["h"] // 2
        for fk in sorted(table.get("foreign_keys", []), key=lambda f: str(f.get("column"))):
            target = str(fk.get("references_table") or "")
            if target not in layout:
                continue
            tgt = layout[target]
            x2 = tgt["x"]
            y2 = tgt["y"] + tgt["h"] // 2
            dx = x2 - x1
            dy = y2 - y1
            length = (dx * dx + dy * dy) ** 0.5
            import math

            angle = math.degrees(math.atan2(dy, dx))
            lines.append(
                {
                    "source": source,
                    "target": target,
                    "column": str(fk.get("column")),
                    "references_column": str(fk.get("references_column")),
                    "constraint_name": fk.get("constraint_name"),
                    "on_delete": fk.get("on_delete"),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "length": length,
                    "angle_deg": angle,
                }
            )
    return lines


# --- Bước 6: Detail Panel + History + Drift viewer ---

_DOMAIN_BADGE_COLOR: dict[str, str] = {
    "core": "gray",
    "recon": "blue",
    "report": "teal",
    "admin": "violet",
    "other": "gray",
}

# Nhóm filter của drawer drift: PK là ràng buộc nên xếp vào Constraint.
_DRIFT_GROUP: dict[str, str] = {
    "TABLE_MISSING": "table",
    "TABLE_EXTRA": "table",
    "COLUMN_MISSING": "column",
    "COLUMN_EXTRA": "column",
    "TYPE_CHANGED": "column",
    "NULLABILITY_CHANGED": "column",
    "FK_CHANGED": "relationship",
    "INDEX_CHANGED": "index",
    "PK_CHANGED": "constraint",
    "CONSTRAINT_CHANGED": "constraint",
}

_DRIFT_MARKER: dict[str, str] = {"table": "−", "column": "+", "relationship": "!", "index": "!", "constraint": "!"}


def format_history_time(timestamp: str | None) -> str:
    """Định dạng timestamp ISO (UTC) thành DD/MM/YYYY HH:mm giờ VN."""
    if not timestamp:
        return "—"
    try:
        dt = datetime.fromisoformat(str(timestamp))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_VN_TZ).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(timestamp)


def _table_incoming(tables: list[dict[str, Any]], table_name: str) -> list[dict[str, Any]]:
    """FK từ các bảng khác trỏ vào table (incoming relationships)."""
    incoming: list[dict[str, Any]] = []
    for other in tables:
        for fk in other.get("foreign_keys", []) or []:
            if fk.get("references_table") == table_name:
                incoming.append(
                    {
                        "source": str(other.get("name")),
                        "column": str(fk.get("column")),
                        "references_column": str(fk.get("references_column")),
                        "constraint_name": fk.get("constraint_name"),
                    }
                )
    return sorted(incoming, key=lambda r: (r["source"], r["column"]))


def _column_marker(col: dict[str, Any]) -> str:
    """Marker cột: ◆ PK, ↗ FK, ◆↗ cả hai, U unique (theo canvas)."""
    is_pk = bool(col.get("primary_key"))
    is_fk = bool(col.get("foreign_key"))
    if is_pk and is_fk:
        return "◆↗"
    if is_pk:
        return "◆"
    if is_fk:
        return "↗"
    if col.get("unique"):
        return "U"
    return ""


def render_table_detail(
    table: dict[str, Any],
    manifest: dict[str, Any],
    history: list[dict[str, Any]],
    query: str,
    drifts: list[dict[str, Any]] | None = None,
) -> Any:
    """Detail một table: header, KPI, badges, cột, relationships, index/constraint, recent changes."""
    name = str(table.get("name"))
    columns = table.get("columns", []) or []
    outgoing = sorted(table.get("foreign_keys", []) or [], key=lambda fk: str(fk.get("column")))
    incoming = _table_incoming(manifest.get("tables", []) or [], name)
    table_drifts = [d for d in (drifts or []) if d.get("table") == name]
    domain = str(table.get("domain") or "other")
    domain_label = str(table.get("domain_label") or domain)

    column_rows: list[Any] = []
    for col in columns:
        col_name = str(col.get("name"))
        matched = bool(query) and matches_query(col_name, query)
        chips: list[Any] = []
        if col.get("primary_key"):
            chips.append(dmc.Badge("PK", size="xs", variant="light", color="red"))
        if col.get("foreign_key"):
            chips.append(dmc.Badge("FK", size="xs", variant="light", color="blue"))
        if col.get("unique"):
            chips.append(dmc.Badge("UNIQUE", size="xs", variant="light", color="violet"))
        nullable_text = "Nullable" if col.get("nullable") else "NOT NULL"
        default = col.get("default")
        default_text = f"Mặc định: {default}" if default is not None else ""
        column_rows.append(
            html.Div(
                [
                    html.Span(_column_marker(col), className="dm-col-marker"),
                    dmc.Text(
                        col_name,
                        size="xs",
                        fw=600,
                        className="rh-code" + (" dm-match" if matched else ""),
                    ),
                    dmc.Text(str(col.get("type") or ""), size="xs", c="dimmed", className="rh-code"),
                    *chips,
                    dmc.Text(nullable_text, size="xs", c="dimmed"),
                    dmc.Text(default_text, size="xs", c="dimmed") if default_text else None,
                ],
                className="dm-col-row",
            )
        )

    def _rel_row(rel: dict[str, Any], direction: str) -> Any:
        if direction == "out":
            text = f"{name}.{rel['column']} → {rel['references_table']}.{rel['references_column']}"
        else:
            text = f"{rel['source']}.{rel['column']} → {name}.{rel['references_column']}"
        constraint = rel.get("constraint_name")
        return dmc.Text(
            text + (f"  ·  {constraint}" if constraint else ""),
            size="xs",
            className="rh-code",
        )

    recent = filter_history(history or [], "", "all", name)[:5]
    recent_rows: list[Any] = []
    for event in recent:
        before = event.get("before")
        after = event.get("after")
        recent_rows.append(
            html.Div(
                [
                    dmc.Text(format_history_time(event.get("timestamp")), size="xs", c="dimmed"),
                    dmc.Badge(str(event.get("change_type")), size="xs", variant="light"),
                    dmc.Text(str(event.get("entity")), size="xs", className="rh-code"),
                    dmc.Text(
                        f"{before if before is not None else '—'} → {after if after is not None else '—'}",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                className="dm-history-row",
            )
        )

    pk_cols = table.get("primary_key", []) or []
    index_items: list[Any] = []
    if pk_cols:
        index_items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(dmc.Text("Primary Key", size="xs", fw=600)),
                    dmc.AccordionPanel(dmc.Text(", ".join(str(c) for c in pk_cols), size="xs", className="rh-code")),
                ],
                value="pk",
            )
        )
    for uc in table.get("unique_constraints", []) or []:
        cols = ", ".join(str(c) for c in uc.get("columns", []) or [])
        index_items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(dmc.Text(f"Unique: {uc.get('name')}", size="xs", fw=600)),
                    dmc.AccordionPanel(dmc.Text(cols, size="xs", className="rh-code")),
                ],
                value=f"uc-{uc.get('name')}",
            )
        )
    for fk in outgoing:
        index_items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(dmc.Text(f"Foreign key: {fk.get('constraint_name')}", size="xs", fw=600)),
                    dmc.AccordionPanel(
                        dmc.Text(
                            f"{name}.{fk.get('column')} → {fk.get('references_table')}.{fk.get('references_column')}",
                            size="xs",
                            className="rh-code",
                        )
                    ),
                ],
                value=f"fk-{fk.get('constraint_name')}",
            )
        )
    for idx in table.get("indexes", []) or []:
        cols = ", ".join(str(c) for c in idx.get("columns", []) or [])
        index_items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Text(
                            f"Index: {idx.get('name')}" + (" (unique)" if idx.get("unique") else ""),
                            size="xs",
                            fw=600,
                        )
                    ),
                    dmc.AccordionPanel(dmc.Text(cols, size="xs", className="rh-code")),
                ],
                value=f"idx-{idx.get('name')}",
            )
        )

    return dmc.Stack(
        [
            dmc.Text(name, fw=700, size="sm", className="rh-code"),
            dmc.Text(str(table.get("description") or ""), size="xs", c="dimmed"),
            dmc.Group(
                [
                    dmc.Badge(domain_label, size="xs", variant="light", color=_DOMAIN_BADGE_COLOR.get(domain, "gray")),
                    dmc.Badge(
                        "⚠ Drift" if table_drifts else "✓ Đồng bộ",
                        size="xs",
                        variant="light",
                        color="yellow" if table_drifts else "teal",
                    ),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.Text(f"Columns: {len(columns)}", size="xs", fw=600),
                    dmc.Text(f"Relationships: {len(outgoing) + len(incoming)}", size="xs", fw=600),
                ],
                gap="md",
            ),
            dmc.Text("Cột", size="xs", fw=700),
            dmc.Stack(column_rows, gap=2),
            dmc.Text(f"Relationships ra ({len(outgoing)})", size="xs", fw=700),
            dmc.Stack([_rel_row(fk, "out") for fk in outgoing], gap=2),
            dmc.Text(f"Relationships vào ({len(incoming)})", size="xs", fw=700),
            dmc.Stack([_rel_row(rel, "in") for rel in incoming], gap=2),
            dmc.Text("Index / Constraint", size="xs", fw=700),
            dmc.Accordion(index_items, chevronPosition="right")
            if index_items
            else dmc.Text("—", size="xs", c="dimmed"),
            dmc.Text("Thay đổi gần đây", size="xs", fw=700),
            (
                dmc.Stack(recent_rows, gap=2)
                if recent_rows
                else dmc.Text("Chưa ghi nhận thay đổi schema cho table này.", size="xs", c="dimmed")
            ),
        ],
        gap="xs",
        p="sm",
    )


def render_relationship_detail(rel: dict[str, Any], manifest: dict[str, Any]) -> Any:
    """Detail một relationship: source/target/constraint/N:1/delete rule + nút Source/Target table."""
    _ = manifest
    source = str(rel.get("source"))
    target = str(rel.get("target"))
    column = str(rel.get("column"))
    references_column = str(rel.get("references_column"))
    constraint = rel.get("constraint")
    on_delete = rel.get("on_delete")
    return dmc.Stack(
        [
            dmc.Text("Relationship", fw=700, size="sm"),
            dmc.Text(f"{source}.{column} → {target}.{references_column}", size="sm", className="rh-code"),
            dmc.Group(
                [
                    dmc.Text("Source:", size="xs", fw=600),
                    dmc.Text(f"{source}.{column}", size="xs", className="rh-code"),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.Text("Target:", size="xs", fw=600),
                    dmc.Text(f"{target}.{references_column}", size="xs", className="rh-code"),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.Text("Constraint:", size="xs", fw=600),
                    dmc.Text(str(constraint or "—"), size="xs", className="rh-code"),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.Text("Cardinality:", size="xs", fw=600),
                    dmc.Text("N:1", size="xs"),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.Text("Delete Rule:", size="xs", fw=600),
                    dmc.Text(str(on_delete) if on_delete else "—", size="xs"),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    button_subtle(
                        f"Source table: {source}",
                        id={"type": "dm-rel-nav", "table": source},
                        icon="lucide:arrow-left",
                        size="xs",
                    ),
                    button_subtle(
                        f"Target table: {target}",
                        id={"type": "dm-rel-nav", "table": target},
                        icon="lucide:arrow-right",
                        size="xs",
                    ),
                ],
                gap="xs",
            ),
        ],
        gap="xs",
        p="sm",
    )


def render_detail(
    selection: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    history: list[dict[str, Any]] | None,
    query: str,
    drifts: list[dict[str, Any]] | None = None,
) -> Any:
    """Detail Panel: dispatch theo selection (table / relationship / trống)."""
    if selection and selection.get("kind") == "relationship":
        return render_relationship_detail(selection, manifest or {})
    if selection and selection.get("kind") == "table" and selection.get("table"):
        name = str(selection["table"])
        tables = {t.get("name"): t for t in (manifest or {}).get("tables", []) or []}
        table = tables.get(name)
        if table is None:
            return empty_state(
                title=f"Không tìm thấy table {name} trong mô hình.",
                description="Table có thể đã bị xóa khỏi model hoặc manifest chưa đồng bộ.",
            )
        return render_table_detail(table, manifest or {}, history or [], query, drifts=drifts)
    return empty_state(
        title="Chọn một table hoặc relationship để xem chi tiết.",
        description="Bấm một table ở Schema Explorer hoặc một entity trên ER Diagram.",
    )


def filter_history(
    history: list[dict[str, Any]],
    query: str,
    change_type: str,
    table: str | None,
) -> list[dict[str, Any]]:
    """Lọc history: type chính xác, table (entity == table hoặc table.column), query không dấu.

    Trả mới nhất trước.
    """
    filtered: list[dict[str, Any]] = []
    for event in history or []:
        if change_type and change_type != "all" and event.get("change_type") != change_type:
            continue
        entity = str(event.get("entity") or "")
        if table and not (entity == table or entity.startswith(table + ".")):
            continue
        if query and not (
            matches_query(entity, query)
            or matches_query(str(event.get("migration_id") or ""), query)
            or matches_query(str(event.get("task_id") or ""), query)
            or matches_query(str(event.get("change_type") or ""), query)
        ):
            continue
        filtered.append(event)
    return list(reversed(filtered))


def render_history_timeline(events: list[dict[str, Any]]) -> Any:
    """Timeline lịch sử thay đổi (mới nhất trước)."""
    if not events:
        return empty_state(
            title="Không có thay đổi nào phù hợp.",
            description="Thử đổi từ khóa tìm kiếm hoặc loại thay đổi.",
        )
    rows: list[Any] = []
    for event in events:
        before = event.get("before")
        after = event.get("after")
        task = event.get("task_id")
        rows.append(
            html.Div(
                [
                    dmc.Group(
                        [
                            dmc.Text(format_history_time(event.get("timestamp")), size="xs", c="dimmed"),
                            dmc.Badge(str(event.get("change_type")), size="xs", variant="light"),
                        ],
                        gap="xs",
                    ),
                    dmc.Text(str(event.get("entity")), size="xs", fw=600, className="rh-code"),
                    dmc.Text(
                        f"Migration: {event.get('migration_id') or '—'}" + (f"  ·  Task: {task}" if task else ""),
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Text(
                        f"{before if before is not None else '—'} → {after if after is not None else '—'}",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                className="dm-history-row",
            )
        )
    return dmc.Stack(
        [dmc.Text(f"{len(events)} thay đổi", size="xs", fw=600), *rows],
        gap="xs",
        pt="sm",
    )


def drift_group(drift_type: str) -> str:
    """Nhóm filter của một drift type (table/column/relationship/index/constraint)."""
    return _DRIFT_GROUP.get(drift_type, "column")


def filter_drifts(drifts: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    """Lọc drift theo nhóm filter của drawer; 'all' giữ nguyên."""
    if not group or group == "all":
        return list(drifts or [])
    return [d for d in (drifts or []) if drift_group(str(d.get("type"))) == group]


def _drift_value(value: Any) -> str:
    return "—" if value is None else str(value)


def drift_report_text(drifts: list[dict[str, Any]]) -> str:
    """Text report drift để developer gửi cho AI/task (không sửa schema)."""
    if not drifts:
        return "Schema đồng bộ, không có drift."
    lines = [f"Schema drift — {len(drifts)} drift"]
    for d in drifts:
        column = d.get("column")
        where = f"{d.get('table')}.{column}" if column else str(d.get("table"))
        lines.append(f"- {d.get('type')} {where}: {d.get('detail')}")
        lines.append(f"  DB: {_drift_value(d.get('db_value'))}")
        lines.append(f"  Model: {_drift_value(d.get('model_value'))}")
    return "\n".join(lines)


def render_drift_list(drifts: list[dict[str, Any]]) -> Any:
    """List drift kèm DB vs Model; trống khi đồng bộ."""
    if not drifts:
        return empty_state(
            title="Schema đồng bộ, không có drift.",
            description="Database khớp với model và migrations.",
        )
    rows: list[Any] = []
    for d in drifts:
        group = drift_group(str(d.get("type")))
        marker = _DRIFT_MARKER.get(group, "!")
        column = d.get("column")
        where = f"{d.get('table')}.{column}" if column else str(d.get("table"))
        rows.append(
            html.Div(
                [
                    dmc.Group(
                        [
                            dmc.Text(marker, size="sm", fw=700),
                            dmc.Badge(str(d.get("type")), size="xs", variant="light"),
                            dmc.Text(where, size="xs", fw=600, className="rh-code"),
                        ],
                        gap="xs",
                    ),
                    dmc.Text(str(d.get("detail") or ""), size="xs", c="dimmed"),
                    dmc.Text(
                        f"DB: {_drift_value(d.get('db_value'))}  ·  Model: {_drift_value(d.get('model_value'))}",
                        size="xs",
                        className="rh-code",
                    ),
                ],
                className="dm-drift-row",
            )
        )
    return dmc.Stack(
        [dmc.Text(f"{len(drifts)} drift", size="xs", fw=600), *rows],
        gap="xs",
        pt="sm",
    )


def layout(**kwargs: Any) -> Any:
    """Giao diện chính màn hình Mô hình dữ liệu. Query ?table=&domain=&mode=."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="data-model-gate-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang mô hình dữ liệu.", tone="crit"),
            ]
        )

    table_param = str(kwargs.get("table") or "").strip() or None
    domain_param = str(kwargs.get("domain") or "all").strip() or "all"
    if domain_param not in {o["value"] for o in DOMAIN_OPTIONS}:
        domain_param = "all"
    mode_param = str(kwargs.get("mode") or "relations").strip() or "relations"
    if mode_param not in {o["value"] for o in MODE_OPTIONS}:
        mode_param = "relations"

    initial_selection: dict[str, Any] = (
        {"kind": "table", "table": table_param}
        if table_param
        else {
            "kind": None,
            "table": None,
        }
    )
    initial_ui: dict[str, Any] = {
        "domain": domain_param,
        "mode": mode_param,
        "expanded": {},
        "center_table": None,
        "history_table": None,
    }

    manifest_data: dict[str, Any] | None = None
    load_error = ""
    if ctx is not None:
        res = get_data_model(ctx)
        if res.ok and res.data:
            manifest_data = res.data
        else:
            load_error = res.message or "Không thể đọc metadata database."

    health_status = "UNKNOWN"
    generated_at: str | None = None
    counts = {"tables": 0, "columns": 0, "relationships": 0}
    if manifest_data is not None:
        health_status = str(manifest_data.get("drift", {}).get("status") or "UNKNOWN")
        generated_at = manifest_data.get("manifest", {}).get("generated_at")
        counts = manifest_data.get("counts", counts)

    return dmc.Box(
        [
            dcc.Store(id="data-model-manifest-store", data=manifest_data),
            dcc.Store(id="data-model-selection-store", data=initial_selection),
            dcc.Store(id="data-model-ui-store", data=initial_ui),
            dcc.Store(id="data-model-dblclick-store", data=None),
            dcc.Store(id="data-model-zoom-store", data=1.0),
            dcc.Store(id="data-model-sync-trigger", data=0),
            dcc.Store(id="data-model-sync-result-store", data=None),
            dcc.Store(id="data-model-history-filter-store", data={"query": "", "change_type": "all", "table": None}),
            dcc.Store(id="data-model-drift-filter-store", data="all"),
            html.Div(id="data-model-notification-area"),
            html.Div(id="data-model-center-sink"),
            html.Div(id="data-model-copy-sink"),
            dcc.Store(id="data-model-copy-store", data=None),
            page_header(
                title="Mô hình dữ liệu",
                subtitle="ER Diagram được sinh tự động từ metadata database, migrations và model của ứng dụng.",
                actions=[
                    button_subtle(
                        "Lịch sử thay đổi",
                        id="data-model-history-btn",
                        icon="lucide:history",
                        size="xs",
                    ),
                    button_subtle(
                        "Xem khác biệt",
                        id="data-model-drift-btn",
                        icon="lucide:git-compare",
                        size="xs",
                        style={} if health_status == "DRIFT" else {"display": "none"},
                    ),
                    button_primary(
                        "Đồng bộ schema",
                        id="data-model-sync-btn",
                        icon="lucide:refresh-cw",
                        size="xs",
                    ),
                ],
            ),
            render_command_bar(domain_param, mode_param, health_status, generated_at),
            html.Div(
                id="data-model-error-container",
                children=(
                    alert_box(
                        load_error,
                        tone="crit",
                        action=button_subtle("Thử lại", id={"type": "dm-retry-btn", "index": 0}, size="sm"),
                    )
                    if load_error
                    else None
                ),
            ),
            dcc.Loading(
                id="data-model-loading",
                type="circle",
                children=dmc.Group(
                    [
                        dmc.Paper(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text("Schema Explorer", fw=600, size="sm"),
                                        dmc.Text(
                                            f"{counts['tables']} tables",
                                            id="data-model-explorer-count",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    justify="space-between",
                                    px="sm",
                                    pt="xs",
                                ),
                                html.Div(
                                    id="data-model-explorer-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 2,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                        dmc.Paper(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text("ER Diagram", fw=600, size="sm"),
                                        dmc.Group(
                                            [
                                                dmc.Text(
                                                    "100%",
                                                    id="data-model-zoom-label",
                                                    size="xs",
                                                    c="dimmed",
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:zoom-in", width=14),
                                                    id="data-model-zoom-in-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Phóng to ER Diagram"},
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:zoom-out", width=14),
                                                    id="data-model-zoom-out-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Thu nhỏ ER Diagram"},
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:maximize", width=14),
                                                    id="data-model-fit-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Vừa màn hình"},
                                                ),
                                            ],
                                            gap=0,
                                        ),
                                    ],
                                    justify="space-between",
                                    px="sm",
                                    pt="xs",
                                ),
                                html.Div(
                                    id="data-model-canvas-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 5,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                        dmc.Paper(
                            [
                                dmc.Text("Chi tiết", fw=600, size="sm", px="sm", pt="xs"),
                                html.Div(
                                    id="data-model-detail-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 3,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                    ],
                    gap="xs",
                    align="stretch",
                    style={"flex": 1, "minHeight": 0, "flexWrap": "nowrap"},
                    className="dm-workspace",
                ),
                parent_style={
                    "flex": 1,
                    "minHeight": 0,
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
            ),
            dmc.Group(
                [
                    dmc.Text(
                        f"{counts['tables']} tables · {counts['columns']} columns · {counts['relationships']} relationships",
                        id="data-model-status-counts",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Text(
                        "SQLAlchemy Core models + Alembic migrations + SQLite metadata",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                justify="space-between",
                px="xs",
                pt=4,
                id="data-model-status-bar",
                style={"flexShrink": 0},
            ),
            drawer_right(
                id="data-model-history-drawer",
                title="Lịch sử thay đổi",
                children=[
                    dmc.TextInput(
                        id="data-model-history-search",
                        placeholder="Tìm entity, migration…",
                        leftSection=DashIconify(icon="lucide:search", width=14),
                        size="xs",
                    ),
                    dmc.Select(
                        id="data-model-history-type-filter",
                        data=HISTORY_TYPE_OPTIONS,
                        value="all",
                        size="xs",
                        clearable=False,
                        **{"aria-label": "Lọc theo loại thay đổi"},
                    ),
                    html.Div(id="data-model-history-timeline"),
                ],
            ),
            drawer_right(
                id="data-model-drift-drawer",
                title="Schema Drift",
                children=[
                    dmc.Select(
                        id="data-model-drift-filter",
                        data=[
                            {"label": "Tất cả", "value": "all"},
                            {"label": "Table", "value": "table"},
                            {"label": "Column", "value": "column"},
                            {"label": "Relationship", "value": "relationship"},
                            {"label": "Index", "value": "index"},
                            {"label": "Constraint", "value": "constraint"},
                        ],
                        value="all",
                        size="xs",
                        clearable=False,
                        **{"aria-label": "Lọc drift theo loại"},
                    ),
                    dcc.Clipboard(
                        id="data-model-drift-copy",
                        title="Copy report",
                        content="",
                    ),
                    html.Div(id="data-model-drift-list"),
                ],
            ),
        ],
        style={
            "height": "calc(100vh - 88px)",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "8px",
        },
        className="dm-page",
    )


# --- Callbacks ---


@callback(
    Output("data-model-explorer-container", "children"),
    Output("data-model-canvas-container", "children"),
    Output("data-model-detail-container", "children"),
    Output("data-model-explorer-count", "children"),
    Output("data-model-status-counts", "children"),
    Output("data-model-zoom-label", "children"),
    Input("data-model-manifest-store", "data"),
    Input("data-model-search", "value"),
    Input("data-model-domain-filter", "value"),
    Input("data-model-mode-select", "value"),
    Input("data-model-selection-store", "data"),
    Input("data-model-ui-store", "data"),
    Input("data-model-zoom-store", "data"),
)
def update_workspace(
    manifest_data: dict[str, Any] | None,
    search: str | None,
    domain: str | None,
    mode: str | None,
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
    zoom: float | None,
) -> tuple[Any, Any, Any, str, str, str]:
    """Dựng lại Explorer + Canvas + Detail theo search/domain/mode/selection."""
    if not manifest_data or not manifest_data.get("manifest"):
        return (
            alert_box("Không thể đọc metadata database.", tone="crit"),
            render_canvas([], selection, ui, zoom or 1.0, search or ""),
            render_detail(selection, None, None, search or "", drifts=[]),
            "0 tables",
            "0 tables · 0 columns · 0 relationships",
            _zoom_label(zoom or 1.0),
        )
    manifest = manifest_data["manifest"]
    tables = manifest.get("tables", []) or []
    if not tables:
        return (
            empty_state(
                title="Chưa có table nào trong mô hình.",
                description="Manifest trống. Bấm Đồng bộ lại để quét schema từ model và migrations.",
                action=button_subtle("Đồng bộ lại", id={"type": "dm-resync-btn", "index": 0}, icon="lucide:refresh-cw"),
            ),
            empty_state(
                title="Chưa có table nào trong mô hình.",
                description="Bấm Đồng bộ lại để quét schema từ model và migrations.",
            ),
            render_detail(selection, manifest, manifest_data.get("history") or [], search or ""),
            "0 tables",
            "0 tables · 0 columns · 0 relationships",
            _zoom_label(zoom or 1.0),
        )
    filtered = filter_tables(tables, search or "", domain or "all")
    counts = manifest_data.get(
        "counts",
        {
            "tables": len(tables),
            "columns": sum(len(t.get("columns", [])) for t in tables),
            "relationships": sum(len(t.get("foreign_keys", [])) for t in tables),
        },
    )
    return (
        render_explorer(filtered, selection, ui, search or ""),
        render_canvas(filtered, selection, ui, zoom or 1.0, search or ""),
        render_detail(
            selection,
            manifest,
            manifest_data.get("history") or [],
            search or "",
            drifts=manifest_data.get("drift", {}).get("drifts") or [],
        ),
        f"{len(filtered)} tables",
        f"{counts['tables']} tables · {counts['columns']} columns · {counts['relationships']} relationships",
        _zoom_label(zoom or 1.0),
    )


@callback(
    Output("data-model-selection-store", "data"),
    Output("app-location", "href", allow_duplicate=True),
    Input({"type": "dm-table-item", "table": ALL}, "n_clicks"),
    State("data-model-selection-store", "data"),
    State("data-model-ui-store", "data"),
    prevent_initial_call=True,
)
def handle_table_click(
    _n_clicks: list[int | None],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Click dòng table: cập nhật selection + URL (?table=&domain=&mode=)."""
    ctx_dash = dash.callback_context
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return selection or {"kind": None, "table": None}, dash.no_update
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    table = triggered.get("table")
    if not table:
        return selection or {"kind": None, "table": None}, dash.no_update
    ui_data = ui or {}
    domain = str(ui_data.get("domain") or "all")
    mode = str(ui_data.get("mode") or "relations")
    return (
        {"kind": "table", "table": str(table)},
        f"/data-model?table={table}&domain={domain}&mode={mode}",
    )


@callback(
    Output("data-model-ui-store", "data"),
    Input({"type": "dm-group-toggle", "domain": ALL}, "n_clicks"),
    State("data-model-ui-store", "data"),
    prevent_initial_call=True,
)
def handle_group_toggle(
    _n_clicks: list[int | None],
    ui: dict[str, Any] | None,
) -> dict[str, Any]:
    """Bấm header group: đảo trạng thái collapse/expand của group đó."""
    ctx_dash = dash.callback_context
    ui_data = dict(ui or {})
    expanded = dict(ui_data.get("expanded") or {})
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return ui_data
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    domain = triggered.get("domain")
    if not domain:
        return ui_data
    current = expanded.get(str(domain))
    expanded[str(domain)] = not current if current is not None else False
    ui_data["expanded"] = expanded
    return ui_data


@callback(
    Output("data-model-selection-store", "data", allow_duplicate=True),
    Output("data-model-ui-store", "data", allow_duplicate=True),
    Output("data-model-history-filter-store", "data"),
    Output("data-model-history-drawer", "opened"),
    Output("data-model-copy-store", "data"),
    Output("data-model-history-search", "value", allow_duplicate=True),
    Output("data-model-history-type-filter", "value", allow_duplicate=True),
    Input({"type": "dm-table-menu", "table": ALL, "action": ALL}, "n_clicks"),
    State("data-model-selection-store", "data"),
    State("data-model-ui-store", "data"),
    State("data-model-history-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_context_menu(
    _n_clicks: list[int | None],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
    history_filter: dict[str, Any] | None,
) -> tuple[Any, Any, Any, bool, Any, Any, Any]:
    """Context menu của dòng table: center/columns/relationships/history/copy.

    TUYỆT ĐỐI KHÔNG có thao tác ghi schema (Drop/Alter/Delete/Run SQL).
    """
    ctx_dash = dash.callback_context
    ui_data = dict(ui or {})
    hist_data = dict(history_filter or {"query": "", "change_type": "all", "table": None})
    fallback_sel = selection or {"kind": None, "table": None}
    no_filter_change = (dash.no_update, dash.no_update)
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return fallback_sel, ui_data, hist_data, False, dash.no_update, *no_filter_change
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    table = str(triggered.get("table") or "")
    action = str(triggered.get("action") or "")
    if not table or not action:
        return fallback_sel, ui_data, hist_data, False, dash.no_update, *no_filter_change
    new_selection: dict[str, Any] = {"kind": "table", "table": table}
    if action == "center":
        ui_data["center_table"] = table
        return new_selection, ui_data, hist_data, False, dash.no_update, *no_filter_change
    if action == "columns":
        ui_data["mode"] = "relations"
        return new_selection, ui_data, hist_data, False, dash.no_update, *no_filter_change
    if action == "relationships":
        ui_data["mode"] = "relations"
        return new_selection, ui_data, hist_data, False, dash.no_update, *no_filter_change
    if action == "history":
        hist_data["table"] = table
        hist_data["query"] = ""
        hist_data["change_type"] = "all"
        # Reset ô tìm kiếm + filter loại trong drawer cho khớp store.
        return new_selection, ui_data, hist_data, True, dash.no_update, "", "all"
    if action == "copy":
        return fallback_sel, ui_data, hist_data, False, {"text": table}, *no_filter_change
    return fallback_sel, ui_data, hist_data, False, dash.no_update, *no_filter_change


@callback(
    Output("data-model-selection-store", "data", allow_duplicate=True),
    Output("data-model-ui-store", "data", allow_duplicate=True),
    Output("data-model-zoom-store", "data", allow_duplicate=True),
    Input("data-model-dblclick-store", "data"),
    State("data-model-selection-store", "data"),
    State("data-model-ui-store", "data"),
    State("data-model-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_dblclick(
    dblclick_data: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
    zoom: float | None,
) -> tuple[Any, Any, Any]:
    """Double-click entity (từ JS asset): chọn table, center, zoom đủ đọc cột."""
    if not dblclick_data or not dblclick_data.get("table"):
        raise dash.exceptions.PreventUpdate
    _ = (selection, zoom)
    ui_data = dict(ui or {})
    ui_data["center_table"] = str(dblclick_data["table"])
    ui_data["mode"] = "relations"
    return (
        {"kind": "table", "table": str(dblclick_data["table"])},
        ui_data,
        1.0,
    )


@callback(
    Output("data-model-search", "value"),
    Output("data-model-domain-filter", "value"),
    Input("data-model-clear-filter-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_clear_filter(n_clicks: int | None) -> tuple[str, str]:
    """Nút Xóa bộ lọc ở empty search: xóa search + domain về Tất cả."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return "", "all"


# Copy tên bảng: clientside ghi clipboard khi copy-store đổi (theo mẫu
# drag_drop_reporting.js dùng window.dash_clientside.set_props; chiều ngược
# lại ở đây là đọc store rồi gọi navigator.clipboard).
clientside_callback(
    """
    function(copyData) {
        if (copyData && copyData.text && navigator.clipboard) {
            navigator.clipboard.writeText(copyData.text).catch(function() {});
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("data-model-copy-sink", "children"),
    Input("data-model-copy-store", "data"),
    prevent_initial_call=True,
)


# --- Bước 5: ER Canvas callbacks ---

MIN_ZOOM = 0.55
MAX_ZOOM = 1.35
ZOOM_STEP = 0.1


def _zoom_label(zoom: float) -> str:
    return f"{int(round(zoom * 100))}%"


def _selection_href(table: str, ui: dict[str, Any] | None) -> str:
    ui_data = ui or {}
    domain = str(ui_data.get("domain") or "all")
    mode = str(ui_data.get("mode") or "relations")
    return f"/data-model?table={table}&domain={domain}&mode={mode}"


@callback(
    Output("data-model-zoom-store", "data", allow_duplicate=True),
    Input("data-model-zoom-in-btn", "n_clicks"),
    State("data-model-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_zoom_in(n_clicks: int | None, zoom: float | None) -> float:
    """Phóng to ER Diagram một bước, kẹp ở MAX_ZOOM.

    Nhãn zoom do update_workspace viết theo zoom-store (một nơi duy nhất).
    """
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return min(MAX_ZOOM, max(MIN_ZOOM, round((zoom or 1.0) + ZOOM_STEP, 1)))


@callback(
    Output("data-model-zoom-store", "data", allow_duplicate=True),
    Input("data-model-zoom-out-btn", "n_clicks"),
    State("data-model-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_zoom_out(n_clicks: int | None, zoom: float | None) -> float:
    """Thu nhỏ ER Diagram một bước, kẹp ở MIN_ZOOM."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return min(MAX_ZOOM, max(MIN_ZOOM, round((zoom or 1.0) - ZOOM_STEP, 1)))


@callback(
    Output("data-model-selection-store", "data", allow_duplicate=True),
    Output("app-location", "href", allow_duplicate=True),
    Input({"type": "dm-entity", "table": ALL}, "n_clicks"),
    State("data-model-selection-store", "data"),
    State("data-model-ui-store", "data"),
    prevent_initial_call=True,
)
def handle_entity_click(
    _n_clicks: list[int | None],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Click entity trên canvas: chọn table + cập nhật URL (như click dòng)."""
    ctx_dash = dash.callback_context
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return selection or {"kind": None, "table": None}, dash.no_update
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    table = triggered.get("table")
    if not table:
        return selection or {"kind": None, "table": None}, dash.no_update
    return {"kind": "table", "table": str(table)}, _selection_href(str(table), ui)


@callback(
    Output("data-model-selection-store", "data", allow_duplicate=True),
    Input({"type": "dm-rel-line", "index": ALL}, "n_clicks"),
    State("data-model-manifest-store", "data"),
    State("data-model-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_rel_click(
    _n_clicks: list[int | None],
    manifest_data: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> dict[str, Any]:
    """Click relationship line: chọn relationship (source/target/column)."""
    ctx_dash = dash.callback_context
    fallback = selection or {"kind": None, "table": None}
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return fallback
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    index = triggered.get("index")
    if index is None or not manifest_data or not manifest_data.get("manifest"):
        return fallback
    tables = manifest_data["manifest"].get("tables", [])
    lines = relationship_lines(tables, layout_entities(tables, "relations"))
    try:
        line = lines[int(index)]
    except (IndexError, ValueError, TypeError):
        return fallback
    return {
        "kind": "relationship",
        "source": line["source"],
        "target": line["target"],
        "column": line["column"],
        "references_column": line["references_column"],
        "constraint": line.get("constraint_name"),
        "on_delete": line.get("on_delete"),
    }


# Fit-to-screen: clientside đọc kích thước viewport + canvas, tính scale rồi
# trả về zoom store (server render lại với transform mới). Không clear
# search/domain/selection.
clientside_callback(
    """
    function(nClicks) {
        var container = document.getElementById('data-model-canvas-container');
        var inner = document.getElementById('data-model-canvas-inner');
        if (!container || !inner) return window.dash_clientside.no_update;
        var w = parseFloat(inner.dataset.w || '0');
        var h = parseFloat(inner.dataset.h || '0');
        if (!w || !h) return window.dash_clientside.no_update;
        var scale = Math.min(container.clientWidth / w, container.clientHeight / h);
        scale = Math.round(scale * 10) / 10;
        scale = Math.max(0.55, Math.min(1.35, scale));
        return scale;
    }
    """,
    Output("data-model-zoom-store", "data", allow_duplicate=True),
    Input("data-model-fit-btn", "n_clicks"),
    prevent_initial_call=True,
)


# Center: clientside cuộn container tới entity khi ui-store đổi center_table.
# Chỉ cuộn khi center_table đổi (tránh cuộn lại mỗi lần ui-store đổi khác).
clientside_callback(
    """
    function(ui) {
        if (!ui || !ui.center_table) return window.dash_clientside.no_update;
        if (window.__dmLastCenter === ui.center_table) return window.dash_clientside.no_update;
        window.__dmLastCenter = ui.center_table;
        var container = document.getElementById('data-model-canvas-container');
        var inner = document.getElementById('data-model-canvas-inner');
        var el = document.querySelector('.dm-entity[data-table="' + ui.center_table + '"]');
        if (!container || !inner || !el) return window.dash_clientside.no_update;
        var zoom = parseFloat(inner.dataset.zoom || '1');
        var left = el.offsetLeft * zoom + el.offsetWidth * zoom / 2 - container.clientWidth / 2;
        var top = el.offsetTop * zoom + el.offsetHeight * zoom / 2 - container.clientHeight / 2;
        container.scrollTo({left: Math.max(0, left), top: Math.max(0, top)});
        return window.dash_clientside.no_update;
    }
    """,
    Output("data-model-center-sink", "children"),
    Input("data-model-ui-store", "data"),
    prevent_initial_call=True,
)


# --- Bước 6: History + Drift callbacks ---


@callback(
    Output("data-model-history-drawer", "opened", allow_duplicate=True),
    Output("data-model-history-search", "value", allow_duplicate=True),
    Output("data-model-history-type-filter", "value", allow_duplicate=True),
    Output("data-model-history-filter-store", "data", allow_duplicate=True),
    Input("data-model-history-btn", "n_clicks"),
    State("data-model-history-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_history_open(
    n_clicks: int | None,
    history_filter: dict[str, Any] | None,
) -> tuple[bool, str, str, dict[str, Any]]:
    """Nút Lịch sử thay đổi ở header: mở drawer + reset filter về mặc định."""
    _ = history_filter
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return True, "", "all", {"query": "", "change_type": "all", "table": None}


@callback(
    Output("data-model-history-timeline", "children"),
    Input("data-model-manifest-store", "data"),
    Input("data-model-history-filter-store", "data"),
    Input("data-model-history-search", "value"),
    Input("data-model-history-type-filter", "value"),
)
def handle_history_timeline(
    manifest_data: dict[str, Any] | None,
    history_filter: dict[str, Any] | None,
    search: str | None,
    change_type: str | None,
) -> Any:
    """Timeline history theo store (table) + ô tìm kiếm + filter loại trong drawer."""
    if not manifest_data or not manifest_data.get("history"):
        return render_history_timeline([])
    hist_filter = history_filter or {}
    table = hist_filter.get("table")
    events = filter_history(
        manifest_data.get("history") or [],
        search or "",
        change_type or "all",
        str(table) if table else None,
    )
    return render_history_timeline(events)


@callback(
    Output("data-model-drift-drawer", "opened"),
    Input("data-model-drift-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_drift_open(n_clicks: int | None) -> bool:
    """Nút Xem khác biệt (chỉ hiện khi health = DRIFT): mở drift drawer."""
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    return True


@callback(
    Output("data-model-drift-list", "children"),
    Input("data-model-manifest-store", "data"),
    Input("data-model-drift-filter", "value"),
)
def handle_drift_list(
    manifest_data: dict[str, Any] | None,
    drift_filter: str | None,
) -> Any:
    """Drift list theo filter nhóm trong drawer."""
    if not manifest_data:
        return render_drift_list([])
    drifts = manifest_data.get("drift", {}).get("drifts") or []
    return render_drift_list(filter_drifts(drifts, drift_filter or "all"))


@callback(
    Output("data-model-drift-copy", "content"),
    Input("data-model-manifest-store", "data"),
    Input("data-model-drift-filter", "value"),
)
def handle_drift_copy(
    manifest_data: dict[str, Any] | None,
    drift_filter: str | None,
) -> str:
    """Nội dung Copy report theo đúng filter đang chọn (không sửa schema)."""
    if not manifest_data:
        return drift_report_text([])
    drifts = manifest_data.get("drift", {}).get("drifts") or []
    return drift_report_text(filter_drifts(drifts, drift_filter or "all"))


@callback(
    Output("data-model-selection-store", "data", allow_duplicate=True),
    Output("app-location", "href", allow_duplicate=True),
    Input({"type": "dm-rel-nav", "table": ALL}, "n_clicks"),
    State("data-model-selection-store", "data"),
    State("data-model-ui-store", "data"),
    prevent_initial_call=True,
)
def handle_rel_nav(
    _n_clicks: list[int | None],
    selection: dict[str, Any] | None,
    ui: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Nút Source/Target table trong relationship detail: chọn table đó + URL."""
    ctx_dash = dash.callback_context
    fallback = selection or {"kind": None, "table": None}
    if (_triggered_clicks(ctx_dash) or 0) <= 0:
        return fallback, dash.no_update
    triggered = _parse_triggered_id(ctx_dash.triggered[0]["prop_id"])
    table = triggered.get("table")
    if not table:
        return fallback, dash.no_update
    return {"kind": "table", "table": str(table)}, _selection_href(str(table), ui)


# --- Bước 7: Sync state machine + loading/empty/error ---


def sync_result_to_ui(result: dict[str, Any] | None, current_health: str = "SYNCED") -> dict[str, Any]:
    """State machine nút Đồng bộ schema -> props UI (button, health, message, drift).

    Trạng thái: NORMAL (result None) / RUNNING ({"running": True}) /
    SUCCESS-NO-CHANGE / SUCCESS-CHANGED / DRIFT / ERROR ({"ok": False}).
    """
    base: dict[str, Any] = {
        "button_loading": False,
        "button_disabled": False,
        "button_label": "Đồng bộ schema",
        "health": current_health,
        "message": None,
        "show_drift": current_health == "DRIFT",
    }
    if result is None:
        return base
    if result.get("running"):
        base.update(
            {
                "button_loading": True,
                "button_disabled": True,
                "button_label": "Đang đồng bộ…",
                "health": "CHECKING",
                "show_drift": False,
            }
        )
        return base
    if not result.get("ok", True):
        base.update(
            {
                "health": "ERROR",
                "message": ("crit", str(result.get("message") or "Không thể đọc metadata database.")),
                "show_drift": False,
            }
        )
        return base
    changed = result.get("changed") or {}
    n_tables = int(changed.get("tables") or 0)
    n_columns = int(changed.get("columns") or 0)
    if result.get("drift_status") == "DRIFT":
        base.update(
            {
                "health": "DRIFT",
                "message": ("warn", "⚠ Schema drift — bấm Xem khác biệt để xem chi tiết."),
                "show_drift": True,
            }
        )
        return base
    if n_tables == 0 and n_columns == 0:
        base.update({"health": "SYNCED", "message": ("ok", "✓ Schema đồng bộ")})
    else:
        base.update(
            {
                "health": "SYNCED",
                "message": (
                    "ok",
                    f"✓ Đã cập nhật mô hình — {n_tables} tables, {n_columns} columns thay đổi",
                ),
            }
        )
    return base


def _sync_ui_outputs(ui: dict[str, Any], result: dict[str, Any] | None) -> tuple[Any, Any, Any]:
    """Chuyển state machine thành (health badge, notification, drift style)."""
    health_node = health_badge(str(ui["health"]))
    message = ui.get("message")
    note = alert_box(message[1], tone=message[0]) if message else None
    drift_style = {} if ui.get("show_drift") else {"display": "none"}
    return health_node, note, drift_style


def _sync_clicked(ctx_dash: Any) -> bool:
    """Có click thật (> 0) trên sync/retry/resync không (int hoặc list pattern ALL)."""
    triggered = getattr(ctx_dash, "triggered", None) or []
    for entry in triggered:
        value = entry.get("value")
        if isinstance(value, int) and value > 0:
            return True
        if isinstance(value, list) and any(isinstance(v, int) and v > 0 for v in value):
            return True
    return False


@callback(
    Output("data-model-sync-btn", "loading"),
    Output("data-model-sync-btn", "disabled"),
    Output("data-model-sync-btn", "children"),
    Output("data-model-sync-trigger", "data"),
    Output("data-model-sync-result-store", "data"),
    Output("data-model-health-container", "children"),
    Output("data-model-notification-area", "children"),
    Output("data-model-drift-btn", "style"),
    Input("data-model-sync-btn", "n_clicks"),
    Input({"type": "dm-retry-btn", "index": ALL}, "n_clicks"),
    Input({"type": "dm-resync-btn", "index": ALL}, "n_clicks"),
    State("data-model-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_sync_click(
    _n_clicks: int | None,
    _retry_clicks: list[int | None],
    _resync_clicks: list[int | None],
    trigger: int | None,
) -> tuple[bool, bool, str, int, None, Any, None, dict[str, str]]:
    """Pha 1: bấm Đồng bộ/Thử lại/Đồng bộ lại -> nút loading + health đang kiểm tra + tăng trigger."""
    if not _sync_clicked(dash.callback_context):
        raise dash.exceptions.PreventUpdate
    ui = sync_result_to_ui({"running": True})
    health_node, _note, drift_style = _sync_ui_outputs(ui, None)
    return (
        True,
        True,
        str(ui["button_label"]),
        int(trigger or 0) + 1,
        None,
        health_node,
        None,
        drift_style,
    )


@callback(
    Output("data-model-manifest-store", "data"),
    Output("data-model-sync-result-store", "data", allow_duplicate=True),
    Output("data-model-sync-btn", "loading", allow_duplicate=True),
    Output("data-model-sync-btn", "disabled", allow_duplicate=True),
    Output("data-model-sync-btn", "children", allow_duplicate=True),
    Output("data-model-health-container", "children", allow_duplicate=True),
    Output("data-model-notification-area", "children", allow_duplicate=True),
    Output("data-model-drift-btn", "style", allow_duplicate=True),
    Output("data-model-error-container", "children"),
    Output("data-model-last-sync", "children"),
    Input("data-model-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_sync_run(trigger: int | None) -> tuple[Any, Any, bool, bool, str, Any, Any, Any, Any, Any]:
    """Pha 2: trigger tăng -> chạy sync_schema, reload manifest, trả trạng thái cuối."""
    if not trigger:
        raise dash.exceptions.PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        result: dict[str, Any] = {"ok": False, "message": "Bạn chưa đăng nhập."}
        manifest_data: Any = dash.no_update
        generated_at: str | None = None
    else:
        res = sync_schema(ctx)
        if res.ok and res.data:
            result = {"ok": True, **res.data}
        else:
            result = {"ok": False, "message": res.message or "Không thể đọc metadata database."}
        reload = get_data_model(ctx)
        if reload.ok and reload.data:
            manifest_data = reload.data
            generated_at = str(reload.data.get("manifest", {}).get("generated_at") or "")
        else:
            manifest_data = dash.no_update
            generated_at = None
    ui = sync_result_to_ui(result)
    health_node, note, drift_style = _sync_ui_outputs(ui, result)
    error_node: Any = None
    if not result.get("ok", True):
        error_node = alert_box(
            str(result.get("message") or "Không thể đọc metadata database."),
            tone="crit",
            action=button_subtle("Thử lại", id={"type": "dm-retry-btn", "index": 0}, size="sm"),
        )
    return (
        manifest_data,
        result,
        bool(ui["button_loading"]),
        bool(ui["button_disabled"]),
        str(ui["button_label"]),
        health_node,
        note,
        drift_style,
        error_node,
        format_last_sync(generated_at) if generated_at else dash.no_update,
    )
