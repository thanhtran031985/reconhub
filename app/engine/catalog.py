from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.engine.sql_dialect import quote_identifier
from app.services.source_conn import open_source_connection

CACHE_TTL_SECONDS = 600.0  # 10 phút

_TABLES_CACHE: dict[tuple[int, str, str], tuple[float, list[dict[str, str]]]] = {}
_COLUMNS_CACHE: dict[tuple[int, str, str], tuple[float, list[dict[str, Any]]]] = {}
_CONSTRAINTS_CACHE: dict[tuple[int, str, str], tuple[float, dict[str, Any]]] = {}
_ROW_ESTIMATE_CACHE: dict[tuple[int, str, str], tuple[float, int | None]] = {}
_SCHEMA_STATS_CACHE: dict[tuple[int, str], tuple[float, list[dict[str, Any]]]] = {}


def invalidate_catalog_cache(ds_id: int | None = None) -> None:
    """Xóa bộ đệm danh mục bảng, cột, constraint và ước lượng số dòng."""
    if ds_id is None:
        _TABLES_CACHE.clear()
        _COLUMNS_CACHE.clear()
        _CONSTRAINTS_CACHE.clear()
        _ROW_ESTIMATE_CACHE.clear()
        _SCHEMA_STATS_CACHE.clear()
    else:
        caches: tuple[dict[Any, Any], ...] = (
            _TABLES_CACHE,
            _COLUMNS_CACHE,
            _CONSTRAINTS_CACHE,
            _ROW_ESTIMATE_CACHE,
            _SCHEMA_STATS_CACHE,
        )
        for cache in caches:
            for k in list(cache.keys()):
                if k[0] == ds_id:
                    cache.pop(k, None)


def _get_ds_row(ds_id: int) -> dict[str, Any] | None:
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(
                    recon_data_source.c.DB_TYPE,
                    recon_data_source.c.FILE_PATH,
                    recon_data_source.c.DEFAULT_SCHEMA,
                    recon_data_source.c.USERNAME,
                ).where(recon_data_source.c.ID == ds_id)
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


@contextmanager
def _sqlite_connection(ds_row: dict[str, Any] | None) -> Iterator[Connection]:
    """Mở connection SQLite tới FILE_PATH của Data Source (nếu có) hoặc engine mặc định."""
    file_path = str(ds_row.get("FILE_PATH") or "").strip() if ds_row else ""
    if file_path:
        ext_engine = create_engine(f"sqlite:///{Path(file_path).as_posix()}")
        try:
            with ext_engine.connect() as conn:
                yield conn
        finally:
            ext_engine.dispose()
    else:
        with get_recon_engine().connect() as conn:
            yield conn


def _verify_sqlite_object(conn: Connection, table_name: str) -> tuple[str, str] | None:
    """Xác minh bảng/view tồn tại trong sqlite_master bằng bind parameter."""
    row = conn.execute(
        text(
            "SELECT name, LOWER(type) FROM sqlite_master "
            "WHERE UPPER(name) = UPPER(:name) AND type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%'"
        ),
        {"name": table_name.strip()},
    ).first()
    if row is None:
        return None
    return str(row[0]), str(row[1])


