from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select

from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.services.source_conn import open_source_connection

CACHE_TTL_SECONDS = 600.0  # 10 phút

_TABLES_CACHE: dict[tuple[int, str, str], tuple[float, list[dict[str, str]]]] = {}
_COLUMNS_CACHE: dict[tuple[int, str, str], tuple[float, list[dict[str, Any]]]] = {}


def invalidate_catalog_cache(ds_id: int | None = None) -> None:
    """Xóa bộ đệm danh mục bảng và cột."""
    if ds_id is None:
        _TABLES_CACHE.clear()
        _COLUMNS_CACHE.clear()
    else:
        for k in list(_TABLES_CACHE.keys()):
            if k[0] == ds_id:
                _TABLES_CACHE.pop(k, None)
        for k_col in list(_COLUMNS_CACHE.keys()):
            if k_col[0] == ds_id:
                _COLUMNS_CACHE.pop(k_col, None)


def _resolve_schema(ds_id: int, schema: str | None) -> str:
    """Xác định schema đích (ưu tiên tham số, nếu không lấy DEFAULT_SCHEMA hoặc USERNAME)."""
    if schema and schema.strip():
        return schema.strip().upper()

    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_data_source.c.DEFAULT_SCHEMA, recon_data_source.c.USERNAME).where(
                    recon_data_source.c.ID == ds_id
                )
            )
            .mappings()
            .first()
        )

    if row:
        target = row["DEFAULT_SCHEMA"] or row["USERNAME"]
        if target:
            return str(target).upper()

    return ""


