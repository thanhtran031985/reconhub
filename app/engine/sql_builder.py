from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine.sql_dialect import quote_identifier, trunc_day
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ProfileSpec, TemplateConfig


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

        sql = f"SELECT\n    {select_clause}\nFROM {from_tbl}"
        if conditions:
            sql += "\nWHERE " + "\n  AND ".join(conditions)

    elif db_source.kind == "sql":
        if not db_source.sql:
            raise ServiceError(ErrorCode.SQL_PARAM_MISSING, "Chưa chỉ định câu lệnh SQL nguồn.")
        sql = db_source.sql.strip().rstrip(";")
        if params:
            for p in db_source.params:
                if p.name in params:
                    binds[p.name] = params[p.name]
    else:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Loại nguồn '{db_source.kind}' không được hỗ trợ.")

    return sql, binds
