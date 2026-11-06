"""Tests cho Format/alignment/width/visibility/total — Bước 3 task 24 (test viết trước).

Rule kiểm tra ở update_column/update_columns (T24-03, T24-04, T24-06, T24-07).
T24-05 (web false/excel true) kiểm tra ở bước 4 qua get_result_layout.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_column


@pytest.fixture()
def rules_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_rules.db"
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
    res = create_template(
        admin_ctx,
        res.data["id"],
        {
            "code": "MAIN",
            "name": "Mẫu chính",
            "display_order": 10,
            "data_source_id": ds_id,
            "source_type": "CUSTOM_SQL",
            "sql_text": "SELECT amount, org, txn_date, raw_blob FROM fin_revenue",
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        },
    )
    assert res.ok, res.message
    version_id = res.data["id"]
    with engine.begin() as conn:
        for order, (field, dtype) in enumerate(
            [
                ("AMOUNT", "NUMBER"),
                ("ORG", "STRING"),
                ("TXN_DATE", "DATE"),
                ("UPDATED_AT", "DATETIME"),
                ("RAW_BLOB", "BINARY"),
            ]
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


class TestLabelUnique:
    def test_duplicate_label_rejected(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        res = update_column(
            admin_ctx, rules_env["version_id"], ids["ORG"], {"label": "AMOUNT"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_duplicate_label_case_insensitive(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        res = update_column(
            admin_ctx, rules_env["version_id"], ids["ORG"], {"label": "amount"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_bulk_duplicate_labels_rejected(self, rules_env, admin_ctx):
        from app.services.report_column import list_columns, update_columns

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        res = update_columns(
            admin_ctx,
            rules_env["version_id"],
            [
                {"id": ids["AMOUNT"], "label": "Chung"},
                {"id": ids["ORG"], "label": "chung"},
            ],
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        by_field = {
            c["field_name"]: c
            for c in list_columns(admin_ctx, rules_env["version_id"]).data
        }
        assert by_field["AMOUNT"]["label"] == "AMOUNT"
        assert by_field["ORG"]["label"] == "ORG"


class TestFormatMask:
    def test_number_masks(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for mask in ("#,##0", "#,##0.00", "#,##0%", "0", "0.00"):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids["AMOUNT"],
                {"format_mask": mask},
            )
            assert res.ok, f"{mask}: {res.message}"
        res = update_column(
            admin_ctx,
            rules_env["version_id"],
            ids["AMOUNT"],
            {"format_mask": "DD/MM/YYYY"},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_date_masks(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for mask in ("DD/MM/YYYY", "YYYY-MM-DD", "MM/YYYY"):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids["TXN_DATE"],
                {"format_mask": mask},
            )
            assert res.ok, f"{mask}: {res.message}"
        res = update_column(
            admin_ctx,
            rules_env["version_id"],
            ids["TXN_DATE"],
            {"format_mask": "#,##0"},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # DATE không nhận mask có giờ
        res = update_column(
            admin_ctx,
            rules_env["version_id"],
            ids["TXN_DATE"],
            {"format_mask": "DD/MM/YYYY HH:mm"},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_datetime_masks(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for mask in ("DD/MM/YYYY", "DD/MM/YYYY HH:mm", "DD/MM/YYYY HH:mm:ss"):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids["UPDATED_AT"],
                {"format_mask": mask},
            )
            assert res.ok, f"{mask}: {res.message}"

    def test_string_and_binary_no_mask(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for field in ("ORG", "RAW_BLOB"):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids[field],
                {"format_mask": "#,##0"},
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"
        # Để trống thì được
        res = update_column(
            admin_ctx, rules_env["version_id"], ids["ORG"], {"format_mask": None}
        )
        assert res.ok, res.message


class TestTotalOnlyNumber:
    def test_total_on_non_number_rejected(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for field in ("ORG", "TXN_DATE", "UPDATED_AT", "RAW_BLOB"):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids[field],
                {"is_total": True},
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"
        res = update_column(
            admin_ctx, rules_env["version_id"], ids["AMOUNT"], {"is_total": True}
        )
        assert res.ok, res.message
        assert res.data["is_total"] is True


class TestWidthRange:
    def test_width_bounds(self, rules_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(rules_env["engine"], rules_env["version_id"])
        for bad in (39, 401, -10, 0):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids["AMOUNT"],
                {"width": bad},
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"
        for ok_width in (40, 400, 120):
            res = update_column(
                admin_ctx,
                rules_env["version_id"],
                ids["AMOUNT"],
                {"width": ok_width},
            )
            assert res.ok, f"{ok_width}: {res.message}"
        res = update_column(
            admin_ctx, rules_env["version_id"], ids["AMOUNT"], {"width": None}
        )
        assert res.ok, res.message
        assert res.data["width"] is None
