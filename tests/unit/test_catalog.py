from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine

from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source
from app.engine.catalog import (
    invalidate_catalog_cache,
    list_columns,
    list_tables,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services.source_conn import open_source_connection


@pytest.fixture
def catalog_env(tmp_path, monkeypatch):
    invalidate_catalog_cache()
    db_file = tmp_path / "catalog_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_data_source.insert().values(
                NAME="ORCL_SRC_TEST",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="10.10.10.1",
                PORT=1521,
                SERVICE_NAME="ORCLPDB",
                USERNAME="RECON_RO",
                PASSWORD_ENC=encrypt_secret("testPass"),
                DEFAULT_SCHEMA="RECON_SRC",
                CALL_TIMEOUT_S=30,
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res.inserted_primary_key[0]

    return engine, ds_id


def test_open_source_connection_success(catalog_env) -> None:
    _, ds_id = catalog_env

    mock_conn = MagicMock()
    with patch("oracledb.connect", return_value=mock_conn) as mock_connect:
        conn = open_source_connection(ds_id)
        assert conn == mock_conn
        mock_connect.assert_called_once()
        assert conn.call_timeout == 30 * 1000


def test_open_source_connection_failure_maps_to_error_code(catalog_env) -> None:
    _, ds_id = catalog_env

    with patch("oracledb.connect", side_effect=Exception("Connection refused")):
        with pytest.raises(ServiceError) as exc_info:
            open_source_connection(ds_id)
        assert exc_info.value.code == ErrorCode.SOURCE_CONNECTION_LOST


def test_catalog_list_tables_and_cache(catalog_env) -> None:
    _, ds_id = catalog_env

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Giả lập trả về 2 bảng/view
    mock_cursor.fetchall.return_value = [
        ("SRC_FACT_INVOICE_DTP", "TABLE"),
        ("V_INVOICE_SUMMARY", "VIEW"),
    ]
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.engine.catalog.open_source_connection", return_value=mock_conn):
        # Lần 1: Gọi mở kết nối và truy vấn DB
        tables = list_tables(ds_id, schema="RECON_SRC")
        assert len(tables) == 2
        assert tables[0]["name"] == "SRC_FACT_INVOICE_DTP"
        assert tables[0]["type"] == "TABLE"
        assert mock_conn.cursor.call_count == 1

        # Lần 2: Nằm trong cache 10 phút, không gọi DB lại
        cached_tables = list_tables(ds_id, schema="RECON_SRC")
        assert len(cached_tables) == 2
        assert mock_conn.cursor.call_count == 1  # Vẫn là 1

        # Lọc theo từ khóa `q`
        filtered = list_tables(ds_id, schema="RECON_SRC", q="FACT")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "SRC_FACT_INVOICE_DTP"


def test_catalog_list_columns(catalog_env) -> None:
    _, ds_id = catalog_env

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # Giả lập 3 cột của bảng SRC_FACT_INVOICE_DTP
    mock_cursor.fetchall.return_value = [
        ("INVOICE_ID", "NUMBER", "N", 22, 19, 0),
        ("INVOICE_NO", "VARCHAR2", "N", 60, None, None),
        ("TOTAL_AMOUNT", "NUMBER", "Y", 22, 18, 2),
    ]
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.engine.catalog.open_source_connection", return_value=mock_conn):
        cols = list_columns(ds_id, schema="RECON_SRC", table_name="SRC_FACT_INVOICE_DTP")
        assert len(cols) == 3
        assert cols[0]["name"] == "INVOICE_ID"
        assert cols[0]["nullable"] is False
        assert cols[1]["name"] == "INVOICE_NO"
        assert cols[1]["data_type"] == "VARCHAR2"
        assert cols[2]["precision"] == 18
        assert cols[2]["scale"] == 2
