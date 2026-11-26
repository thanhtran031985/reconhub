"""Panel Properties & Measure Studio AST builders cho Model Studio (Task 107 Bước 4)."""

from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from app.schemas.semantic_model import (
    AST_ARITH_OPS,
    CARDINALITIES,
    FIELD_ROLES,
    JOIN_TYPES,
    MEASURE_AGGREGATIONS,
    RLS_POLICY_TYPES,
    SENSITIVITIES,
    TABLE_ROLES,
    allowed_aggregations_for,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.status_chip import status_chip

ROLE_LABELS: dict[str, str] = {
    "FACT": "Fact (Bảng sự kiện)",
    "DIMENSION": "Dimension (Bảng chiều)",
    "BRIDGE": "Bridge (Bảng cầu nối)",
    "UNCLASSIFIED": "Chưa phân loại",
}

FIELD_ROLE_LABELS: dict[str, str] = {
    "DIMENSION": "Dimension (Thuộc tính phân nhóm)",
    "MEASURE_CANDIDATE": "Measure Candidate (Số liệu)",
    "KEY": "Key (Khóa nối bảng)",
    "HIDDEN": "Hidden (Ẩn khỏi Report Studio)",
}

AGG_LABELS: dict[str, str] = {
    "NONE": "Không tổng hợp (NONE)",
    "SUM": "SUM — Tính tổng",
    "AVG": "AVG — Trung bình",
    "MIN": "MIN — Giá trị nhỏ nhất",
    "MAX": "MAX — Giá trị lớn nhất",
    "COUNT": "COUNT — Đếm dòng",
    "COUNT_DISTINCT": "COUNT_DISTINCT — Đếm giá trị duy nhất",
}

SENS_LABELS: dict[str, str] = {
    "NORMAL": "Bình thường (NORMAL)",
    "INTERNAL": "Nội bộ (INTERNAL)",
    "RESTRICTED": "Hạn chế / Nhạy cảm (RESTRICTED)",
}


def agg_options_for_field(fld: dict[str, Any]) -> list[dict[str, str]]:
    """Danh sách phép tổng hợp hợp lệ theo DATA_TYPE (khóa SUM cho non-numeric)."""
    dtype = str(fld.get("data_type") or "STRING").upper()
    allowed = allowed_aggregations_for(dtype)
    return [{"label": AGG_LABELS.get(a, a), "value": a} for a in allowed]


def _operand_ast(
    kind: str | None,
    field_id: str | int | None,
    agg: str | None,
    measure_id: str | int | None,
    const_val: str | float | int | None,
) -> dict[str, Any]:
    k = str(kind or "FIELD_AGG").upper()
    if k == "MEASURE" and measure_id not in (None, ""):
        return {"op": "MEASURE", "measure_id": int(str(measure_id))}
    if k == "CONST" and const_val not in (None, ""):
        try:
            num = float(const_val)
            val: int | float = int(num) if num.is_integer() else num
        except (TypeError, ValueError):
            val = 0
        return {"op": "CONST", "value": val}
    fid = int(str(field_id)) if field_id not in (None, "") else 0
    norm_agg = str(agg or "SUM").upper()
    if norm_agg == "NONE":
        return {"op": "FIELD", "field_id": fid}
    return {"op": norm_agg, "arg": {"op": "FIELD", "field_id": fid}}


def build_calculated_ast_from_form(
    *,
    op: str,
    left_kind: str | None,
    left_field_id: str | int | None,
    left_agg: str | None,
    left_measure_id: str | int | None,
    left_const: str | float | int | None,
    right_kind: str | None = None,
    right_field_id: str | int | None = None,
    right_agg: str | None = None,
    right_measure_id: str | int | None = None,
    right_const: str | float | int | None = None,
    digits: int | None = 2,
) -> dict[str, Any]:
    """Dựng JSON AST whitelist an toàn từ form UI Calculated Measure."""
    norm_op = str(op or "DIVIDE").upper()
    left_node = _operand_ast(left_kind, left_field_id, left_agg, left_measure_id, left_const)
    if norm_op == "ROUND":
        d = max(0, min(6, int(digits if digits is not None else 2)))
        return {"op": "ROUND", "value": left_node, "digits": d}
    right_node = _operand_ast(right_kind, right_field_id, right_agg, right_measure_id, right_const)
    if norm_op == "COALESCE":
        return {"op": "COALESCE", "args": [left_node, right_node]}
    if norm_op not in AST_ARITH_OPS:
        norm_op = "DIVIDE"
    return {"op": norm_op, "left": left_node, "right": right_node}


def format_ast_preview(expr: Any, bundle: dict[str, Any]) -> str:
    """Chuyển AST JSON sang chuỗi công thức dễ đọc (chỉ để hiển thị)."""
    if not isinstance(expr, dict):
        return "—"
    fld_map: dict[int, str] = {}
    for t in bundle.get("tables") or []:
        alias = str(t.get("alias") or t.get("source_object") or "")
        for f in t.get("fields") or []:
            fld_map[int(f["id"])] = f"{alias}.{f['source_column']}"
    meas_map = {int(m["id"]): str(m["code"]) for m in (bundle.get("measures") or [])}

    op = str(expr.get("op") or "").upper()
    if op == "FIELD":
        return fld_map.get(int(expr.get("field_id") or 0), f"FIELD#{expr.get('field_id')}")
    if op == "MEASURE":
        return meas_map.get(int(expr.get("measure_id") or 0), f"MEAS#{expr.get('measure_id')}")
    if op == "CONST":
        return str(expr.get("value"))
    if "arg" in expr:
        return f"{op}({format_ast_preview(expr.get('arg'), bundle)})"
    if op == "ROUND":
        return f"ROUND({format_ast_preview(expr.get('value'), bundle)}, {expr.get('digits', 0)})"
    if "left" in expr and "right" in expr:
        return f"{op}({format_ast_preview(expr['left'], bundle)}, {format_ast_preview(expr['right'], bundle)})"
    if isinstance(expr.get("args"), list):
        return f"{op}(" + ", ".join(format_ast_preview(a, bundle) for a in expr["args"]) + ")"
    return op or "—"


def render_table_properties(bundle: dict[str, Any], tbl: dict[str, Any]) -> Any:
    """Form cấu hình Table Properties, Fact Grain & khung RLS metadata V1."""
    tid = int(tbl["id"])
    fields = list(tbl.get("fields") or [])
    col_opts = [{"label": f"{f['source_column']} ({f.get('data_type')})", "value": str(f["source_column"])} for f in fields]
    date_opts = [
        {"label": str(f["source_column"]), "value": str(f["source_column"])}
        for f in fields
        if str(f.get("data_type") or "").upper() in ("DATE", "DATETIME")
    ]
    role = str(tbl.get("table_role") or "UNCLASSIFIED").upper()
    policies = [p for p in (bundle.get("rls_policies") or []) if int(p["table_id"]) == tid]

    rls_rows = (
        [
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Stack(
                            [
                                dmc.Text(f"{p['column_name']} · {p['policy_type']}", size="xs", fw=600, className="rh-code"),
                                dmc.Text(
                                    f"Thuộc tính: {p.get('scope_attr') or '—'} · Admin bypass: {'Có' if p.get('admin_bypass') else 'Không'}",
                                    size="xs",
                                    c="dimmed",
                                ),
                            ],
                            gap=2,
                        ),
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:trash-2", width=13),
                            id={"type": "rms-prop-rls-del", "id": int(p["id"])},
                            variant="subtle",
                            color="red",
                            size="sm",
                            **{"aria-label": f"Xóa RLS {p['column_name']}"},
                        ),
                    ],
                    justify="space-between",
                    align="center",
                ),
                withBorder=True,
                p=6,
                radius="sm",
            )
            for p in policies
        ]
        if policies
        else [dmc.Text("Chưa có cấu hình RLS V1 cho bảng này.", size="xs", c="dimmed")]
    )

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Thuộc tính bảng", fw=700, size="sm"),
                    dmc.Badge(tbl.get("object_type") or "TABLE", size="xs", variant="outline"),
                ],
                justify="space-between",
            ),
            dmc.Text(f"{tbl.get('source_owner') or 'main'}.{tbl.get('source_object')}", size="xs", c="dimmed", className="rh-code"),
            html.Div(id="rms-prop-tbl-alert"),
            dmc.TextInput(id="rms-prop-tbl-alias", label="Alias trên model", value=str(tbl.get("alias") or ""), size="xs", className="rh-code"),
            dmc.TextInput(id="rms-prop-tbl-name", label="Tên hiển thị", value=str(tbl.get("display_name") or ""), size="xs"),
            dmc.Select(
                id="rms-prop-tbl-role",
                label="Vai trò bảng (Table Role)",
                data=[{"label": ROLE_LABELS.get(r, r), "value": r} for r in TABLE_ROLES],
                value=role,
                allowDeselect=False,
                size="xs",
            ),
            dmc.TextInput(
                id="rms-prop-tbl-grain-desc",
                label="Mô tả Grain (bắt buộc cho Fact)",
                placeholder="VD: 1 dòng = 1 dòng hóa đơn chi tiết",
                value=str(tbl.get("grain_desc") or ""),
                withAsterisk=(role == "FACT"),
                size="xs",
            ),
            dmc.MultiSelect(
                id="rms-prop-tbl-grain-keys",
                label="Khóa Grain (Grain Keys)",
                data=col_opts,
                value=[str(k) for k in (tbl.get("grain_keys") or [])],
                searchable=True,
                size="xs",
            ),
            dmc.Select(
                id="rms-prop-tbl-date-fld",
                label="Cột ngày mặc định",
                data=date_opts,
                value=tbl.get("default_date_field"),
                clearable=True,
                searchable=True,
                size="xs",
            ),
            dmc.Switch(
                id="rms-prop-tbl-hidden",
                label="Ẩn bảng khỏi cây báo cáo",
                checked=bool(tbl.get("is_hidden")),
                size="xs",
            ),
            dmc.Group(
                [
                    button_primary("Lưu bảng", id="rms-prop-tbl-save", icon="lucide:save", size="xs"),
                    button_subtle("+ Measure", id="rms-prop-tbl-new-meas", icon="lucide:sigma", size="xs"),
                    button_danger("Xóa bảng", id={"type": "rms-prop-remove-btn", "kind": "table"}, size="xs"),
                ],
                justify="space-between",
                gap="xs",
            ),
            dmc.Divider(my="xs", label="Phân quyền dòng dữ liệu (RLS V1 Metadata)", labelPosition="left"),
            dmc.Stack(rls_rows, gap=4),
            dmc.Select(id="rms-prop-rls-col", label="Cột phân quyền", data=col_opts, size="xs", searchable=True),
            dmc.Select(
                id="rms-prop-rls-type",
                label="Loại chính sách",
                data=[{"label": p, "value": p} for p in RLS_POLICY_TYPES],
                value="OWNER_USERNAME",
                allowDeselect=False,
                size="xs",
            ),
            dmc.TextInput(
                id="rms-prop-rls-scope",
                label="Thuộc tính ngữ cảnh (Scope Attr)",
                placeholder="VD: username, org_code",
                value="username",
                size="xs",
            ),
            dmc.Group(
                [
                    dmc.Switch(id="rms-prop-rls-bypass", label="Admin bỏ qua RLS", checked=True, size="xs"),
                    dmc.Switch(id="rms-prop-rls-active", label="Kích hoạt", checked=True, size="xs"),
                ],
                justify="space-between",
            ),
            button_subtle("Thêm / cập nhật RLS", id="rms-prop-rls-save", icon="lucide:shield", size="xs"),
        ],
        p="sm",
        gap="xs",
    )


