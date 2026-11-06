"""Tests cho Preview và schema diff — Bước 4 task 24 (test viết trước).

get_result_layout, preview_result_layout, restore_column_order
(T24-05, T24-08, T24-09, T24-10).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_column, recon_rpt_tpl_ver


@pytest.fixture()
def preview_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_col_preview.db"
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


def _col_ids(engine, version_id):
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_rpt_column)
                .where(recon_rpt_column.c.VERSION_ID == version_id)
                .order_by(recon_rpt_column.c.DISPLAY_ORDER)
            )
            .mappings()
            .all()
        )
    return {r["FIELD_NAME"]: int(r["ID"]) for r in rows}


class TestGetResultLayout:
    def test_web_and_excel_share_metadata(self, preview_env, admin_ctx):
        from app.services.report_column import get_result_layout

        web = get_result_layout(admin_ctx, preview_env["version_id"], "web")
        excel = get_result_layout(admin_ctx, preview_env["version_id"], "excel")
        assert web.ok and excel.ok
        # Cùng metadata: field/label/type/format/order giống nhau
        for w, e in zip(web.data["columns"], excel.data["columns"], strict=False):
            assert w["field_name"] == e["field_name"]
            assert w["label"] == e["label"]
            assert w["data_type"] == e["data_type"]
            assert w["format_mask"] == e["format_mask"]
            assert w["alignment"] == e["alignment"]
            assert w["width"] == e["width"]
            assert w["display_order"] == e["display_order"]
        assert [c["field_name"] for c in web.data["columns"]] == [
            "AMOUNT",
            "ORG",
            "TXN_DATE",
        ]
        assert web.data["total_row"] is False

    def test_web_false_excel_true(self, preview_env, admin_ctx):
        from app.services.report_column import get_result_layout, update_column

        ids = _col_ids(preview_env["engine"], preview_env["version_id"])
        res = update_column(
            admin_ctx,
            preview_env["version_id"],
            ids["ORG"],
            {"web_visible": False, "excel_visible": True},
        )
        assert res.ok, res.message
        web = get_result_layout(admin_ctx, preview_env["version_id"], "web")
        excel = get_result_layout(admin_ctx, preview_env["version_id"], "excel")
        assert [c["field_name"] for c in web.data["columns"]] == [
            "AMOUNT",
            "TXN_DATE",
        ]
        assert [c["field_name"] for c in excel.data["columns"]] == [
            "AMOUNT",
            "ORG",
            "TXN_DATE",
        ]

    def test_total_row_flag(self, preview_env, admin_ctx):
        from app.services.report_column import get_result_layout, update_column

        ids = _col_ids(preview_env["engine"], preview_env["version_id"])
        assert update_column(
            admin_ctx,
            preview_env["version_id"],
            ids["AMOUNT"],
            {"is_total": True},
        ).ok
        res = get_result_layout(admin_ctx, preview_env["version_id"], "web")
        assert res.ok, res.message
        assert res.data["total_row"] is True
        assert res.data["columns"][0]["is_total"] is True

    def test_layout_validation(self, preview_env, admin_ctx, norole_ctx):
        from app.services.report_column import get_result_layout

        res = get_result_layout(admin_ctx, preview_env["version_id"], "pdf")
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = get_result_layout(norole_ctx, preview_env["version_id"], "web")
        assert not res.ok and res.code == "FORBIDDEN"


class TestPreviewResultLayout:
    def test_preview_updates_immediately(self, preview_env, admin_ctx):
        from app.services.report_column import preview_result_layout, update_column

        res = preview_result_layout(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert res.data["columns"][0]["label"] == "AMOUNT"
        ids = _col_ids(preview_env["engine"], preview_env["version_id"])
        assert update_column(
            admin_ctx,
            preview_env["version_id"],
            ids["AMOUNT"],
            {"label": "Số tiền", "web_visible": False},
        ).ok
        # Preview đọc lại từ DB nên thấy ngay thay đổi, không cần cache bust
        res = preview_result_layout(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert [c["field_name"] for c in res.data["columns"]] == [
            "ORG",
            "TXN_DATE",
        ]


class TestRestoreColumnOrder:
    def test_restore_db_order(self, preview_env, admin_ctx):
        from app.services.report_column import (
            list_columns,
            reorder_columns,
            restore_column_order,
        )

        ids = _col_ids(preview_env["engine"], preview_env["version_id"])
        assert reorder_columns(
            admin_ctx,
            preview_env["version_id"],
            [ids["TXN_DATE"], ids["ORG"], ids["AMOUNT"]],
        ).ok
        cols = list_columns(admin_ctx, preview_env["version_id"]).data
        assert [c["field_name"] for c in cols] == ["TXN_DATE", "ORG", "AMOUNT"]
        res = restore_column_order(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert [c["field_name"] for c in res.data["columns"]] == [
            "AMOUNT",
            "ORG",
            "TXN_DATE",
        ]
        assert [c["display_order"] for c in res.data["columns"]] == [10, 20, 30]

    def test_restore_validation(self, preview_env, admin_ctx, operator_ctx):
        from app.services.report_column import restore_column_order

        res = restore_column_order(operator_ctx, preview_env["version_id"])
        assert not res.ok and res.code == "FORBIDDEN"
        engine = preview_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == preview_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = restore_column_order(admin_ctx, preview_env["version_id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"
