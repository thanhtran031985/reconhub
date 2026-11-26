"""Canvas geometry, Star Schema Auto Layout & HTML+SVG connector builders (Task 107 Bước 3)."""

from __future__ import annotations

import json
from typing import Any

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from app.ui.components.button import button_primary

CARD_WIDTH = 252
CARD_HEADER_H = 34
COL_ROW_H = 24
CARD_PAD_BOTTOM = 8
MAX_CARD_COLS = 16
MIN_CARD_H = 68
MIN_CANVAS_W = 1120
MIN_CANVAS_H = 680


def _visible_canvas_fields(tbl: dict[str, Any]) -> list[dict[str, Any]]:
    fields = list(tbl.get("fields") or [])
    return fields[:MAX_CARD_COLS]


def table_box(tbl: dict[str, Any]) -> dict[str, int]:
    """Tính bounding box (x, y, w, h) cho Entity Card trên Canvas."""
    vis_fields = _visible_canvas_fields(tbl)
    extra_footer = 20 if len(tbl.get("fields") or []) > MAX_CARD_COLS else 0
    h = max(MIN_CARD_H, CARD_HEADER_H + len(vis_fields) * COL_ROW_H + CARD_PAD_BOTTOM + extra_footer)
    return {
        "x": int(tbl.get("pos_x") or 0),
        "y": int(tbl.get("pos_y") or 0),
        "w": CARD_WIDTH,
        "h": h,
    }


