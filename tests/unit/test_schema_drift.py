"""Tests cho Schema Drift — Bước 2 task 31 (test viết trước).

Drift test dùng dict model/db tổng hợp, không cần DB thật (trừ
check_live_drift).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.db.metadata import metadata
from app.services import schema_drift as sd


def _table(
    name: str,
    columns: list[tuple[str, str, bool]] | None = None,
    pk: list[str] | None = None,
    fks: list[dict] | None = None,
    uqs: list[dict] | None = None,
    idx: list[dict] | None = None,
) -> dict:
    cols = [
        {
            "name": cname,
            "type": ctype,
            "nullable": nullable,
            "primary_key": cname in (pk or []),
            "foreign_key": None,
            "unique": False,
            "default": None,
        }
        for cname, ctype, nullable in (columns or [("ID", "INTEGER", False)])
    ]
    return {
        "name": name,
        "columns": cols,
        "primary_key": list(pk or ["ID"]),
        "foreign_keys": list(fks or []),
        "unique_constraints": list(uqs or []),
        "indexes": list(idx or []),
    }


def _fk(column: str, ref_table: str, ref_column: str, name: str | None = None) -> dict:
    return {
        "column": column,
        "references_table": ref_table,
        "references_column": ref_column,
        "constraint_name": name,
        "on_delete": None,
    }


def _base_tables() -> list[dict]:
    return [
        _table(
            "RECON_RUN",
            columns=[("ID", "INTEGER", False), ("STATUS", "VARCHAR(10)", False)],
            pk=["ID"],
            fks=[_fk("FILE_ID", "RECON_FILE", "ID", "fk_a")],
            uqs=[{"name": "uq_run", "columns": ["STATUS"]}],
            idx=[{"name": "ix_run", "columns": ["STATUS"], "unique": False}],
        ),
        _table("RECON_FILE", columns=[("ID", "INTEGER", False)], pk=["ID"]),
    ]


def _drift_of(model: list[dict], db: list[dict], dtype: str) -> list[dict]:
    return [d for d in sd.compare_schemas(model, db) if d["type"] == dtype]


def test_no_drift_when_identical():
    tables = _base_tables()
    assert sd.compare_schemas(tables, tables) == []
    assert sd.drift_status([]) == "SYNCED"


def test_drift_status_drift():
    assert sd.drift_status([{"type": "TABLE_MISSING"}]) == "DRIFT"


def test_table_missing():
    model = _base_tables()
    db = [t for t in _base_tables() if t["name"] != "RECON_RUN"]
    drifts = _drift_of(model, db, "TABLE_MISSING")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    assert drifts[0]["column"] is None
    assert drifts[0]["model_value"] == "RECON_RUN"
    assert drifts[0]["db_value"] is None


def test_table_extra():
    model = _base_tables()
    db = _base_tables() + [_table("RECON_EXTRA")]
    drifts = _drift_of(model, db, "TABLE_EXTRA")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_EXTRA"
    assert drifts[0]["db_value"] == "RECON_EXTRA"
    assert drifts[0]["model_value"] is None


def test_column_missing():
    model = _base_tables()
    db = _base_tables()
    db[0]["columns"] = [c for c in db[0]["columns"] if c["name"] != "STATUS"]
    drifts = _drift_of(model, db, "COLUMN_MISSING")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    assert drifts[0]["column"] == "STATUS"
    assert drifts[0]["model_value"] == "VARCHAR(10)"


def test_column_extra():
    model = _base_tables()
    db = _base_tables()
    db[0]["columns"] = db[0]["columns"] + [
        {
            "name": "NEW_COL",
            "type": "TEXT",
            "nullable": True,
            "primary_key": False,
            "foreign_key": None,
            "unique": False,
            "default": None,
        }
    ]
    drifts = _drift_of(model, db, "COLUMN_EXTRA")
    assert len(drifts) == 1
    assert drifts[0]["column"] == "NEW_COL"
    assert drifts[0]["db_value"] == "TEXT"


def test_type_changed_case_insensitive():
    model = _base_tables()
    db = _base_tables()
    db[0]["columns"][1]["type"] = "varchar(10)"
    assert _drift_of(model, db, "TYPE_CHANGED") == []
    db[0]["columns"][1]["type"] = "VARCHAR(20)"
    drifts = _drift_of(model, db, "TYPE_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["column"] == "STATUS"
    assert drifts[0]["db_value"] == "VARCHAR(20)"
    assert drifts[0]["model_value"] == "VARCHAR(10)"


def test_nullability_changed():
    model = _base_tables()
    db = _base_tables()
    db[0]["columns"][1]["nullable"] = True
    drifts = _drift_of(model, db, "NULLABILITY_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["column"] == "STATUS"
    assert drifts[0]["db_value"] is True
    assert drifts[0]["model_value"] is False


def test_pk_changed():
    model = _base_tables()
    db = _base_tables()
    db[0]["primary_key"] = ["ID", "STATUS"]
    drifts = _drift_of(model, db, "PK_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    assert drifts[0]["column"] is None
    assert drifts[0]["model_value"] == "ID"
    assert drifts[0]["db_value"] == "ID, STATUS"


def test_fk_changed_and_constraint_name_ignored():
    model = _base_tables()
    db = _base_tables()
    # Chỉ đổi tên constraint -> không drift (SQLite trả None).
    db[0]["foreign_keys"][0]["constraint_name"] = None
    assert _drift_of(model, db, "FK_CHANGED") == []
    # Đổi cột tham chiếu -> drift.
    db[0]["foreign_keys"][0]["references_column"] = "CODE"
    drifts = _drift_of(model, db, "FK_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    assert "RECON_FILE.ID" in (drifts[0]["model_value"] or "")
    assert "RECON_FILE.CODE" in (drifts[0]["db_value"] or "")


def test_index_changed():
    model = _base_tables()
    db = _base_tables()
    db[0]["indexes"] = [{"name": "ix_run", "columns": ["STATUS"], "unique": True}]
    drifts = _drift_of(model, db, "INDEX_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    db = _base_tables()
    db[0]["indexes"] = db[0]["indexes"] + [{"name": "ix_new", "columns": ["ID"], "unique": False}]
    assert len(_drift_of(model, db, "INDEX_CHANGED")) == 1


def test_constraint_changed():
    model = _base_tables()
    db = _base_tables()
    db[0]["unique_constraints"] = [{"name": "uq_run", "columns": ["STATUS", "ID"]}]
    drifts = _drift_of(model, db, "CONSTRAINT_CHANGED")
    assert len(drifts) == 1
    assert drifts[0]["table"] == "RECON_RUN"
    db = _base_tables()
    db[0]["unique_constraints"] = [{"name": "uq_other", "columns": ["STATUS"]}]
    # Chỉ đổi tên constraint, cùng tập cột -> không drift.
    assert _drift_of(model, db, "CONSTRAINT_CHANGED") == []


def test_check_live_drift_synced(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    try:
        metadata.create_all(engine)
        result = sd.check_live_drift(engine)
        assert result["status"] == "SYNCED"
        assert result["drifts"] == []
    finally:
        engine.dispose()


def test_check_live_drift_detects_extra_column(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    try:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE RECON_RUN ADD COLUMN EXTRA_COL TEXT"))
        result = sd.check_live_drift(engine)
        assert result["status"] == "DRIFT"
        extras = [d for d in result["drifts"] if d["type"] == "COLUMN_EXTRA"]
        assert len(extras) == 1
        assert extras[0]["table"] == "RECON_RUN"
        assert extras[0]["column"] == "EXTRA_COL"
    finally:
        engine.dispose()


def test_check_live_drift_ignores_alembic_version(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'live.db'}")
    try:
        metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        result = sd.check_live_drift(engine)
        assert result["status"] == "SYNCED"
    finally:
        engine.dispose()
