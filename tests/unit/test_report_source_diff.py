"""Tests cho column/parameter diff — Bước 4 task 22 (test viết trước).

analyze_version_source (chỉ đọc) và apply_source_diff (chỉ version DRAFT)
khi nguồn đổi: cột mới/mất/đổi type, bind mới/mất (T22-08).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import (
    metadata,
    recon_audit_log,
    recon_rpt_column,
    recon_rpt_param,
    recon_rpt_tpl_ver,
)


@pytest.fixture()
def diff_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_diff.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_source",
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
    report_id = res.data["id"]

    def _make_template(code, **overrides):
        payload = {
            "code": code,
            "name": f"Mẫu {code}",
            "display_order": 10,
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        }
        payload.update(overrides)
        res = create_template(admin_ctx, report_id, payload)
        assert res.ok, res.message
        return res.data

    view_tpl = _make_template(
        "MAIN",
        data_source_id=ds_id,
        source_type="VIEW",
        source_owner="FIN",
        source_object="V_REVENUE",
    )
    sql_tpl = _make_template(
        "SQL1",
        data_source_id=ds_id,
        source_type="CUSTOM_SQL",
        sql_text="SELECT amount, org FROM fin_revenue WHERE org = :p_org",
    )
    nosrc_tpl = _make_template("NOSRC")

    with engine.begin() as conn:
        for ver_id in (view_tpl["id"], sql_tpl["id"]):
            for order, (field, dtype) in enumerate(
                [("AMOUNT", "NUMBER"), ("ORG", "STRING"), ("TXN_DATE", "DATE")]
            ):
                conn.execute(
                    recon_rpt_column.insert().values(
                        VERSION_ID=ver_id,
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
        for ver_id, param_defs in (
            (view_tpl["id"], (("p_org", "ORG", "STRING"), ("p_date", "TXN_DATE", "DATE"))),
            (sql_tpl["id"], (("p_org", "ORG", "STRING"),)),
        ):
            for code, col, dtype in param_defs:
                conn.execute(
                    recon_rpt_param.insert().values(
                        VERSION_ID=ver_id,
                        CODE=code,
                        LABEL=code,
                        DATA_TYPE=dtype,
                        CONTROL_TYPE="TEXT",
                        REQUIRED="N",
                        DISPLAY_ROW=1,
                        DISPLAY_ORDER=10,
                        GRID_SPAN=6,
                        FILTER_COLUMN=col,
                        FILTER_OPERATOR="=",
                        IS_VISIBLE="Y",
                    )
                )
    return {
        "engine": engine,
        "ds_id": ds_id,
        "view_version_id": view_tpl["id"],
        "sql_version_id": sql_tpl["id"],
        "nosrc_version_id": nosrc_tpl["id"],
    }


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


def _read_only_conn():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def _catalog_conn(rows):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


class TestAnalyzeView:
    def test_added_and_type_changed(self, diff_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import analyze_version_source

        invalidate_catalog_cache()
        ro_conn, _ = _read_only_conn()
        catalog_conn = _catalog_conn(
            [
                ("AMOUNT", "NUMBER", "Y", 22, 18, 2),
                ("ORG", "VARCHAR2", "Y", 60, None, None),
                ("REGION", "VARCHAR2", "Y", 30, None, None),
                ("TXN_DATE", "TIMESTAMP", "Y", 11, None, None),
            ]
        )
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
            res = analyze_version_source(admin_ctx, diff_env["view_version_id"])
        assert res.ok, res.message
        diff = res.data
        assert [c["name"] for c in diff["added"]] == ["REGION"]
        assert diff["added"][0]["data_type"] == "STRING"
        assert diff["removed"] == []
        assert diff["type_changed"] == [
            {"name": "TXN_DATE", "old_type": "DATE", "new_type": "DATETIME"}
        ]
        assert diff["new_binds"] == []
        assert diff["missing_binds"] == []

    def test_removed_column_and_stale_param(self, diff_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import analyze_version_source

        invalidate_catalog_cache()
        ro_conn, _ = _read_only_conn()
        catalog_conn = _catalog_conn(
            [
                ("AMOUNT", "NUMBER", "Y", 22, 18, 2),
                ("ORG", "VARCHAR2", "Y", 60, None, None),
            ]
        )
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
            res = analyze_version_source(admin_ctx, diff_env["view_version_id"])
        assert res.ok, res.message
        assert res.data["removed"] == ["TXN_DATE"]
        assert res.data["missing_binds"] == ["p_date"]

    def test_no_diff(self, diff_env, admin_ctx):
        from app.engine.catalog import invalidate_catalog_cache
        from app.services.report_source import analyze_version_source

        invalidate_catalog_cache()
        ro_conn, _ = _read_only_conn()
        catalog_conn = _catalog_conn(
            [
                ("AMOUNT", "NUMBER", "Y", 22, 18, 2),
                ("ORG", "VARCHAR2", "Y", 60, None, None),
                ("TXN_DATE", "DATE", "Y", 7, None, None),
            ]
        )
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
            res = analyze_version_source(admin_ctx, diff_env["view_version_id"])
        assert res.ok, res.message
        assert res.data == {
            "added": [],
            "removed": [],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": [],
        }


class TestAnalyzeCustomSql:
    def _sql_conn(self, description):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = description
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    def test_added_and_new_bind(self, diff_env, admin_ctx):
        from app.services.report_source import analyze_version_source

        conn = self._sql_conn(
            [
                ("AMOUNT", SimpleNamespace(name="DB_TYPE_NUMBER"), 0, 0, 18, 2, True),
                ("ORG", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 60, 0, True),
                ("CHANNEL", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 20, 0, True),
            ]
        )
        engine = diff_env["engine"]
        with engine.begin() as db:
            db.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == diff_env["sql_version_id"])
                .values(
                    SQL_TEXT="SELECT amount, org, channel FROM fin_revenue "
                    "WHERE org = :p_org AND channel = :p_channel"
                )
            )
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = analyze_version_source(admin_ctx, diff_env["sql_version_id"])
        assert res.ok, res.message
        assert [c["name"] for c in res.data["added"]] == ["CHANNEL"]
        assert res.data["removed"] == ["TXN_DATE"]
        assert res.data["new_binds"] == ["p_channel"]
        assert res.data["missing_binds"] == []

    def test_missing_bind(self, diff_env, admin_ctx):
        from app.services.report_source import analyze_version_source

        conn = self._sql_conn(
            [
                ("AMOUNT", SimpleNamespace(name="DB_TYPE_NUMBER"), 0, 0, 18, 2, True),
                ("ORG", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 60, 0, True),
            ]
        )
        engine = diff_env["engine"]
        with engine.begin() as db:
            db.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == diff_env["sql_version_id"])
                .values(SQL_TEXT="SELECT amount, org FROM fin_revenue")
            )
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = analyze_version_source(admin_ctx, diff_env["sql_version_id"])
        assert res.ok, res.message
        assert res.data["missing_binds"] == ["p_org"]


class TestAnalyzeErrors:
    def test_version_not_found(self, diff_env, admin_ctx):
        from app.services.report_source import analyze_version_source

        res = analyze_version_source(admin_ctx, 999999)
        assert not res.ok and res.code == "NOT_FOUND"

    def test_version_without_source(self, diff_env, admin_ctx):
        from app.services.report_source import analyze_version_source

        res = analyze_version_source(admin_ctx, diff_env["nosrc_version_id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_forbidden_for_operator(self, diff_env, operator_ctx):
        from app.services.report_source import analyze_version_source

        res = analyze_version_source(operator_ctx, diff_env["view_version_id"])
        assert not res.ok and res.code == "FORBIDDEN"


class TestApplySourceDiff:
    def test_apply_added_and_type_changed(self, diff_env, admin_ctx):
        from app.services.report_source import apply_source_diff

        diff = {
            "added": [
                {
                    "name": "REGION",
                    "data_type": "STRING",
                    "oracle_data_type": "VARCHAR2",
                    "nullable": True,
                    "length": 30,
                    "precision": None,
                    "scale": None,
                }
            ],
            "removed": [],
            "type_changed": [
                {"name": "TXN_DATE", "old_type": "DATE", "new_type": "DATETIME"}
            ],
            "new_binds": [],
            "missing_binds": [],
        }
        res = apply_source_diff(admin_ctx, diff_env["view_version_id"], diff)
        assert res.ok, res.message
        engine = diff_env["engine"]
        with engine.connect() as conn:
            cols = {
                r["FIELD_NAME"]: dict(r)
                for r in conn.execute(
                    select(recon_rpt_column).where(
                        recon_rpt_column.c.VERSION_ID
                        == diff_env["view_version_id"]
                    )
                ).mappings()
            }
            audit = conn.execute(
                select(recon_audit_log).where(
                    recon_audit_log.c.ENTITY == "RECON_RPT_TPL_VER",
                    recon_audit_log.c.ACTION == "UPDATE_VERSION_SOURCE",
                )
            ).mappings().all()
        assert cols["REGION"]["DATA_TYPE"] == "STRING"
        assert cols["REGION"]["WEB_VISIBLE"] == "Y"
        assert cols["REGION"]["DISPLAY_ORDER"] == 40
        assert cols["TXN_DATE"]["DATA_TYPE"] == "DATETIME"
        assert len(audit) == 1

    def test_apply_removed_keeps_row_but_hides(self, diff_env, admin_ctx):
        from app.services.report_source import apply_source_diff

        diff = {
            "added": [],
            "removed": ["TXN_DATE"],
            "type_changed": [],
            "new_binds": [],
            "missing_binds": ["p_date"],
        }
        res = apply_source_diff(admin_ctx, diff_env["view_version_id"], diff)
        assert res.ok, res.message
        engine = diff_env["engine"]
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(recon_rpt_column).where(
                        recon_rpt_column.c.VERSION_ID
                        == diff_env["view_version_id"],
                        recon_rpt_column.c.FIELD_NAME == "TXN_DATE",
                    )
                )
                .mappings()
                .first()
            )
        assert row is not None  # Q6: giữ dòng, không xóa
        assert row["WEB_VISIBLE"] == "N"
        assert row["EXCEL_VISIBLE"] == "N"

    def test_apply_rejects_non_draft(self, diff_env, admin_ctx):
        from app.services.report_source import apply_source_diff

        engine = diff_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == diff_env["view_version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = apply_source_diff(
            admin_ctx,
            diff_env["view_version_id"],
            {"added": [], "removed": [], "type_changed": [], "new_binds": [], "missing_binds": []},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_apply_forbidden_for_operator(self, diff_env, operator_ctx):
        from app.services.report_source import apply_source_diff

        res = apply_source_diff(
            operator_ctx,
            diff_env["view_version_id"],
            {"added": [], "removed": [], "type_changed": [], "new_binds": [], "missing_binds": []},
        )
        assert not res.ok and res.code == "FORBIDDEN"
