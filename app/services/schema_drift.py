"""Schema Drift — so sánh model với database SQLite thật.

Hàm thuần (không dùng ``ctx``): ``compare_schemas`` nhận 2 danh sách bảng
theo shape chuẩn của :mod:`app.services.schema_inspector` (model extraction
hoặc ``inspect_live_db``) và trả các drift entry. FK so theo cặp
(cột -> bảng.cột tham chiếu), KHÔNG so tên constraint vì SQLite trả None;
PK so theo tập cột; index so theo (tên, tập cột, unique); unique constraint
so theo tập cột (không so tên).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Engine

from app.db.engine import get_recon_engine
from app.services.schema_inspector import extract_model_schema, inspect_live_db

# Bảng hạ tầng Alembic có trong DB thật nhưng không thuộc model: bỏ qua khi
# kiểm tra drift live để không báo TABLE_EXTRA giả.
IGNORED_LIVE_TABLES = frozenset({"alembic_version"})


def normalize_type(type_str: str) -> str:
    """Chuẩn hoá kiểu để so sánh: upper-case, gọn khoảng trắng."""
    return re.sub(r"\s+", " ", type_str.strip().upper())


def _fk_signature(foreign_keys: list[dict[str, Any]]) -> str | None:
    if not foreign_keys:
        return None
    parts = sorted(f"{fk['column']}->{fk['references_table']}.{fk['references_column']}" for fk in foreign_keys)
    return "; ".join(parts)


def _index_signature(indexes: list[dict[str, Any]]) -> str | None:
    if not indexes:
        return None
    parts = sorted(
        f"{ix['name']}({','.join(sorted(ix['columns']))}){' UNIQUE' if ix['unique'] else ''}" for ix in indexes
    )
    return "; ".join(parts)


def _constraint_signature(unique_constraints: list[dict[str, Any]]) -> str | None:
    if not unique_constraints:
        return None
    parts = sorted(",".join(sorted(uc["columns"])) for uc in unique_constraints)
    return "; ".join(parts)


def compare_schemas(model_tables: list[dict[str, Any]], db_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """So sánh model với DB -> danh sách drift entry.

    Mỗi entry: ``{type, table, column, detail, db_value, model_value}``.
    """
    drifts: list[dict[str, Any]] = []

    def _entry(
        dtype: str,
        table: str,
        column: str | None,
        detail: str,
        db_value: Any,
        model_value: Any,
    ) -> dict[str, Any]:
        return {
            "type": dtype,
            "table": table,
            "column": column,
            "detail": detail,
            "db_value": db_value,
            "model_value": model_value,
        }

    model_map = {t["name"]: t for t in model_tables}
    db_map = {t["name"]: t for t in db_tables}
    for name in sorted(set(model_map) - set(db_map)):
        drifts.append(
            _entry(
                "TABLE_MISSING", name, None, f"Bảng {name} có trong model nhưng không có trong database.", None, name
            )
        )
    for name in sorted(set(db_map) - set(model_map)):
        drifts.append(
            _entry("TABLE_EXTRA", name, None, f"Bảng {name} có trong database nhưng không có trong model.", name, None)
        )
    for name in sorted(set(model_map) & set(db_map)):
        model_table = model_map[name]
        db_table = db_map[name]
        model_cols = {c["name"]: c for c in model_table["columns"]}
        db_cols = {c["name"]: c for c in db_table["columns"]}
        for col_name in sorted(set(model_cols) - set(db_cols)):
            drifts.append(
                _entry(
                    "COLUMN_MISSING",
                    name,
                    col_name,
                    f"Cột {name}.{col_name} có trong model nhưng không có trong database.",
                    None,
                    model_cols[col_name]["type"],
                )
            )
        for col_name in sorted(set(db_cols) - set(model_cols)):
            drifts.append(
                _entry(
                    "COLUMN_EXTRA",
                    name,
                    col_name,
                    f"Cột {name}.{col_name} có trong database nhưng không có trong model.",
                    db_cols[col_name]["type"],
                    None,
                )
            )
        for col_name in sorted(set(model_cols) & set(db_cols)):
            model_col = model_cols[col_name]
            db_col = db_cols[col_name]
            if normalize_type(str(db_col["type"])) != normalize_type(str(model_col["type"])):
                drifts.append(
                    _entry(
                        "TYPE_CHANGED",
                        name,
                        col_name,
                        f"Kiểu cột {name}.{col_name} khác nhau giữa database và model.",
                        db_col["type"],
                        model_col["type"],
                    )
                )
            if bool(db_col["nullable"]) != bool(model_col["nullable"]):
                drifts.append(
                    _entry(
                        "NULLABILITY_CHANGED",
                        name,
                        col_name,
                        f"Tính nullable của cột {name}.{col_name} khác nhau giữa database và model.",
                        db_col["nullable"],
                        model_col["nullable"],
                    )
                )
        if sorted(model_table["primary_key"]) != sorted(db_table["primary_key"]):
            drifts.append(
                _entry(
                    "PK_CHANGED",
                    name,
                    None,
                    f"Khóa chính của bảng {name} khác nhau giữa database và model.",
                    ", ".join(sorted(db_table["primary_key"])) or None,
                    ", ".join(sorted(model_table["primary_key"])) or None,
                )
            )
        if _fk_signature(model_table["foreign_keys"]) != _fk_signature(db_table["foreign_keys"]):
            drifts.append(
                _entry(
                    "FK_CHANGED",
                    name,
                    None,
                    f"Khóa ngoại của bảng {name} khác nhau giữa database và model.",
                    _fk_signature(db_table["foreign_keys"]),
                    _fk_signature(model_table["foreign_keys"]),
                )
            )
        if _index_signature(model_table["indexes"]) != _index_signature(db_table["indexes"]):
            drifts.append(
                _entry(
                    "INDEX_CHANGED",
                    name,
                    None,
                    f"Index của bảng {name} khác nhau giữa database và model.",
                    _index_signature(db_table["indexes"]),
                    _index_signature(model_table["indexes"]),
                )
            )
        if _constraint_signature(model_table["unique_constraints"]) != _constraint_signature(
            db_table["unique_constraints"]
        ):
            drifts.append(
                _entry(
                    "CONSTRAINT_CHANGED",
                    name,
                    None,
                    f"Unique constraint của bảng {name} khác nhau giữa database và model.",
                    _constraint_signature(db_table["unique_constraints"]),
                    _constraint_signature(model_table["unique_constraints"]),
                )
            )
    return drifts


def drift_status(drifts: list[dict[str, Any]]) -> str:
    """[] -> SYNCED, có drift -> DRIFT."""
    return "SYNCED" if not drifts else "DRIFT"


def check_live_drift(engine: Engine | None = None) -> dict[str, Any]:
    """So sánh model với database app thật. Dùng cho UI sau; không dùng ctx."""
    live_engine = engine or get_recon_engine()
    try:
        db_tables = [t for t in inspect_live_db(live_engine) if t["name"] not in IGNORED_LIVE_TABLES]
    finally:
        if engine is None:
            live_engine.dispose()
    drifts = compare_schemas(extract_model_schema(), db_tables)
    return {"status": drift_status(drifts), "drifts": drifts}
