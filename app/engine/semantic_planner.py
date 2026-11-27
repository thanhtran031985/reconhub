"""Graph Resolver cho Semantic Query Planner (Task 108 Bước 2).

Hàm thuần: nhận ``SemanticQueryIntent`` + bundle metadata (dạng trả về của
``load_version_bundle``) và trả ``ResolvedSemanticPlan``. Không đụng DB trực
tiếp, không sinh SQL (việc đó thuộc ``semantic_sql.py``).

Quy tắc đồ thị áp dụng ở đây (ghi rõ trong decisions.md D7):
- Chỉ version ``ACTIVE`` được chạy báo cáo; mọi trạng thái khác đều chặn bằng
  ``MODEL_VERSION_LOCKED`` (kể cả ``VALIDATED``).
- Field ``HIDDEN`` (``field_role == "HIDDEN"`` hoặc ``is_visible == False``)
  không được chọn/lọc/sắp xếp.
- ``RELATIONSHIP_LOOP``: quan hệ tự trỏ vào chính bảng đó, hoặc chu trình
  có hướng (đi theo chiều many -> one rồi quay lại bảng xuất phát).
- ``AMBIGUOUS_PATH``: >= 2 quan hệ active giữa cùng một cặp bảng, hoặc có
  2 đường join khác nhau từ root tới cùng một bảng (diamond).
"""

from __future__ import annotations

from collections import deque
from typing import Any, NoReturn

from pydantic import BaseModel, Field

from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_model import AST_ALL_OPS, allowed_aggregations_for
from app.schemas.semantic_query import SemanticQueryIntent

_MAX_AST_DEPTH = 8


class ResolvedJoinStep(BaseModel):
    """Một bước join trong cây join: parent (đã có trong cây) -> child (mới)."""

    rel_id: int
    rel_name: str
    parent_table_id: int
    child_table_id: int
    parent_column: str
    child_column: str
    cardinality: str
    join_type: str


class ResolvedDim(BaseModel):
    field_id: int
    table_id: int
    source_column: str
    data_type: str
    date_part: str | None = None
    output_alias: str


class ResolvedMeasure(BaseModel):
    measure_id: int | None = None
    code: str
    table_id: int
    base_field_id: int | None = None
    aggregation: str | None = None
    expr: dict[str, Any] | None = None
    output_alias: str


class ResolvedFilter(BaseModel):
    field_id: int
    table_id: int
    source_column: str
    data_type: str
    operator: str
    value: Any = None


class ResolvedRls(BaseModel):
    table_id: int
    column_name: str
    policy_type: str
    scope_attr: str | None = None
    admin_bypass: bool = True


class ResolvedSort(BaseModel):
    target_type: str
    ref_id: int
    direction: str
    output_alias: str


class ResolvedTable(BaseModel):
    """Metadata tối thiểu của một bảng để compiler đủ dữ kiện qualify tên."""

    table_id: int
    source_owner: str = ""
    source_object: str
    alias: str
    table_role: str


class ResolvedField(BaseModel):
    """Metadata tối thiểu của một field để compiler dịch AST FIELD."""

    field_id: int
    table_id: int
    source_column: str
    data_type: str


class ResolvedSemanticPlan(BaseModel):
    """Kế hoạch logic đã duyệt: cây join + các lựa chọn đã phân giải."""

    root_table: dict[str, Any]
    primary_fact_table_id: int | None = None
    tables_used: list[int] = Field(default_factory=list)
    join_steps: list[ResolvedJoinStep] = Field(default_factory=list)
    selected_dims: list[ResolvedDim] = Field(default_factory=list)
    selected_measures: list[ResolvedMeasure] = Field(default_factory=list)
    resolved_filters: list[ResolvedFilter] = Field(default_factory=list)
    resolved_rls: list[ResolvedRls] = Field(default_factory=list)
    resolved_sorts: list[ResolvedSort] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Index whitelist để compiler (Bước 3) tự chứa đủ metadata mà không cần
    # bundle gốc: mọi tên bảng/cột/measure nó chạm tới đều phải có trong này.
    table_index: dict[int, ResolvedTable] = Field(default_factory=dict)
    field_index: dict[int, ResolvedField] = Field(default_factory=dict)
    measure_index: dict[int, ResolvedMeasure] = Field(default_factory=dict)