def list_tables(
    ds_id: int,
    schema: str | None = None,
    q: str | None = None,
    object_type: str | None = None,
) -> list[dict[str, str]]:
    """Liệt kê danh sách bảng và view trong schema Oracle hoặc SQLite với cache 10 phút.

    Trả về danh sách: [{"name": str, "type": "TABLE" | "VIEW", "schema": str}]
    object_type: None (cả bảng và view, hành vi cũ), "TABLE" hoặc "VIEW"
    (task 22 — picker riêng từng loại).
    """
    if object_type is not None and object_type not in ("TABLE", "VIEW"):
        raise ValueError("object_type phải là None, 'TABLE' hoặc 'VIEW'")

    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = conn.execute(
            select(recon_data_source.c.DB_TYPE).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()

    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        from sqlalchemy import text
        with engine.connect() as conn:
            types = ("table",) if object_type == "TABLE" else ("view",) if object_type == "VIEW" else ("table", "view")
            types_str = ", ".join(f"'{t}'" for t in types)
            query = f"SELECT name, UPPER(type) FROM sqlite_master WHERE type IN ({types_str}) AND name NOT LIKE 'sqlite_%'"
            if q:
                term = q.strip().upper()
                query += f" AND UPPER(name) LIKE '%{term}%'"
            query += " ORDER BY name"
            raw_rows = conn.execute(text(query)).fetchall()
            return [{"name": str(r[0]), "type": str(r[1]), "schema": "main"} for r in raw_rows]

    resolved_schema = _resolve_schema(ds_id, schema)
    cache_key = (ds_id, resolved_schema, object_type or "")
    now = time.monotonic()

    cached = _TABLES_CACHE.get(cache_key)
    if cached is not None:
        cached_at, tables = cached
        if now - cached_at < CACHE_TTL_SECONDS:
            if q:
                term = q.strip().upper()
                return [t for t in tables if term in t["name"].upper()]
            return tables

    ora_conn = open_source_connection(ds_id)
    try:
        cursor = ora_conn.cursor()
        if object_type == "TABLE":
            sql = """
                SELECT TABLE_NAME, 'TABLE' AS TABLE_TYPE
                FROM ALL_TABLES
                WHERE OWNER = :schema
                ORDER BY TABLE_NAME
            """
        elif object_type == "VIEW":
            sql = """
                SELECT VIEW_NAME AS TABLE_NAME, 'VIEW' AS TABLE_TYPE
                FROM ALL_VIEWS
                WHERE OWNER = :schema
                ORDER BY TABLE_NAME
            """
        else:
            sql = """
                SELECT TABLE_NAME, 'TABLE' AS TABLE_TYPE
                FROM ALL_TABLES
                WHERE OWNER = :schema
                UNION ALL
                SELECT VIEW_NAME AS TABLE_NAME, 'VIEW' AS TABLE_TYPE
                FROM ALL_VIEWS
                WHERE OWNER = :schema
                ORDER BY TABLE_NAME
            """
        cursor.execute(sql, {"schema": resolved_schema})
        raw_rows = cursor.fetchall()

        tables_result = [
            {
                "name": str(row[0]),
                "type": str(row[1]),
                "schema": resolved_schema,
            }
            for row in raw_rows
        ]
        _TABLES_CACHE[cache_key] = (now, tables_result)

        if q:
            term = q.strip().upper()
            return [t for t in tables_result if term in t["name"].upper()]
        return tables_result
    finally:
        ora_conn.close()


def list_columns(
    ds_id: int,
    schema: str,
    table_name: str,
) -> list[dict[str, Any]]:
    """Liệt kê thông tin các cột của bảng hoặc view Oracle hoặc SQLite với cache 10 phút.

    Trả về danh sách: [{"name": str, "data_type": str, "nullable": bool, "length": int, "precision": int, "scale": int}]
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = conn.execute(
            select(recon_data_source.c.DB_TYPE).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()

    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        from sqlalchemy import text
        with engine.connect() as conn:
            raw = conn.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
            return [
                {
                    "name": str(r[1]),
                    "data_type": str(r[2] or "TEXT").upper(),
                    "nullable": not bool(r[3]),
                    "length": None,
                    "precision": None,
                    "scale": None,
                }
                for r in raw
            ]

    norm_schema = schema.strip().upper()
    norm_table = table_name.strip().upper()
    cache_key = (ds_id, norm_schema, norm_table)
    now = time.monotonic()

    cached = _COLUMNS_CACHE.get(cache_key)
    if cached is not None:
        cached_at, cols = cached
        if now - cached_at < CACHE_TTL_SECONDS:
            return cols

    ora_conn = open_source_connection(ds_id)
    try:
        cursor = ora_conn.cursor()
        sql = """
            SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :schema AND TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
        """
        cursor.execute(sql, {"schema": norm_schema, "table_name": norm_table})
        raw_rows = cursor.fetchall()

        cols_result = [
            {
                "name": str(r[0]),
                "data_type": str(r[1]),
                "nullable": (str(r[2]).upper() == "Y"),
                "length": int(r[3]) if r[3] is not None else None,
                "precision": int(r[4]) if r[4] is not None else None,
                "scale": int(r[5]) if r[5] is not None else None,
            }
            for r in raw_rows
        ]
        _COLUMNS_CACHE[cache_key] = (now, cols_result)
        return cols_result
    finally:
        ora_conn.close()


def describe_sql(conn: Any, sql: str) -> list[dict[str, Any]]:
    """Phân tích cấu trúc cột của câu lệnh SQL tùy biến qua SELECT * FROM (...) WHERE 1=0."""
    cursor = conn.cursor()
    try:
        clean_sql = sql.strip().rstrip(";")
        wrapped_sql = f"SELECT * FROM (\n{clean_sql}\n) WHERE 1=0"
        if hasattr(cursor, "parse"):
            cursor.parse(wrapped_sql)
        else:
            cursor.execute(wrapped_sql)
        desc = cursor.description or []
        res = []
        for d in desc:
            type_name = getattr(d[1], "name", str(d[1])).replace("DB_TYPE_", "")
            res.append(
                {
                    "name": str(d[0]),
                    "data_type": type_name,
                    "nullable": bool(d[6]) if len(d) > 6 else True,
                    "precision": int(d[4]) if len(d) > 4 and d[4] is not None else None,
                    "scale": int(d[5]) if len(d) > 5 and d[5] is not None else None,
                }
            )
        return res
    finally:
        try:
            cursor.close()
        except Exception:
            pass
