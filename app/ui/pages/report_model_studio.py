"""Trang Model Studio (/report-models/<model_id>) — Bước 2–5 task 107 (REPORT-STUDIO-01B)."""

from __future__ import annotations

import copy
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.schemas.errors import ErrorCode, ServiceError, ServiceResult
from app.services.perm import page_gate
from app.services.semantic_model import (
    add_table_to_draft,
    delete_measure,
    delete_rls_policy,
    diff_model_versions,
    discover_source_objects,
    get_model,
    get_model_version_detail,
    impact_analysis,
    open_or_create_draft,
    remove_table_from_draft,
    save_draft_state,
    update_field_props,
    update_table_props,
    upsert_measure,
    upsert_rls_policy,
)
from app.services.semantic_model_validate import (
    delete_relationship,
    profile_relationship_data,
    publish_model_version,
    upsert_relationship,
    validate_model,
    validate_relationship_structure,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.error_state import error_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.model_canvas import (
    auto_layout_star_schema,
    build_relationship_connectors,
    compute_canvas_fit,
    render_model_canvas_inner,
    table_box,
)
from app.ui.components.model_lifecycle import (
    render_publish_modal_body,
    render_stale_conflict_body,
    render_validation_drawer_body,
    resolve_validation_issue_selection,
)
from app.ui.components.model_properties import (
    agg_options_for_field,
    build_calculated_ast_from_form,
    format_ast_preview,
    render_empty_properties,
    render_field_properties,
    render_measure_studio,
    render_rel_validation_result,
    render_relationship_properties,
    render_table_properties,
)
from app.ui.components.notification import toast_error, toast_success
from app.ui.components.page_header import page_header
from app.ui.components.skeleton_grid import skeleton_panel
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/report-models/<model_id>",
        path="/report-models/1",
        title="Model Studio – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_model"

ROLE_GROUPS: list[tuple[str, str, str]] = [
    ("FACT", "Bảng sự kiện (Fact)", "blue"),
    ("DIMENSION", "Bảng chiều (Dimension)", "teal"),
    ("BRIDGE", "Bảng cầu nối (Bridge)", "grape"),
    ("UNCLASSIFIED", "Chưa phân loại", "gray"),
]


def _fmt_int(val: int | None) -> str:
    if val is None:
        return "—"
    return f"{int(val):,}".replace(",", ".")


def load_studio_bundle(ctx: Ctx, model_id: int) -> tuple[dict[str, Any] | None, str | None]:
    """Tải metadata model và bản Draft editable (hoặc bản chỉ đọc nếu đã Archive)."""
    model_res = get_model(ctx, model_id)
    if not model_res.ok or not model_res.data:
        return None, model_res.message or "Không tìm thấy mô hình."
    model = model_res.data
    if not model.get("is_archived"):
        draft_res = open_or_create_draft(ctx, model_id)
        if draft_res.ok and draft_res.data:
            return draft_res.data, None
        return None, draft_res.message or "Không mở được bản nháp mô hình."

    versions = list(model.get("versions") or [])
    if not versions:
        return None, "Mô hình chưa có phiên bản."
    ver_id = int(model.get("active_version_id") or versions[0]["id"])
    ver_res = get_model_version_detail(ctx, ver_id)
    if not ver_res.ok or not ver_res.data:
        return None, ver_res.message or "Không tải được phiên bản mô hình."
    return ver_res.data, None


def render_studio_header(
    bundle: dict[str, Any],
    *,
    dirty: bool = False,
) -> Any:
    """Dựng header 1 dòng cho Model Studio (tên model, trạng thái, nút hành động)."""
    model = bundle.get("model") or {}
    ver = bundle.get("version") or {}
    ver_no = int(ver.get("version_no") or 1)
    ver_status = str(ver.get("status") or "DRAFT").upper()
    is_editable = ver_status in ("DRAFT", "VALIDATED") and not model.get("is_archived")

    title_group = dmc.Group(
        [
            dmc.Title(str(model.get("name") or "Model Studio"), order=4, size=18, fw=600),
            dmc.Badge(str(model.get("code") or ""), variant="outline", size="sm", className="rh-code"),
            dmc.Badge(f"v{ver_no}", variant="light", size="sm"),
            status_chip(ver_status, size="sm"),
        ],
        gap="xs",
        align="center",
        style={"minWidth": 0, "flexWrap": "wrap"},
    )

    report_studio_btn = dmc.Tooltip(
        label="Khả dụng ở Task 109 (Report Studio)",
        withArrow=True,
        children=dmc.Button(
            "Report Studio",
            id="rms-open-report-studio-btn",
            size="xs",
            variant="default",
            disabled=True,
            leftSection=DashIconify(icon="lucide:bar-chart-3", width=14),
            **{"aria-label": "Mở Report Studio (Khả dụng ở Task 109)"},
        ),
    )

    more_menu = dmc.Menu(
        [
            dmc.MenuTarget(
                dmc.ActionIcon(
                    DashIconify(icon="lucide:more-vertical", width=15),
                    id="rms-more-btn",
                    variant="subtle",
                    color="gray",
                    size="sm",
                    **{"aria-label": "Thao tác khác"},
                )
            ),
            dmc.MenuDropdown(
                [
                    dmc.MenuItem(
                        "Về danh sách Model Center",
                        href="/report-models",
                        leftSection=DashIconify(icon="lucide:arrow-left", width=14),
                    ),
                ]
            ),
        ],
        position="bottom-end",
        withArrow=True,
    )

    actions: list[Any] = [
        report_studio_btn,
        button_subtle(
            "Kiểm tra model",
            id="rms-validate-btn",
            icon="lucide:shield-check",
            size="xs",
            **{"aria-label": "Kiểm tra model"},
        ),
        dmc.Button(
            "Lưu nháp*" if dirty else "Lưu nháp",
            id="rms-save-btn",
            size="xs",
            variant="default",
            disabled=not is_editable,
            leftSection=DashIconify(icon="lucide:save", width=14),
            **{"aria-label": "Lưu nháp thay đổi"},
        ),
        button_primary(
            "Phát hành",
            id="rms-publish-btn",
            icon="lucide:upload-cloud",
            size="xs",
            disabled=not is_editable,
            **{"aria-label": "Phát hành phiên bản mô hình"},  # type: ignore[arg-type]
        ),
    ]
    if ver_status == "ACTIVE" and not model.get("is_archived"):
        actions.append(
            button_primary(
                "Tạo bản nháp mới",
                id="rms-new-draft-btn",
                icon="lucide:git-branch-plus",
                size="xs",
                **{"aria-label": "Tạo bản nháp mới từ phiên bản ACTIVE"},  # type: ignore[arg-type]
            )
        )
    actions.append(more_menu)

    ds = model.get("data_source") or {}
    ds_sub = f"Data Source: {ds.get('name') or '—'} ({ds.get('env') or 'DEV'})"
    return page_header(
        title=title_group,
        subtitle=ds_sub,
        actions=actions,
        mb=0,
    )


def render_explorer_panel(
    bundle: dict[str, Any],
    *,
    selection: dict[str, Any] | None = None,
    query: str = "",
    expanded_tables: list[int] | None = None,
) -> Any:
    """Dựng cây Model Explorer (Fact/Dim/Bridge/Unclassified + Cột + Quan hệ)."""
    tables = list(bundle.get("tables") or [])
    rels = list(bundle.get("relationships") or [])
    measures = list(bundle.get("measures") or [])
    q = (query or "").strip().lower()
    sel_kind = (selection or {}).get("kind")
    sel_id = (selection or {}).get("id")
    expanded_set = {int(tid) for tid in (expanded_tables or [])}
    if sel_kind == "table" and sel_id:
        expanded_set.add(int(sel_id))
    elif sel_kind == "field" and (selection or {}).get("table_id"):
        expanded_set.add(int((selection or {})["table_id"]))

    if not tables:
        return dmc.Stack(
            [
                empty_state(
                    title="Mô hình chưa có bảng nào",
                    description="Bấm Thêm bảng để nạp bảng/view từ Data Source.",
                    action=button_primary(
                        "Thêm bảng",
                        id={"type": "rms-empty-add-btn", "src": "explorer"},
                        icon="lucide:plus",
                        size="xs",
                    ),
                )
            ],
            p="xs",
        )

    table_by_id = {int(t["id"]): t for t in tables}
    sections: list[Any] = []
    matched_any = False

    for role_code, role_label, role_color in ROLE_GROUPS:
        role_tables = [t for t in tables if str(t.get("table_role") or "UNCLASSIFIED").upper() == role_code]
        group_nodes: list[Any] = []
        for tbl in role_tables:
            tid = int(tbl["id"])
            fields = list(tbl.get("fields") or [])
            tbl_hay = f"{tbl.get('alias', '')} {tbl.get('source_object', '')} {tbl.get('display_name', '')}".lower()
            tbl_match = not q or (q in tbl_hay)
            matched_fields = [
                f
                for f in fields
                if q
                and q
                in f"{f.get('source_column', '')} {f.get('field_code', '')} {f.get('display_name', '')}".lower()
            ]
            if q and not tbl_match and not matched_fields:
                continue
            matched_any = True
            is_expanded = bool(matched_fields) or (tid in expanded_set)
            is_selected = sel_kind == "table" and sel_id == tid
            row_cls = "rms-table-row active" if is_selected else "rms-table-row"
            chevron = "lucide:chevron-down" if is_expanded else "lucide:chevron-right"

            group_nodes.append(
                html.Button(
                    dmc.Group(
                        [
                            dmc.Group(
                                [
                                    DashIconify(icon=chevron, width=13),
                                    dmc.Text(str(tbl.get("alias") or tbl.get("source_object")), size="xs", fw=600, className="rh-code"),
                                ],
                                gap=4,
                                style={"minWidth": 0},
                            ),
                            dmc.Badge(f"{len(fields)}", size="xs", variant="light", color=role_color),
                        ],
                        justify="space-between",
                        style={"width": "100%", "minWidth": 0},
                    ),
                    id={"type": "rms-exp-table-btn", "id": tid},
                    className=row_cls,
                    **{"aria-label": f"Bảng {tbl.get('source_object')}"},  # type: ignore[arg-type]
                )
            )
            if is_expanded:
                col_rows: list[Any] = []
                for fld in fields:
                    fid = int(fld["id"])
                    is_f_match = bool(q) and any(int(mf["id"]) == fid for mf in matched_fields)
                    f_sel = sel_kind == "field" and sel_id == fid
                    f_cls = "rms-col-item rms-match" if is_f_match else ("rms-col-item active" if f_sel else "rms-col-item")
                    icon_name = (
                        "lucide:key-round"
                        if fld.get("is_pk")
                        else ("lucide:link-2" if fld.get("is_fk") else ("lucide:eye-off" if not fld.get("is_visible", True) else "lucide:columns-3"))
                    )
                    col_rows.append(
                        html.Button(
                            dmc.Group(
                                [
                                    DashIconify(icon=icon_name, width=12),
                                    dmc.Text(
                                        str(fld.get("source_column") or fld.get("field_code")),
                                        size="xs",
                                        className="rh-code",
                                        style={"flex": 1, "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                                    ),
                                    dmc.Text(str(fld.get("data_type") or ""), size="xs", c="dimmed"),
                                ],
                                gap=6,
                                style={"width": "100%", "minWidth": 0, "flexWrap": "nowrap"},
                            ),
                            id={"type": "rms-exp-field-btn", "id": fid, "table_id": tid},
                            className=f_cls,
                            **{"aria-label": f"Cột {fld.get('source_column')}"},  # type: ignore[arg-type]
                        )
                    )
                group_nodes.append(dmc.Stack(col_rows, gap=1))

        if group_nodes:
            sections.append(
                dmc.Stack(
                    [
                        dmc.Text(f"{role_label} ({len(role_tables)})", size="xs", fw=600, c="dimmed", px=6, pt=6),
                        dmc.Stack(group_nodes, gap=2),
                    ],
                    gap=2,
                )
            )

    if q and not matched_any:
        return dmc.Stack(
            [
                empty_state(
                    title="Không khớp bảng hoặc cột",
                    description="Thử từ khóa khác hoặc xóa bộ lọc trong Explorer.",
                    action=button_subtle("Xóa tìm kiếm", id={"type": "rms-exp-clear-btn", "k": 1}, icon="lucide:x", size="xs"),
                )
            ],
            p="xs",
        )

    rel_nodes: list[Any] = []
    for r in rels:
        rid = int(r["id"])
        src_t = table_by_id.get(int(r["from_table_id"]), {}).get("alias", f"T#{r['from_table_id']}")
        dst_t = table_by_id.get(int(r["to_table_id"]), {}).get("alias", f"T#{r['to_table_id']}")
        label = f"{src_t} → {dst_t}"
        if q and q not in f"{label} {r.get('name', '')}".lower():
            continue
        is_rel_sel = sel_kind == "relationship" and sel_id == rid
        rel_nodes.append(
            html.Button(
                dmc.Group(
                    [
                        DashIconify(icon="lucide:git-commit-horizontal", width=13),
                        dmc.Text(label, size="xs", className="rh-code", style={"flex": 1, "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"}),
                        dmc.Badge("*:1" if r.get("cardinality") == "MANY_TO_ONE" else "1:1", size="xs", variant="light"),
                    ],
                    gap=6,
                    style={"width": "100%", "flexWrap": "nowrap"},
                ),
                id={"type": "rms-exp-rel-btn", "id": rid},
                className="rms-table-row active" if is_rel_sel else "rms-table-row",
                **{"aria-label": f"Quan hệ {label}"},  # type: ignore[arg-type]
            )
        )
    sections.append(
        dmc.Stack(
            [
                dmc.Text(f"Quan hệ ({len(rels)})", size="xs", fw=600, c="dimmed", px=6, pt=8),
                dmc.Stack(rel_nodes, gap=2) if rel_nodes else dmc.Text("Chưa có quan hệ nào.", size="xs", c="dimmed", px=6),
            ],
            gap=2,
        )
    )
    sections.append(
        dmc.Stack(
            [
                dmc.Text(f"Measures ({len(measures)})", size="xs", fw=600, c="dimmed", px=6, pt=8),
                dmc.Stack(
                    [
                        html.Button(
                            dmc.Group(
                                [
                                    DashIconify(icon="lucide:sigma", width=13),
                                    dmc.Text(str(m.get("name") or m.get("code")), size="xs", style={"flex": 1}),
                                    dmc.Badge(str(m.get("measure_type") or "SIMPLE"), size="xs", variant="light", color="purple"),
                                ],
                                gap=6,
                                style={"width": "100%"},
                            ),
                            id={"type": "rms-exp-meas-btn", "id": int(m["id"])},
                            className="rms-table-row active" if (sel_kind == "measure" and sel_id == int(m["id"])) else "rms-table-row",
                            **{"aria-label": f"Measure {m.get('code')}"},  # type: ignore[arg-type]
                        )
                        for m in measures
                    ],
                    gap=2,
                )
                if measures
                else dmc.Text("Chưa có measure.", size="xs", c="dimmed", px=6),
            ],
            gap=2,
        )
    )
    return dmc.Stack(sections, gap="xs", p="xs")


def render_source_picker_list(
    objects: list[dict[str, Any]],
    *,
    existing_objects: set[str],
    query: str = "",
    object_type: str = "ALL",
) -> Any:
    """Dựng danh sách đối tượng nguồn trong Drawer + Thêm bảng."""
    q = (query or "").strip().lower()
    otype_flt = (object_type or "ALL").upper()
    filtered = [
        o
        for o in objects
        if (otype_flt == "ALL" or str(o.get("type") or "").upper() == otype_flt)
        and (not q or q in str(o.get("name") or "").lower())
    ]
    if not filtered:
        return empty_state(
            title="Không thấy bảng hoặc view phù hợp",
            description="Kiểm tra từ khóa tìm kiếm, schema nguồn hoặc nhấn Tải lại.",
        )

    rows: list[Any] = []
    for obj in filtered:
        name = str(obj["name"])
        t_type = str(obj.get("type") or "TABLE").upper()
        schema = str(obj.get("schema") or "")
        already = name.upper() in existing_objects
        est_label = "View" if t_type == "VIEW" else f"{_fmt_int(obj.get('row_estimate'))} dòng"

        right_ctrl: Any = (
            dmc.Badge("Đã thêm", color="ok", variant="light", size="sm")
            if already
            else button_primary(
                "Thêm",
                id={"type": "rms-picker-add-btn", "object": name, "obj_type": t_type, "schema": schema},
                icon="lucide:plus",
                size="xs",
                **{"aria-label": f"Thêm bảng {name} vào mô hình"},  # type: ignore[arg-type]
            )
        )
        rows.append(
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Stack(
                            [
                                dmc.Group(
                                    [
                                        DashIconify(
                                            icon="lucide:table-2" if t_type == "TABLE" else "lucide:eye",
                                            width=14,
                                        ),
                                        dmc.Text(name, size="xs", fw=600, className="rh-code"),
                                        dmc.Badge(t_type, size="xs", variant="outline"),
                                    ],
                                    gap=6,
                                ),
                                dmc.Group(
                                    [
                                        dmc.Text(f"Schema: {schema or '—'}", size="xs", c="dimmed"),
                                        dmc.Text(f"PK: {int(obj.get('pk_count') or 0)}", size="xs", c="dimmed"),
                                        dmc.Text(f"FK: {int(obj.get('fk_count') or 0)}", size="xs", c="dimmed"),
                                        dmc.Text(est_label, size="xs", c="dimmed"),
                                    ],
                                    gap="sm",
                                ),
                            ],
                            gap=2,
                            style={"minWidth": 0, "flex": 1},
                        ),
                        right_ctrl,
                    ],
                    justify="space-between",
                    align="center",
                ),
                withBorder=True,
                p="xs",
                radius="sm",
            )
        )
    return dmc.Stack(rows, gap="xs")


