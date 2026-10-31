from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine.sql_dialect import quote_identifier, trunc_day
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ProfileSpec, TemplateConfig


def _render_field_db_expr(f_name: str, config: TemplateConfig) -> str:
    """Sinh biểu thức SQL Oracle cho trường logic hoặc trường phái sinh."""
    field_map = {f.name: f for f in config.fields}
    derived_map = {d.name: d for d in config.derived}

    if f_name in field_map:
        f = field_map[f_name]
        if not f.db:
            raise ServiceError(
                ErrorCode.COLUMN_NOT_FOUND,
                f"Trường '{f_name}' không có ánh xạ cột cơ sở dữ liệu.",
            )
        base = f'"src".{quote_identifier(f.db)}'

        # Áp dụng các phép chuẩn hóa text (trim, upper, lower, value_map)
        for op in f.norm:
            if op == "trim":
                base = f"TRIM({base})"
            elif op == "upper":
                base = f"UPPER({base})"
            elif op == "lower":
                base = f"LOWER({base})"
            elif isinstance(op, dict) and "value_map" in op:
                vmap = op["value_map"]
                cases = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in vmap.items())
                base = f"CASE {base} {cases} ELSE {base} END"
        return base

    if f_name in derived_map:
        d = derived_map[f_name]
        rendered_args = [
            _render_field_db_expr(arg, config) if isinstance(arg, str) and (arg in field_map or arg in derived_map) else str(arg)
            for arg in d.expr.args
        ]
        if d.expr.fn == "trunc_day":
            return f"TRUNC({rendered_args[0]})"
        if d.expr.fn == "trunc_month":
            return f"TRUNC({rendered_args[0]}, 'MM')"
        if d.expr.fn == "concat":
            return " || ".join(rendered_args)
        if d.expr.fn == "substr":
            if len(rendered_args) > 2:
                return f"SUBSTR({rendered_args[0]}, {rendered_args[1]}, {rendered_args[2]})"
            return f"SUBSTR({rendered_args[0]}, {rendered_args[1]})"
        if d.expr.fn == "coalesce":
            return f"COALESCE({', '.join(rendered_args)})"

    raise ServiceError(
        ErrorCode.COLUMN_NOT_FOUND,
        f"Không tìm thấy định nghĩa trường '{f_name}' trong template.",
    )


