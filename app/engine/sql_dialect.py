from __future__ import annotations

from typing import Literal

Dialect = Literal["ORACLE", "SQLITE"]

_DATE_PARTS = ("DAY", "MONTH", "QUARTER", "YEAR")


def _normalize_dialect(dialect: str) -> Dialect:
    """Chuẩn hóa tên dialect; ném ValueError với dialect lạ (chặn input lạ sớm)."""
    d = str(dialect or "").upper()
    if d not in ("ORACLE", "SQLITE"):
        raise ValueError(f"Dialect không hỗ trợ: {dialect!r} (chỉ ORACLE hoặc SQLITE).")
    return d  # type: ignore[return-value]


def quote_identifier(ident: str, dialect: str = "ORACLE") -> str:
    """Quote định danh bảng hoặc cột theo chuẩn Oracle (VD: "SCHEMA"."TABLE" hoặc "COLUMN").

    SQLite cũng chấp nhận dấu ngoặc kép nên cùng một dạng quote dùng được
    cho cả hai dialect; tham số ``dialect`` giữ chỗ cho khác biệt sau này.

    Dấu ``"`` nhúng trong tên được nhân đôi theo chuẩn SQL (``"A""B"``) để
    không thể phá quote — tên lạ từ metadata cũng không chèn được SQL.
    """
    _normalize_dialect(dialect)
    parts = ident.strip().split(".")
    quoted_parts = []
    for p in parts:
        clean = p.strip()
        if len(clean) >= 2 and clean.startswith('"') and clean.endswith('"'):
            clean = clean[1:-1]
        quoted_parts.append('"' + clean.replace('"', '""') + '"')
    return ".".join(quoted_parts)


def date_part_expr(expr: str, part: str, dialect: str) -> str:
    """Biểu thức cắt phần ngày ảo (Virtual Date Hierarchy) trả về chuỗi ISO thống nhất.

    DAY -> ``YYYY-MM-DD``, MONTH -> ``YYYY-MM``, QUARTER -> ``YYYY-Qn``,
    YEAR -> ``YYYY`` trên cả Oracle và SQLite (quyết định D6 task 108).
    """
    d = _normalize_dialect(dialect)
    p = str(part or "").upper()
    if p not in _DATE_PARTS:
        raise ValueError(f"Phần ngày không hỗ trợ: {part!r} (chỉ DAY, MONTH, QUARTER, YEAR).")
    if d == "ORACLE":
        if p == "DAY":
            return f"TO_CHAR({expr}, 'YYYY-MM-DD')"
        if p == "MONTH":
            return f"TO_CHAR({expr}, 'YYYY-MM')"
        if p == "QUARTER":
            return (
                f"CASE WHEN {expr} IS NULL THEN NULL "
                f"ELSE TO_CHAR({expr}, 'YYYY') || '-Q' || TO_CHAR({expr}, 'Q') END"
            )
        return f"TO_CHAR({expr}, 'YYYY')"
    if p == "DAY":
        return f"DATE({expr})"
    if p == "MONTH":
        return f"STRFTIME('%Y-%m', {expr})"
    if p == "QUARTER":
        return (
            f"CASE WHEN {expr} IS NULL THEN NULL ELSE "
            "PRINTF('%04d-Q%d', CAST(STRFTIME('%Y', "
            f"{expr}) AS INTEGER), "
            f"CAST((CAST(STRFTIME('%m', {expr}) AS INTEGER) + 2) / 3 AS INTEGER)) END"
        )
    return f"STRFTIME('%Y', {expr})"


def safe_divide(left_expr: str, right_expr: str) -> str:
    """Phép chia an toàn: chia 0 trả NULL nhờ NULLIF (dùng cho DIVIDE/DIV).

    Nhân ``1.0`` để ép chia thập phân trên SQLite (chia 2 số nguyên trên
    SQLite ra số nguyên, khác Oracle NUMBER luôn ra thập phân).
    """
    return f"((({left_expr}) * 1.0) / NULLIF(({right_expr}), 0))"


def paged_sql(sql: str, limit: int, offset: int, dialect: str) -> str:
    """Thêm phân trang: Oracle dùng OFFSET/FETCH, SQLite dùng LIMIT/OFFSET."""
    d = _normalize_dialect(dialect)
    if int(limit) < 1:
        raise ValueError("limit phân trang phải >= 1.")
    if int(offset) < 0:
        raise ValueError("offset phân trang phải >= 0.")
    if d == "ORACLE":
        return f"{sql} OFFSET {int(offset)} ROWS FETCH NEXT {int(limit)} ROWS ONLY"
    return f"{sql} LIMIT {int(limit)} OFFSET {int(offset)}"


def top_limit_sql(sql: str, limit: int, dialect: str) -> str:
    """Giới hạn Top-N: Oracle dùng FETCH FIRST, SQLite dùng LIMIT."""
    d = _normalize_dialect(dialect)
    if int(limit) < 1:
        raise ValueError("limit phải >= 1.")
    if d == "ORACLE":
        return f"{sql} FETCH FIRST {int(limit)} ROWS ONLY"
    return f"{sql} LIMIT {int(limit)}"


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