def _resolve_schema(ds_id: int, schema: str | None) -> str:
    """Xác định schema đích (ưu tiên tham số, nếu không lấy DEFAULT_SCHEMA hoặc USERNAME)."""
    if schema and schema.strip():
        return schema.strip().upper()

    row = _get_ds_row(ds_id)
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

    ds_row = _get_ds_row(ds_id)
    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        with _sqlite_connection(ds_row) as conn:
            if object_type == "TABLE":
                raw_rows = conn.execute(
                    text("SELECT name, UPPER(type) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                ).fetchall()
            elif object_type == "VIEW":
                raw_rows = conn.execute(
                    text("SELECT name, UPPER(type) FROM sqlite_master WHERE type = 'view' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                ).fetchall()
            else:
                raw_rows = conn.execute(
                    text("SELECT name, UPPER(type) FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name")
                ).fetchall()
            tables = [{"name": str(r[0]), "type": str(r[1]), "schema": "main"} for r in raw_rows]
            if q:
                term = q.strip().upper()
                return [t for t in tables if term in t["name"].upper()]
            return tables

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


def list_schema_table_stats(
    ds_id: int,
    schema: str | None = None,
    *,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Đọc toàn bộ bảng/view của schema kèm NUM_ROWS và PK/FK count chỉ với 1 kết nối Oracle (cache 10 phút).

    Giúp Drawer + Thêm bảng không bị N+1 query (80+ round-trip VPN) như cách enrich từng bảng.
    """
    ds_row = _get_ds_row(ds_id)
    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        raw = list_tables(ds_id, schema=schema)
        out_sqlite: list[dict[str, Any]] = []
        for t in raw:
            t_name = str(t["name"])
            t_type = str(t["type"]).upper()
            t_schema = str(t.get("schema") or "main")
            pk_cnt = 0
            fk_cnt = 0
            row_est: int | None = None
            if t_type == "TABLE":
                try:
                    cons = list_table_constraints(ds_id, t_schema, t_name)
                    pk_cnt = len(cons.get("primary_key") or [])
                    fk_cnt = len(cons.get("foreign_keys") or [])
                except Exception:
                    pk_cnt = 0
                    fk_cnt = 0
                try:
                    row_est = estimate_table_rows(ds_id, t_schema, t_name)
                except Exception:
                    row_est = None
            out_sqlite.append(
                {
                    "name": t_name,
                    "type": t_type,
                    "schema": t_schema,
                    "pk_count": pk_cnt,
                    "fk_count": fk_cnt,
                    "row_estimate": row_est,
                }
            )
        return out_sqlite

    resolved_schema = _resolve_schema(ds_id, schema)
    cache_key = (ds_id, resolved_schema)
    now = time.monotonic()
    if not force_refresh:
        cached = _SCHEMA_STATS_CACHE.get(cache_key)
        if cached is not None and (now - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]
    else:
        invalidate_catalog_cache(ds_id)

    ora_conn = open_source_connection(ds_id)
    try:
        cursor = ora_conn.cursor()
        cursor.execute(
            """
            SELECT TABLE_NAME, 'TABLE' AS TABLE_TYPE, NUM_ROWS
            FROM ALL_TABLES
            WHERE OWNER = :schema
            UNION ALL
            SELECT VIEW_NAME AS TABLE_NAME, 'VIEW' AS TABLE_TYPE, NULL AS NUM_ROWS
            FROM ALL_VIEWS
            WHERE OWNER = :schema
            ORDER BY TABLE_NAME
            """,
            {"schema": resolved_schema},
        )
        obj_rows = cursor.fetchall()

        cons_map: dict[str, tuple[int, int]] = {}
        try:
            cursor.execute(
                """
                SELECT
                    TABLE_NAME,
                    SUM(CASE WHEN CONSTRAINT_TYPE = 'P' THEN 1 ELSE 0 END) AS PK_CNT,
                    SUM(CASE WHEN CONSTRAINT_TYPE = 'R' THEN 1 ELSE 0 END) AS FK_CNT
                FROM ALL_CONSTRAINTS
                WHERE OWNER = :schema AND CONSTRAINT_TYPE IN ('P', 'R')
                GROUP BY TABLE_NAME
                """,
                {"schema": resolved_schema},
            )
            for cr in cursor.fetchall():
                cons_map[str(cr[0]).upper()] = (int(cr[1] or 0), int(cr[2] or 0))
        except Exception:
            cons_map = {}

        result: list[dict[str, Any]] = []
        base_tables: list[dict[str, str]] = []
        for row in obj_rows:
            t_name = str(row[0])
            t_type = str(row[1]).upper()
            num_rows = int(row[2]) if t_type == "TABLE" and row[2] is not None else None
            pk_cnt, fk_cnt = cons_map.get(t_name.upper(), (0, 0)) if t_type == "TABLE" else (0, 0)
            result.append(
                {
                    "name": t_name,
                    "type": t_type,
                    "schema": resolved_schema,
                    "pk_count": pk_cnt,
                    "fk_count": fk_cnt,
                    "row_estimate": num_rows,
                }
            )
            base_tables.append({"name": t_name, "type": t_type, "schema": resolved_schema})
            if t_type == "TABLE":
                _ROW_ESTIMATE_CACHE[(ds_id, resolved_schema, t_name.upper())] = (now, num_rows)

        _SCHEMA_STATS_CACHE[cache_key] = (now, result)
        _TABLES_CACHE[(ds_id, resolved_schema, "")] = (now, base_tables)
        return result
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
    ds_row = _get_ds_row(ds_id)
    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        with _sqlite_connection(ds_row) as conn:
            verified = _verify_sqlite_object(conn, table_name)
            if verified is None:
                return []
            safe_name, _ = verified
            raw = conn.execute(text(f"PRAGMA table_info({quote_identifier(safe_name)})")).fetchall()
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


def list_table_constraints(
    ds_id: int,
    schema: str,
    table_name: str,
) -> dict[str, Any]:
    """Đọc khóa chính (PK), khóa duy nhất (UK) và khóa ngoại (FK) của bảng.

    View hoặc bảng không có ràng buộc trả về các danh sách rỗng. Kết quả cache 10 phút.
    """
    empty: dict[str, Any] = {"primary_key": [], "unique_keys": [], "foreign_keys": []}
    ds_row = _get_ds_row(ds_id)
    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        with _sqlite_connection(ds_row) as conn:
            verified = _verify_sqlite_object(conn, table_name)
            if verified is None or verified[1] != "table":
                return empty
            safe_name, _ = verified
            quoted = quote_identifier(safe_name)

            ti_rows = conn.execute(text(f"PRAGMA table_info({quoted})")).fetchall()
            pk_pairs = sorted(
                [(int(r[5]), str(r[1])) for r in ti_rows if int(r[5] or 0) > 0],
                key=lambda item: item[0],
            )
            pk_cols = [col for _, col in pk_pairs]

            unique_keys: list[list[str]] = []
            idx_rows = conn.execute(text(f"PRAGMA index_list({quoted})")).fetchall()
            for idx in idx_rows:
                idx_name = str(idx[1])
                is_unique = bool(idx[2])
                origin = str(idx[3]) if len(idx) > 3 else ""
                if not is_unique or origin == "pk":
                    continue
                ii_rows = conn.execute(text(f"PRAGMA index_info({quote_identifier(idx_name)})")).fetchall()
                cols = [str(c[2]) for c in sorted(ii_rows, key=lambda r: int(r[0])) if c[2] is not None]
                if cols and cols != pk_cols:
                    unique_keys.append(cols)

            fk_groups: dict[int, dict[str, Any]] = {}
            fk_rows = conn.execute(text(f"PRAGMA foreign_key_list({quoted})")).fetchall()
            for r in fk_rows:
                fk_id = int(r[0])
                seq = int(r[1])
                ref_tbl = str(r[2])
                from_col = str(r[3])
                to_col = str(r[4])
                grp = fk_groups.setdefault(
                    fk_id,
                    {"name": f"fk_{safe_name}_{fk_id}", "ref_schema": "main", "ref_table": ref_tbl, "pairs": []},
                )
                grp["pairs"].append((seq, from_col, to_col))

            foreign_keys: list[dict[str, Any]] = []
            for grp in fk_groups.values():
                pairs = sorted(grp["pairs"], key=lambda p: p[0])
                foreign_keys.append(
                    {
                        "name": grp["name"],
                        "columns": [p[1] for p in pairs],
                        "ref_schema": grp["ref_schema"],
                        "ref_table": grp["ref_table"],
                        "ref_columns": [p[2] for p in pairs],
                    }
                )
            return {"primary_key": pk_cols, "unique_keys": unique_keys, "foreign_keys": foreign_keys}

    norm_schema = _resolve_schema(ds_id, schema)
    norm_table = table_name.strip().upper()
    cache_key = (ds_id, norm_schema, norm_table)
    now = time.monotonic()
    cached = _CONSTRAINTS_CACHE.get(cache_key)
    if cached is not None and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    ora_conn = open_source_connection(ds_id)
    try:
        cursor = ora_conn.cursor()
        sql = """
            SELECT
                c.CONSTRAINT_NAME,
                c.CONSTRAINT_TYPE,
                cc.COLUMN_NAME,
                cc.POSITION,
                rc.OWNER AS REF_OWNER,
                rc.TABLE_NAME AS REF_TABLE,
                rcc.COLUMN_NAME AS REF_COLUMN
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc
                ON cc.OWNER = c.OWNER
               AND cc.CONSTRAINT_NAME = c.CONSTRAINT_NAME
            LEFT JOIN ALL_CONSTRAINTS rc
                ON rc.OWNER = c.R_OWNER
               AND rc.CONSTRAINT_NAME = c.R_CONSTRAINT_NAME
            LEFT JOIN ALL_CONS_COLUMNS rcc
                ON rcc.OWNER = rc.OWNER
               AND rcc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
               AND rcc.POSITION = cc.POSITION
            WHERE c.OWNER = :schema
              AND c.TABLE_NAME = :table_name
              AND c.CONSTRAINT_TYPE IN ('P', 'U', 'R')
              AND c.STATUS = 'ENABLED'
            ORDER BY c.CONSTRAINT_TYPE, c.CONSTRAINT_NAME, cc.POSITION
        """
        cursor.execute(sql, {"schema": norm_schema, "table_name": norm_table})
        rows = cursor.fetchall()

        pk_items: list[tuple[int, str]] = []
        uk_map: dict[str, list[tuple[int, str]]] = {}
        fk_map: dict[str, dict[str, Any]] = {}
        for r in rows:
            cname = str(r[0])
            ctype = str(r[1]).upper()
            col = str(r[2])
            pos = int(r[3] or 1)
            ref_owner = str(r[4]) if r[4] is not None else None
            ora_ref_tbl: str | None = str(r[5]) if r[5] is not None else None
            ref_col = str(r[6]) if r[6] is not None else None
            if ctype == "P":
                pk_items.append((pos, col))
            elif ctype == "U":
                uk_map.setdefault(cname, []).append((pos, col))
            elif ctype == "R" and ora_ref_tbl:
                grp = fk_map.setdefault(
                    cname,
                    {"name": cname, "ref_schema": ref_owner, "ref_table": ora_ref_tbl, "pairs": []},
                )
                grp["pairs"].append((pos, col, ref_col or ""))

        result = {
            "primary_key": [c for _, c in sorted(pk_items, key=lambda x: x[0])],
            "unique_keys": [
                [c for _, c in sorted(cols, key=lambda x: x[0])]
                for cols in uk_map.values()
            ],
            "foreign_keys": [
                {
                    "name": grp["name"],
                    "columns": [p[1] for p in sorted(grp["pairs"], key=lambda x: x[0])],
                    "ref_schema": grp["ref_schema"],
                    "ref_table": grp["ref_table"],
                    "ref_columns": [p[2] for p in sorted(grp["pairs"], key=lambda x: x[0])],
                }
                for grp in fk_map.values()
            ],
        }
        _CONSTRAINTS_CACHE[cache_key] = (now, result)
        return result
    finally:
        ora_conn.close()


def estimate_table_rows(
    ds_id: int,
    schema: str,
    table_name: str,
) -> int | None:
    """Ước lượng số dòng của bảng (ALL_TABLES.NUM_ROWS trên Oracle; COUNT cho table SQLite).

    View trả về None. Kết quả cache 10 phút.
    """
    ds_row = _get_ds_row(ds_id)
    if ds_row and str(ds_row.get("DB_TYPE")).upper() == "SQLITE":
        with _sqlite_connection(ds_row) as conn:
            verified = _verify_sqlite_object(conn, table_name)
            if verified is None or verified[1] != "table":
                return None
            safe_name, _ = verified
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {quote_identifier(safe_name)}")).scalar_one()
                return int(cnt)
            except SQLAlchemyError:
                return None

    norm_schema = _resolve_schema(ds_id, schema)
    norm_table = table_name.strip().upper()
    cache_key = (ds_id, norm_schema, norm_table)
    now = time.monotonic()
    cached = _ROW_ESTIMATE_CACHE.get(cache_key)
    if cached is not None and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    ora_conn = open_source_connection(ds_id)
    try:
        cursor = ora_conn.cursor()
        cursor.execute(
            "SELECT NUM_ROWS FROM ALL_TABLES WHERE OWNER = :schema AND TABLE_NAME = :table_name",
            {"schema": norm_schema, "table_name": norm_table},
        )
        row = cursor.fetchone()
        est = int(row[0]) if row is not None and row[0] is not None else None
        _ROW_ESTIMATE_CACHE[cache_key] = (now, est)
        return est
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
