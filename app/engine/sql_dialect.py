from __future__ import annotations


def quote_identifier(ident: str) -> str:
    """Quote định danh bảng hoặc cột theo chuẩn Oracle (VD: "SCHEMA"."TABLE" hoặc "COLUMN")."""
    parts = ident.strip().split(".")
    quoted_parts = []
    for p in parts:
        clean = p.strip().strip('"')
        quoted_parts.append(f'"{clean}"')
    return ".".join(quoted_parts)


def trunc_day(expr: str) -> str:
    """Hàm cắt ngày giờ về 00:00:00 trên Oracle."""
    return f"TRUNC({expr})"


def trunc_month(expr: str) -> str:
    """Hàm cắt ngày về đầu tháng trên Oracle."""
    return f"TRUNC({expr}, 'MM')"


def concat(*exprs: str) -> str:
    """Hàm nối chuỗi trên Oracle dùng toán tử ||."""
    return " || ".join(exprs)


def substr(expr: str, start: int, length: int | None = None) -> str:
    """Hàm trích xuất chuỗi con trên Oracle."""
    if length is not None:
        return f"SUBSTR({expr}, {start}, {length})"
    return f"SUBSTR({expr}, {start})"


def coalesce(*exprs: str) -> str:
    """Hàm COALESCE trên Oracle."""
    return f"COALESCE({', '.join(exprs)})"
