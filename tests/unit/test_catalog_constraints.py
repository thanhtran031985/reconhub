"""Tests cho mở rộng catalog đọc PK/FK constraints và ước lượng số dòng (Bước 2 task 106)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source
from app.engine.catalog import (
    estimate_table_rows,
    invalidate_catalog_cache,
    list_columns,
    list_table_constraints,
    list_tables,
)


@pytest.fixture
def ds_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_catalog_cache()
    meta_db = tmp_path / "meta.db"
    meta_url = f"sqlite:///{meta_db.as_posix()}"
    src_db = tmp_path / "star_source.db"
    monkeypatch.setenv("RECON_DB_URL", meta_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    from app.core.config import get_settings

    get_settings.cache_clear()

    meta_engine = create_engine(meta_url)
    metadata.create_all(meta_engine)

    src_engine = create_engine(f"sqlite:///{src_db.as_posix()}")
    with src_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE DIM_CUSTOMER (
                    CUSTOMER_ID INTEGER PRIMARY KEY,
                    CUSTOMER_CODE TEXT NOT NULL UNIQUE,
                    CUSTOMER_NAME TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE FACT_SALES (
                    SALES_ID INTEGER PRIMARY KEY,
                    CUSTOMER_ID INTEGER NOT NULL,
                    AMOUNT NUMERIC NOT NULL,
                    FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMER(CUSTOMER_ID)
                )
                """
            )
        )
        conn.execute(text("CREATE VIEW V_SALES AS SELECT SALES_ID, CUSTOMER_ID, AMOUNT FROM FACT_SALES"))
        conn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'C01', 'Cong ty A'), (2, 'C02', 'Cong ty B')"))
        conn.execute(text("INSERT INTO FACT_SALES VALUES (10, 1, 1000), (11, 2, 2000), (12, 1, 500)"))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with meta_engine.begin() as conn:
        res_sq = conn.execute(
            recon_data_source.insert().values(
                NAME="SQLITE_STAR",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(src_db),
                CALL_TIMEOUT_S=30,
                MAX_ROWS=1000000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        sqlite_ds_id = int(res_sq.inserted_primary_key[0])

        res_ora = conn.execute(
            recon_data_source.insert().values(
                NAME="ORA_STAR",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="10.0.0.1",
                PORT=1521,
                SERVICE_NAME="ORCLPDB",
                USERNAME="RECON_RO",
                PASSWORD_ENC=encrypt_secret("secret"),
                DEFAULT_SCHEMA="DWH",
                CALL_TIMEOUT_S=30,
                MAX_ROWS=1000000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ora_ds_id = int(res_ora.inserted_primary_key[0])

    yield meta_engine, src_engine, sqlite_ds_id, ora_ds_id
    src_engine.dispose()
    meta_engine.dispose()


def test_sqlite_constraints_and_row_estimate(ds_env) -> None:
    _, _, sqlite_ds_id, _ = ds_env

    tbls = list_tables(sqlite_ds_id)
    names = {t["name"]: t["type"] for t in tbls}
    assert names["DIM_CUSTOMER"] == "TABLE"
    assert names["FACT_SALES"] == "TABLE"
    assert names["V_SALES"] == "VIEW"

    cols = list_columns(sqlite_ds_id, "main", "FACT_SALES")
    assert [c["name"] for c in cols] == ["SALES_ID", "CUSTOMER_ID", "AMOUNT"]

    c_dim = list_table_constraints(sqlite_ds_id, "main", "DIM_CUSTOMER")
    assert c_dim["primary_key"] == ["CUSTOMER_ID"]
    assert ["CUSTOMER_CODE"] in c_dim["unique_keys"]
    assert c_dim["foreign_keys"] == []

    c_fact = list_table_constraints(sqlite_ds_id, "main", "FACT_SALES")
    assert c_fact["primary_key"] == ["SALES_ID"]
    assert len(c_fact["foreign_keys"]) == 1
    fk = c_fact["foreign_keys"][0]
    assert fk["columns"] == ["CUSTOMER_ID"]
    assert fk["ref_table"] == "DIM_CUSTOMER"
    assert fk["ref_columns"] == ["CUSTOMER_ID"]

    c_view = list_table_constraints(sqlite_ds_id, "main", "V_SALES")
    assert c_view == {"primary_key": [], "unique_keys": [], "foreign_keys": []}

    assert estimate_table_rows(sqlite_ds_id, "main", "DIM_CUSTOMER") == 2
    assert estimate_table_rows(sqlite_ds_id, "main", "FACT_SALES") == 3
    assert estimate_table_rows(sqlite_ds_id, "main", "V_SALES") is None


def test_oracle_constraints_and_row_estimate_with_cache(ds_env) -> None:
    _, _, _, ora_ds_id = ds_env

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Query 1: PK/UK/FK rows; Query 2: NUM_ROWS; Query 3: empty view constraints; Query 4: empty view NUM_ROWS
    mock_cursor.fetchall.side_effect = [
        [
            ("PK_FACT_SALES", "P", "SALES_ID", 1, None, None, None),
            ("UQ_FACT_CODE", "U", "INVOICE_NO", 1, None, None, None),
            ("FK_FACT_CUST", "R", "CUSTOMER_ID", 1, "DWH", "DIM_CUSTOMER", "CUSTOMER_ID"),
        ],
        [],  # view constraints
    ]
    mock_cursor.fetchone.side_effect = [
        (1250000,),
        None,
    ]
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.engine.catalog.open_source_connection", return_value=mock_conn):
        res = list_table_constraints(ora_ds_id, "DWH", "FACT_SALES")
        assert res["primary_key"] == ["SALES_ID"]
        assert res["unique_keys"] == [["INVOICE_NO"]]
        assert res["foreign_keys"] == [
            {
                "name": "FK_FACT_CUST",
                "columns": ["CUSTOMER_ID"],
                "ref_schema": "DWH",
                "ref_table": "DIM_CUSTOMER",
                "ref_columns": ["CUSTOMER_ID"],
            }
        ]
        # Cache hit không mở cursor thêm lần nữa
        res_cached = list_table_constraints(ora_ds_id, "DWH", "FACT_SALES")
        assert res_cached == res
        assert mock_cursor.execute.call_count == 1

        rows_est = estimate_table_rows(ora_ds_id, "DWH", "FACT_SALES")
        assert rows_est == 1250000
        assert estimate_table_rows(ora_ds_id, "DWH", "FACT_SALES") == 1250000
        assert mock_cursor.execute.call_count == 2

        view_c = list_table_constraints(ora_ds_id, "DWH", "V_EMPTY")
        assert view_c == {"primary_key": [], "unique_keys": [], "foreign_keys": []}
        assert estimate_table_rows(ora_ds_id, "DWH", "V_EMPTY") is None

        invalidate_catalog_cache(ora_ds_id)
