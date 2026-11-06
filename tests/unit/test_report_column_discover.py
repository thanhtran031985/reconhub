"""Tests cho Auto-discover column metadata — Bước 1 task 24 (test viết trước).

list_columns (T24-01) và refresh_columns (cột mới/mất/đổi type, default theo type).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_column, recon_rpt_tpl_ver


@pytest.fixture()
def column_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_column.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_source",
        "app.services.report_column",
        "app.engine.catalog",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.report import create_report
    from app.services.report_template import create_template
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator"), (3, "norole")]:
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

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    res = create_report(
        admin_ctx,
        {
            "code": "FIN_REVENUE",
            "name": "Doanh thu",
            "category_code": "FIN",
            "owner": "admin",
            "is_visible": True,
        },
    )
    assert res.ok, res.message
    res = create_template(
        admin_ctx,
        res.data["id"],
        {
            "code": "MAIN",
            "name": "Mẫu chính",
            "display_order": 10,
            "data_source_id": ds_id,
            "source_type": "CUSTOM_SQL",
            "sql_text": "SELECT amount, org, txn_date FROM fin_revenue",
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        },
    )
    assert res.ok, res.message
    version_id = res.data["id"]
    with engine.begin() as conn:
        for order, (field, dtype) in enumerate(
            [("AMOUNT", "NUMBER"), ("ORG", "STRING"), ("TXN_DATE", "DATE")]
        ):
            conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=version_id,
                    FIELD_NAME=field,
                    LABEL=field,
                    DATA_TYPE=dtype,
                    DISPLAY_ORDER=(order + 1) * 10,
                    WEB_VISIBLE="Y",
                    EXCEL_VISIBLE="Y",
                    ALIGNMENT="LEFT",
                    IS_TOTAL="N",
                )
            )
    return {"engine": engine, "ds_id": ds_id, "version_id": version_id}


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def norole_ctx() -> Ctx:
    return Ctx(user_id=3, username="norole", full_name="norole", roles=[])


def _sql_conn(description):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.description = description
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


def _col(description_name, db_type):
    return (description_name, SimpleNamespace(name=db_type), 0, 0, 60, 0, True)


class TestListColumns:
    def test_grid_has_all_fields(self, column_env, admin_ctx):
        from app.services.report_column import list_columns

        res = list_columns(admin_ctx, column_env["version_id"])
        assert res.ok, res.message
        assert len(res.data) == 3
        assert [c["field_name"] for c in res.data] == ["AMOUNT", "ORG", "TXN_DATE"]
        first = res.data[0]
        for key in (
            "id",
            "field_name",
            "label",
            "data_type",
            "display_order",
            "web_visible",
            "excel_visible",
            "format_mask",
            "alignment",
            "width",
            "is_total",
        ):
            assert key in first, f"thiếu trường {key}"
        assert first["data_type"] == "NUMBER"
        assert first["web_visible"] is True and first["excel_visible"] is True
        assert first["is_total"] is False

    def test_list_allowed_for_operator(self, column_env, operator_ctx):
        from app.services.report_column import list_columns

        res = list_columns(operator_ctx, column_env["version_id"])
        assert res.ok, res.message

    def test_list_forbidden_without_menu(self, column_env, norole_ctx):
        from app.services.report_column import list_columns

        res = list_columns(norole_ctx, column_env["version_id"])
        assert not res.ok and res.code == "FORBIDDEN"


class TestRefreshColumns:
    def test_refresh_adds_new_columns_with_type_defaults(self, column_env, admin_ctx):
        from app.services.report_column import list_columns, refresh_columns

        conn = _sql_conn(
            [
                _col("AMOUNT", "DB_TYPE_NUMBER"),
                _col("ORG", "DB_TYPE_VARCHAR"),
                _col("TXN_DATE", "DB_TYPE_DATE"),
                _col("CHANNEL", "DB_TYPE_VARCHAR"),
                _col("QTY", "DB_TYPE_NUMBER"),
                _col("DUE_DATE", "DB_TYPE_DATE"),
                _col("UPDATED_AT", "DB_TYPE_TIMESTAMP"),
            ]
        )
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = refresh_columns(admin_ctx, column_env["version_id"])
        assert res.ok, res.message
        assert [c["name"] for c in res.data["diff"]["added"]] == [
            "CHANNEL",
            "QTY",
            "DUE_DATE",
            "UPDATED_AT",
        ]
        by_field = {
            c["field_name"]: c
            for c in list_columns(admin_ctx, column_env["version_id"]).data
        }
        assert len(by_field) == 7
        # Default theo type (Q6)
        assert by_field["CHANNEL"]["alignment"] == "LEFT"
        assert by_field["CHANNEL"]["width"] == 180
        assert by_field["QTY"]["alignment"] == "RIGHT"
        assert by_field["QTY"]["width"] == 120
        assert by_field["DUE_DATE"]["alignment"] == "CENTER"
        assert by_field["DUE_DATE"]["width"] == 110
        assert by_field["UPDATED_AT"]["alignment"] == "CENTER"
        assert by_field["UPDATED_AT"]["width"] == 160
        assert by_field["UPDATED_AT"]["data_type"] == "DATETIME"
        # Cột cũ không đổi
        assert by_field["AMOUNT"]["display_order"] == 10

    def test_refresh_no_diff(self, column_env, admin_ctx):
        from app.services.report_column import refresh_columns

        conn = _sql_conn(
            [
                _col("AMOUNT", "DB_TYPE_NUMBER"),
                _col("ORG", "DB_TYPE_VARCHAR"),
                _col("TXN_DATE", "DB_TYPE_DATE"),
            ]
        )
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = refresh_columns(admin_ctx, column_env["version_id"])
        assert res.ok, res.message
        assert res.data["diff"]["added"] == []
        assert res.data["diff"]["removed"] == []
        assert res.data["diff"]["type_changed"] == []

    def test_refresh_rejects_non_draft(self, column_env, admin_ctx):
        from app.services.report_column import refresh_columns

        engine = column_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == column_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = refresh_columns(admin_ctx, column_env["version_id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_refresh_forbidden_for_operator(self, column_env, operator_ctx):
        from app.services.report_column import refresh_columns

        res = refresh_columns(operator_ctx, column_env["version_id"])
        assert not res.ok and res.code == "FORBIDDEN"
