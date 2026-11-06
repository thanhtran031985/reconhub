"""Task 18 bước 1: migration 0006 — 5 bảng batch + cột mới + FILE_SET_HASH.

Kiểm tra: upgrade 2 lần, downgrade/upgrade, dữ liệu cũ vẫn đọc được
(FILE_SET_HASH tính lại, SOURCE_FILE_ID = FILE_ID), UQ mới, PK mới.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_batch.db"


@pytest.fixture
def temp_db_url(temp_db_path: Path) -> str:
    return f"sqlite:///{temp_db_path.as_posix()}"


def run_alembic_upgrade(db_url: str, revision: str = "head") -> None:
    root = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, revision)


def run_alembic_downgrade(db_url: str, revision: str = "base") -> None:
    root = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.downgrade(alembic_cfg, revision)


def _seed_legacy_data(engine) -> dict[str, int]:
    """Gieo dữ liệu theo schema 0005: 1 file + 1 load + 2 dòng + 1 run."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                "IS_CURRENT_METADATA, CREATED_BY, "
                "CREATED_AT, UPDATED_AT) VALUES ('ORACLE_TEST', 'DEV', 'SOURCE', "
                "'ORACLE', 'localhost', 1521, 'XE', 600, 1000000, 'Y', 'N', 'admin', "
                ":now, :now)"
            ),
            {"now": now},
        ).lastrowid
        tmpl_id = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CREATED_AT, "
                "UPDATED_AT, ROW_VERSION) VALUES ('DTP_TMPL', 'Template DTP', "
                "'admin', 'ACTIVE', :now, :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, "
                "CONFIG_JSON, CREATED_BY, CREATED_AT) VALUES (:t, 1, 'ACTIVE', "
                "'{}', 'admin', :now)"
            ),
            {"t": tmpl_id, "now": now},
        )
        file_id = conn.execute(
            text(
                "INSERT INTO RECON_FILE (SHA256, ORIGINAL_NAME, SIZE_BYTES, "
                "STORAGE_PATH, UPLOADED_BY, UPLOADED_AT) VALUES (:sha, 'dtp.xlsx', "
                "1234, 'storage/dtp.xlsx', 'admin', :now)"
            ),
            {"sha": "a" * 64, "now": now},
        ).lastrowid
        load_id = conn.execute(
            text(
                "INSERT INTO RECON_EXCEL_LOAD (FILE_ID, SHEET_NAME, TEMPLATE_ID, "
                "TEMPLATE_VERSION, ROWS_READ, ROWS_INVALID, BYTES_EST, "
                "CONTROL_TOTAL_FILE, CONTROL_TOTAL_CALC, LOADED_AT) VALUES "
                "(:f, 'Sheet1', :t, 1, 2, 0, 400, '100.00', '100.00', :now)"
            ),
            {"f": file_id, "t": tmpl_id, "now": now},
        ).lastrowid
        for row_no in (5, 6):
            conn.execute(
                text(
                    "INSERT INTO RECON_EXCEL_ROW (LOAD_ID, EXCEL_ROW_NO, DATA_JSON, "
                    "IS_VALID) VALUES (:l, :r, '{\"A\": 1}', 'Y')"
                ),
                {"l": load_id, "r": row_no},
            )
        run_id = conn.execute(
            text(
                "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                "FILE_ID, EXCEL_LOAD_ID, DATA_SOURCE_ID, P_FROM, P_TO, STATUS, "
                "APPLY_RANGE_EXCEL, PROGRESS_PCT, CREATED_BY, CREATED_AT) VALUES (:t, 1, 'DEFAULT', :f, :l, :d, "
                ":now, :now, 'DONE', 'Y', 0, 'admin', :now)"
            ),
            {"t": tmpl_id, "f": file_id, "l": load_id, "d": ds_id, "now": now},
        ).lastrowid
        # Trùng nội dung: cùng file SHA-256 nhưng FILE_ID khác, đã nạp
        # cho cùng template — migration 0006 phải gộp về 1 bản nạp.
        file2_id = conn.execute(
            text(
                "INSERT INTO RECON_FILE (SHA256, ORIGINAL_NAME, SIZE_BYTES, "
                "STORAGE_PATH, UPLOADED_BY, UPLOADED_AT) VALUES (:sha, 'dtp-2.xlsx', "
                "1234, 'storage/dtp-2.xlsx', 'admin', :now)"
            ),
            {"sha": "a" * 64, "now": now},
        ).lastrowid
        load2_id = conn.execute(
            text(
                "INSERT INTO RECON_EXCEL_LOAD (FILE_ID, SHEET_NAME, TEMPLATE_ID, "
                "TEMPLATE_VERSION, ROWS_READ, ROWS_INVALID, BYTES_EST, "
                "CONTROL_TOTAL_FILE, CONTROL_TOTAL_CALC, LOADED_AT) VALUES "
                "(:f, 'Sheet1', :t, 1, 2, 0, 400, '100.00', '100.00', :now)"
            ),
            {"f": file2_id, "t": tmpl_id, "now": now},
        ).lastrowid
        for row_no in (5, 6):
            conn.execute(
                text(
                    "INSERT INTO RECON_EXCEL_ROW (LOAD_ID, EXCEL_ROW_NO, DATA_JSON, "
                    "IS_VALID) VALUES (:l, :r, '{\"A\": 1}', 'Y')"
                ),
                {"l": load2_id, "r": row_no},
            )
        run2_id = conn.execute(
            text(
                "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                "FILE_ID, EXCEL_LOAD_ID, DATA_SOURCE_ID, P_FROM, P_TO, STATUS, "
                "APPLY_RANGE_EXCEL, PROGRESS_PCT, CREATED_BY, CREATED_AT) VALUES (:t, 1, 'DEFAULT', :f, :l, :d, "
                ":now, :now, 'DONE', 'Y', 0, 'admin', :now)"
            ),
            {"t": tmpl_id, "f": file2_id, "l": load2_id, "d": ds_id, "now": now},
        ).lastrowid
    return {
        "ds_id": ds_id,
        "tmpl_id": tmpl_id,
        "file_id": file_id,
        "load_id": load_id,
        "run_id": run_id,
        "file2_id": file2_id,
        "load2_id": load2_id,
        "run2_id": run2_id,
    }