def render_field_properties(bundle: dict[str, Any], tbl: dict[str, Any], fld: dict[str, Any]) -> Any:
    """Form cấu hình Field Properties, quy tắc Aggregation và Virtual Date Hierarchy."""
    fid = int(fld["id"])
    dtype = str(fld.get("data_type") or "STRING").upper()
    sort_opts = [
        {"label": f"{f['source_column']} ({f.get('display_name')})", "value": str(f["id"])}
        for f in (tbl.get("fields") or [])
        if int(f["id"]) != fid
    ]
    is_date_type = dtype in ("DATE", "DATETIME")
    agg_opts = agg_options_for_field(fld)
    cur_agg = str(fld.get("default_agg") or "NONE").upper()
    if cur_agg not in [o["value"] for o in agg_opts]:
        cur_agg = agg_opts[0]["value"] if agg_opts else "NONE"

    _ = bundle
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Thuộc tính trường dữ liệu", fw=700, size="sm"),
                    dmc.Badge(dtype, size="xs", variant="light", className="rh-code"),
                ],
                justify="space-between",
            ),
            dmc.Text(f"{tbl.get('alias')}.{fld.get('source_column')}", size="xs", c="dimmed", className="rh-code"),
            html.Div(id="rms-prop-fld-alert"),
            dmc.TextInput(id="rms-prop-fld-code", label="Mã logic (Field Code)", value=str(fld.get("field_code") or ""), size="xs", className="rh-code"),
            dmc.TextInput(id="rms-prop-fld-name", label="Tên hiển thị", value=str(fld.get("display_name") or ""), size="xs"),
            dmc.Select(
                id="rms-prop-fld-role",
                label="Vai trò trường",
                data=[{"label": FIELD_ROLE_LABELS.get(r, r), "value": r} for r in FIELD_ROLES],
                value=str(fld.get("field_role") or "DIMENSION"),
                allowDeselect=False,
                size="xs",
            ),
            dmc.Select(
                id="rms-prop-fld-agg",
                label="Phép tổng hợp mặc định",
                description="Khóa SUM trên kiểu chữ / ngày / boolean." if dtype != "NUMBER" else None,
                data=agg_opts,
                value=cur_agg,
                allowDeselect=False,
                size="xs",
            ),
            dmc.TextInput(
                id="rms-prop-fld-format",
                label="Định dạng hiển thị (Format Mask)",
                placeholder="VD: #,##0 hoặc DD/MM/YYYY",
                value=str(fld.get("format_mask") or ""),
                size="xs",
                className="rh-code",
            ),
            dmc.TextInput(id="rms-prop-fld-folder", label="Thư mục nhóm (Folder)", value=str(fld.get("folder") or ""), size="xs"),
            dmc.Select(
                id="rms-prop-fld-sortby",
                label="Sắp xếp theo cột (Sort By Field)",
                data=sort_opts,
                value=str(fld["sort_by_field_id"]) if fld.get("sort_by_field_id") else None,
                clearable=True,
                searchable=True,
                size="xs",
            ),
            dmc.Select(
                id="rms-prop-fld-sens",
                label="Độ nhạy dữ liệu",
                data=[{"label": SENS_LABELS.get(s, s), "value": s} for s in SENSITIVITIES],
                value=str(fld.get("sensitivity") or "NORMAL"),
                allowDeselect=False,
                size="xs",
            ),
            dmc.Switch(id="rms-prop-fld-visible", label="Hiển thị trong Report Studio", checked=bool(fld.get("is_visible", True)), size="xs"),
            dmc.Switch(id="rms-prop-fld-filterable", label="Cho phép dùng làm bộ lọc", checked=bool(fld.get("is_filterable", True)), size="xs"),
            dmc.Switch(
                id="rms-prop-fld-date-hier",
                label="Phân cấp ngày ảo (Ngày / Tháng / Quý / Năm)",
                checked=bool(fld.get("enable_date_hierarchy")),
                disabled=not is_date_type,
                size="xs",
            ),
            dmc.Textarea(id="rms-prop-fld-desc", label="Mô tả", value=str(fld.get("description") or ""), minRows=2, size="xs"),
            button_primary("Lưu thuộc tính cột", id="rms-prop-fld-save", icon="lucide:save", size="xs"),
        ],
        p="sm",
        gap="xs",
    )