def _fail(code: ErrorCode, message: str) -> NoReturn:
    raise ServiceError(code, message)


def _walk_ast_refs(
    expr: Any,
    fields_by_id: dict[int, dict[str, Any]],
    measures_by_id: dict[int, dict[str, Any]],
    depth: int = 0,
) -> tuple[set[int], set[int]]:
    """Duyệt AST Calculated Measure: trả (field_ids, measure_ids) và kiểm tra whitelist.

    Kiểm tra cả quy tắc aggregation: SUM/AVG chỉ áp dụng cho FIELD kiểu NUMBER.
    """
    if depth > _MAX_AST_DEPTH:
        _fail(ErrorCode.VALIDATION_ERROR, "Biểu thức Measure vượt quá độ sâu cho phép (tối đa 8 cấp).")
    if not isinstance(expr, dict):
        _fail(ErrorCode.SQL_NOT_ALLOWED, "Biểu thức Measure phải là cấu trúc JSON AST hợp lệ.")
    op = str(expr.get("op") or "").upper()
    if op not in AST_ALL_OPS:
        _fail(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử '{op}' không nằm trong danh sách cho phép.")
    if op == "FIELD":
        fid = expr.get("field_id")
        if not isinstance(fid, int) or fid not in fields_by_id:
            _fail(ErrorCode.MODEL_INVALID, "FIELD trong biểu thức không tồn tại trong mô hình.")
        return {int(fid)}, set()
    if op == "MEASURE":
        mid = expr.get("measure_id")
        if not isinstance(mid, int) or mid not in measures_by_id:
            _fail(ErrorCode.MODEL_INVALID, "MEASURE tham chiếu không tồn tại trong mô hình.")
        return set(), {int(mid)}
    if op == "CONST":
        return set(), set()
    if op in ("SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX"):
        arg = expr.get("arg")
        if arg is None:
            _fail(ErrorCode.VALIDATION_ERROR, f"Hàm {op} thiếu tham số 'arg'.")
        refs = _walk_ast_refs(arg, fields_by_id, measures_by_id, depth + 1)
        if op in ("SUM", "AVG") and isinstance(arg, dict) and str(arg.get("op") or "").upper() == "FIELD":
            f_meta = fields_by_id.get(int(arg["field_id"]))
            if f_meta and str(f_meta["data_type"]).upper() != "NUMBER":
                _fail(
                    ErrorCode.VALIDATION_ERROR,
                    f"Hàm {op} chỉ áp dụng cho trường kiểu NUMBER (trường '{f_meta['source_column']}' kiểu {f_meta['data_type']}).",
                )
        return refs
    if op in ("ADD", "SUB", "MUL", "DIV", "DIVIDE"):
        parts: list[Any] = []
        if "left" in expr and "right" in expr:
            parts = [expr["left"], expr["right"]]
        elif isinstance(expr.get("args"), list):
            parts = list(expr["args"])
        else:
            _fail(ErrorCode.VALIDATION_ERROR, f"Phép toán {op} cần đủ 'left'/'right' hoặc 'args'.")
        f_all: set[int] = set()
        m_all: set[int] = set()
        for part in parts:
            f_sub, m_sub = _walk_ast_refs(part, fields_by_id, measures_by_id, depth + 1)
            f_all |= f_sub
            m_all |= m_sub
        return f_all, m_all
    if op == "ROUND":
        digits = expr.get("digits", 0)
        if not isinstance(digits, int) or not 0 <= digits <= 6:
            _fail(ErrorCode.VALIDATION_ERROR, "ROUND.digits phải là số nguyên từ 0 đến 6.")
        return _walk_ast_refs(expr.get("value"), fields_by_id, measures_by_id, depth + 1)
    if op == "COALESCE":
        args = expr.get("args")
        if not isinstance(args, list) or len(args) < 2:
            _fail(ErrorCode.VALIDATION_ERROR, "COALESCE cần ít nhất 2 tham số.")
        f_all = set()
        m_all = set()
        for arg in args:
            f_sub, m_sub = _walk_ast_refs(arg, fields_by_id, measures_by_id, depth + 1)
            f_all |= f_sub
            m_all |= m_sub
        return f_all, m_all
    if op == "CASE":
        branches = expr.get("branches")
        if not isinstance(branches, list) or not branches:
            _fail(ErrorCode.VALIDATION_ERROR, "CASE cần ít nhất một nhánh when/then.")
        f_all = set()
        m_all = set()
        for branch in branches:
            if not isinstance(branch, dict) or "when" not in branch or "then" not in branch:
                _fail(ErrorCode.VALIDATION_ERROR, "Mỗi nhánh CASE cần đủ 'when' và 'then'.")
            for key in ("when", "then"):
                f_sub, m_sub = _walk_ast_refs(branch[key], fields_by_id, measures_by_id, depth + 1)
                f_all |= f_sub
                m_all |= m_sub
        if expr.get("else") is not None:
            f_sub, m_sub = _walk_ast_refs(expr["else"], fields_by_id, measures_by_id, depth + 1)
            f_all |= f_sub
            m_all |= m_sub
        return f_all, m_all
    _fail(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử '{op}' không nằm trong danh sách cho phép.")


def _measure_tables(
    measure: dict[str, Any],
    fields_by_id: dict[int, dict[str, Any]],
    measures_by_id: dict[int, dict[str, Any]],
    stack: tuple[int, ...] = (),
) -> set[int]:
    """Trả tập bảng mà một measure chạm tới; phát hiện vòng tham chiếu MEASURE."""
    mid = int(measure["id"])
    if mid in stack:
        names = " -> ".join(str(measures_by_id[m]["code"]) for m in (*stack, mid))
        _fail(ErrorCode.MODEL_INVALID, f"Measure tham chiếu vòng nhau: {names}.")
    if str(measure["measure_type"]).upper() == "SIMPLE":
        base_id = measure.get("base_field_id")
        if base_id is None or int(base_id) not in fields_by_id:
            _fail(
                ErrorCode.MODEL_INVALID,
                f"Measure '{measure['code']}' thiếu trường gốc hợp lệ.",
            )
        return {int(fields_by_id[int(base_id)]["table_id"])}
    field_ids, measure_ids = _walk_ast_refs(measure.get("expr_json"), fields_by_id, measures_by_id)
    tables = {int(fields_by_id[fid]["table_id"]) for fid in field_ids}
    for ref_id in sorted(measure_ids):
        tables |= _measure_tables(measures_by_id[ref_id], fields_by_id, measures_by_id, (*stack, mid))
    return tables


def _resolve_measure_entry(
    measure: dict[str, Any],
    fields_by_id: dict[int, dict[str, Any]],
    measures_by_id: dict[int, dict[str, Any]],
    output_alias: str,
) -> ResolvedMeasure:
    """Dựng ResolvedMeasure cho một measure đã lưu (dùng chung cho measure chọn
    và measure chỉ được tham chiếu qua AST)."""
    m_tables = _measure_tables(measure, fields_by_id, measures_by_id)
    anchor_table_id: int
    if measure.get("table_id") is not None:
        anchor_table_id = int(measure["table_id"])
    elif m_tables:
        anchor_table_id = sorted(m_tables)[0]
    else:
        _fail(
            ErrorCode.MODEL_INVALID,
            f"Measure '{measure['code']}' không gắn với bảng nào trong mô hình.",
        )
    return ResolvedMeasure(
        measure_id=int(measure["id"]),
        code=str(measure["code"]),
        table_id=anchor_table_id,
        base_field_id=measure.get("base_field_id"),
        aggregation=measure.get("aggregation"),
        expr=measure.get("expr_json"),
        output_alias=output_alias,
    )


def _collect_referenced_measure_ids(
    expr: Any,
    measures_by_id: dict[int, dict[str, Any]],
    seen: frozenset[int] = frozenset(),
) -> set[int]:
    """Thu thập mọi measure_id được tham chiếu (đệ quy) từ một AST expr."""
    if not isinstance(expr, dict):
        return set()
    found: set[int] = set()
    if str(expr.get("op") or "").upper() == "MEASURE" and isinstance(expr.get("measure_id"), int):
        mid = int(expr["measure_id"])
        if mid in seen:
            return set()  # vòng tham chiếu đã bị _measure_tables chặn trước đó
        found.add(mid)
        ref = measures_by_id.get(mid)
        if ref is not None and str(ref["measure_type"]).upper() == "CALCULATED":
            found |= _collect_referenced_measure_ids(ref.get("expr_json"), measures_by_id, seen | {mid})
    for value in expr.values():
        if isinstance(value, dict):
            found |= _collect_referenced_measure_ids(value, measures_by_id, seen)
        elif isinstance(value, list):
            for item in value:
                found |= _collect_referenced_measure_ids(item, measures_by_id, seen)
    return found


def _check_agg_allowed(agg: str, field: dict[str, Any]) -> None:
    """Khóa aggregation không hợp lệ theo DATA_TYPE (vd SUM trên STRING)."""
    allowed = allowed_aggregations_for(str(field["data_type"]))
    if str(agg).upper() not in allowed:
        _fail(
            ErrorCode.VALIDATION_ERROR,
            f"Hàm {str(agg).upper()} không áp dụng cho trường '{field['source_column']}' kiểu {field['data_type']} "
            f"(chỉ cho phép: {', '.join(allowed)}).",
        )


def _check_visible(field: dict[str, Any]) -> None:
    """Khóa field HIDDEN (theo field_role hoặc cờ is_visible)."""
    if str(field["field_role"]).upper() == "HIDDEN" or not field.get("is_visible", True):
        _fail(
            ErrorCode.VALIDATION_ERROR,
            f"Trường '{field['source_column']}' đã ẩn trong mô hình, không thể chọn/lọc/sắp xếp.",
        )


def _validate_filter_value(value: Any) -> None:
    """Giá trị lọc chỉ được là scalar hoặc danh sách scalar (chặn dict lồng nhau)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for item in value:
            if item is None or isinstance(item, (bool, int, float, str)):
                continue
            _fail(ErrorCode.VALIDATION_ERROR, "Giá trị lọc phải là số, chuỗi, hoặc danh sách các giá trị đơn giản.")
        return
    _fail(ErrorCode.VALIDATION_ERROR, "Giá trị lọc phải là số, chuỗi, hoặc danh sách các giá trị đơn giản.")


def resolve_semantic_plan(intent: SemanticQueryIntent, bundle: dict[str, Any]) -> ResolvedSemanticPlan:
    """Phân giải SemanticQueryIntent trên bundle metadata thành kế hoạch logic.

    Ném ServiceError với mã lỗi tiếng Việt khi intent vi phạm quy tắc ngữ nghĩa.
    """
    version = bundle.get("version") or {}
    if str(version.get("status") or "").upper() != "ACTIVE":
        _fail(
            ErrorCode.MODEL_VERSION_LOCKED,
            "Chỉ phiên bản mô hình đã phát hành (ACTIVE) mới được dùng để chạy báo cáo.",
        )

    tables: list[dict[str, Any]] = list(bundle.get("tables") or [])
    tables_by_id = {int(t["id"]): t for t in tables}
    fields_by_id: dict[int, dict[str, Any]] = {}
    for table in tables:
        for f in table.get("fields") or []:
            fields_by_id[int(f["id"])] = f
    measures_by_id = {int(m["id"]): m for m in (bundle.get("measures") or [])}

    # --- Phân giải dimensions ---
    selected_dims: list[ResolvedDim] = []
    for dim in intent.dimensions:
        field = fields_by_id.get(int(dim.field_id))
        if field is None:
            _fail(ErrorCode.MODEL_INVALID, f"Trường #{dim.field_id} không tồn tại trong mô hình.")
        _check_visible(field)
        selected_dims.append(
            ResolvedDim(
                field_id=int(dim.field_id),
                table_id=int(field["table_id"]),
                source_column=str(field["source_column"]),
                data_type=str(field["data_type"]),
                date_part=dim.date_part,
                output_alias=dim.alias or str(field["field_code"]),
            )
        )

    # --- Phân giải measures ---
    selected_measures: list[ResolvedMeasure] = []
    measure_tables: dict[int, set[int]] = {}
    for sel in intent.measures:
        if sel.measure_id is not None:
            measure = measures_by_id.get(int(sel.measure_id))
            if measure is None:
                _fail(ErrorCode.MODEL_INVALID, f"Measure #{sel.measure_id} không tồn tại trong mô hình.")
            m_tables = _measure_tables(measure, fields_by_id, measures_by_id)
            measure_tables[int(sel.measure_id)] = m_tables
            selected_measures.append(
                _resolve_measure_entry(measure, fields_by_id, measures_by_id, sel.alias or str(measure["code"]))
            )
        else:
            field = fields_by_id.get(int(sel.field_id or 0))
            if field is None:
                _fail(ErrorCode.MODEL_INVALID, f"Trường #{sel.field_id} không tồn tại trong mô hình.")
            _check_visible(field)
            _check_agg_allowed(str(sel.aggregation), field)
            selected_measures.append(
                ResolvedMeasure(
                    measure_id=None,
                    code=str(field["field_code"]),
                    table_id=int(field["table_id"]),
                    base_field_id=int(field["id"]),
                    aggregation=str(sel.aggregation),
                    expr=None,
                    output_alias=sel.alias or str(field["field_code"]),
                )
            )
    # Kiểm tra aggregation của SIMPLE measure đã lưu (phòng dữ liệu cũ/lệch)
    for res in selected_measures:
        if res.measure_id is not None:
            measure = measures_by_id[int(res.measure_id)]
            if str(measure["measure_type"]).upper() == "SIMPLE" and measure.get("base_field_id") is not None:
                base = fields_by_id.get(int(measure["base_field_id"]))
                if base is not None and measure.get("aggregation"):
                    _check_agg_allowed(str(measure["aggregation"]), base)

    # --- Phân giải filters ---
    resolved_filters: list[ResolvedFilter] = []
    for flt in intent.filters:
        field = fields_by_id.get(int(flt.field_id))
        if field is None:
            _fail(ErrorCode.MODEL_INVALID, f"Trường #{flt.field_id} không tồn tại trong mô hình.")
        _check_visible(field)
        _validate_filter_value(flt.value)
        if flt.operator == "RELATIVE_DATE" and str(field["data_type"]).upper() not in ("DATE", "DATETIME"):
            _fail(
                ErrorCode.VALIDATION_ERROR,
                f"RELATIVE_DATE chỉ áp dụng cho trường kiểu DATE/DATETIME (trường '{field['source_column']}' kiểu {field['data_type']}).",
            )
        resolved_filters.append(
            ResolvedFilter(
                field_id=int(flt.field_id),
                table_id=int(field["table_id"]),
                source_column=str(field["source_column"]),
                data_type=str(field["data_type"]),
                operator=str(flt.operator),
                value=flt.value,
            )
        )

    # --- Alias đầu ra không được trùng ---
    aliases = [d.output_alias for d in selected_dims] + [m.output_alias for m in selected_measures]
    if len(set(aliases)) != len(aliases):
        seen: set[str] = set()
        dup = ""
        for alias in aliases:
            if alias in seen:
                dup = alias
                break
            seen.add(alias)
        _fail(ErrorCode.VALIDATION_ERROR, f"Tên cột đầu ra '{dup}' bị trùng, hãy đặt alias khác nhau.")

    # --- Phân giải sorts (chỉ được sắp xếp theo trường/measure đã chọn) ---
    dim_alias_by_field = {d.field_id: d.output_alias for d in selected_dims}
    measure_alias_by_id = {m.measure_id: m.output_alias for m in selected_measures if m.measure_id is not None}
    resolved_sorts: list[ResolvedSort] = []
    for sort in intent.sorts:
        sort_alias: str | None
        if sort.target_type == "FIELD":
            sort_alias = dim_alias_by_field.get(int(sort.id))
            if sort_alias is None:
                _fail(
                    ErrorCode.VALIDATION_ERROR,
                    f"Sắp xếp theo trường #{sort.id} chưa được chọn làm dimension.",
                )
        else:
            sort_alias = measure_alias_by_id.get(int(sort.id))
            if sort_alias is None:
                _fail(
                    ErrorCode.VALIDATION_ERROR,
                    f"Sắp xếp theo measure #{sort.id} chưa được chọn.",
                )
        resolved_sorts.append(
            ResolvedSort(
                target_type=str(sort.target_type),
                ref_id=int(sort.id),
                direction=str(sort.direction),
                output_alias=str(sort_alias),
            )
        )

    # --- Tập bảng tham gia ---
    involved: set[int] = set()
    involved |= {d.table_id for d in selected_dims}
    for res in selected_measures:
        if res.measure_id is not None:
            involved |= measure_tables[int(res.measure_id)]
        else:
            involved.add(res.table_id)
    involved |= {f.table_id for f in resolved_filters}

    fact_tables = sorted(tid for tid in involved if str(tables_by_id[tid]["table_role"]).upper() == "FACT")
    primary_fact_table_id: int | None = None
    if len(fact_tables) >= 2:
        by_fact: dict[int, list[str]] = {}
        for res in selected_measures:
            m_tables = measure_tables[int(res.measure_id)] if res.measure_id is not None else {res.table_id}
            for tid in m_tables:
                if tid in fact_tables:
                    by_fact.setdefault(tid, []).append(res.output_alias)
        for rdim in selected_dims:
            if rdim.table_id in fact_tables:
                by_fact.setdefault(rdim.table_id, []).append(rdim.output_alias)
        parts = []
        for tid in fact_tables:
            table = tables_by_id[tid]
            grain = str(table.get("grain_desc") or ", ".join(table.get("grain_keys") or []) or "?")
            names = ", ".join(sorted(set(by_fact.get(tid, []))))
            parts.append(f"'{names}' thuộc Fact '{table['alias']}' (grain: {grain})")
        _fail(
            ErrorCode.MULTI_FACT_NOT_ALLOWED,
            "Không thể dùng 2 bảng Fact trong cùng một visual: "
            + "; ".join(parts)
            + ". V1 chỉ cho 1 Fact chính mỗi visual.",
        )
    if len(fact_tables) == 1:
        primary_fact_table_id = fact_tables[0]

    # --- Chọn root (anchor) ---
    if primary_fact_table_id is not None:
        root_table_id = primary_fact_table_id
    elif selected_measures:
        first = selected_measures[0]
        root_table_id = first.table_id
    else:
        root_table_id = selected_dims[0].table_id
    root_table = tables_by_id[root_table_id]

    # --- Đồ thị quan hệ active giữa các bảng tham gia ---
    rels = [r for r in (bundle.get("relationships") or []) if r.get("is_active")]
    fields_by_table_col: dict[tuple[int, str], dict[str, Any]] = {
        (int(t["id"]), str(f["source_column"]).upper()): f for t in tables for f in (t.get("fields") or [])
    }
    edges: list[dict[str, Any]] = []
    for rel in rels:
        from_id = int(rel["from_table_id"])
        to_id = int(rel["to_table_id"])
        if from_id not in involved or to_id not in involved:
            continue
        if from_id == to_id:
            _fail(
                ErrorCode.RELATIONSHIP_LOOP,
                f"Quan hệ '{rel['name']}' tự trỏ vào cùng một bảng '{tables_by_id[from_id]['alias']}'.",
            )
        if (from_id, str(rel["from_column"]).upper()) not in fields_by_table_col:
            _fail(
                ErrorCode.MODEL_INVALID,
                f"Quan hệ '{rel['name']}' trỏ tới cột không tồn tại: {tables_by_id[from_id]['alias']}.{rel['from_column']}.",
            )
        if (to_id, str(rel["to_column"]).upper()) not in fields_by_table_col:
            _fail(
                ErrorCode.MODEL_INVALID,
                f"Quan hệ '{rel['name']}' trỏ tới cột không tồn tại: {tables_by_id[to_id]['alias']}.{rel['to_column']}.",
            )
        edges.append(rel)

    pair_rels: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for rel in edges:
        a, b = int(rel["from_table_id"]), int(rel["to_table_id"])
        pair: tuple[int, int] = (a, b) if a <= b else (b, a)
        pair_rels.setdefault(pair, []).append(rel)
    for (t1, t2), dup_rels in pair_rels.items():
        if len(dup_rels) > 1:
            names = ", ".join(f"'{r['name']}'" for r in dup_rels)
            _fail(
                ErrorCode.AMBIGUOUS_PATH,
                f"Có {len(dup_rels)} quan hệ cùng kích hoạt giữa '{tables_by_id[t1]['alias']}' và "
                f"'{tables_by_id[t2]['alias']}' ({names}); hãy chỉ giữ 1 quan hệ active.",
            )

    # Chu trình có hướng (đi theo chiều many -> one rồi quay lại bảng xuất phát)
    directed_adj: dict[int, list[tuple[int, dict[str, Any]]]] = {tid: [] for tid in involved}
    for rel in edges:
        directed_adj[int(rel["from_table_id"])].append((int(rel["to_table_id"]), rel))
    color: dict[int, int] = {tid: 0 for tid in involved}  # 0=trắng, 1=xám, 2=đen
    cycle_rel: dict[str, Any] = {}

    def _dfs_directed(node: int) -> bool:
        color[node] = 1
        for nxt, rel in directed_adj.get(node, []):
            if color[nxt] == 1:
                cycle_rel.update(rel)
                return True
            if color[nxt] == 0 and _dfs_directed(nxt):
                return True
        color[node] = 2
        return False

    for tid in sorted(involved):
        if color[tid] == 0 and _dfs_directed(tid):
            _fail(
                ErrorCode.RELATIONSHIP_LOOP,
                f"Phát hiện vòng lặp quan hệ (loop) đi qua '{cycle_rel.get('name')}'.",
            )

    # --- BFS xây cây join từ root ---
    adjacency: dict[int, list[tuple[int, dict[str, Any]]]] = {tid: [] for tid in involved}
    for rel in edges:
        a, b = int(rel["from_table_id"]), int(rel["to_table_id"])
        adjacency[a].append((b, rel))
        adjacency[b].append((a, rel))
    visited: dict[int, int | None] = {root_table_id: None}
    parent_edge: dict[int, dict[str, Any] | None] = {root_table_id: None}
    order: list[int] = [root_table_id]
    queue: deque[int] = deque([root_table_id])
    join_steps: list[ResolvedJoinStep] = []
    while queue:
        node = queue.popleft()
        for neighbor, rel in adjacency.get(node, []):
            if neighbor not in visited:
                visited[neighbor] = node
                parent_edge[neighbor] = rel
                order.append(neighbor)
                queue.append(neighbor)
                if int(rel["from_table_id"]) == node:
                    parent_col, child_col = str(rel["from_column"]), str(rel["to_column"])
                else:
                    parent_col, child_col = str(rel["to_column"]), str(rel["from_column"])
                join_steps.append(
                    ResolvedJoinStep(
                        rel_id=int(rel["id"]),
                        rel_name=str(rel["name"]),
                        parent_table_id=node,
                        child_table_id=neighbor,
                        parent_column=parent_col,
                        child_column=child_col,
                        cardinality=str(rel["cardinality"]),
                        join_type=str(rel["join_type"]),
                    )
                )
            elif parent_edge.get(node) is rel or parent_edge.get(neighbor) is rel:
                continue  # cạnh cây nối node với cha/con của nó, không phải đường thứ 2
            else:
                # Cạnh tới bảng đã thăm mà không phải cạnh cây -> đường đi thứ 2
                other = parent_edge.get(neighbor)
                names = f"'{rel['name']}'"
                if other is not None:
                    names += f" và '{other['name']}'"
                _fail(
                    ErrorCode.AMBIGUOUS_PATH,
                    f"Có 2 đường join khác nhau từ '{root_table['alias']}' tới "
                    f"'{tables_by_id[neighbor]['alias']}' ({names}); hãy chỉ giữ 1 đường active.",
                )
    missing = sorted(involved - set(visited))
    if missing:
        names = ", ".join(f"'{tables_by_id[tid]['alias']}'" for tid in missing)
        _fail(
            ErrorCode.MODEL_INVALID,
            f"Không thể nối bảng {names} vào cây join từ '{root_table['alias']}': thiếu quan hệ active.",
        )

    # --- RLS áp dụng cho các bảng tham gia ---
    resolved_rls: list[ResolvedRls] = []
    for policy in bundle.get("rls_policies") or []:
        if not policy.get("is_active"):
            continue
        if int(policy["table_id"]) not in involved:
            continue
        resolved_rls.append(
            ResolvedRls(
                table_id=int(policy["table_id"]),
                column_name=str(policy["column_name"]),
                policy_type=str(policy["policy_type"]),
                scope_attr=policy.get("scope_attr"),
                admin_bypass=bool(policy.get("admin_bypass", True)),
            )
        )

    # --- Cảnh báo ---
    warnings: list[str] = []
    for tid in sorted(involved):
        if str(tables_by_id[tid]["table_role"]).upper() == "UNCLASSIFIED":
            warnings.append(f"Bảng '{tables_by_id[tid]['alias']}' chưa phân loại Role (UNCLASSIFIED).")
    for rflt in resolved_filters:
        field = fields_by_id[int(rflt.field_id)]
        if not field.get("is_filterable", True):
            warnings.append(f"Trường '{field['source_column']}' không đánh dấu Filterable nhưng vẫn dùng làm bộ lọc.")

    # --- Index whitelist cho compiler (Bước 3) ---
    referenced_measure_ids: set[int] = set()
    for res in selected_measures:
        if res.measure_id is not None:
            referenced_measure_ids.add(int(res.measure_id))
            src = measures_by_id[int(res.measure_id)]
            if str(src["measure_type"]).upper() == "CALCULATED":
                referenced_measure_ids |= _collect_referenced_measure_ids(src.get("expr_json"), measures_by_id)
    measure_index: dict[int, ResolvedMeasure] = {}
    for mid in sorted(referenced_measure_ids):
        src = measures_by_id[mid]
        measure_index[mid] = _resolve_measure_entry(src, fields_by_id, measures_by_id, str(src["code"]))
    table_index = {
        int(t["id"]): ResolvedTable(
            table_id=int(t["id"]),
            source_owner=str(t.get("source_owner") or ""),
            source_object=str(t["source_object"]),
            alias=str(t["alias"]),
            table_role=str(t["table_role"]),
        )
        for t in tables
    }
    field_index = {
        int(f["id"]): ResolvedField(
            field_id=int(f["id"]),
            table_id=int(f["table_id"]),
            source_column=str(f["source_column"]),
            data_type=str(f["data_type"]),
        )
        for f in fields_by_id.values()
    }

    return ResolvedSemanticPlan(
        root_table=root_table,
        primary_fact_table_id=primary_fact_table_id,
        tables_used=order,
        join_steps=join_steps,
        selected_dims=selected_dims,
        selected_measures=selected_measures,
        resolved_filters=resolved_filters,
        resolved_rls=resolved_rls,
        resolved_sorts=resolved_sorts,
        warnings=warnings,
        table_index=table_index,
        field_index=field_index,
        measure_index=measure_index,
    )