def test_batch_migration_lifecycle(temp_db_url: str) -> None:
    run_alembic_upgrade(temp_db_url, "head")
    run_alembic_upgrade(temp_db_url, "head")
    run_alembic_downgrade(temp_db_url, "0005_export_claim")
    run_alembic_upgrade(temp_db_url, "head")


def test_batch_migration_creates_tables_and_columns(temp_db_url: str) -> None:
    run_alembic_upgrade(temp_db_url, "head")
    engine = create_engine(temp_db_url)
    names = set(inspect(engine).get_table_names())
    for table in [
        "RECON_BATCH_DEF",
        "RECON_BATCH_DEF_ITEM",
        "RECON_BATCH_RUN",
        "RECON_BATCH_RUN_ITEM",
        "RECON_BATCH_RUN_FILE",
    ]:
        assert table in names
    run_cols = {c["name"] for c in inspect(engine).get_columns("RECON_RUN")}
    assert {"BATCH_RUN_ID", "BATCH_RUN_ITEM_ID"} <= run_cols
    load_cols = {c["name"] for c in inspect(engine).get_columns("RECON_EXCEL_LOAD")}
    assert {"FILE_SET_HASH", "SOURCE_FILES_JSON"} <= load_cols
    row_cols = {c["name"] for c in inspect(engine).get_columns("RECON_EXCEL_ROW")}
    assert "SOURCE_FILE_ID" in row_cols
    pk = inspect(engine).get_pk_constraint("RECON_EXCEL_ROW")
    assert pk["constrained_columns"] == ["LOAD_ID", "SOURCE_FILE_ID", "EXCEL_ROW_NO"]


