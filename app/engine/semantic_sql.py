"""SQL Compiler cho Semantic Query Planner (Task 108 Bước 3).

Biên dịch ``ResolvedSemanticPlan`` (đã duyệt ở Bước 2) thành SQL read-only
cho Oracle hoặc SQLite. Nguyên tắc bảo mật:

- Mọi tên bảng/cột/alias chỉ lấy từ whitelist metadata trong ``plan`` (index
  bảng/field/measure) và đi qua ``quote_identifier`` — không có tên nào từ
  input thô của browser lọt vào SQL text.
- Mọi giá trị (filter, CONST, username, role, scope) chỉ đi qua bind param
  ``:b0``, ``:b1``, ... — không bao giờ nối chuỗi giá trị vào SQL.
- SQL cuối luôn qua ``sql_guard.check_report_sql``; lỗi guard -> fail-closed
  bằng ``SQL_NOT_ALLOWED`` thay vì trả SQL về cho service chạy.
- RLS V1 đọc quyền từ snapshot server-side (``username``/``roles``/``is_admin``/
  ``org_scopes``) do service truyền vào — intent không mang thông tin quyền.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, NoReturn

from app.engine.semantic_planner import ResolvedFilter, ResolvedMeasure, ResolvedSemanticPlan
from app.engine.sql_dialect import (
    Dialect,
    date_part_expr,
    paged_sql,
    quote_identifier,
    safe_divide,
    top_limit_sql,
)
from app.engine.sql_guard import check_report_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_model import AST_ALL_OPS
from app.schemas.semantic_query import SemanticQueryIntent, SemanticQueryPlan

# Múi giờ Việt Nam (UTC+7 cố định, tương thích cả Windows lẫn Linux không cần gói tzdata).
_VN_TZ = timezone(timedelta(hours=7))
_MAX_AST_DEPTH = 8


def _fail(code: ErrorCode, message: str) -> NoReturn:
    raise ServiceError(code, message)


class _Binder:
    """Cấp bind param ``:b0``, ``:b1``, ... theo thứ tự xuất hiện kèm kiểu nguồn tùy chọn."""

    def __init__(self) -> None:
        self.binds: dict[str, Any] = {}
        self.bind_types: dict[str, str] = {}
        self._counter = 0

    def add(self, value: Any, data_type: str | None = None) -> str:
        name = f"b{self._counter}"
        self._counter += 1
        self.binds[name] = value
        if data_type:
            self.bind_types[name] = str(data_type).upper()
        return f":{name}"


class _Compiler:
    def __init__(
        self,
        resolved: ResolvedSemanticPlan,
        intent: SemanticQueryIntent,
        *,
        username: str,
        roles: list[str],
        is_admin: bool,
        org_scopes: dict[str, str | None],
        dialect: Dialect,
        preview_max_rows: int,
        chart_max_points: int,
        now: datetime | None,
    ) -> None:
        self.plan = resolved
        self.intent = intent
        self.username = username
        self.roles = roles
        self.is_admin = is_admin
        self.org_scopes = org_scopes
        self.dialect = dialect
        self.preview_max_rows = preview_max_rows
        self.chart_max_points = chart_max_points
        self.now = now
        self.binder = _Binder()
        self.warnings: list[str] = list(resolved.warnings)
        self.alias_by_table: dict[int, str] = {tid: f"t{i}" for i, tid in enumerate(resolved.tables_used)}

    # -- định danh ---------------------------------------------------------
    def _table_sql(self, table_id: int) -> str:
        table = self.plan.table_index.get(table_id)
        if table is None:
            _fail(ErrorCode.MODEL_INVALID, f"Bảng #{table_id} không có trong mô hình đã duyệt.")
        obj = quote_identifier(table.source_object, self.dialect)
        if self.dialect == "ORACLE" and table.source_owner:
            return f"{quote_identifier(table.source_owner, self.dialect)}.{obj}"
        return obj

    def _col(self, table_id: int, column: str) -> str:
        alias = self.alias_by_table.get(table_id)
        if alias is None:
            _fail(ErrorCode.MODEL_INVALID, f"Bảng #{table_id} không có trong cây join.")
        return f"{alias}.{quote_identifier(column, self.dialect)}"

    def _field_col(self, field_id: int) -> str:
        field = self.plan.field_index.get(int(field_id))
        if field is None:
            _fail(ErrorCode.MODEL_INVALID, f"Trường #{field_id} không có trong mô hình đã duyệt.")
        return self._col(field.table_id, field.source_column)

    # -- SELECT -----------------------------------------------------------
    def _dim_expr(self, dim: Any) -> str:
        col = self._col(dim.table_id, dim.source_column)
        if dim.date_part is not None:
            return date_part_expr(col, str(dim.date_part), self.dialect)
        return col

    def _measure_sql(self, measure: ResolvedMeasure, visiting: frozenset[int]) -> str:
        if measure.measure_id is not None and measure.expr is not None:
            return self._compile_ast(measure.expr, visiting, depth=0)
        if measure.measure_id is not None and measure.base_field_id is None:
            _fail(ErrorCode.MODEL_INVALID, f"Measure '{measure.code}' thiếu trường gốc.")
        base_id = measure.base_field_id
        if base_id is None:
            _fail(ErrorCode.MODEL_INVALID, f"Measure '{measure.code}' thiếu trường gốc.")
        col = self._field_col(int(base_id))
        agg = str(measure.aggregation or "NONE").upper()
        if agg in ("NONE", ""):
            return col
        if agg == "COUNT_DISTINCT":
            return f"COUNT(DISTINCT {col})"
        if agg in ("SUM", "COUNT", "AVG", "MIN", "MAX"):
            return f"{agg}({col})"
        _fail(ErrorCode.SQL_NOT_ALLOWED, f"Hàm tổng hợp '{agg}' không nằm trong danh sách cho phép.")

    def _compile_ast(self, expr: Any, visiting: frozenset[int], depth: int) -> str:
        if depth > _MAX_AST_DEPTH:
            _fail(ErrorCode.VALIDATION_ERROR, "Biểu thức Measure vượt quá độ sâu cho phép (tối đa 8 cấp).")
        if not isinstance(expr, dict):
            _fail(ErrorCode.SQL_NOT_ALLOWED, "Biểu thức Measure phải là cấu trúc JSON AST hợp lệ.")
        op = str(expr.get("op") or "").upper()
        if op not in AST_ALL_OPS:
            _fail(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử '{op}' không nằm trong danh sách cho phép.")
        if op == "FIELD":
            fid = expr.get("field_id")
            if not isinstance(fid, int):
                _fail(ErrorCode.VALIDATION_ERROR, "FIELD trong biểu thức thiếu field_id.")
            return self._field_col(int(fid))
        if op == "MEASURE":
            mid = expr.get("measure_id")
            if not isinstance(mid, int):
                _fail(ErrorCode.VALIDATION_ERROR, "MEASURE trong biểu thức thiếu measure_id.")
            if int(mid) in visiting:
                _fail(ErrorCode.MODEL_INVALID, "Measure tham chiếu vòng nhau.")
            ref = self.plan.measure_index.get(int(mid))
            if ref is None:
                _fail(ErrorCode.MODEL_INVALID, f"MEASURE #{mid} không có trong mô hình đã duyệt.")
            return self._measure_sql(ref, visiting | {int(mid)})
        if op == "CONST":
            value = expr.get("value")
            if value is None:
                return "NULL"
            if not isinstance(value, (int, float, str, bool)):
                _fail(ErrorCode.VALIDATION_ERROR, "Hằng số CONST trong biểu thức không hợp lệ.")
            # bool -> 1/0 để bind được cả Oracle (oracledb) lẫn SQLite.
            if isinstance(value, bool):
                return self.binder.add(1 if value else 0)
            return self.binder.add(value)
        if op in ("SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX"):
            arg = expr.get("arg")
            if arg is None:
                _fail(ErrorCode.VALIDATION_ERROR, f"Hàm {op} thiếu tham số 'arg'.")
            inner = self._compile_ast(arg, visiting, depth + 1)
            if op == "COUNT_DISTINCT":
                return f"COUNT(DISTINCT {inner})"
            return f"{op}({inner})"
        if op in ("ADD", "SUB", "MUL", "DIV", "DIVIDE"):
            parts: list[Any] = []
            if "left" in expr and "right" in expr:
                parts = [expr["left"], expr["right"]]
            elif isinstance(expr.get("args"), list):
                parts = list(expr["args"])
            else:
                _fail(ErrorCode.VALIDATION_ERROR, f"Phép toán {op} cần đủ 'left'/'right' hoặc 'args'.")
            if len(parts) < 2:
                _fail(ErrorCode.VALIDATION_ERROR, f"Phép toán {op} cần ít nhất 2 toán hạng.")
            compiled = [self._compile_ast(p, visiting, depth + 1) for p in parts]
            if op in ("DIV", "DIVIDE"):
                result = compiled[0]
                for nxt in compiled[1:]:
                    result = safe_divide(result, nxt)
                return result
            symbol = {"ADD": "+", "SUB": "-", "MUL": "*"}[op]
            return "(" + f" {symbol} ".join(compiled) + ")"
        if op == "ROUND":
            digits = expr.get("digits", 0)
            if not isinstance(digits, int) or isinstance(digits, bool) or not 0 <= digits <= 6:
                _fail(ErrorCode.VALIDATION_ERROR, "ROUND.digits phải là số nguyên từ 0 đến 6.")
            value = self._compile_ast(expr.get("value"), visiting, depth + 1)
            return f"ROUND({value}, {digits})"
        if op == "COALESCE":
            args = expr.get("args")
            if not isinstance(args, list) or len(args) < 2:
                _fail(ErrorCode.VALIDATION_ERROR, "COALESCE cần ít nhất 2 tham số.")
            compiled = [self._compile_ast(a, visiting, depth + 1) for a in args]
            return f"COALESCE({', '.join(compiled)})"
        if op == "CASE":
            branches = expr.get("branches")
            if not isinstance(branches, list) or not branches:
                _fail(ErrorCode.VALIDATION_ERROR, "CASE cần ít nhất một nhánh when/then.")
            parts = ["CASE"]
            for branch in branches:
                if not isinstance(branch, dict) or "when" not in branch or "then" not in branch:
                    _fail(ErrorCode.VALIDATION_ERROR, "Mỗi nhánh CASE cần đủ 'when' và 'then'.")
                # `when` là biểu thức giá trị (không có toán tử so sánh trong
                # whitelist): biên dịch dạng truthy số để chạy cả Oracle/SQLite.
                when = self._compile_ast(branch["when"], visiting, depth + 1)
                then = self._compile_ast(branch["then"], visiting, depth + 1)
                parts.append(f"WHEN ({when} <> 0) THEN {then}")
            if expr.get("else") is not None:
                parts.append(f"ELSE {self._compile_ast(expr['else'], visiting, depth + 1)}")
            parts.append("END")
            return " ".join(parts)
        _fail(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử '{op}' không nằm trong danh sách cho phép.")

    # -- RELATIVE_DATE ----------------------------------------------------
    def _relative_range(self, value: str) -> tuple[datetime, datetime]:
        ref = self.now if self.now is not None else datetime.now(_VN_TZ)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=_VN_TZ)
        else:
            ref = ref.astimezone(_VN_TZ)
        today = ref.date()

        def at_midnight(d: date) -> datetime:
            return datetime.combine(d, time(0, 0))

        if value == "TODAY":
            return at_midnight(today), at_midnight(today + timedelta(days=1))
        if value == "YESTERDAY":
            return at_midnight(today - timedelta(days=1)), at_midnight(today)
        if value == "LAST_7_DAYS":
            return at_midnight(today - timedelta(days=6)), at_midnight(today + timedelta(days=1))
        if value == "THIS_MONTH":
            start = date(today.year, today.month, 1)
            if today.month == 12:
                end = date(today.year + 1, 1, 1)
            else:
                end = date(today.year, today.month + 1, 1)
            return at_midnight(start), at_midnight(end)
        if value == "LAST_MONTH":
            start = date(today.year, today.month, 1)
            if today.month == 1:
                prev = date(today.year - 1, 12, 1)
            else:
                prev = date(today.year, today.month - 1, 1)
            return at_midnight(prev), at_midnight(start)
        if value == "THIS_YEAR":
            return at_midnight(date(today.year, 1, 1)), at_midnight(date(today.year + 1, 1, 1))
        _fail(ErrorCode.VALIDATION_ERROR, f"Giá trị RELATIVE_DATE '{value}' không hỗ trợ.")

    # -- WHERE: RLS + filter ----------------------------------------------
    def _rls_predicates(self) -> list[str]:
        predicates: list[str] = []
        for policy in self.plan.resolved_rls:
            if self.is_admin and policy.admin_bypass:
                self.warnings.append(f"Chính sách RLS trên bảng #{policy.table_id} bỏ qua cho ADMIN (admin_bypass).")
                continue
            col = self._col(policy.table_id, policy.column_name)
            ptype = str(policy.policy_type).upper()
            if ptype == "OWNER_USERNAME":
                if not self.username:
                    _fail(
                        ErrorCode.RLS_SCOPE_MISSING,
                        "Không xác định được username để áp chính sách RLS OWNER_USERNAME.",
                    )
                predicates.append(f"{col} = {self.binder.add(self.username)}")
            elif ptype == "ROLE_LIST":
                if not self.roles:
                    predicates.append("1 = 0")
                    self.warnings.append(
                        f"Người dùng không có role nào nên không thấy dòng nào của bảng #{policy.table_id} (RLS ROLE_LIST)."
                    )
                else:
                    binds = ", ".join(self.binder.add(r) for r in self.roles)
                    predicates.append(f"{col} IN ({binds})")
            elif ptype == "ORG_SCOPE_HOOK":
                attr = (policy.scope_attr or "").strip()
                if not attr:
                    _fail(
                        ErrorCode.RLS_SCOPE_MISSING,
                        f"Chính sách RLS ORG_SCOPE_HOOK trên bảng #{policy.table_id} chưa gán scope (scope_attr trống).",
                    )
                scope = self.org_scopes.get(attr)
                if scope is None:
                    _fail(
                        ErrorCode.RLS_SCOPE_MISSING,
                        f"Chưa gán phạm vi tổ chức '{attr}' cho người dùng hiện tại.",
                    )
                if scope == "":
                    predicates.append("1 = 0")
                    self.warnings.append(
                        f"Phạm vi tổ chức '{attr}' rỗng nên truy vấn không trả dòng nào của bảng #{policy.table_id}."
                    )
                else:
                    predicates.append(f"{col} = {self.binder.add(scope)}")
            else:
                _fail(ErrorCode.MODEL_INVALID, f"Loại chính sách RLS '{policy.policy_type}' không hỗ trợ.")
        return predicates

    def _filter_predicate(self, flt: ResolvedFilter) -> str:
        col = self._col(flt.table_id, flt.source_column)
        op = str(flt.operator).upper()
        dtype = str(flt.data_type).upper()
        bind_dtype = dtype if dtype in ("DATE", "DATETIME") else None
        value = flt.value
        if op == "IS_NULL":
            return f"{col} IS NULL"
        if op == "RELATIVE_DATE":
            start, end = self._relative_range(str(value))
            return f"{col} >= {self.binder.add(start, dtype)} AND {col} < {self.binder.add(end, dtype)}"
        if op == "BETWEEN":
            if not isinstance(value, list) or len(value) != 2:
                _fail(ErrorCode.VALIDATION_ERROR, "BETWEEN cần value là danh sách đúng 2 phần tử.")
            if value[0] is None or value[1] is None:
                _fail(ErrorCode.VALIDATION_ERROR, "BETWEEN không chấp nhận đầu mút NULL.")
            return f"{col} BETWEEN {self.binder.add(value[0], bind_dtype)} AND {self.binder.add(value[1], bind_dtype)}"
        if op == "IN":
            if not isinstance(value, list) or not value:
                _fail(ErrorCode.VALIDATION_ERROR, "IN cần value là danh sách không rỗng.")
            for item in value:
                if item is None or isinstance(item, (list, dict)):
                    _fail(ErrorCode.VALIDATION_ERROR, "IN chỉ chấp nhận danh sách giá trị đơn.")
            binds = ", ".join(self.binder.add(v, bind_dtype) for v in value)
            return f"{col} IN ({binds})"
        if op == "LIKE_PREFIX":
            if not isinstance(value, str):
                _fail(ErrorCode.VALIDATION_ERROR, "LIKE_PREFIX cần value là chuỗi.")
            escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            return f"{col} LIKE {self.binder.add(escaped)} ESCAPE '\\'"
        if op in ("=", ">=", "<="):
            if value is None or isinstance(value, (list, dict)):
                _fail(ErrorCode.VALIDATION_ERROR, f"Toán tử {op} cần value là giá trị đơn.")
            return f"{col} {op} {self.binder.add(value, bind_dtype)}"
        _fail(ErrorCode.SQL_NOT_ALLOWED, f"Toán tử lọc '{op}' không nằm trong danh sách cho phép.")

    # -- biên dịch chính ----------------------------------------------------
    def compile(self) -> SemanticQueryPlan:
        plan = self.plan
        select_items: list[str] = []
        output_columns: list[dict[str, Any]] = []
        group_by: list[str] = []
        for dim in plan.selected_dims:
            expr = self._dim_expr(dim)
            select_items.append(f"{expr} AS {quote_identifier(dim.output_alias, self.dialect)}")
            output_columns.append(
                {
                    "name": dim.output_alias,
                    "label": dim.output_alias,
                    "data_type": "STRING" if dim.date_part is not None else dim.data_type,
                }
            )
            group_by.append(expr)
        for measure in plan.selected_measures:
            visiting: frozenset[int] = frozenset()
            if measure.measure_id is not None:
                visiting = frozenset({int(measure.measure_id)})
            expr = self._measure_sql(measure, visiting)
            select_items.append(f"{expr} AS {quote_identifier(measure.output_alias, self.dialect)}")
            output_columns.append(
                {
                    "name": measure.output_alias,
                    "label": measure.output_alias,
                    "data_type": self._measure_data_type(measure),
                }
            )

        root_id = plan.tables_used[0]
        sql_parts = [
            f"SELECT {', '.join(select_items)}",
            f"FROM {self._table_sql(root_id)} {self.alias_by_table[root_id]}",
        ]
        for step in plan.join_steps:
            keyword = "LEFT OUTER JOIN" if str(step.join_type).upper() == "LEFT_OUTER" else None
            if keyword is None:
                if str(step.join_type).upper() == "INNER":
                    keyword = "INNER JOIN"
                else:
                    _fail(ErrorCode.MODEL_INVALID, f"Kiểu join '{step.join_type}' không hỗ trợ.")
            child_alias = self.alias_by_table[step.child_table_id]
            parent_alias = self.alias_by_table[step.parent_table_id]
            sql_parts.append(
                f"{keyword} {self._table_sql(step.child_table_id)} {child_alias} "
                f"ON {parent_alias}.{quote_identifier(step.parent_column, self.dialect)} = "
                f"{child_alias}.{quote_identifier(step.child_column, self.dialect)}"
            )

        rls = self._rls_predicates()
        filters = [self._filter_predicate(f) for f in plan.resolved_filters]
        where = rls + filters
        if where:
            sql_parts.append("WHERE " + " AND ".join(where))
        if group_by:
            sql_parts.append("GROUP BY " + ", ".join(group_by))
        base_sql = " ".join(sql_parts)

        order_aliases_upper = {s.output_alias.upper() for s in plan.resolved_sorts}
        order_items = [
            f"{quote_identifier(s.output_alias, self.dialect)} {str(s.direction).upper()}" for s in plan.resolved_sorts
        ]
        # Tie-breaker ổn định cho phân trang: cột đầu ra đầu tiên chưa có trong
        # ORDER BY (kể cả khi sort đã ở cột đầu thì lấy cột tiếp theo).
        for col in output_columns:
            if str(col["name"]).upper() not in order_aliases_upper:
                order_items.append(f"{quote_identifier(str(col['name']), self.dialect)} ASC")
                break
        if order_items:
            sql_parts.append("ORDER BY " + ", ".join(order_items))

        # Giới hạn dòng: TABLE/KPI theo preview_max_rows; chart lấy thêm 1 dòng
        # để phát hiện truncated (BAR/LINE chỉ hiển thị chart_max_points điểm).
        fetch_extra_row = False
        if str(self.intent.visual_type).upper() in ("BAR", "LINE"):
            row_limit = min(int(self.intent.limit), int(self.chart_max_points) + 1)
            fetch_extra_row = row_limit == int(self.chart_max_points) + 1
        else:
            row_limit = min(int(self.intent.limit), int(self.preview_max_rows))
        sql = " ".join(sql_parts)
        if int(self.intent.offset) > 0:
            sql = paged_sql(sql, row_limit, int(self.intent.offset), self.dialect)
        else:
            sql = top_limit_sql(sql, row_limit, self.dialect)

        # Kiểm chứng cuối: SQL guard + khớp tập bind (fail-closed).
        ok, reason, discovered = check_report_sql(sql)
        if not ok:
            _fail(ErrorCode.SQL_NOT_ALLOWED, reason or "SQL sinh ra không được phép.")
        if set(discovered) != set(self.binder.binds):
            _fail(
                ErrorCode.SQL_NOT_ALLOWED,
                "SQL sinh ra chứa bind param không khớp với danh sách bind đã đăng ký.",
            )

        return SemanticQueryPlan(
            sql=sql,
            binds=dict(self.binder.binds),
            dialect=self.dialect,
            primary_fact_table_id=plan.primary_fact_table_id,
            tables_used=list(plan.tables_used),
            output_columns=output_columns,
            rls_applied=len(rls) > 0,
            warnings=self.warnings,
            row_limit=row_limit,
            fetch_extra_row=fetch_extra_row,
            base_sql=base_sql,
            bind_types=dict(self.binder.bind_types),
        )

    def _measure_data_type(self, measure: ResolvedMeasure) -> str:
        if measure.measure_id is not None and measure.expr is not None:
            return "NUMBER"
        agg = str(measure.aggregation or "NONE").upper()
        if agg in ("SUM", "AVG", "COUNT", "COUNT_DISTINCT"):
            return "NUMBER"
        if measure.base_field_id is not None:
            field = self.plan.field_index.get(int(measure.base_field_id))
            if field is not None:
                return field.data_type
        return "NUMBER"


def compile_semantic_query(
    resolved: ResolvedSemanticPlan,
    intent: SemanticQueryIntent,
    *,
    username: str,
    roles: list[str] | None = None,
    is_admin: bool = False,
    org_scopes: dict[str, str | None] | None = None,
    dialect: Dialect = "ORACLE",
    preview_max_rows: int = 500,
    chart_max_points: int = 50,
    now: datetime | None = None,
) -> SemanticQueryPlan:
    """Biên dịch kế hoạch đã duyệt thành SQL read-only + binds.

    ``username``/``roles``/``is_admin``/``org_scopes`` là snapshot quyền do
    service lấy từ ``ctx`` phía server — không lấy từ intent.
    """
    compiler = _Compiler(
        resolved,
        intent,
        username=username,
        roles=list(roles or []),
        is_admin=is_admin,
        org_scopes=dict(org_scopes or {}),
        dialect=dialect,
        preview_max_rows=preview_max_rows,
        chart_max_points=chart_max_points,
        now=now,
    )
    return compiler.compile()