def render_canvas_panel(
    bundle: dict[str, Any],
    *,
    selection: dict[str, Any] | None = None,
    zoom: float = 1.0,
    focus_token: str = "",
) -> Any:
    """Dựng vùng Canvas Model Studio (Toolbar + Container HTML/SVG)."""
    toolbar = html.Div(
        [
            dmc.Group(
                [
                    button_subtle(
                        "+ Tạo quan hệ",
                        id="rms-new-rel-btn",
                        icon="lucide:git-branch-plus",
                        size="xs",
                        **{"aria-label": "Tạo quan hệ mới"},
                    ),
                    button_subtle(
                        "Auto Layout",
                        id="rms-auto-layout-btn",
                        icon="lucide:sparkles",
                        size="xs",
                        **{"aria-label": "Tự động sắp xếp Star Schema"},
                    ),
                    button_subtle(
                        "Undo vị trí",
                        id="rms-undo-layout-btn",
                        icon="lucide:undo-2",
                        size="xs",
                        **{"aria-label": "Hoàn tác vị trí bảng"},
                    ),
                ],
                gap="xs",
            ),
            dmc.Group(
                [
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:zoom-out", width=14),
                        id="rms-zoom-out-btn",
                        variant="subtle",
                        color="gray",
                        size="sm",
                        **{"aria-label": "Thu nhỏ canvas"},
                    ),
                    dmc.Text(f"{int(round(zoom * 100))}%", id="rms-zoom-label", size="xs", fw=600, w=42, ta="center"),
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:zoom-in", width=14),
                        id="rms-zoom-in-btn",
                        variant="subtle",
                        color="gray",
                        size="sm",
                        **{"aria-label": "Phóng to canvas"},
                    ),
                    button_subtle(
                        "Fit",
                        id="rms-zoom-fit-btn",
                        icon="lucide:maximize-2",
                        size="xs",
                        **{"aria-label": "Vừa khung nhìn"},
                    ),
                ],
                gap=4,
                align="center",
            ),
        ],
        className="rms-canvas-toolbar",
    )

    canvas_inner = render_model_canvas_inner(bundle, selection=selection, zoom=zoom, focus_token=focus_token)

    return html.Div(
        [
            toolbar,
            html.Div(canvas_inner, id="rm-canvas-container"),
        ],
        className="rms-canvas-col",
    )


def render_properties_panel(
    bundle: dict[str, Any],
    *,
    selection: dict[str, Any] | None = None,
) -> Any:
    """Dựng panel Properties bên phải theo ngữ cảnh lựa chọn (Bước 4–5)."""
    model = bundle.get("model") or {}
    ver = bundle.get("version") or {}
    ver_status = str(ver.get("status") or "DRAFT").upper()
    is_editable = ver_status in ("DRAFT", "VALIDATED") and not model.get("is_archived")

    panel: Any = None
    if not selection:
        panel = render_empty_properties()
    else:
        kind = str(selection.get("kind") or "")
        raw_id = selection.get("id")
        target_id = int(raw_id) if raw_id is not None else None
        if kind == "table" and target_id is not None:
            tbl = next((t for t in (bundle.get("tables") or []) if int(t["id"]) == target_id), None)
            if tbl:
                panel = render_table_properties(bundle, tbl)
        elif kind == "field" and target_id is not None:
            for t in bundle.get("tables") or []:
                fld = next((f for f in (t.get("fields") or []) if int(f["id"]) == target_id), None)
                if fld:
                    panel = render_field_properties(bundle, t, fld)
                    break
        elif kind == "relationship" and target_id is not None:
            rel = next((r for r in (bundle.get("relationships") or []) if int(r["id"]) == target_id), None)
            if rel:
                panel = render_relationship_properties(bundle, rel)
        elif kind == "measure":
            tbl_id = int(selection["table_id"]) if selection.get("table_id") is not None else None
            panel = render_measure_studio(bundle, measure_id=target_id, table_id=tbl_id)
    if panel is None:
        panel = render_empty_properties()
    if not is_editable:
        return dmc.Stack(
            [
                alert_box(
                    title="Phiên bản chỉ đọc",
                    message="Phiên bản này đã Phát hành (ACTIVE) hoặc Lưu trữ. Bấm 'Tạo bản nháp mới' để chỉnh sửa.",
                    tone="info",
                ),
                panel,
            ],
            gap="xs",
            p="xs",
        )
    return panel


