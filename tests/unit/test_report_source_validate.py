"""Tests cho validate_version_sql — Bước 1 task 22 (test viết trước).

Service kiểm tra SQL CUSTOM_SQL của version: validator SELECT-only
rồi describe thử qua Oracle (0 dòng) để lấy column metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata


@pytest.fixture()
def validate_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_validate.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in ["app.services.menu_sync", "app.services.perm", "app.services.report_source"]:
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
                "CALL_TIMEOUT_S, MAX_ROWS, IS_CURRENT_METADATA, IS_ACTIVE, CREATED_BY, CREATED_AT, UPDATED_AT) "
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


def _mock_ora_conn():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.description = [
        ("AMOUNT", SimpleNamespace(name="DB_TYPE_NUMBER"), 0, 0, 18, 2, True),
        ("ORG", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 60, 0, True),
        ("TXN_DATE", SimpleNamespace(name="DB_TYPE_DATE"), 0, 0, 0, 0, True),
    ]
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestValidateVersionSql:
    def test_validate_ok_returns_binds_and_columns(self, validate_env, admin_ctx):
        from app.services.report_source import validate_version_sql

        _, ds_id = validate_env
        mock_conn, mock_cursor = _mock_ora_conn()
        sql = "SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org"
        with patch(
            "app.services.report_source.open_source_connection", return_value=mock_conn
        ):
            res = validate_version_sql(admin_ctx, sql, ds_id)
        assert res.ok, res.message
        assert res.data["binds"] == ["p_org"]
        assert [c["name"] for c in res.data["columns"]] == ["AMOUNT", "ORG", "TXN_DATE"]
        assert res.data["columns"][0]["data_type"] == "NUMBER"
        # Timeout = min(300 mặc định, CALL_TIMEOUT_S=30 của Data Source)
        assert mock_conn.call_timeout == 30 * 1000
        wrapped = mock_cursor.parse.call_args[0][0]
        assert "WHERE 1=0" in wrapped

    def test_validate_rejects_bad_sql(self, validate_env, admin_ctx):
        from app.services.report_source import validate_version_sql

        _, ds_id = validate_env
        res = validate_version_sql(admin_ctx, "DELETE FROM fin_revenue", ds_id)
        assert not res.ok and res.code == "SQL_NOT_ALLOWED"

    def test_validate_describe_failure(self, validate_env, admin_ctx):
        from app.services.report_source import validate_version_sql

        _, ds_id = validate_env
        mock_conn, mock_cursor = _mock_ora_conn()
        mock_cursor.parse.side_effect = Exception("ORA-00942: table or view does not exist")
        with patch(
            "app.services.report_source.open_source_connection", return_value=mock_conn
        ):
            res = validate_version_sql(
                admin_ctx, "SELECT * FROM missing_table", ds_id
            )
        assert not res.ok and res.code == "SQL_DESCRIBE_FAILED"

    def test_validate_forbidden_for_operator(self, validate_env, operator_ctx):
        from app.services.report_source import validate_version_sql

        _, ds_id = validate_env
        res = validate_version_sql(
            operator_ctx, "SELECT * FROM fin_revenue", ds_id
        )
        assert not res.ok and res.code == "FORBIDDEN"