def auto_layout_star_schema(
    tables: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[int, tuple[int, int]]:
    """Sắp xếp Star Schema deterministic: Fact ở giữa, Dim vệ tinh hai bên, không chồng lấn."""
    if not tables:
        return {}

    _ = relationships
    facts = sorted(
        [t for t in tables if str(t.get("table_role") or "").upper() == "FACT"],
        key=lambda t: str(t.get("alias") or t.get("id")),
    )
    bridges = sorted(
        [t for t in tables if str(t.get("table_role") or "").upper() == "BRIDGE"],
        key=lambda t: str(t.get("alias") or t.get("id")),
    )
    dims = sorted(
        [t for t in tables if str(t.get("table_role") or "").upper() == "DIMENSION"],
        key=lambda t: str(t.get("alias") or t.get("id")),
    )
    others = sorted(
        [
            t
            for t in tables
            if str(t.get("table_role") or "UNCLASSIFIED").upper() not in ("FACT", "DIMENSION", "BRIDGE")
        ],
        key=lambda t: str(t.get("alias") or t.get("id")),
    )

    positions: dict[int, tuple[int, int]] = {}
    gap_y = 44
    col_left_x = 44
    col_center_x = 410
    col_right_x = 776
    col_far_right_x = 1100

    # 1. Fact ở cột giữa (nếu không có Fact chính thức, lấy phần tử đầu tiên ở giữa)
    center_nodes = facts if facts else (others[:1] if others else dims[:1])
    used_ids = {int(t["id"]) for t in center_nodes}
    y_center = 64
    for tbl in center_nodes:
        tid = int(tbl["id"])
        box = table_box(tbl)
        positions[tid] = (col_center_x, y_center)
        y_center += box["h"] + gap_y

    # 2. Dimension & Bridge xen kẽ trái/phải quanh Fact
    satellites = [t for t in [*dims, *bridges, *others] if int(t["id"]) not in used_ids]
    lane_x = [col_left_x, col_right_x, col_far_right_x]
    lane_y = [48, 48, 48]

    for idx, tbl in enumerate(satellites):
        # Ưu tiên cân 2 bên trái/phải trước; khi quá dài mới sang cột phải ngoài
        lane_idx = idx % 2 if idx < 8 else 2
        tid = int(tbl["id"])
        box = table_box(tbl)
        positions[tid] = (lane_x[lane_idx], lane_y[lane_idx])
        lane_y[lane_idx] += box["h"] + gap_y

    return positions


def compute_canvas_fit(
    tables: list[dict[str, Any]],
    viewport_w: int = 800,
    viewport_h: int = 560,
) -> float:
    """Tính mức zoom phù hợp để hiển thị toàn bộ bảng trong viewport."""
    if not tables:
        return 1.0
    boxes = [table_box(t) for t in tables]
    max_x = max(b["x"] + b["w"] for b in boxes) + 64
    max_y = max(b["y"] + b["h"] for b in boxes) + 64
    if max_x <= 0 or max_y <= 0:
        return 1.0
    ratio = min(float(viewport_w) / float(max_x), float(viewport_h) / float(max_y))
    clamped = max(0.4, min(1.25, ratio))
    return round(clamped, 2)


def _column_y_offset(tbl: dict[str, Any], column_name: str, box_h: int) -> int:
    vis_fields = _visible_canvas_fields(tbl)
    target = column_name.strip().upper()
    for idx, fld in enumerate(vis_fields):
        if str(fld.get("source_column") or "").strip().upper() == target:
            return CARD_HEADER_H + idx * COL_ROW_H + COL_ROW_H // 2
    return min(box_h - 14, CARD_HEADER_H + 14)


def build_relationship_connectors(
    tables: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    selection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Tính hình học SVG bezier & trạng thái highlight cho danh sách quan hệ."""
    table_map = {int(t["id"]): t for t in tables}
    box_map = {int(t["id"]): table_box(t) for t in tables}

    sel_kind = (selection or {}).get("kind")
    sel_id = (selection or {}).get("id")
    sel_tid = int(sel_id) if sel_kind == "table" and sel_id is not None else None
    sel_rid = int(sel_id) if sel_kind == "relationship" and sel_id is not None else None
    has_sel = (sel_tid is not None) or (sel_rid is not None)

    connectors: list[dict[str, Any]] = []
    for rel in relationships:
        rid = int(rel["id"])
        src_id = int(rel["from_table_id"])
        dst_id = int(rel["to_table_id"])
        if src_id not in box_map or dst_id not in box_map:
            continue
        sb = box_map[src_id]
        db = box_map[dst_id]
        y1 = sb["y"] + _column_y_offset(table_map[src_id], str(rel.get("from_column") or ""), sb["h"])
        y2 = db["y"] + _column_y_offset(table_map[dst_id], str(rel.get("to_column") or ""), db["h"])

        # Chọn cổng trái/phải sao cho dây đi gọn nhất
        src_cx = sb["x"] + sb["w"] // 2
        dst_cx = db["x"] + db["w"] // 2
        if dst_cx >= src_cx:
            x1 = sb["x"] + sb["w"]
            x2 = db["x"]
            dir_x = 1
        else:
            x1 = sb["x"]
            x2 = db["x"] + db["w"]
            dir_x = -1

        curve = max(48, abs(x2 - x1) // 2)
        cx1 = x1 + dir_x * curve
        cx2 = x2 - dir_x * curve
        path_d = f"M {x1} {y1} C {cx1} {y1}, {cx2} {y2}, {x2} {y2}"
        mid_x = int((x1 + x2) / 2)
        mid_y = int((y1 + y2) / 2)

        val_st = str(rel.get("validation_status") or "").upper()
        is_active = bool(rel.get("is_active", True))
        if rid == sel_rid:
            state_cls = "selected"
        elif sel_tid is not None and (src_id == sel_tid or dst_id == sel_tid):
            state_cls = "related"
        elif val_st == "ERROR":
            state_cls = "error"
        elif val_st == "WARNING":
            state_cls = "warning"
        elif not is_active:
            state_cls = "inactive"
        elif has_sel:
            state_cls = "dimmed"
        else:
            state_cls = "normal"

        card = str(rel.get("cardinality") or "MANY_TO_ONE")
        connectors.append(
            {
                "id": rid,
                "name": str(rel.get("name") or ""),
                "from_table_id": src_id,
                "to_table_id": dst_id,
                "from_column": str(rel.get("from_column") or ""),
                "to_column": str(rel.get("to_column") or ""),
                "cardinality": card,
                "label": "*:1" if card == "MANY_TO_ONE" else "1:1",
                "join_type": str(rel.get("join_type") or "LEFT_OUTER"),
                "is_active": is_active,
                "validation_status": val_st or "UNCHECKED",
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "mid_x": mid_x,
                "mid_y": mid_y,
                "path_d": path_d,
                "state_cls": state_cls,
            }
        )
    return connectors


def render_model_canvas_inner(
    bundle: dict[str, Any],
    *,
    selection: dict[str, Any] | None = None,
    zoom: float = 1.0,
    focus_token: str = "",
) -> Any:
    """Dựng vùng bên trong #rm-canvas-container gồm Entity Cards + SVG connector metadata."""
    tables = list(bundle.get("tables") or [])
    rels = list(bundle.get("relationships") or [])

    if not tables:
        from app.ui.components.empty_state import empty_state

        return empty_state(
            title="Canvas mô hình đang trống",
            description="Thêm các bảng Fact / Dimension từ Explorer để bắt đầu vẽ mô hình.",
            action=button_primary("Thêm bảng", id={"type": "rms-empty-add-btn", "src": "canvas"}, icon="lucide:plus", size="xs"),
        )

    sel_kind = (selection or {}).get("kind")
    raw_sel_id = (selection or {}).get("id")
    sel_id = int(raw_sel_id) if raw_sel_id is not None else None

    connectors = build_relationship_connectors(tables, rels, selection=selection)
    related_tables: set[int] = set()
    if sel_kind == "table" and sel_id is not None:
        related_tables.add(sel_id)
        for c in connectors:
            if c["from_table_id"] == sel_id or c["to_table_id"] == sel_id:
                related_tables.add(c["from_table_id"])
                related_tables.add(c["to_table_id"])
    elif sel_kind == "relationship" and sel_id is not None:
        for c in connectors:
            if c["id"] == sel_id:
                related_tables.add(c["from_table_id"])
                related_tables.add(c["to_table_id"])

    boxes = {int(t["id"]): table_box(t) for t in tables}
    canvas_w = max(MIN_CANVAS_W, max(b["x"] + b["w"] for b in boxes.values()) + 120)
    canvas_h = max(MIN_CANVAS_H, max(b["y"] + b["h"] for b in boxes.values()) + 120)

    rel_chips: list[Any] = [
        html.Button(
            c["label"],
            id={"type": "rms-rel-chip", "id": c["id"]},
            className=f"rms-rel-chip {c['state_cls']}",
            style={"left": max(4, c["mid_x"] - 18), "top": max(4, c["mid_y"] - 11)},
            title=f"{c['name']} ({c['from_column']} → {c['to_column']})",
            **{"data-rel-id": str(c["id"]), "aria-label": f"Quan hệ {c['name']} {c['label']}"},  # type: ignore[arg-type]
        )
        for c in connectors
    ]

    role_color_map = {"FACT": "blue", "DIMENSION": "teal", "BRIDGE": "grape", "UNCLASSIFIED": "gray"}
    role_short_map = {"FACT": "FACT", "DIMENSION": "DIM", "BRIDGE": "BRIDGE", "UNCLASSIFIED": "CHƯA GÁN"}

    cards: list[Any] = []
    for tbl in tables:
        tid = int(tbl["id"])
        box = boxes[tid]
        role = str(tbl.get("table_role") or "UNCLASSIFIED").upper()
        fields = list(tbl.get("fields") or [])
        vis_fields = _visible_canvas_fields(tbl)

        if sel_kind == "table" and sel_id == tid:
            card_cls = "rms-entity-card selected"
        elif sel_kind == "field" and (selection or {}).get("table_id") == tid:
            card_cls = "rms-entity-card selected"
        elif related_tables and tid in related_tables:
            card_cls = "rms-entity-card related"
        elif related_tables:
            card_cls = "rms-entity-card dimmed"
        else:
            card_cls = "rms-entity-card"

        col_nodes: list[Any] = []
        for fld in vis_fields:
            fid = int(fld["id"])
            col_name = str(fld["source_column"])
            is_fld_sel = sel_kind == "field" and sel_id == fid
            col_cls = "rms-entity-col selected" if is_fld_sel else "rms-entity-col"

            markers: list[Any] = []
            if fld.get("is_pk"):
                markers.append(dmc.Badge("PK", size="xs", variant="light", color="blue"))
            if fld.get("is_fk"):
                markers.append(dmc.Badge("FK", size="xs", variant="light", color="orange"))
            if not markers and fld.get("field_role") == "MEASURE_CANDIDATE":
                markers.append(dmc.Badge("Σ", size="xs", variant="light", color="purple"))
            if not fld.get("is_visible", True):
                markers.append(DashIconify(icon="lucide:eye-off", width=11))

            col_nodes.append(
                html.Div(
                    [
                        dmc.Group(
                            [
                                html.Span(
                                    className="rms-port-dot rms-port-left",
                                    title=f"Kéo nối từ {tbl.get('alias')}.{col_name}",
                                    **{"data-table-id": str(tid), "data-column": col_name},  # type: ignore[arg-type]
                                ),
                                *markers,
                                dmc.Text(
                                    col_name,
                                    size="xs",
                                    className="rh-code",
                                    style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                                ),
                            ],
                            gap=4,
                            style={"minWidth": 0, "flex": 1, "flexWrap": "nowrap"},
                        ),
                        dmc.Group(
                            [
                                dmc.Text(str(fld.get("data_type") or ""), size="xs", c="dimmed", className="rh-code"),
                                html.Span(
                                    className="rms-port-dot rms-port-right",
                                    title=f"Kéo nối từ {tbl.get('alias')}.{col_name}",
                                    **{"data-table-id": str(tid), "data-column": col_name},  # type: ignore[arg-type]
                                ),
                            ],
                            gap=4,
                            style={"flexShrink": 0, "flexWrap": "nowrap"},
                        ),
                    ],
                    className=col_cls,
                    **{"data-table-id": str(tid), "data-field-id": str(fid), "data-column": col_name},  # type: ignore[arg-type]
                )
            )
        if len(fields) > MAX_CARD_COLS:
            col_nodes.append(
                dmc.Text(
                    f"+{len(fields) - MAX_CARD_COLS} cột nữa (xem ở Explorer)",
                    size="xs",
                    c="dimmed",
                    px=8,
                    py=2,
                )
            )

        cards.append(
            html.Div(
                [
                    html.Div(
                        [
                            dmc.Text(
                                str(tbl.get("alias") or tbl.get("source_object")),
                                size="xs",
                                fw=700,
                                className="rh-code",
                                style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap", "flex": 1},
                            ),
                            dmc.Badge(
                                role_short_map.get(role, role),
                                size="xs",
                                variant="light",
                                color=role_color_map.get(role, "gray"),
                            ),
                        ],
                        className="rms-entity-header",
                        **{"data-drag-handle": str(tid)},  # type: ignore[arg-type]
                    ),
                    html.Div(col_nodes),
                ],
                id={"type": "rms-canvas-card", "id": tid},
                className=card_cls,
                style={"left": box["x"], "top": box["y"], "width": box["w"], "minHeight": box["h"], "zIndex": 2},
                **{"data-table-id": str(tid)},  # type: ignore[arg-type]
            )
        )

    svg_host = html.Div(
        id="rms-rel-svg-layer",
        className="rms-rel-svg",
        style={"width": canvas_w, "height": canvas_h},
        **{  # type: ignore[arg-type]
            "data-width": str(canvas_w),
            "data-height": str(canvas_h),
            "data-rels": json.dumps(connectors, ensure_ascii=False),
        },
    )

    return html.Div(
        [svg_host, *rel_chips, *cards],
        id="rm-canvas-inner",
        style={
            "position": "relative",
            "width": canvas_w,
            "height": canvas_h,
            "transform": f"scale({zoom})",
            "transformOrigin": "0 0",
        },
        **{
            "data-zoom": str(zoom),
            "data-w": str(canvas_w),
            "data-h": str(canvas_h),
            "data-focus-target": focus_token,
        },  # type: ignore[arg-type]
    )