def render_status_bar(bundle: dict[str, Any], *, dirty: bool = False) -> Any:
    """Thanh trạng thái gọn ở đáy màn Model Studio."""
    tables = list(bundle.get("tables") or [])
    rels = list(bundle.get("relationships") or [])
    measures = list(bundle.get("measures") or [])
    rls_list = list(bundle.get("rls_policies") or [])
    ver = bundle.get("version") or {}
    val = ver.get("validation") or {}
    summary = val.get("summary") or {}
    err_cnt = int(summary.get("error_count") or 0)
    warn_cnt = int(summary.get("warning_count") or 0)

    fact_c = sum(1 for t in tables if t.get("table_role") == "FACT")
    dim_c = sum(1 for t in tables if t.get("table_role") == "DIMENSION")
    bridge_c = sum(1 for t in tables if t.get("table_role") == "BRIDGE")
    active_rel = sum(1 for r in rels if r.get("is_active", True))

    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Text(f"Bảng: {len(tables)} ({fact_c}F / {dim_c}D / {bridge_c}B)", size="xs"),
                    dmc.Text(f"Quan hệ: {active_rel}/{len(rels)}", size="xs"),
                    dmc.Text(f"Measures: {len(measures)}", size="xs"),
                    dmc.Text(f"RLS: {len(rls_list)}", size="xs"),
                ],
                gap="md",
            ),
            dmc.Group(
                [
                    dmc.Badge("Chưa lưu nháp", color="warn", variant="light", size="xs") if dirty else dmc.Badge("Đã đồng bộ", color="ok", variant="light", size="xs"),
                    dmc.Badge(f"{err_cnt} lỗi · {warn_cnt} cảnh báo", color="crit" if err_cnt else ("warn" if warn_cnt else "gray"), variant="light", size="xs"),
                ],
                gap="xs",
            ),
        ],
        id="rms-status-bar",
        className="rms-status-bar",
    )