def render_rel_validation_result(val_data: dict[str, Any] | None) -> Any:
    """Hiển thị kết quả kiểm tra Tầng 1/Tầng 2 cho quan hệ."""
    if not val_data:
        return dmc.Text("Chưa chạy kiểm tra mẫu dữ liệu cho quan hệ này.", size="xs", c="dimmed")
    st = str(val_data.get("status") or "PASS").upper()
    tone = "crit" if st == "ERROR" else ("warn" if st == "WARNING" else "ok")
    checks = list(val_data.get("checks") or [])
    metrics = val_data.get("metrics") or {}
    lines = [
        dmc.Text(f"[{c.get('status')}] {c.get('message')}", size="xs")
        for c in checks
    ]
    if metrics:
        lines.append(
            dmc.Text(
                f"Mẫu: {metrics.get('sample_rows', 0)} dòng · Độ phủ join: {float(metrics.get('join_coverage', 1.0)) * 100:.1f}%",
                size="xs",
                fw=600,
            )
        )
    return alert_box(
        title=f"Kết quả kiểm tra: {st}",
        message=dmc.Stack(lines, gap=2) if lines else str(val_data.get("message") or st),
        tone=tone,
    )


def render_relationship_properties(bundle: dict[str, Any], rel: dict[str, Any]) -> Any:
    """Form cấu hình Relationship Properties + Validation Tầng 1 & Tầng 2."""
    tables = list(bundle.get("tables") or [])
    tbl_opts = [{"label": f"{t.get('alias') or t.get('source_object')} ({t.get('table_role')})", "value": str(t["id"])} for t in tables]
    from_tid = int(rel["from_table_id"])
    to_tid = int(rel["to_table_id"])

    def _cols_of(tid: int) -> list[dict[str, str]]:
        tbl = next((t for t in tables if int(t["id"]) == tid), None)
        if not tbl:
            return []
        return [{"label": f"{f['source_column']} ({f.get('data_type')})", "value": str(f["source_column"])} for f in tbl.get("fields") or []]

    val_data = rel.get("validation")
    if isinstance(val_data, dict) and "checks" not in val_data and "datatype_compat" in val_data:
        dc = val_data["datatype_compat"]
        val_data = {"status": dc.get("status", "PASS"), "checks": [{"status": dc.get("status"), "message": dc.get("message")}]}

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Thuộc tính quan hệ", fw=700, size="sm"),
                    status_chip(str(rel.get("validation_status") or "UNCHECKED"), size="xs"),
                ],
                justify="space-between",
            ),
            html.Div(id="rms-prop-rel-alert"),
            dmc.TextInput(id="rms-prop-rel-name", label="Tên quan hệ", value=str(rel.get("name") or ""), size="xs"),
            dmc.Select(id="rms-prop-rel-from-tbl", label="Bảng nguồn (From / Nhiều *)", data=tbl_opts, value=str(from_tid), allowDeselect=False, size="xs"),
            dmc.Select(id="rms-prop-rel-from-col", label="Cột nguồn", data=_cols_of(from_tid), value=str(rel.get("from_column") or ""), allowDeselect=False, size="xs", searchable=True),
            dmc.Select(id="rms-prop-rel-to-tbl", label="Bảng đích (To / Một 1)", data=tbl_opts, value=str(to_tid), allowDeselect=False, size="xs"),
            dmc.Select(id="rms-prop-rel-to-col", label="Cột đích", data=_cols_of(to_tid), value=str(rel.get("to_column") or ""), allowDeselect=False, size="xs", searchable=True),
            dmc.Select(
                id="rms-prop-rel-card",
                label="Bội số (Cardinality)",
                data=[
                    {"label": "Nhiều (*) → Một (1)", "value": "MANY_TO_ONE" if c == "MANY_TO_ONE" else c}
                    if c == "MANY_TO_ONE"
                    else {"label": "Một (1) → Một (1)", "value": c}
                    for c in CARDINALITIES
                ],
                value=str(rel.get("cardinality") or "MANY_TO_ONE"),
                allowDeselect=False,
                size="xs",
            ),
            dmc.Select(
                id="rms-prop-rel-join",
                label="Kiểu Join mặc định",
                data=[{"label": "LEFT OUTER JOIN" if j == "LEFT_OUTER" else "INNER JOIN", "value": j} for j in JOIN_TYPES],
                value=str(rel.get("join_type") or "LEFT_OUTER"),
                allowDeselect=False,
                size="xs",
            ),
            dmc.Text("Lọc chéo: Single (Bảng chiều lọc Bảng sự kiện)", size="xs", c="dimmed"),
            dmc.Switch(id="rms-prop-rel-active", label="Kích hoạt (Active)", checked=bool(rel.get("is_active", True)), size="xs"),
            dmc.Group(
                [
                    button_subtle("Kiểm tra quan hệ", id="rms-prop-rel-val1", icon="lucide:git-compare", size="xs"),
                    button_subtle("Kiểm tra dữ liệu mẫu", id="rms-prop-rel-val2", icon="lucide:database-zap", size="xs"),
                ],
                gap="xs",
            ),
            html.Div(render_rel_validation_result(val_data), id="rms-prop-rel-val-result"),
            dmc.Group(
                [
                    button_primary("Áp dụng thay đổi", id="rms-prop-rel-save", icon="lucide:check", size="xs"),
                    button_danger("Xóa quan hệ", id={"type": "rms-prop-remove-btn", "kind": "relationship"}, size="xs"),
                ],
                justify="space-between",
                gap="xs",
            ),
        ],
        p="sm",
        gap="xs",
    )