def build_source_sql(
    config: TemplateConfig,
    profile: ProfileSpec | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Sinh câu truy vấn SELECT nguồn cho Oracle dựa trên cấu hình template và tham số chạy."""
    db_source = config.db_source
    binds: dict[str, Any] = {}

    if db_source.kind == "table":
        # 1. Thu thập danh sách cột trong whitelist (các trường có mapping DB)
        db_cols: list[str] = []
        for f in config.fields:
            if f.db and f.db not in db_cols:
                db_cols.append(f.db)

        if not db_cols:
            raise ServiceError(
                ErrorCode.COLUMN_NOT_FOUND,
                "Không tìm thấy cột cơ sở dữ liệu nào được cấu hình trong template.",
            )

        if not db_source.table:
            raise ServiceError(ErrorCode.TABLE_NOT_FOUND, "Chưa chỉ định bảng nguồn trong cấu hình.")

        from_tbl = quote_identifier(db_source.table)
        select_clause = ",\n    ".join(quote_identifier(c) for c in db_cols)

        # 2. Xử lý mệnh đề WHERE từ filters và static_where
        conditions: list[str] = []

        # Filters động gắn với params
        for flt in db_source.filters:
            param_val = params.get(flt.param) if params else None
            # Nếu param rỗng và có cờ skip_if_empty thì bỏ qua
            if (param_val is None or (isinstance(param_val, str) and not param_val.strip())) and flt.skip_if_empty:
                continue

            col_expr = quote_identifier(flt.column)
            if flt.cast == "trunc_day":
                col_expr = trunc_day(col_expr)

            bind_key = flt.param
            binds[bind_key] = param_val
            conditions.append(f"{col_expr} {flt.op} :{bind_key}")

        # Filters tĩnh (static_where)
        for sflt in db_source.static_where:
            col_expr = quote_identifier(sflt.column)
            if sflt.op.lower() == "in":
                if isinstance(sflt.value, list):
                    items = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in sflt.value)
                    conditions.append(f"{col_expr} IN ({items})")
                else:
                    conditions.append(f"{col_expr} IN ({sflt.value})")
            elif sflt.value is None or str(sflt.value).lower() == "null":
                if sflt.op == "=":
                    conditions.append(f"{col_expr} IS NULL")
                elif sflt.op in ("!=", "<>"):
                    conditions.append(f"{col_expr} IS NOT NULL")
                else:
                    conditions.append(f"{col_expr} {sflt.op} NULL")
            elif isinstance(sflt.value, (int, float, Decimal)):
                conditions.append(f"{col_expr} {sflt.op} {sflt.value}")
            else:
                conditions.append(f"{col_expr} {sflt.op} '{sflt.value}'")

        base_sql = f"SELECT\n    {select_clause}\nFROM {from_tbl}"
        if conditions:
            base_sql += "\nWHERE " + "\n  AND ".join(conditions)

    elif db_source.kind == "sql":
        if not db_source.sql:
            raise ServiceError(ErrorCode.SQL_PARAM_MISSING, "Chưa chỉ định câu lệnh SQL nguồn.")
        base_sql = db_source.sql.strip().rstrip(";")
        if params:
            for p in db_source.params:
                if p.name in params:
                    binds[p.name] = params[p.name]
    else:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Loại nguồn '{db_source.kind}' không được hỗ trợ.")

    # 3. Áp dụng Pushdown Aggregate theo Profile nếu có
    if profile is not None and profile.aggregate and db_source.pushdown_aggregate:
        outer_selects: list[str] = []
        group_by_exprs: list[str] = []

        # Các trường Group By
        for g in profile.group_by:
            expr = _render_field_db_expr(g, config)
            outer_selects.append(f'{expr} AS "{g}"')
            group_by_exprs.append(expr)

        # Các trường Measures
        for m in profile.measures:
            if m.agg == "sum":
                if not m.field:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Measure SUM '{m.name}' thiếu trường dữ liệu.")
                f_expr = _render_field_db_expr(m.field, config)
                outer_selects.append(f'SUM({f_expr}) AS "{m.name}"')
            elif m.agg == "count":
                if m.field:
                    f_expr = _render_field_db_expr(m.field, config)
                    outer_selects.append(f'COUNT({f_expr}) AS "{m.name}"')
                else:
                    outer_selects.append(f'COUNT(*) AS "{m.name}"')
            elif m.agg == "count_distinct":
                if not m.field:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Measure COUNT_DISTINCT '{m.name}' thiếu trường dữ liệu.")
                f_expr = _render_field_db_expr(m.field, config)
                outer_selects.append(f'COUNT(DISTINCT {f_expr}) AS "{m.name}"')
            elif m.agg == "min":
                if not m.field:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Measure MIN '{m.name}' thiếu trường dữ liệu.")
                f_expr = _render_field_db_expr(m.field, config)
                outer_selects.append(f'MIN({f_expr}) AS "{m.name}"')
            elif m.agg == "max":
                if not m.field:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Measure MAX '{m.name}' thiếu trường dữ liệu.")
                f_expr = _render_field_db_expr(m.field, config)
                outer_selects.append(f'MAX({f_expr}) AS "{m.name}"')
            elif m.agg == "first_distinct":
                if not m.field:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Measure FIRST_DISTINCT '{m.name}' thiếu trường dữ liệu.")
                f_expr = _render_field_db_expr(m.field, config)
                outer_selects.append(f'MIN({f_expr}) AS "{m.name}"')
                outer_selects.append(f'COUNT(DISTINCT {f_expr}) AS "{m.name}__CNT_DIST"')

        # Thụt lề base_sql để bọc trong subquery
        indented_base = "\n".join(f"    {line}" for line in base_sql.splitlines())
        outer_select_str = ",\n    ".join(outer_selects)
        group_by_str = ",\n    ".join(group_by_exprs)

        final_sql = (
            f"SELECT\n    {outer_select_str}\n"
            f"FROM (\n{indented_base}\n) src\n"
            f"GROUP BY\n    {group_by_str}"
        )
        return final_sql, binds

    return base_sql, binds