def layout(model_id: str | None = None) -> Any:
    """Layout chính của Model Studio (/report-models/<model_id>)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate is not None:
        return gate
    assert ctx is not None

    try:
        mid = int(str(model_id or "0"))
    except ValueError:
        mid = 0

    if mid <= 0:
        return dmc.Box(
            error_state(
                title="Mã mô hình không hợp lệ",
                message="Vui lòng mở mô hình từ danh sách Model Center.",
                action=dcc.Link(button_primary("Về Model Center", icon="lucide:arrow-left", size="xs"), href="/report-models"),
            ),
            p="md",
        )

    try:
        bundle, err = load_studio_bundle(ctx, mid)
    except ServiceError as exc:
        bundle, err = None, exc.message

    if err or bundle is None:
        return dmc.Box(
            error_state(
                title="Không mở được Model Studio",
                message=err or "Không tìm thấy mô hình.",
                retry_id="rms-reload-btn",
                action=dcc.Link(button_subtle("Về Model Center", icon="lucide:arrow-left", size="xs"), href="/report-models"),
            ),
            p="md",
        )

    add_table_drawer = drawer_right(
        id="rms-add-table-drawer",
        title="Thêm bảng / view vào mô hình",
        opened=False,
        size=540,
        children=dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.TextInput(
                            id="rms-picker-search",
                            placeholder="Tìm tên bảng hoặc view...",
                            leftSection=DashIconify(icon="lucide:search", width=14),
                            size="xs",
                            debounce=250,
                            style={"flex": 1},
                            **{"aria-label": "Tìm đối tượng nguồn"},
                        ),
                        dmc.SegmentedControl(
                            id="rms-picker-type",
                            data=[
                                {"label": "Tất cả", "value": "ALL"},
                                {"label": "Table", "value": "TABLE"},
                                {"label": "View", "value": "VIEW"},
                            ],
                            value="ALL",
                            size="xs",
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:refresh-cw", width=14),
                            id="rms-picker-refresh-btn",
                            variant="subtle",
                            color="gray",
                            size="sm",
                            **{"aria-label": "Làm mới danh sách bảng nguồn"},
                        ),
                    ],
                    gap="xs",
                    align="center",
                ),
                html.Div(skeleton_panel(lines=4), id="rms-picker-list"),
                dmc.Group(
                    [button_subtle("Đóng", id="rms-picker-close-btn", size="xs")],
                    justify="flex-end",
                ),
            ],
            gap="sm",
        ),
    )

    rel_modal = dmc.Modal(
        id="rms-rel-modal",
        title=dmc.Text("Tạo quan hệ giữa 2 bảng", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rms-rel-modal-alert"),
                dmc.TextInput(id="rms-rel-m-name", label="Tên quan hệ", placeholder="VD: REL_SALES_CUSTOMER", withAsterisk=True, size="xs"),
                dmc.Group(
                    [
                        dmc.Select(id="rms-rel-m-from-tbl", label="Bảng nguồn (From / N)", data=[], allowDeselect=False, size="xs", style={"flex": 1}),
                        dmc.Select(id="rms-rel-m-from-col", label="Cột nguồn", data=[], allowDeselect=False, size="xs", style={"flex": 1}, searchable=True),
                    ],
                    gap="xs",
                ),
                dmc.Group(
                    [
                        dmc.Select(id="rms-rel-m-to-tbl", label="Bảng đích (To / 1)", data=[], allowDeselect=False, size="xs", style={"flex": 1}),
                        dmc.Select(id="rms-rel-m-to-col", label="Cột đích", data=[], allowDeselect=False, size="xs", style={"flex": 1}, searchable=True),
                    ],
                    gap="xs",
                ),
                dmc.Group(
                    [
                        dmc.Select(
                            id="rms-rel-m-card",
                            label="Bội số (Cardinality)",
                            data=[
                                {"label": "Nhiều (*) → Một (1)", "value": "MANY_TO_ONE"},
                                {"label": "Một (1) → Một (1)", "value": "ONE_TO_ONE"},
                            ],
                            value="MANY_TO_ONE",
                            allowDeselect=False,
                            size="xs",
                            style={"flex": 1},
                        ),
                        dmc.Select(
                            id="rms-rel-m-join",
                            label="Kiểu Join",
                            data=[
                                {"label": "LEFT OUTER JOIN", "value": "LEFT_OUTER"},
                                {"label": "INNER JOIN", "value": "INNER"},
                            ],
                            value="LEFT_OUTER",
                            allowDeselect=False,
                            size="xs",
                            style={"flex": 1},
                        ),
                    ],
                    gap="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rms-rel-m-cancel", size="xs"),
                        button_primary("Tạo quan hệ", id="rms-rel-m-submit", icon="lucide:git-branch-plus", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    del_modal = modal_confirm(
        id="rms-del-modal",
        title="Xác nhận xóa khỏi bản nháp",
        description=dmc.Stack(
            [
                dmc.Text(id="rms-del-modal-desc", size="sm"),
                dmc.Text(
                    "Giữ lại: Không xóa bảng/dữ liệu trên DB nguồn; các phiên bản Active trước đó vẫn giữ nguyên.",
                    size="xs",
                    c="dimmed",
                ),
            ],
            gap="xs",
        ),
        confirm_label="Xóa khỏi nháp",
        danger=True,
        opened=False,
    )

    return dmc.Box(
        [
            dcc.Store(id="rms-bundle-store", data=bundle),
            dcc.Store(id="rms-selection-store", data=None),
            dcc.Store(id="rms-source-objects-store", data=[]),
            dcc.Store(id="rms-zoom-store", data=1.0),
            dcc.Store(id="rms-dirty-store", data=False),
            dcc.Store(id="rms-layout-history-store", data=[]),
            dcc.Store(id="rms-drag-pos-store", data=None),
            dcc.Store(id="rms-connect-draft-store", data=None),
            dcc.Store(id="rms-canvas-click-store", data=None),
            dcc.Store(id="rms-canvas-dblclick-store", data=None),
            dcc.Store(id="rms-del-target-store", data=None),
            dcc.Store(id="rms-val-issues-store", data=[]),
            dcc.Store(id="rms-focus-seq-store", data=0),
            dmc.NotificationContainer(id="rms-studio-notif", position="top-right", **{"aria-live": "polite"}),
            html.Div(render_studio_header(bundle, dirty=False), id="rms-header-wrap"),
            html.Div(
                alert_box(
                    title="Chế độ xem trên màn hình nhỏ",
                    message="Thiết kế sơ đồ quan hệ và thuộc tính mô hình yêu cầu màn hình máy tính (≥ 1280px).",
                    tone="info",
                ),
                className="rms-mobile-notice",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dmc.Group(
                                [
                                    dmc.Text("Model Explorer", fw=700, size="xs"),
                                    button_primary(
                                        "Thêm bảng",
                                        id="rms-add-table-btn",
                                        icon="lucide:plus",
                                        size="xs",
                                        **{"aria-label": "Thêm bảng vào mô hình"},  # type: ignore[arg-type]
                                    ),
                                ],
                                justify="space-between",
                                p="xs",
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            dmc.Box(
                                dmc.TextInput(
                                    id="rms-explorer-search",
                                    placeholder="Tìm bảng hoặc cột...",
                                    value="",
                                    leftSection=DashIconify(icon="lucide:search", width=13),
                                    size="xs",
                                    debounce=200,
                                    **{"aria-label": "Tìm bảng hoặc cột trong Explorer"},
                                ),
                                px="xs",
                                py=6,
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            html.Div(
                                render_explorer_panel(bundle, selection=None, query=""),
                                id="rms-explorer-body",
                                className="rms-explorer-scroll",
                            ),
                        ],
                        id="rms-explorer",
                        className="rms-explorer",
                    ),
                    html.Div(
                        render_canvas_panel(bundle, selection=None, zoom=1.0),
                        id="rms-canvas-wrap",
                        className="rms-canvas-col",
                    ),
                    html.Div(
                        [
                            dmc.Group(
                                [dmc.Text("Properties", fw=700, size="xs")],
                                p="xs",
                                style={"borderBottom": "1px solid var(--line)"},
                            ),
                            html.Div(
                                render_properties_panel(bundle, selection=None),
                                id="rms-properties-body",
                                className="rms-properties-scroll",
                            ),
                        ],
                        id="rms-properties",
                        className="rms-properties",
                    ),
                ],
                className="rms-workspace",
            ),
            html.Div(render_status_bar(bundle, dirty=False), id="rms-status-wrap"),
            add_table_drawer,
            rel_modal,
            del_modal,
            drawer_right(
                id="rms-validate-drawer",
                title="Kiểm tra mô hình",
                opened=False,
                size=520,
                children=html.Div(id="rms-validate-drawer-body"),
            ),
            dmc.Modal(
                id="rms-stale-modal",
                title=dmc.Text("Xung đột phiên bản bản nháp (STALE_DATA)", fw=700, size="md"),
                opened=False,
                radius="md",
                children=dmc.Stack(
                    [
                        html.Div(id="rms-stale-modal-body"),
                        dmc.Group(
                            [
                                button_subtle("Giữ phiên bản đang sửa", id="rms-stale-keep-btn", size="xs"),
                                button_primary("Tải lại bản mới", id="rms-stale-reload-btn", icon="lucide:refresh-cw", size="xs"),
                            ],
                            justify="flex-end",
                            gap="xs",
                        ),
                    ],
                    gap="md",
                ),
            ),
            dmc.Modal(
                id="rms-publish-modal",
                title=dmc.Text("Phát hành phiên bản mô hình", fw=700, size="md"),
                opened=False,
                size="lg",
                radius="md",
                children=html.Div(render_publish_modal_body(bundle, None), id="rms-publish-modal-body"),
            ),
        ],
        id="rms-page",
        className="rms-page",
    )


@callback(
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-explorer-search", "value"),
    Input("rms-explorer-search", "value"),
    Input({"type": "rms-exp-clear-btn", "k": ALL}, "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_explorer_search(
    query: str | None,
    _clear_clicks: list[Any],
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any]:
    if not bundle:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if isinstance(trig, dict) and trig.get("type") == "rms-exp-clear-btn":
        if not dash.callback_context.triggered or not dash.callback_context.triggered[0].get("value"):
            raise PreventUpdate
        return render_explorer_panel(bundle, selection=selection, query=""), ""
    return render_explorer_panel(bundle, selection=selection, query=query or ""), dash.no_update


@callback(
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Input({"type": "rms-exp-table-btn", "id": ALL}, "n_clicks"),
    Input({"type": "rms-exp-field-btn", "id": ALL, "table_id": ALL}, "n_clicks"),
    Input({"type": "rms-exp-rel-btn", "id": ALL}, "n_clicks"),
    Input({"type": "rms-exp-meas-btn", "id": ALL}, "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_explorer_select(
    _tbl_clicks: list[Any],
    _fld_clicks: list[Any],
    _rel_clicks: list[Any],
    _meas_clicks: list[Any],
    bundle: dict[str, Any] | None,
    query: str | None,
    zoom: float | None,
) -> tuple[Any, Any, Any, Any]:
    if not bundle or not dash.callback_context.triggered:
        raise PreventUpdate
    trig_val = dash.callback_context.triggered[0].get("value")
    if not trig_val:
        raise PreventUpdate
    raw_id = dash.callback_context.triggered_id
    if not isinstance(raw_id, dict):
        raise PreventUpdate
    t = str(raw_id.get("type") or "")
    sel: dict[str, Any] | None = None
    if t == "rms-exp-table-btn":
        sel = {"kind": "table", "id": int(raw_id["id"])}
    elif t == "rms-exp-field-btn":
        sel = {"kind": "field", "id": int(raw_id["id"]), "table_id": int(raw_id["table_id"])}
    elif t == "rms-exp-rel-btn":
        sel = {"kind": "relationship", "id": int(raw_id["id"])}
    elif t == "rms-exp-meas-btn":
        sel = {"kind": "measure", "id": int(raw_id["id"])}
    if sel is None:
        raise PreventUpdate
    z = float(zoom or 1.0)
    return (
        sel,
        render_explorer_panel(bundle, selection=sel, query=query or ""),
        render_canvas_panel(bundle, selection=sel, zoom=z),
        render_properties_panel(bundle, selection=sel),
    )


@callback(
    Output("rms-add-table-drawer", "opened"),
    Output("rms-source-objects-store", "data"),
    Output("rms-picker-list", "children"),
    Input("rms-add-table-btn", "n_clicks"),
    Input({"type": "rms-empty-add-btn", "src": ALL}, "n_clicks"),
    Input("rms-picker-refresh-btn", "n_clicks"),
    Input("rms-picker-close-btn", "n_clicks"),
    Input("rms-picker-search", "value"),
    Input("rms-picker-type", "value"),
    State("rms-bundle-store", "data"),
    State("rms-source-objects-store", "data"),
    prevent_initial_call=True,
)
def handle_add_table_drawer(
    open_c: int | None,
    _empty_clicks: list[Any],
    refresh_c: int | None,
    close_c: int | None,
    q: str | None,
    otype: str | None,
    bundle: dict[str, Any] | None,
    cached_objs: list[dict[str, Any]] | None,
) -> tuple[bool, Any, Any]:
    if not bundle:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if trig == "rms-picker-close-btn":
        if not close_c:
            raise PreventUpdate
        return False, dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    is_empty_open = isinstance(trig, dict) and trig.get("type") == "rms-empty-add-btn"
    if trig == "rms-add-table-btn" or is_empty_open:
        triggered_val = dash.callback_context.triggered[0].get("value") if dash.callback_context.triggered else None
        if not triggered_val:
            raise PreventUpdate
    objects = list(cached_objs or [])
    if trig in ("rms-add-table-btn", "rms-picker-refresh-btn") or is_empty_open or not objects:
        ds_id = int((bundle.get("model") or {}).get("data_source_id") or 0)
        res = discover_source_objects(ctx, ds_id, enrich=True)
        if not res.ok or not res.data:
            return True, dash.no_update, error_state(title="Không tải được bảng nguồn", message=res.message)
        objects = list(res.data.get("objects") or [])

    existing = {str(t["source_object"]).upper() for t in (bundle.get("tables") or [])}
    return (
        True,
        objects,
        render_source_picker_list(objects, existing_objects=existing, query=q or "", object_type=otype or "ALL"),
    )


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-picker-list", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input({"type": "rms-picker-add-btn", "object": ALL, "obj_type": ALL, "schema": ALL}, "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-source-objects-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-picker-search", "value"),
    State("rms-picker-type", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_picker_add_table(
    _clicks: list[Any],
    bundle: dict[str, Any] | None,
    objects: list[dict[str, Any]] | None,
    selection: dict[str, Any] | None,
    exp_query: str | None,
    pick_q: str | None,
    pick_type: str | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    if not bundle or not dash.callback_context.triggered:
        raise PreventUpdate
    if not dash.callback_context.triggered[0].get("value"):
        raise PreventUpdate
    trig_id = dash.callback_context.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    cur_det = get_model_version_detail(ctx, ver_id)
    live_tables = list((cur_det.data or {}).get("tables") or []) if cur_det.ok and cur_det.data else list(bundle.get("tables") or [])
    n_existing = len(live_tables)
    res = add_table_to_draft(
        ctx,
        ver_id,
        {
            "source_owner": trig_id.get("schema") or None,
            "source_object": trig_id["object"],
            "object_type": trig_id.get("obj_type") or "TABLE",
            "pos_x": 40 + (n_existing % 3) * 320,
            "pos_y": 40 + (n_existing // 3) * 260,
        },
    )
    no = dash.no_update
    if not res.ok:
        return no, no, no, no, no, [toast_error(res.message or "Không thêm được bảng.")]

    refreshed = get_model_version_detail(ctx, ver_id)
    new_bundle = refreshed.data if refreshed.ok and refreshed.data else bundle
    existing = {str(t["source_object"]).upper() for t in (new_bundle.get("tables") or [])}
    return (
        new_bundle,
        render_explorer_panel(new_bundle, selection=selection, query=exp_query or ""),
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_status_bar(new_bundle, dirty=False),
        render_source_picker_list(list(objects or []), existing_objects=existing, query=pick_q or "", object_type=pick_type or "ALL"),
        [toast_success(f"Đã thêm bảng {trig_id['object']} vào mô hình.")],
    )


def _table_select_options(bundle: dict[str, Any] | None) -> list[dict[str, str]]:
    return [
        {"label": f"{t.get('alias') or t.get('source_object')} ({t.get('table_role')})", "value": str(t["id"])}
        for t in (bundle or {}).get("tables") or []
    ]


def _col_select_options(bundle: dict[str, Any] | None, table_id: str | int | None) -> list[dict[str, str]]:
    if not bundle or not table_id:
        return []
    tid = int(str(table_id))
    tbl = next((t for t in bundle.get("tables") or [] if int(t["id"]) == tid), None)
    if not tbl:
        return []
    return [
        {"label": f"{f['source_column']} ({f.get('data_type')})", "value": str(f["source_column"])}
        for f in tbl.get("fields") or []
    ]


@callback(
    Output("rms-zoom-store", "data"),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Input("rms-zoom-in-btn", "n_clicks"),
    Input("rms-zoom-out-btn", "n_clicks"),
    Input("rms-zoom-fit-btn", "n_clicks"),
    Input("rms-canvas-dblclick-store", "data"),
    State("rms-zoom-store", "data"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_canvas_zoom_or_dblclick(
    zoom_in: int | None,
    zoom_out: int | None,
    zoom_fit: int | None,
    dblclick: dict[str, Any] | None,
    cur_zoom: float | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[float, Any]:
    if not bundle:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    z = float(cur_zoom or 1.0)
    new_sel = selection
    if trig == "rms-zoom-in-btn":
        if not zoom_in:
            raise PreventUpdate
        new_z = round(min(1.6, z + 0.15), 2)
    elif trig == "rms-zoom-out-btn":
        if not zoom_out:
            raise PreventUpdate
        new_z = round(max(0.4, z - 0.15), 2)
    elif trig == "rms-zoom-fit-btn":
        if not zoom_fit:
            raise PreventUpdate
        new_z = compute_canvas_fit(list(bundle.get("tables") or []))
    elif trig == "rms-canvas-dblclick-store":
        if not isinstance(dblclick, dict) or not dblclick.get("id"):
            raise PreventUpdate
        new_z = 1.15
        new_sel = {"kind": "table", "id": int(dblclick["id"])}
    else:
        raise PreventUpdate
    return new_z, render_canvas_panel(bundle, selection=new_sel, zoom=new_z)


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-layout-history-store", "data"),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-auto-layout-btn", "n_clicks"),
    Input("rms-undo-layout-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-layout-history-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_auto_layout_or_undo(
    auto_c: int | None,
    undo_c: int | None,
    bundle: dict[str, Any] | None,
    history: list[dict[str, list[int]]] | None,
    selection: dict[str, Any] | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    if not bundle:
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    tables = list(bundle.get("tables") or [])
    if not tables:
        raise PreventUpdate

    new_bundle = copy.deepcopy(bundle)
    hist = list(history or [])
    no = dash.no_update

    if trig == "rms-auto-layout-btn":
        if not auto_c:
            raise PreventUpdate
        snapshot = {str(t["id"]): [int(t.get("pos_x") or 0), int(t.get("pos_y") or 0)] for t in tables}
        hist.append(snapshot)
        pos_map = auto_layout_star_schema(tables, list(bundle.get("relationships") or []))
        for t in new_bundle["tables"]:
            tid = int(t["id"])
            if tid in pos_map:
                t["pos_x"], t["pos_y"] = pos_map[tid]
        toast = [toast_success("Đã sắp xếp Star Schema (bấm Undo vị trí nếu muốn hoàn tác).")]
    elif trig == "rms-undo-layout-btn":
        if not undo_c or not hist:
            return no, no, no, no, no, no, [toast_error("Chưa có thao tác sắp xếp trước đó để hoàn tác.")]
        snapshot = hist.pop()
        for t in new_bundle["tables"]:
            coords = snapshot.get(str(t["id"]))
            if coords and len(coords) == 2:
                t["pos_x"], t["pos_y"] = int(coords[0]), int(coords[1])
        toast = [toast_success("Đã khôi phục vị trí bảng trước đó.")]
    else:
        raise PreventUpdate

    return (
        new_bundle,
        hist,
        True,
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_studio_header(new_bundle, dirty=True),
        render_status_bar(new_bundle, dirty=True),
        toast,
    )


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Input("rms-drag-pos-store", "data"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_card_drag_end(
    drag_data: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, bool, Any, Any]:
    if not bundle or not isinstance(drag_data, dict) or not drag_data.get("table_id"):
        raise PreventUpdate
    tid = int(drag_data["table_id"])
    nx = int(drag_data.get("pos_x") or 0)
    ny = int(drag_data.get("pos_y") or 0)
    new_bundle = copy.deepcopy(bundle)
    updated = False
    for t in new_bundle.get("tables") or []:
        if int(t["id"]) == tid:
            t["pos_x"] = nx
            t["pos_y"] = ny
            updated = True
            break
    if not updated:
        raise PreventUpdate
    return (
        new_bundle,
        True,
        render_studio_header(new_bundle, dirty=True),
        render_status_bar(new_bundle, dirty=True),
    )


@callback(
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Input("rms-canvas-click-store", "data"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_canvas_click(
    click_data: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
    exp_query: str | None,
    zoom: float | None,
) -> tuple[Any, Any, Any, Any]:
    if not bundle or not isinstance(click_data, dict):
        raise PreventUpdate
    kind = str(click_data.get("kind") or "")
    sel: dict[str, Any] | None = None
    if kind == "clear":
        sel = None
    elif kind in ("table", "relationship"):
        sel = {"kind": kind, "id": int(click_data["id"])}
    elif kind == "field":
        sel = {"kind": "field", "id": int(click_data["id"]), "table_id": int(click_data["table_id"])}
    else:
        raise PreventUpdate

    return (
        sel,
        render_explorer_panel(bundle, selection=sel, query=exp_query or ""),
        render_canvas_panel(bundle, selection=sel, zoom=float(zoom or 1.0)),
        render_properties_panel(bundle, selection=sel),
    )


@callback(
    Output("rms-rel-modal", "opened"),
    Output("rms-rel-modal-alert", "children"),
    Output("rms-rel-m-name", "value"),
    Output("rms-rel-m-from-tbl", "data"),
    Output("rms-rel-m-from-tbl", "value"),
    Output("rms-rel-m-from-col", "data"),
    Output("rms-rel-m-from-col", "value"),
    Output("rms-rel-m-to-tbl", "data"),
    Output("rms-rel-m-to-tbl", "value"),
    Output("rms-rel-m-to-col", "data"),
    Output("rms-rel-m-to-col", "value"),
    Input("rms-new-rel-btn", "n_clicks"),
    Input("rms-connect-draft-store", "data"),
    Input("rms-rel-m-cancel", "n_clicks"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_open_rel_modal(
    new_btn: int | None,
    wire_data: dict[str, Any] | None,
    cancel_btn: int | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, ...]:
    trig = dash.callback_context.triggered_id
    no = dash.no_update
    if trig == "rms-rel-m-cancel":
        return False, None, no, no, no, no, no, no, no, no, no
    if not bundle:
        raise PreventUpdate
    tbl_opts = _table_select_options(bundle)
    if trig == "rms-connect-draft-store":
        if not isinstance(wire_data, dict) or not wire_data.get("from_table_id"):
            raise PreventUpdate
        ft = str(wire_data["from_table_id"])
        fc = str(wire_data.get("from_column") or "")
        tt = str(wire_data["to_table_id"])
        tc = str(wire_data.get("to_column") or "")
        rel_name = f"REL_{fc}_{tc}"[:100]
        return (
            True,
            None,
            rel_name,
            tbl_opts,
            ft,
            _col_select_options(bundle, ft),
            fc,
            tbl_opts,
            tt,
            _col_select_options(bundle, tt),
            tc,
        )
    if trig == "rms-new-rel-btn":
        if not new_btn:
            raise PreventUpdate
        ft_opt: str | None = tbl_opts[0]["value"] if tbl_opts else None
        tt_opt: str | None = tbl_opts[1]["value"] if len(tbl_opts) > 1 else ft_opt
        return (
            True,
            None,
            "",
            tbl_opts,
            ft_opt,
            _col_select_options(bundle, ft_opt),
            None,
            tbl_opts,
            tt_opt,
            _col_select_options(bundle, tt_opt),
            None,
        )
    raise PreventUpdate


@callback(
    Output("rms-rel-m-from-col", "data", allow_duplicate=True),
    Output("rms-rel-m-to-col", "data", allow_duplicate=True),
    Input("rms-rel-m-from-tbl", "value"),
    Input("rms-rel-m-to-tbl", "value"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_rel_modal_table_change(
    from_tid: str | None,
    to_tid: str | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, Any]:
    if not bundle:
        raise PreventUpdate
    return _col_select_options(bundle, from_tid), _col_select_options(bundle, to_tid)


@callback(
    Output("rms-rel-modal", "opened", allow_duplicate=True),
    Output("rms-rel-modal-alert", "children", allow_duplicate=True),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-rel-m-submit", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-rel-m-name", "value"),
    State("rms-rel-m-from-tbl", "value"),
    State("rms-rel-m-from-col", "value"),
    State("rms-rel-m-to-tbl", "value"),
    State("rms-rel-m-to-col", "value"),
    State("rms-rel-m-card", "value"),
    State("rms-rel-m-join", "value"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_rel_modal_submit(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    name: str | None,
    from_tid: str | None,
    from_col: str | None,
    to_tid: str | None,
    to_col: str | None,
    cardinality: str | None,
    join_type: str | None,
    exp_query: str | None,
    zoom: float | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    no = dash.no_update
    if not name or not from_tid or not from_col or not to_tid or not to_col:
        return True, alert_box(message="Vui lòng chọn đầy đủ bảng, cột nguồn/đích và tên quan hệ.", tone="crit"), no, no, no, no, no, no, no

    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    res = upsert_relationship(
        ctx,
        ver_id,
        {
            "name": str(name).strip(),
            "from_table_id": int(from_tid),
            "from_column": str(from_col).strip(),
            "to_table_id": int(to_tid),
            "to_column": str(to_col).strip(),
            "cardinality": cardinality or "MANY_TO_ONE",
            "join_type": join_type or "LEFT_OUTER",
            "cross_filter": "SINGLE",
            "is_active": True,
        },
    )
    if not res.ok or not res.data:
        return True, alert_box(message=res.message or "Không tạo được quan hệ.", tone="crit"), no, no, no, no, no, no, no

    refreshed = get_model_version_detail(ctx, ver_id)
    new_bundle = refreshed.data if refreshed.ok and refreshed.data else bundle
    new_sel = {"kind": "relationship", "id": int(res.data["id"])}
    return (
        False,
        None,
        new_bundle,
        new_sel,
        render_explorer_panel(new_bundle, selection=new_sel, query=exp_query or ""),
        render_canvas_panel(new_bundle, selection=new_sel, zoom=float(zoom or 1.0)),
        render_properties_panel(new_bundle, selection=new_sel),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast_success(f"Đã tạo quan hệ {name}.")],
    )


def _refresh_bundle(ctx: Ctx, bundle: dict[str, Any]) -> dict[str, Any]:
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    ref = get_model_version_detail(ctx, ver_id)
    if not (ref.ok and isinstance(ref.data, dict)):
        return bundle
    refreshed: dict[str, Any] = ref.data
    # Giữ tọa độ canvas chưa Lưu nháp (VD vừa Auto Layout / kéo card trước khi sửa Properties)
    client_pos = {
        int(t["id"]): (int(t.get("pos_x") or 0), int(t.get("pos_y") or 0))
        for t in (bundle.get("tables") or [])
        if t.get("id") is not None
    }
    for tbl in refreshed.get("tables") or []:
        tid = int(tbl["id"])
        if tid in client_pos:
            tbl["pos_x"], tbl["pos_y"] = client_pos[tid]
    return refreshed


def save_table_properties(
    ctx: Ctx | None,
    *,
    bundle: dict[str, Any],
    table_id: int,
    alias: str | None,
    display_name: str | None,
    table_role: str | None,
    grain_desc: str | None,
    grain_keys: list[str] | None,
    default_date_field: str | None,
    is_hidden: bool,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None
    payload: dict[str, Any] = {
        "alias": str(alias or "").strip() or None,
        "display_name": str(display_name or "").strip() or None,
        "table_role": str(table_role or "UNCLASSIFIED").upper(),
        "grain_desc": str(grain_desc or "").strip() or None,
        "grain_keys": list(grain_keys or []),
        "default_date_field": default_date_field or None,
        "is_hidden": bool(is_hidden),
    }
    res = update_table_props(ctx, int(table_id), payload)
    if not res.ok:
        return None, res.message or "Không lưu được thuộc tính bảng.", None
    new_bundle = _refresh_bundle(ctx, bundle)
    return new_bundle, None, toast_success("Đã cập nhật thuộc tính bảng.")


def save_rls_policy_from_studio(
    ctx: Ctx | None,
    *,
    bundle: dict[str, Any],
    table_id: int,
    column_name: str | None,
    policy_type: str | None,
    scope_attr: str | None,
    admin_bypass: bool,
    is_active: bool,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None
    if not column_name:
        return None, "Vui lòng chọn cột áp dụng chính sách RLS.", None
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    res = upsert_rls_policy(
        ctx,
        ver_id,
        {
            "table_id": int(table_id),
            "column_name": str(column_name).strip(),
            "policy_type": str(policy_type or "OWNER_USERNAME").upper(),
            "scope_attr": str(scope_attr or "").strip() or None,
            "admin_bypass": bool(admin_bypass),
            "is_active": bool(is_active),
        },
    )
    if not res.ok:
        return None, res.message or "Không lưu được cấu hình RLS.", None
    new_bundle = _refresh_bundle(ctx, bundle)
    return new_bundle, None, toast_success("Đã lưu cấu hình metadata RLS V1.")


def save_field_properties(
    ctx: Ctx | None,
    *,
    bundle: dict[str, Any],
    field_id: int,
    field_code: str | None = None,
    display_name: str | None = None,
    field_role: str | None = None,
    default_agg: str | None = None,
    format_mask: str | None = None,
    is_visible: bool = True,
    is_filterable: bool = True,
    sort_by_field_id: str | int | None = None,
    folder: str | None = None,
    enable_date_hierarchy: bool = False,
    sensitivity: str | None = None,
    description: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None
    sort_fid = int(str(sort_by_field_id)) if sort_by_field_id not in (None, "") else None
    payload: dict[str, Any] = {
        "display_name": str(display_name or "").strip() or None,
        "field_role": str(field_role or "DIMENSION").upper(),
        "default_agg": str(default_agg or "NONE").upper(),
        "format_mask": str(format_mask or "").strip() or None,
        "is_visible": bool(is_visible),
        "is_filterable": bool(is_filterable),
        "sort_by_field_id": sort_fid,
        "clear_sort_by": sort_fid is None,
        "folder": str(folder or "").strip() or None,
        "enable_date_hierarchy": bool(enable_date_hierarchy),
        "sensitivity": str(sensitivity or "NORMAL").upper(),
        "description": str(description or "").strip() or None,
    }
    if field_code and str(field_code).strip():
        payload["field_code"] = str(field_code).strip()
    res = update_field_props(ctx, int(field_id), payload)
    if not res.ok:
        return None, res.message or "Không lưu được thuộc tính cột.", None
    new_bundle = _refresh_bundle(ctx, bundle)
    return new_bundle, None, toast_success("Đã cập nhật thuộc tính trường dữ liệu.")


def run_relationship_tier2_profile(ctx: Ctx, rel_id: int) -> ServiceResult[Any]:
    """Chạy kiểm tra dữ liệu mẫu Tầng 2 (timeout 15s, giới hạn 50.000 dòng)."""
    return profile_relationship_data(ctx, int(rel_id), sample_limit=50000, timeout_sec=15)


def save_measure_from_studio(
    ctx: Ctx | None,
    *,
    bundle: dict[str, Any],
    measure_id: int | None,
    code: str | None,
    name: str | None,
    measure_type: str | None,
    table_id: str | int | None,
    base_field_id: str | int | None,
    aggregation: str | None,
    ast_expr: dict[str, Any] | None,
    format_mask: str | None = None,
    folder: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    mtype = str(measure_type or "SIMPLE").upper()
    norm_tid = int(str(table_id)) if table_id not in (None, "") else None
    norm_bfid = int(str(base_field_id)) if base_field_id not in (None, "") else None
    payload: dict[str, Any] = {
        "id": int(measure_id) if measure_id is not None else None,
        "table_id": norm_tid,
        "code": str(code or "").strip().upper(),
        "name": str(name or "").strip(),
        "measure_type": mtype,
        "base_field_id": norm_bfid if mtype == "SIMPLE" else None,
        "aggregation": str(aggregation or "SUM").upper() if mtype == "SIMPLE" else None,
        "expr_json": ast_expr if mtype == "CALCULATED" else None,
        "format_mask": str(format_mask or "").strip() or None,
        "folder": str(folder or "").strip() or None,
    }
    res = upsert_measure(ctx, ver_id, payload)
    if not res.ok:
        return None, res.message or "Không lưu được Measure.", None
    new_bundle = _refresh_bundle(ctx, bundle)
    return new_bundle, None, toast_success(f"Đã lưu Measure {payload['code']}.")


@callback(
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Input("rms-prop-tbl-new-meas", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_open_measure_from_table(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[Any, Any]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    tid = int(selection["id"]) if selection and selection.get("kind") == "table" and selection.get("id") else None
    new_sel = {"kind": "measure", "id": None, "table_id": tid}
    return new_sel, render_properties_panel(bundle, selection=new_sel)


@callback(
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Input("rms-prop-empty-new-meas-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_open_measure_from_empty(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, Any]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    new_sel = {"kind": "measure", "id": None, "table_id": None}
    return new_sel, render_properties_panel(bundle, selection=new_sel)


@callback(
    Output("rms-prop-tbl-alert", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-prop-tbl-save", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-prop-tbl-alias", "value"),
    State("rms-prop-tbl-name", "value"),
    State("rms-prop-tbl-role", "value"),
    State("rms-prop-tbl-grain-desc", "value"),
    State("rms-prop-tbl-grain-keys", "value"),
    State("rms-prop-tbl-date-fld", "value"),
    State("rms-prop-tbl-hidden", "checked"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_save_table_props(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    alias: str | None,
    display_name: str | None,
    role: str | None,
    grain_desc: str | None,
    grain_keys: list[str] | None,
    date_fld: str | None,
    is_hidden: bool | None,
    exp_q: str | None,
    zoom: float | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle or not selection or selection.get("kind") != "table":
        raise PreventUpdate
    ctx = get_current_ctx()
    new_bundle, err, toast = save_table_properties(
        ctx,
        bundle=bundle,
        table_id=int(selection["id"]),
        alias=alias,
        display_name=display_name,
        table_role=role,
        grain_desc=grain_desc,
        grain_keys=grain_keys,
        default_date_field=date_fld,
        is_hidden=bool(is_hidden),
    )
    no = dash.no_update
    if err or not new_bundle:
        return alert_box(message=err or "Lỗi lưu bảng.", tone="crit"), no, no, no, no, no, no
    return (
        None,
        new_bundle,
        render_explorer_panel(new_bundle, selection=selection, query=exp_q or ""),
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_properties_panel(new_bundle, selection=selection),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast] if toast else dash.no_update,
    )


@callback(
    Output("rms-prop-tbl-alert", "children", allow_duplicate=True),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-prop-rls-save", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-prop-rls-col", "value"),
    State("rms-prop-rls-type", "value"),
    State("rms-prop-rls-scope", "value"),
    State("rms-prop-rls-bypass", "checked"),
    State("rms-prop-rls-active", "checked"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_save_rls(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    col_name: str | None,
    policy_type: str | None,
    scope_attr: str | None,
    admin_bypass: bool | None,
    is_active: bool | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle or not selection or selection.get("kind") != "table":
        raise PreventUpdate
    ctx = get_current_ctx()
    new_bundle, err, toast = save_rls_policy_from_studio(
        ctx,
        bundle=bundle,
        table_id=int(selection["id"]),
        column_name=col_name,
        policy_type=policy_type,
        scope_attr=scope_attr,
        admin_bypass=bool(admin_bypass),
        is_active=bool(is_active),
    )
    no = dash.no_update
    if err or not new_bundle:
        return alert_box(message=err or "Không lưu được RLS.", tone="crit"), no, no, no, no
    return (
        None,
        new_bundle,
        render_properties_panel(new_bundle, selection=selection),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast] if toast else dash.no_update,
    )


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input({"type": "rms-prop-rls-del", "id": ALL}, "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_delete_rls(
    _clicks: list[Any],
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not bundle or not dash.callback_context.triggered or not dash.callback_context.triggered[0].get("value"):
        raise PreventUpdate
    trig_id = dash.callback_context.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = delete_rls_policy(ctx, int(trig_id["id"]))
    no = dash.no_update
    if not res.ok:
        return no, no, no, [toast_error(res.message or "Không xóa được RLS.")]
    new_bundle = _refresh_bundle(ctx, bundle)
    return (
        new_bundle,
        render_properties_panel(new_bundle, selection=selection),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast_success("Đã xóa chính sách RLS.")],
    )


@callback(
    Output("rms-prop-fld-alert", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-prop-fld-save", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-prop-fld-code", "value"),
    State("rms-prop-fld-name", "value"),
    State("rms-prop-fld-role", "value"),
    State("rms-prop-fld-agg", "value"),
    State("rms-prop-fld-format", "value"),
    State("rms-prop-fld-visible", "checked"),
    State("rms-prop-fld-filterable", "checked"),
    State("rms-prop-fld-sortby", "value"),
    State("rms-prop-fld-folder", "value"),
    State("rms-prop-fld-date-hier", "checked"),
    State("rms-prop-fld-sens", "value"),
    State("rms-prop-fld-desc", "value"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_save_field_props(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    field_code: str | None,
    display_name: str | None,
    field_role: str | None,
    default_agg: str | None,
    format_mask: str | None,
    is_visible: bool | None,
    is_filterable: bool | None,
    sort_by: str | None,
    folder: str | None,
    date_hier: bool | None,
    sensitivity: str | None,
    desc: str | None,
    exp_q: str | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle or not selection or selection.get("kind") != "field":
        raise PreventUpdate
    ctx = get_current_ctx()
    new_bundle, err, toast = save_field_properties(
        ctx,
        bundle=bundle,
        field_id=int(selection["id"]),
        field_code=field_code,
        display_name=display_name,
        field_role=field_role,
        default_agg=default_agg,
        format_mask=format_mask,
        is_visible=bool(is_visible),
        is_filterable=bool(is_filterable),
        sort_by_field_id=sort_by,
        folder=folder,
        enable_date_hierarchy=bool(date_hier),
        sensitivity=sensitivity,
        description=desc,
    )
    no = dash.no_update
    if err or not new_bundle:
        return alert_box(message=err or "Không lưu được thuộc tính cột.", tone="crit"), no, no, no, no, no
    return (
        None,
        new_bundle,
        render_explorer_panel(new_bundle, selection=selection, query=exp_q or ""),
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_properties_panel(new_bundle, selection=selection),
        [toast] if toast else dash.no_update,
    )


@callback(
    Output("rms-prop-rel-from-col", "data"),
    Output("rms-prop-rel-to-col", "data"),
    Input("rms-prop-rel-from-tbl", "value"),
    Input("rms-prop-rel-to-tbl", "value"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_prop_rel_table_change(
    from_tid: str | None,
    to_tid: str | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, Any]:
    if not bundle:
        raise PreventUpdate
    return _col_select_options(bundle, from_tid), _col_select_options(bundle, to_tid)


@callback(
    Output("rms-prop-rel-alert", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-prop-rel-save", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-prop-rel-name", "value"),
    State("rms-prop-rel-from-tbl", "value"),
    State("rms-prop-rel-from-col", "value"),
    State("rms-prop-rel-to-tbl", "value"),
    State("rms-prop-rel-to-col", "value"),
    State("rms-prop-rel-card", "value"),
    State("rms-prop-rel-join", "value"),
    State("rms-prop-rel-active", "checked"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_prop_rel_save(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    name: str | None,
    from_tid: str | None,
    from_col: str | None,
    to_tid: str | None,
    to_col: str | None,
    card: str | None,
    join_type: str | None,
    is_active: bool | None,
    exp_q: str | None,
    zoom: float | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle or not selection or selection.get("kind") != "relationship":
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    res = upsert_relationship(
        ctx,
        ver_id,
        {
            "id": int(selection["id"]),
            "name": str(name or "").strip(),
            "from_table_id": int(from_tid or 0),
            "from_column": str(from_col or "").strip(),
            "to_table_id": int(to_tid or 0),
            "to_column": str(to_col or "").strip(),
            "cardinality": card or "MANY_TO_ONE",
            "join_type": join_type or "LEFT_OUTER",
            "cross_filter": "SINGLE",
            "is_active": bool(is_active),
        },
    )
    no = dash.no_update
    if not res.ok:
        return alert_box(message=res.message or "Không cập nhật được quan hệ.", tone="crit"), no, no, no, no, no, no
    new_bundle = _refresh_bundle(ctx, bundle)
    return (
        None,
        new_bundle,
        render_explorer_panel(new_bundle, selection=selection, query=exp_q or ""),
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_properties_panel(new_bundle, selection=selection),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast_success("Đã áp dụng thay đổi cho quan hệ.")],
    )


@callback(
    Output("rms-prop-rel-val-result", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Input("rms-prop-rel-val1", "n_clicks"),
    Input("rms-prop-rel-val2", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_rel_validation_buttons(
    c1: int | None,
    c2: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    zoom: float | None,
) -> tuple[Any, Any, Any]:
    if not bundle or not selection or selection.get("kind") != "relationship":
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    rel_id = int(selection["id"])
    no = dash.no_update
    if trig == "rms-prop-rel-val1":
        if not c1:
            raise PreventUpdate
        rel_issues = [i for i in validate_relationship_structure(bundle) if i.get("target_id") == rel_id]
        st = "ERROR" if any(i["severity"] == "ERROR" for i in rel_issues) else ("WARNING" if rel_issues else "PASS")
        checks = [{"status": i["severity"], "message": i["message"]} for i in rel_issues] or [
            {"status": "PASS", "message": "Cấu trúc, kiểu dữ liệu và đồ thị quan hệ hợp lệ (không loop/ambiguous path)."}
        ]
        return render_rel_validation_result({"status": st, "checks": checks}), no, no

    if trig == "rms-prop-rel-val2":
        if not c2:
            raise PreventUpdate
        ctx = get_current_ctx()
        if ctx is None:
            raise PreventUpdate
        res = run_relationship_tier2_profile(ctx, rel_id)
        if not res.ok or not res.data:
            return alert_box(message=res.message or "Không chạy được profiling mẫu.", tone="crit"), no, no
        new_bundle = _refresh_bundle(ctx, bundle)
        return (
            render_rel_validation_result(res.data),
            new_bundle,
            render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        )
    raise PreventUpdate


@callback(
    Output("rms-prop-meas-simple-box", "style"),
    Output("rms-prop-meas-calc-box", "style"),
    Output("rms-prop-meas-preview", "children"),
    Input("rms-prop-meas-type", "value"),
    Input("rms-prop-meas-op", "value"),
    Input("rms-prop-meas-lkind", "value"),
    Input("rms-prop-meas-lfld", "value"),
    Input("rms-prop-meas-lagg", "value"),
    Input("rms-prop-meas-lmeas", "value"),
    Input("rms-prop-meas-lconst", "value"),
    Input("rms-prop-meas-rkind", "value"),
    Input("rms-prop-meas-rfld", "value"),
    Input("rms-prop-meas-ragg", "value"),
    Input("rms-prop-meas-rmeas", "value"),
    Input("rms-prop-meas-rconst", "value"),
    Input("rms-prop-meas-digits", "value"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_measure_ast_preview(
    mtype: str | None,
    op: str | None,
    lk: str | None,
    lfld: str | None,
    lagg: str | None,
    lmeas: str | None,
    lconst: str | None,
    rk: str | None,
    rfld: str | None,
    ragg: str | None,
    rmeas: str | None,
    rconst: str | None,
    digits: int | float | None,
    bundle: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], str]:
    is_calc = str(mtype or "SIMPLE").upper() == "CALCULATED"
    s_style = {"display": "none" if is_calc else "flex"}
    c_style = {"display": "flex" if is_calc else "none"}
    if not bundle:
        return s_style, c_style, "—"
    ast = build_calculated_ast_from_form(
        op=str(op or "DIVIDE"),
        left_kind=lk,
        left_field_id=lfld,
        left_agg=lagg,
        left_measure_id=lmeas,
        left_const=lconst,
        right_kind=rk,
        right_field_id=rfld,
        right_agg=ragg,
        right_measure_id=rmeas,
        right_const=rconst,
        digits=int(digits) if digits is not None else 2,
    )
    return s_style, c_style, format_ast_preview(ast, bundle)


@callback(
    Output("rms-prop-meas-alert", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-prop-meas-save", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-prop-meas-code", "value"),
    State("rms-prop-meas-name", "value"),
    State("rms-prop-meas-type", "value"),
    State("rms-prop-meas-table", "value"),
    State("rms-prop-meas-base-fld", "value"),
    State("rms-prop-meas-agg", "value"),
    State("rms-prop-meas-op", "value"),
    State("rms-prop-meas-lkind", "value"),
    State("rms-prop-meas-lfld", "value"),
    State("rms-prop-meas-lagg", "value"),
    State("rms-prop-meas-lmeas", "value"),
    State("rms-prop-meas-lconst", "value"),
    State("rms-prop-meas-rkind", "value"),
    State("rms-prop-meas-rfld", "value"),
    State("rms-prop-meas-ragg", "value"),
    State("rms-prop-meas-rmeas", "value"),
    State("rms-prop-meas-rconst", "value"),
    State("rms-prop-meas-digits", "value"),
    State("rms-prop-meas-format", "value"),
    State("rms-prop-meas-folder", "value"),
    State("rms-explorer-search", "value"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_save_measure(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    code: str | None,
    name: str | None,
    mtype: str | None,
    table_id: str | None,
    base_fld_id: str | None,
    agg: str | None,
    op: str | None,
    lk: str | None,
    lfld: str | None,
    lagg: str | None,
    lmeas: str | None,
    lconst: str | None,
    rk: str | None,
    rfld: str | None,
    ragg: str | None,
    rmeas: str | None,
    rconst: str | None,
    digits: int | float | None,
    fmt: str | None,
    folder: str | None,
    exp_q: str | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    cur_mid = int(selection["id"]) if selection and selection.get("kind") == "measure" and selection.get("id") else None
    ast = None
    if str(mtype or "SIMPLE").upper() == "CALCULATED":
        ast = build_calculated_ast_from_form(
            op=str(op or "DIVIDE"),
            left_kind=lk,
            left_field_id=lfld,
            left_agg=lagg,
            left_measure_id=lmeas,
            left_const=lconst,
            right_kind=rk,
            right_field_id=rfld,
            right_agg=ragg,
            right_measure_id=rmeas,
            right_const=rconst,
            digits=int(digits) if digits is not None else 2,
        )
    new_bundle, err, toast = save_measure_from_studio(
        ctx,
        bundle=bundle,
        measure_id=cur_mid,
        code=code,
        name=name,
        measure_type=mtype,
        table_id=table_id,
        base_field_id=base_fld_id,
        aggregation=agg,
        ast_expr=ast,
        format_mask=fmt,
        folder=folder,
    )
    no = dash.no_update
    if err or not new_bundle:
        return alert_box(message=err or "Không lưu được Measure.", tone="crit"), no, no, no, no, no, no
    saved_m = next((m for m in new_bundle.get("measures") or [] if m["code"] == str(code or "").strip().upper()), None)
    new_sel = {"kind": "measure", "id": int(saved_m["id"])} if saved_m else selection
    return (
        None,
        new_bundle,
        new_sel,
        render_explorer_panel(new_bundle, selection=new_sel, query=exp_q or ""),
        render_properties_panel(new_bundle, selection=new_sel),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast] if toast else dash.no_update,
    )


@callback(
    Output("rms-del-modal", "opened", allow_duplicate=True),
    Output("rms-del-target-store", "data"),
    Output("rms-del-modal-desc", "children"),
    Input({"type": "rms-prop-remove-btn", "kind": ALL}, "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    prevent_initial_call=True,
)
def handle_open_delete_modal(
    _clicks: list[Any],
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
) -> tuple[bool, Any, str]:
    if not bundle or not selection or not dash.callback_context.triggered:
        raise PreventUpdate
    if not dash.callback_context.triggered[0].get("value"):
        raise PreventUpdate
    trig = dash.callback_context.triggered_id
    if not isinstance(trig, dict):
        raise PreventUpdate
    kind = str(trig.get("kind") or "")
    ctx = get_current_ctx()
    model_id = int((bundle.get("model") or {}).get("id") or 0)
    rpt_warn = ""
    if ctx is not None and model_id:
        imp = impact_analysis(ctx, model_id)
        if imp.ok and imp.data and imp.data.get("reports"):
            rpt_warn = f" Cảnh báo: hiện có {len(imp.data['reports'])} báo cáo tham chiếu tới mô hình."

    if kind == "table" and selection.get("kind") == "table":
        tid = int(selection["id"])
        return True, {"kind": "table", "id": tid}, f"Sẽ gỡ bảng và toàn bộ cột/quan hệ liên kết khỏi bản nháp.{rpt_warn}"
    if kind == "relationship" and selection.get("kind") == "relationship":
        rid = int(selection["id"])
        return True, {"kind": "relationship", "id": rid}, f"Sẽ xóa quan hệ này khỏi bản nháp.{rpt_warn}"
    if kind == "measure" and selection.get("kind") == "measure" and selection.get("id"):
        mid = int(selection["id"])
        return True, {"kind": "measure", "id": mid}, f"Sẽ xóa Measure này khỏi bản nháp.{rpt_warn}"
    raise PreventUpdate


@callback(
    Output("rms-del-modal", "opened", allow_duplicate=True),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-del-modal-confirm", "n_clicks"),
    Input("rms-del-modal-cancel", "n_clicks"),
    State("rms-del-target-store", "data"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_confirm_delete(
    conf_c: int | None,
    cancel_c: int | None,
    target: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
    exp_q: str | None,
    zoom: float | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    trig = dash.callback_context.triggered_id
    no = dash.no_update
    if trig == "rms-del-modal-cancel":
        return False, no, no, no, no, no, no, no
    if not conf_c or not target or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    kind = str(target.get("kind") or "")
    tid = int(target["id"])
    if kind == "table":
        res = remove_table_from_draft(ctx, tid)
    elif kind == "relationship":
        res = delete_relationship(ctx, tid)
    elif kind == "measure":
        res = delete_measure(ctx, tid)
    else:
        raise PreventUpdate
    if not res.ok:
        return False, no, no, no, no, no, no, [toast_error(res.message or "Không xóa được.")]
    new_bundle = _refresh_bundle(ctx, bundle)
    return (
        False,
        new_bundle,
        None,
        render_explorer_panel(new_bundle, selection=None, query=exp_q or ""),
        render_canvas_panel(new_bundle, selection=None, zoom=float(zoom or 1.0)),
        render_properties_panel(new_bundle, selection=None),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        [toast_success("Đã xóa khỏi bản nháp.")],
    )


def run_full_model_validation(
    ctx: Ctx | None,
    bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Chạy kiểm tra toàn diện mô hình (validate_model) và đồng bộ lại bundle."""
    if ctx is None:
        return None, None, "Phiên đăng nhập đã hết hạn."
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    res = validate_model(ctx, ver_id, check_physical=True)
    if not res.ok or not res.data:
        return None, None, res.message or "Kiểm tra mô hình thất bại."
    refreshed = _refresh_bundle(ctx, bundle)
    return refreshed, res.data, None


