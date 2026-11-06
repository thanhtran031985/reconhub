"""Tests cho Oracle metadata discovery — Bước 2 task 22 (test viết trước).

list_report_objects (VIEW/TABLE), list_report_columns + map kiểu Oracle
(T22-04, T22-05, T22-07 nhánh mock), kiểm tra read-only (T22-09).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata


@pytest.fixture()
def discovery_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_discovery.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report_source",
        "app.engine.catalog",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
        res = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, USERNAME, PASSWORD_ENC, DEFAULT_SCHEMA, "
                "CALL_TIMEOUT_S, MAX_ROWS, IS_CURRENT_METADATA, IS_ACTIVE, CREATED_BY, "
                "CREATED_AT, UPDATED_AT) "
                "VALUES ('ORCL', 'DEV', 'SOURCE', 'ORACLE', '10.0.0.1', 1521, "
                "'ORCLPDB', 'RECON_RO', :pw, 'FIN', 30, 10000, 'N', 'Y', 'SEED', :now, :now)"
            ),
            {"pw": encrypt_secret("testPass"), "now": now},
        )
        ds_id = int(res.lastrowid)
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]})
    clear_perm_cache()
    return engine, ds_id


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


def _read_only_conn():
    """Kết nối Oracle giả lập: account chỉ đọc (USER_SYS_PRIVS rỗng)."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestMapOracleType:
    def test_types(self):
        from app.services.report_source import map_oracle_type

        assert map_oracle_type("DATE") == "DATE"
        assert map_oracle_type("TIMESTAMP") == "DATETIME"
        assert map_oracle_type("TIMESTAMP(6)") == "DATETIME"
        assert map_oracle_type("NUMBER") == "NUMBER"
        assert map_oracle_type("FLOAT") == "NUMBER"
        assert map_oracle_type("VARCHAR2") == "STRING"
        assert map_oracle_type("CHAR") == "STRING"
        assert map_oracle_type("NVARCHAR2") == "STRING"
        assert map_oracle_type("CLOB") == "STRING"
        assert map_oracle_type("BLOB") == "BINARY"
        assert map_oracle_type("KIEU_LA") == "STRING"


class TestListReportObjects:
    def test_list_views_only(self, discovery_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import list_report_objects

        invalidate_catalog_cache()
        _, ds_id = discovery_env
        ro_conn, _ = _read_only_conn()
        catalog_conn = MagicMock()
        catalog_cursor = MagicMock()
        catalog_cursor.fetchall.return_value = [("V_REVENUE", "VIEW")]
        catalog_conn.cursor.return_value = catalog_cursor
        with (
            patch(
                "app.services.report_source.open_source_connection",
                return_value=ro_conn,
            ),
            patch(
                "app.engine.catalog.open_source_connection",
                return_value=catalog_conn,
            ),
        ):
            res = list_report_objects(admin_ctx, ds_id, "VIEW")
        assert res.ok, res.message
        assert res.data == [{"name": "V_REVENUE", "type": "VIEW", "schema": "FIN"}]
        executed_sql = catalog_cursor.execute.call_args[0][0]
        assert "ALL_VIEWS" in executed_sql
        assert "ALL_TABLES" not in executed_sql

    def test_list_tables_only(self, discovery_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import list_report_objects

        invalidate_catalog_cache()
        _, ds_id = discovery_env
        ro_conn, _ = _read_only_conn()
        catalog_conn = MagicMock()
        catalog_cursor = MagicMock()
        catalog_cursor.fetchall.return_value = [("FIN_REVENUE", "TABLE")]
        catalog_conn.cursor.return_value = catalog_cursor
        with (
            patch(
                "app.services.report_source.open_source_connection",
                return_value=ro_conn,
            ),
            patch(
                "app.engine.catalog.open_source_connection",
                return_value=catalog_conn,
            ),
        ):
            res = list_report_objects(admin_ctx, ds_id, "TABLE")
        assert res.ok, res.message
        assert res.data == [{"name": "FIN_REVENUE", "type": "TABLE", "schema": "FIN"}]
        executed_sql = catalog_cursor.execute.call_args[0][0]
        assert "ALL_TABLES" in executed_sql
        assert "ALL_VIEWS" not in executed_sql

    def test_invalid_source_type(self, discovery_env, admin_ctx):
        from app.services.report_source import list_report_objects

        _, ds_id = discovery_env
        res = list_report_objects(admin_ctx, ds_id, "CUSTOM_SQL")
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_write_account_rejected(self, discovery_env, admin_ctx):
        from app.services.report_source import list_report_objects

        _, ds_id = discovery_env
        write_conn = MagicMock()
        write_cursor = MagicMock()
        write_cursor.fetchall.return_value = [("INSERT ANY TABLE",)]
        write_conn.cursor.return_value = write_cursor
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=write_conn,
        ):
            res = list_report_objects(admin_ctx, ds_id, "VIEW")
        assert not res.ok and res.code == "DS_NOT_READ_ONLY"

    def test_forbidden_for_operator(self, discovery_env, operator_ctx):
        from app.services.report_source import list_report_objects

        _, ds_id = discovery_env
        res = list_report_objects(operator_ctx, ds_id, "VIEW")
        assert not res.ok and res.code == "FORBIDDEN"


class TestListReportColumns:
    def test_columns_mapped(self, discovery_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import list_report_columns

        invalidate_catalog_cache()
        _, ds_id = discovery_env
        ro_conn, _ = _read_only_conn()
        catalog_conn = MagicMock()
        catalog_cursor = MagicMock()
        catalog_cursor.fetchall.return_value = [
            ("AMOUNT", "NUMBER", "Y", 22, 18, 2),
            ("ORG", "VARCHAR2", "Y", 60, None, None),
            ("TXN_DATE", "DATE", "N", 7, None, None),
            ("NOTE", "CLOB", "Y", 4000, None, None),
            ("CREATED_AT", "TIMESTAMP", "Y", 11, None, None),
        ]
        catalog_conn.cursor.return_value = catalog_cursor
        with (
            patch(
                "app.services.report_source.open_source_connection",
                return_value=ro_conn,
            ),
            patch(
                "app.engine.catalog.open_source_connection",
                return_value=catalog_conn,
            ),
        ):
            res = list_report_columns(admin_ctx, ds_id, "FIN", "V_REVENUE")
        assert res.ok, res.message
        by_name = {c["name"]: c for c in res.data}
        assert by_name["AMOUNT"]["data_type"] == "NUMBER"
        assert by_name["AMOUNT"]["oracle_data_type"] == "NUMBER"
        assert by_name["ORG"]["data_type"] == "STRING"
        assert by_name["TXN_DATE"]["data_type"] == "DATE"
        assert by_name["NOTE"]["data_type"] == "STRING"
        assert by_name["CREATED_AT"]["data_type"] == "DATETIME"
        assert by_name["TXN_DATE"]["nullable"] is False

    def test_empty_owner_or_object(self, discovery_env, admin_ctx):
        from app.services.report_source import list_report_columns

        _, ds_id = discovery_env
        res = list_report_columns(admin_ctx, ds_id, "", "V_REVENUE")
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = list_report_columns(admin_ctx, ds_id, "FIN", "")
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_forbidden_for_operator(self, discovery_env, operator_ctx):
        from app.services.report_source import list_report_columns

        _, ds_id = discovery_env
        res = list_report_columns(operator_ctx, ds_id, "FIN", "V_REVENUE")
        assert not res.ok and res.code == "FORBIDDEN"