def render_measure_studio(
    bundle: dict[str, Any],
    *,
    measure_id: int | None = None,
    table_id: int | None = None,
) -> Any:
    """Measure Studio: tạo/sửa Simple Measure & Structured AST Calculated Measure."""
    tables = list(bundle.get("tables") or [])
    measures = list(bundle.get("measures") or [])
    target = next((m for m in measures if measure_id is not None and int(m["id"]) == int(measure_id)), None)

    tbl_opts = [{"label": str(t.get("alias") or t.get("source_object")), "value": str(t["id"])} for t in tables]
    all_field_opts = [
        {"label": f"{t.get('alias')}.{f['source_column']} ({f.get('data_type')})", "value": str(f["id"])}
        for t in tables
        for f in (t.get("fields") or [])
    ]
    other_meas_opts = [
        {"label": f"{m['code']} — {m['name']}", "value": str(m["id"])}
        for m in measures
        if target is None or int(m["id"]) != int(target["id"])
    ]

    cur_type = str(target.get("measure_type") or "SIMPLE") if target else "SIMPLE"
    expr = target.get("expr_json") if target and isinstance(target.get("expr_json"), dict) else {}
    cur_op = str(expr.get("op") or "DIVIDE")
    if cur_op not in ("DIVIDE", "ADD", "SUB", "MUL", "ROUND", "COALESCE"):
        cur_op = "DIVIDE"

    raw_args = expr.get("args")
    expr_args: list[Any] = raw_args if isinstance(raw_args, list) else []
    left_raw = expr.get("value") if cur_op == "ROUND" else (expr.get("left") or (expr_args[0] if expr_args else {}))
    right_raw = expr.get("right") or (expr_args[1] if len(expr_args) > 1 else {})

    def _unpack_operand(node: Any) -> tuple[str, str | None, str, str | None, str]:
        if not isinstance(node, dict):
            return "FIELD_AGG", all_field_opts[0]["value"] if all_field_opts else None, "SUM", None, "1"
        nop = str(node.get("op") or "").upper()
        if nop == "MEASURE":
            return "MEASURE", None, "SUM", str(node.get("measure_id")), "1"
        if nop == "CONST":
            return "CONST", None, "SUM", None, str(node.get("value", 1))
        if nop == "FIELD":
            return "FIELD_AGG", str(node.get("field_id")), "NONE", None, "1"
        arg = node.get("arg") or {}
        return "FIELD_AGG", str(arg.get("field_id")) if isinstance(arg, dict) and arg.get("field_id") else None, nop or "SUM", None, "1"

    lk, lfld, lagg, lmeas, lconst = _unpack_operand(left_raw)
    rk, rfld, ragg, rmeas, rconst = _unpack_operand(right_raw)
    sel_tid = str(target["table_id"]) if target and target.get("table_id") else (str(table_id) if table_id else (tbl_opts[0]["value"] if tbl_opts else None))

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Measure Studio", fw=700, size="sm"),
                    dmc.Badge("Chỉnh sửa" if target else "Tạo mới", size="xs", variant="light", color="purple"),
                ],
                justify="space-between",
            ),
            html.Div(id="rms-prop-meas-alert"),
            dmc.TextInput(
                id="rms-prop-meas-code",
                label="Mã Measure",
                placeholder="VD: TOTAL_REVENUE",
                value=str(target.get("code") or "") if target else "",
                withAsterisk=True,
                size="xs",
                className="rh-code",
            ),
            dmc.TextInput(
                id="rms-prop-meas-name",
                label="Tên hiển thị",
                placeholder="VD: Tổng doanh thu",
                value=str(target.get("name") or "") if target else "",
                withAsterisk=True,
                size="xs",
            ),
            dmc.Select(id="rms-prop-meas-table", label="Bảng sở hữu (tùy chọn)", data=tbl_opts, value=sel_tid, clearable=True, size="xs"),
            dmc.SegmentedControl(
                id="rms-prop-meas-type",
                data=[
                    {"label": "Simple Measure", "value": "SIMPLE"},
                    {"label": "Calculated (AST)", "value": "CALCULATED"},
                ],
                value=cur_type,
                size="xs",
                fullWidth=True,
            ),
            dmc.Stack(
                [
                    dmc.Select(
                        id="rms-prop-meas-base-fld",
                        label="Trường dữ liệu gốc",
                        data=all_field_opts,
                        value=str(target["base_field_id"]) if target and target.get("base_field_id") else (all_field_opts[0]["value"] if all_field_opts else None),
                        searchable=True,
                        size="xs",
                    ),
                    dmc.Select(
                        id="rms-prop-meas-agg",
                        label="Phép tổng hợp",
                        data=[{"label": a, "value": a} for a in MEASURE_AGGREGATIONS],
                        value=str(target.get("aggregation") or "SUM") if target else "SUM",
                        size="xs",
                    ),
                ],
                id="rms-prop-meas-simple-box",
                gap="xs",
                style={"display": "flex" if cur_type == "SIMPLE" else "none"},
            ),
            dmc.Stack(
                [
                    dmc.Select(
                        id="rms-prop-meas-op",
                        label="Phép toán AST chuẩn hóa",
                        data=[
                            {"label": "DIVIDE (Chia an toàn)", "value": "DIVIDE"},
                            {"label": "ADD (+)", "value": "ADD"},
                            {"label": "SUB (-)", "value": "SUB"},
                            {"label": "MUL (*)", "value": "MUL"},
                            {"label": "ROUND (Làm tròn)", "value": "ROUND"},
                            {"label": "COALESCE (Thay NULL)", "value": "COALESCE"},
                        ],
                        value=cur_op,
                        size="xs",
                    ),
                    dmc.Text("Toán hạng trái / Giá trị", size="xs", fw=600),
                    dmc.Group(
                        [
                            dmc.Select(
                                id="rms-prop-meas-lkind",
                                data=[
                                    {"label": "Field + Agg", "value": "FIELD_AGG"},
                                    {"label": "Measure", "value": "MEASURE"},
                                    {"label": "Hằng số", "value": "CONST"},
                                ],
                                value=lk,
                                size="xs",
                                style={"flex": 1},
                            ),
                            dmc.Select(
                                id="rms-prop-meas-lagg",
                                data=[{"label": a, "value": a} for a in MEASURE_AGGREGATIONS],
                                value=lagg,
                                size="xs",
                                w=110,
                            ),
                        ],
                        gap="xs",
                    ),
                    dmc.Select(id="rms-prop-meas-lfld", label="Trường (Trái)", data=all_field_opts, value=lfld, searchable=True, size="xs"),
                    dmc.Select(id="rms-prop-meas-lmeas", label="Hoặc Measure (Trái)", data=other_meas_opts, value=lmeas, clearable=True, size="xs"),
                    dmc.TextInput(id="rms-prop-meas-lconst", label="Hoặc Hằng số (Trái)", value=lconst, size="xs", className="rh-code"),
                    dmc.Text("Toán hạng phải / Chữ số ROUND", size="xs", fw=600),
                    dmc.Group(
                        [
                            dmc.Select(
                                id="rms-prop-meas-rkind",
                                data=[
                                    {"label": "Field + Agg", "value": "FIELD_AGG"},
                                    {"label": "Measure", "value": "MEASURE"},
                                    {"label": "Hằng số", "value": "CONST"},
                                ],
                                value=rk,
                                size="xs",
                                style={"flex": 1},
                            ),
                            dmc.Select(
                                id="rms-prop-meas-ragg",
                                data=[{"label": a, "value": a} for a in MEASURE_AGGREGATIONS],
                                value=ragg,
                                size="xs",
                                w=110,
                            ),
                        ],
                        gap="xs",
                    ),
                    dmc.Select(id="rms-prop-meas-rfld", label="Trường (Phải)", data=all_field_opts, value=rfld, searchable=True, size="xs"),
                    dmc.Select(id="rms-prop-meas-rmeas", label="Hoặc Measure (Phải)", data=other_meas_opts, value=rmeas, clearable=True, size="xs"),
                    dmc.TextInput(id="rms-prop-meas-rconst", label="Hoặc Hằng số (Phải)", value=rconst, size="xs", className="rh-code"),
                    dmc.NumberInput(
                        id="rms-prop-meas-digits",
                        label="Số lẻ ROUND (0-6)",
                        value=int(expr.get("digits", 2)) if cur_op == "ROUND" else 2,
                        min=0,
                        max=6,
                        size="xs",
                    ),
                    dmc.Paper(
                        dmc.Text(
                            format_ast_preview(expr, bundle) if expr else "DIVIDE(...)",
                            id="rms-prop-meas-preview",
                            size="xs",
                            className="rh-code",
                        ),
                        withBorder=True,
                        p="xs",
                        radius="sm",
                        bg="var(--surface)",
                    ),
                ],
                id="rms-prop-meas-calc-box",
                gap="xs",
                style={"display": "flex" if cur_type == "CALCULATED" else "none"},
            ),
            dmc.TextInput(
                id="rms-prop-meas-format",
                label="Định dạng (Format Mask)",
                value=str(target.get("format_mask") or "#,##0") if target else "#,##0",
                size="xs",
                className="rh-code",
            ),
            dmc.TextInput(
                id="rms-prop-meas-folder",
                label="Thư mục (Folder)",
                value=str(target.get("folder") or "") if target else "",
                size="xs",
            ),
            dmc.Group(
                [
                    button_primary("Lưu Measure", id="rms-prop-meas-save", icon="lucide:save", size="xs"),
                    button_danger("Xóa Measure", id={"type": "rms-prop-remove-btn", "kind": "measure"}, size="xs", disabled=(target is None)),
                ],
                justify="space-between",
                gap="xs",
            ),
        ],
        p="sm",
        gap="xs",
    )


def render_empty_properties() -> Any:
    return dmc.Stack(
        [
            empty_state(
                title="Chưa chọn đối tượng",
                description="Chọn Bảng, Cột, Quan hệ hoặc Measure trong Explorer / Canvas để chỉnh thuộc tính.",
                action=button_primary("Tạo Measure mới", id="rms-prop-empty-new-meas-btn", icon="lucide:sigma", size="xs"),
                icon="lucide:sliders-horizontal",
            )
        ],
        p="sm",
    )