def test_batch_migration_backfills_old_data(temp_db_url: str) -> None:
    run_alembic_upgrade(temp_db_url, "0005_export_claim")
    engine = create_engine(temp_db_url)
    ids = _seed_legacy_data(engine)
    run_alembic_upgrade(temp_db_url, "head")

    with engine.connect() as conn:
        # FILE_SET_HASH = sha256(SHA256 của file) cho dữ liệu cũ
        row = conn.execute(
            text("SELECT FILE_SET_HASH, SOURCE_FILES_JSON FROM RECON_EXCEL_LOAD WHERE ID = :l"),
            {"l": ids["load_id"]},
        ).one()
        assert row[0] == hashlib.sha256(("a" * 64).encode()).hexdigest()
        assert '"file_id": %d' % ids["file_id"] in (row[1] or "")
        assert '"name": "dtp.xlsx"' in (row[1] or "")
        # SOURCE_FILE_ID = FILE_ID cho dòng cũ
        src = (
            conn.execute(
                text("SELECT DISTINCT SOURCE_FILE_ID FROM RECON_EXCEL_ROW WHERE LOAD_ID = :l"),
                {"l": ids["load_id"]},
            )
            .scalars()
            .all()
        )
        assert src == [ids["file_id"]]
        # Run cũ vẫn đọc được
        status = conn.execute(text("SELECT STATUS FROM RECON_RUN WHERE ID = :r"), {"r": ids["run_id"]}).scalar_one()
        assert status == "DONE"
        # Bản nạp trùng nội dung đã gộp: chỉ còn 1 load, run2 trỏ về load giữ lại
        loads = conn.execute(
            text("SELECT COUNT(*) FROM RECON_EXCEL_LOAD WHERE TEMPLATE_ID = :t"),
            {"t": ids["tmpl_id"]},
        ).scalar_one()
        assert loads == 1
        run2_load = conn.execute(
            text("SELECT EXCEL_LOAD_ID FROM RECON_RUN WHERE ID = :r"), {"r": ids["run2_id"]}
        ).scalar_one()
        assert run2_load == ids["load_id"]
        dropped_rows = conn.execute(
            text("SELECT COUNT(*) FROM RECON_EXCEL_ROW WHERE LOAD_ID = :l"),
            {"l": ids["load2_id"]},
        ).scalar_one()
        assert dropped_rows == 0
        # UQ mới: cùng file + sheet + template + version không nạp trùng
        with pytest.raises(Exception, match="UNIQUE constraint failed"):
            conn.execute(
                text(
                    "INSERT INTO RECON_EXCEL_LOAD (FILE_ID, SHEET_NAME, TEMPLATE_ID, "
                    "TEMPLATE_VERSION, ROWS_READ, ROWS_INVALID, BYTES_EST, LOADED_AT, "
                    "FILE_SET_HASH) VALUES (:f, 'Sheet1', :t, 1, 1, 0, 200, "
                    "CURRENT_TIMESTAMP, :h)"
                ),
                {
                    "f": ids["file_id"],
                    "t": ids["tmpl_id"],
                    "h": hashlib.sha256(("a" * 64).encode()).hexdigest(),
                },
            )
        # PK mới: cùng LOAD_ID + EXCEL_ROW_NO nhưng khác file thì được
        conn.execute(
            text(
                "INSERT INTO RECON_EXCEL_ROW (LOAD_ID, SOURCE_FILE_ID, EXCEL_ROW_NO, "
                "DATA_JSON, IS_VALID) VALUES (:l, 999, 5, '{}', 'Y')"
            ),
            {"l": ids["load_id"]},
        )
        with pytest.raises(Exception, match="UNIQUE constraint failed"):
            conn.execute(
                text(
                    "INSERT INTO RECON_EXCEL_ROW (LOAD_ID, SOURCE_FILE_ID, "
                    "EXCEL_ROW_NO, DATA_JSON, IS_VALID) VALUES (:l, :f, 5, '{}', 'Y')"
                ),
                {"l": ids["load_id"], "f": ids["file_id"]},
            )


def test_batch_migration_downgrade_removes_batch_tables(temp_db_url: str) -> None:
    run_alembic_upgrade(temp_db_url, "head")
    run_alembic_downgrade(temp_db_url, "0005_export_claim")
    engine = create_engine(temp_db_url)
    names = set(inspect(engine).get_table_names())
    assert not (
        {"RECON_BATCH_DEF", "RECON_BATCH_DEF_ITEM", "RECON_BATCH_RUN", "RECON_BATCH_RUN_ITEM", "RECON_BATCH_RUN_FILE"}
        & names
    )
    run_cols = {c["name"] for c in inspect(engine).get_columns("RECON_RUN")}
    assert not ({"BATCH_RUN_ID", "BATCH_RUN_ITEM_ID"} & run_cols)
    load_cols = {c["name"] for c in inspect(engine).get_columns("RECON_EXCEL_LOAD")}
    assert not ({"FILE_SET_HASH", "SOURCE_FILES_JSON"} & load_cols)
    row_cols = {c["name"] for c in inspect(engine).get_columns("RECON_EXCEL_ROW")}
    assert "SOURCE_FILE_ID" not in row_cols
    pk = inspect(engine).get_pk_constraint("RECON_EXCEL_ROW")
    assert pk["constrained_columns"] == ["LOAD_ID", "EXCEL_ROW_NO"]