def save_studio_draft(
    ctx: Ctx | None,
    bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, ServiceResult[dict[str, Any]]]:
    """Lưu vị trí canvas và metadata bản nháp kèm kiểm tra optimistic concurrency (STALE_DATA)."""
    if ctx is None:
        return None, ServiceResult(ok=False, code=ErrorCode.UNAUTHENTICATED, message="Phiên đăng nhập đã hết hạn.")
    ver = bundle.get("version") or {}
    ver_id = int(ver.get("id") or 0)
    row_ver = int(ver.get("row_version") or 1)
    positions = [
        {
            "table_id": int(t["id"]),
            "pos_x": int(t.get("pos_x") or 0),
            "pos_y": int(t.get("pos_y") or 0),
        }
        for t in (bundle.get("tables") or [])
    ]
    res = save_draft_state(
        ctx,
        ver_id,
        {"expected_row_version": row_ver, "positions": positions},
    )
    if not res.ok:
        return None, res
    refreshed = _refresh_bundle(ctx, bundle)
    return refreshed, res


def build_publish_preview(
    ctx: Ctx | None,
    bundle: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Tổng hợp Validation + Version Diff + Impact Analysis cho Modal Phát hành."""
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn."
    model = bundle.get("model") or {}
    ver = bundle.get("version") or {}
    model_id = int(model.get("id") or 0)
    ver_id = int(ver.get("id") or 0)

    val_res = validate_model(ctx, ver_id, check_physical=True)
    if not val_res.ok or not val_res.data:
        return None, val_res.message or "Không kiểm tra được mô hình trước khi phát hành."

    active_ver_id = model.get("active_version_id")
    diff_data: dict[str, Any] | None = None
    if active_ver_id is not None and int(active_ver_id) != ver_id:
        diff_res = diff_model_versions(ctx, ver_id, int(active_ver_id))
        if diff_res.ok and diff_res.data:
            diff_data = diff_res.data

    imp_res = impact_analysis(ctx, model_id, target_version_id=ver_id)
    imp_data = (
        imp_res.data
        if (imp_res.ok and imp_res.data)
        else {"reports": [], "visuals": [], "scheduled_exports": []}
    )
    err_cnt = int((val_res.data.get("summary") or {}).get("error_count") or 0)
    ver_status = str(ver.get("status") or "").upper()
    is_editable = ver_status in ("DRAFT", "VALIDATED") and not model.get("is_archived")
    return {
        "validation": val_res.data,
        "diff": diff_data,
        "impact": imp_data,
        "can_publish": (err_cnt == 0 and is_editable),
    }, None


def publish_from_studio(
    ctx: Ctx | None,
    bundle: dict[str, Any],
    *,
    change_note: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Thực thi publish_model_version với Change Note bắt buộc và trả về bundle ACTIVE chỉ đọc."""
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn."
    note = (change_note or "").strip()
    if not note:
        return None, "Vui lòng nhập ghi chú phát hành (Change Note)."
    ver_id = int((bundle.get("version") or {}).get("id") or 0)
    pub_res = publish_model_version(ctx, ver_id, {"change_note": note})
    if not pub_res.ok:
        return None, pub_res.message or "Không thể phát hành phiên bản mô hình."
    det = get_model_version_detail(ctx, ver_id)
    if det.ok and det.data:
        return det.data, None
    return None, det.message or "Đã phát hành nhưng không tải lại được phiên bản ACTIVE."


@callback(
    Output("rms-validate-drawer", "opened"),
    Output("rms-validate-drawer-body", "children"),
    Output("rms-val-issues-store", "data"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-validate-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-selection-store", "data"),
    State("rms-zoom-store", "data"),
    State("rms-dirty-store", "data"),
    prevent_initial_call=True,
)
def handle_validate_model(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    zoom: float | None,
    dirty: bool | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    new_bundle, val_data, err = run_full_model_validation(ctx, bundle)
    no = dash.no_update
    if err or new_bundle is None or val_data is None:
        return True, alert_box(title="Lỗi kiểm tra mô hình", message=err or "Thất bại.", tone="crit"), [], no, no, no, no, no
    issues = list(val_data.get("issues") or [])
    err_cnt = int((val_data.get("summary") or {}).get("error_count") or 0)
    toast = (
        [toast_error(f"Phát hiện {err_cnt} lỗi ERROR trong mô hình.")]
        if err_cnt > 0
        else [toast_success("Kiểm tra mô hình hoàn tất.")]
    )
    return (
        True,
        render_validation_drawer_body(new_bundle, val_data),
        issues,
        new_bundle,
        render_canvas_panel(new_bundle, selection=selection, zoom=float(zoom or 1.0)),
        render_studio_header(new_bundle, dirty=bool(dirty)),
        render_status_bar(new_bundle, dirty=bool(dirty)),
        toast,
    )


@callback(
    Output("rms-validate-drawer", "opened", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-focus-seq-store", "data"),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Input({"type": "rms-val-issue-btn", "idx": ALL}, "n_clicks"),
    State("rms-val-issues-store", "data"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    State("rms-focus-seq-store", "data"),
    prevent_initial_call=True,
)
def handle_validation_issue_click(
    clicks: list[Any],
    issues: list[dict[str, Any]] | None,
    bundle: dict[str, Any] | None,
    exp_q: str | None,
    zoom: float | None,
    focus_seq: int | None,
) -> tuple[Any, ...]:
    if not bundle or not issues or not dash.callback_context.triggered:
        raise PreventUpdate
    if not dash.callback_context.triggered[0].get("value"):
        raise PreventUpdate
    raw_id = dash.callback_context.triggered_id
    if not isinstance(raw_id, dict) or "idx" not in raw_id:
        raise PreventUpdate
    idx = int(raw_id["idx"])
    if idx < 0 or idx >= len(issues):
        raise PreventUpdate
    sel = resolve_validation_issue_selection(bundle, issues[idx])
    if sel is None:
        raise PreventUpdate
    next_seq = int(focus_seq or 0) + 1
    return (
        False,
        sel,
        next_seq,
        render_explorer_panel(bundle, selection=sel, query=exp_q or ""),
        render_canvas_panel(
            bundle,
            selection=sel,
            zoom=float(zoom or 1.0),
            focus_token=f"issue-{next_seq}",
        ),
        render_properties_panel(bundle, selection=sel),
    )


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-stale-modal", "opened"),
    Output("rms-stale-modal-body", "children"),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-save-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_save_draft(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    saved_bundle, res = save_studio_draft(ctx, bundle)
    no = dash.no_update
    if res.code == ErrorCode.STALE_DATA:
        srv_rv = (res.details or {}).get("server_row_version") if isinstance(res.details, dict) else None
        return (
            no,
            no,
            no,
            no,
            True,
            render_stale_conflict_body(res.message or "Bản nháp đã thay đổi trên phiên khác.", srv_rv),
            [toast_error(res.message or "Xung đột phiên bản bản nháp.")],
        )
    if not res.ok or saved_bundle is None:
        return no, no, no, no, False, no, [toast_error(res.message or "Không lưu được bản nháp.")]
    return (
        saved_bundle,
        False,
        render_studio_header(saved_bundle, dirty=False),
        render_status_bar(saved_bundle, dirty=False),
        False,
        no,
        [toast_success("Đã lưu bản nháp.")],
    )


@callback(
    Output("rms-stale-modal", "opened", allow_duplicate=True),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-stale-reload-btn", "n_clicks"),
    Input("rms-stale-keep-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_stale_conflict_action(
    reload_c: int | None,
    keep_c: int | None,
    bundle: dict[str, Any] | None,
    exp_q: str | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    trig = dash.callback_context.triggered_id
    no = dash.no_update
    if trig == "rms-stale-keep-btn":
        if not keep_c:
            raise PreventUpdate
        return False, no, no, no, no, no, no, no, no, [toast_success("Đang giữ phiên bản bạn đang sửa.")]
    if trig != "rms-stale-reload-btn" or not reload_c or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    model_id = int((bundle.get("model") or {}).get("id") or 0)
    fresh_bundle, err = load_studio_bundle(ctx, model_id)
    if err or fresh_bundle is None:
        return False, no, no, no, no, no, no, no, no, [toast_error(err or "Không tải lại được bản nháp.")]
    z = float(zoom or 1.0)
    return (
        False,
        fresh_bundle,
        False,
        None,
        render_studio_header(fresh_bundle, dirty=False),
        render_explorer_panel(fresh_bundle, selection=None, query=exp_q or ""),
        render_canvas_panel(fresh_bundle, selection=None, zoom=z),
        render_properties_panel(fresh_bundle, selection=None),
        render_status_bar(fresh_bundle, dirty=False),
        [toast_success("Đã tải lại bản nháp mới nhất từ máy chủ.")],
    )


@callback(
    Output("rms-publish-modal", "opened"),
    Output("rms-publish-modal-body", "children"),
    Input("rms-publish-btn", "n_clicks"),
    Input("rms-pub-cancel-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    prevent_initial_call=True,
)
def handle_open_publish_modal(
    pub_c: int | None,
    cancel_c: int | None,
    bundle: dict[str, Any] | None,
) -> tuple[bool, Any]:
    trig = dash.callback_context.triggered_id
    no = dash.no_update
    if trig == "rms-pub-cancel-btn":
        if not cancel_c:
            raise PreventUpdate
        return False, no
    if not pub_c or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    preview, err = build_publish_preview(ctx, bundle)
    if err or preview is None:
        return True, alert_box(title="Không mở được màn hình phát hành", message=err or "Thất bại.", tone="crit")
    return True, render_publish_modal_body(bundle, preview)


@callback(
    Output("rms-publish-modal", "opened", allow_duplicate=True),
    Output("rms-pub-modal-alert", "children"),
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-stale-modal", "opened", allow_duplicate=True),
    Output("rms-stale-modal-body", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-pub-confirm-btn", "n_clicks"),
    State("rms-pub-change-note", "value"),
    State("rms-bundle-store", "data"),
    State("rms-dirty-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_confirm_publish(
    conf_c: int | None,
    change_note: str | None,
    bundle: dict[str, Any] | None,
    dirty: bool | None,
    exp_q: str | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    if not conf_c or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    no = dash.no_update
    cur_bundle = bundle
    if dirty:
        saved, save_res = save_studio_draft(ctx, cur_bundle)
        if save_res.code == ErrorCode.STALE_DATA:
            srv_rv = (save_res.details or {}).get("server_row_version") if isinstance(save_res.details, dict) else None
            return (
                False,
                None,
                no,
                no,
                no,
                no,
                no,
                no,
                no,
                no,
                True,
                render_stale_conflict_body(save_res.message or "Bản nháp đã thay đổi trên phiên khác.", srv_rv),
                [toast_error(save_res.message or "Xung đột phiên bản bản nháp.")],
            )
        if not save_res.ok or saved is None:
            return no, alert_box(title="Không lưu được bản nháp trước khi phát hành", message=save_res.message or "Lỗi.", tone="crit"), no, no, no, no, no, no, no, no, False, no, no
        cur_bundle = saved

    active_bundle, pub_err = publish_from_studio(ctx, cur_bundle, change_note=change_note or "")
    if pub_err or active_bundle is None:
        return no, alert_box(title="Không phát hành được mô hình", message=pub_err or "Kiểm tra lại điều kiện phát hành.", tone="crit"), no, no, no, no, no, no, no, no, False, no, no

    ver_no = int((active_bundle.get("version") or {}).get("version_no") or 1)
    z = float(zoom or 1.0)
    return (
        False,
        None,
        active_bundle,
        False,
        None,
        render_studio_header(active_bundle, dirty=False),
        render_explorer_panel(active_bundle, selection=None, query=exp_q or ""),
        render_canvas_panel(active_bundle, selection=None, zoom=z),
        render_properties_panel(active_bundle, selection=None),
        render_status_bar(active_bundle, dirty=False),
        False,
        no,
        [toast_success(f"Đã phát hành phiên bản v{ver_no} (ACTIVE).")],
    )


@callback(
    Output("rms-bundle-store", "data", allow_duplicate=True),
    Output("rms-dirty-store", "data", allow_duplicate=True),
    Output("rms-selection-store", "data", allow_duplicate=True),
    Output("rms-header-wrap", "children", allow_duplicate=True),
    Output("rms-explorer-body", "children", allow_duplicate=True),
    Output("rms-canvas-wrap", "children", allow_duplicate=True),
    Output("rms-properties-body", "children", allow_duplicate=True),
    Output("rms-status-wrap", "children", allow_duplicate=True),
    Output("rms-studio-notif", "sendNotifications", allow_duplicate=True),
    Input("rms-new-draft-btn", "n_clicks"),
    State("rms-bundle-store", "data"),
    State("rms-explorer-search", "value"),
    State("rms-zoom-store", "data"),
    prevent_initial_call=True,
)
def handle_create_new_draft(
    n_clicks: int | None,
    bundle: dict[str, Any] | None,
    exp_q: str | None,
    zoom: float | None,
) -> tuple[Any, ...]:
    if not n_clicks or not bundle:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    model_id = int((bundle.get("model") or {}).get("id") or 0)
    res = open_or_create_draft(ctx, model_id)
    no = dash.no_update
    if not res.ok or not res.data:
        return no, no, no, no, no, no, no, no, [toast_error(res.message or "Không tạo được bản nháp mới.")]
    new_bundle = res.data
    z = float(zoom or 1.0)
    return (
        new_bundle,
        False,
        None,
        render_studio_header(new_bundle, dirty=False),
        render_explorer_panel(new_bundle, selection=None, query=exp_q or ""),
        render_canvas_panel(new_bundle, selection=None, zoom=z),
        render_properties_panel(new_bundle, selection=None),
        render_status_bar(new_bundle, dirty=False),
        [toast_success("Đã mở bản nháp mới để chỉnh sửa.")],
    )


__all__ = [
    "MENU_CODE",
    "agg_options_for_field",
    "auto_layout_star_schema",
    "build_calculated_ast_from_form",
    "build_publish_preview",
    "build_relationship_connectors",
    "compute_canvas_fit",
    "layout",
    "load_studio_bundle",
    "publish_from_studio",
    "render_canvas_panel",
    "render_explorer_panel",
    "render_properties_panel",
    "render_publish_modal_body",
    "render_source_picker_list",
    "render_stale_conflict_body",
    "render_status_bar",
    "render_studio_header",
    "render_validation_drawer_body",
    "resolve_validation_issue_selection",
    "run_full_model_validation",
    "run_relationship_tier2_profile",
    "save_field_properties",
    "save_measure_from_studio",
    "save_rls_policy_from_studio",
    "save_studio_draft",
    "save_table_properties",
    "table_box",
]
