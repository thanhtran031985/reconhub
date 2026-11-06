"""Tests cho Editable mapping grid và row drag — Bước 2 task 24 (test viết trước).

update_column/update_columns/move_column/reorder_columns (T24-02).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_column, recon_rpt_tpl_ver


@pytest.fixture()
def grid_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_grid.db"
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


class TestUpdateColumn:
    def test_update_fields(self, grid_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_column(
            admin_ctx,
            grid_env["version_id"],
            ids["AMOUNT"],
            {
                "label": "Số tiền",
                "format_mask": "#,##0.00",
                "alignment": "RIGHT",
                "width": 140,
                "is_total": True,
            },
        )
        assert res.ok, res.message
        assert res.data["label"] == "Số tiền"
        assert res.data["format_mask"] == "#,##0.00"
        assert res.data["alignment"] == "RIGHT"
        assert res.data["width"] == 140
        assert res.data["is_total"] is True

    def test_clear_format_and_width(self, grid_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_column(
            admin_ctx,
            grid_env["version_id"],
            ids["AMOUNT"],
            {"format_mask": "#,##0", "width": 120},
        )
        assert res.ok, res.message
        res = update_column(
            admin_ctx,
            grid_env["version_id"],
            ids["AMOUNT"],
            {"format_mask": None, "width": None},
        )
        assert res.ok, res.message
        assert res.data["format_mask"] is None
        assert res.data["width"] is None

    def test_readonly_fields_rejected(self, grid_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        for bad in (
            {"field_name": "OTHER"},
            {"data_type": "STRING"},
            {"display_order": 99},
        ):
            res = update_column(
                admin_ctx, grid_env["version_id"], ids["AMOUNT"], bad
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_empty_label_rejected(self, grid_env, admin_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        for bad_label in ("", "   "):
            res = update_column(
                admin_ctx,
                grid_env["version_id"],
                ids["AMOUNT"],
                {"label": bad_label},
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_update_validation(self, grid_env, admin_ctx, operator_ctx):
        from app.services.report_column import update_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_column(
            operator_ctx,
            grid_env["version_id"],
            ids["AMOUNT"],
            {"label": "X"},
        )
        assert not res.ok and res.code == "FORBIDDEN"
        res = update_column(
            admin_ctx, grid_env["version_id"], 99999, {"label": "X"}
        )
        assert not res.ok and res.code == "NOT_FOUND"
        engine = grid_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == grid_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = update_column(
            admin_ctx, grid_env["version_id"], ids["AMOUNT"], {"label": "X"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestUpdateColumnsBulk:
    def test_bulk_save(self, grid_env, admin_ctx):
        from app.services.report_column import list_columns, update_columns

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_columns(
            admin_ctx,
            grid_env["version_id"],
            [
                {"id": ids["AMOUNT"], "label": "Số tiền", "alignment": "RIGHT"},
                {"id": ids["ORG"], "label": "Đơn vị", "web_visible": False},
            ],
        )
        assert res.ok, res.message
        by_field = {
            c["field_name"]: c
            for c in list_columns(admin_ctx, grid_env["version_id"]).data
        }
        assert by_field["AMOUNT"]["label"] == "Số tiền"
        assert by_field["AMOUNT"]["alignment"] == "RIGHT"
        assert by_field["ORG"]["label"] == "Đơn vị"
        assert by_field["ORG"]["web_visible"] is False

    def test_bulk_all_or_nothing(self, grid_env, admin_ctx):
        from app.services.report_column import list_columns, update_columns

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_columns(
            admin_ctx,
            grid_env["version_id"],
            [
                {"id": ids["AMOUNT"], "label": "Số tiền"},
                {"id": ids["ORG"], "label": ""},
            ],
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        by_field = {
            c["field_name"]: c
            for c in list_columns(admin_ctx, grid_env["version_id"]).data
        }
        # Không dòng nào được ghi
        assert by_field["AMOUNT"]["label"] == "AMOUNT"
        assert by_field["ORG"]["label"] == "ORG"

    def test_bulk_unknown_id(self, grid_env, admin_ctx):
        from app.services.report_column import update_columns

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = update_columns(
            admin_ctx,
            grid_env["version_id"],
            [{"id": ids["AMOUNT"], "label": "Số tiền"}, {"id": 99999, "label": "X"}],
        )
        assert not res.ok and res.code == "NOT_FOUND"


class TestMoveReorderColumns:
    def test_move_column(self, grid_env, admin_ctx):
        from app.services.report_column import list_columns, move_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = move_column(
            admin_ctx, grid_env["version_id"], ids["TXN_DATE"], to_index=0
        )
        assert res.ok, res.message
        assert res.data["display_order"] == 10
        cols = list_columns(admin_ctx, grid_env["version_id"]).data
        assert [c["field_name"] for c in cols] == ["TXN_DATE", "AMOUNT", "ORG"]
        assert [c["display_order"] for c in cols] == [10, 20, 30]

    def test_move_index_clamped(self, grid_env, admin_ctx):
        from app.services.report_column import list_columns, move_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = move_column(
            admin_ctx, grid_env["version_id"], ids["AMOUNT"], to_index=99
        )
        assert res.ok, res.message
        cols = list_columns(admin_ctx, grid_env["version_id"]).data
        assert [c["field_name"] for c in cols] == ["ORG", "TXN_DATE", "AMOUNT"]

    def test_move_validation(self, grid_env, admin_ctx, operator_ctx):
        from app.services.report_column import move_column

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = move_column(
            operator_ctx, grid_env["version_id"], ids["AMOUNT"], to_index=0
        )
        assert not res.ok and res.code == "FORBIDDEN"
        res = move_column(
            admin_ctx, grid_env["version_id"], ids["AMOUNT"], to_index=-1
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_reorder_columns(self, grid_env, admin_ctx):
        from app.services.report_column import list_columns, reorder_columns

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        res = reorder_columns(
            admin_ctx,
            grid_env["version_id"],
            [ids["TXN_DATE"], ids["ORG"], ids["AMOUNT"]],
        )
        assert res.ok, res.message
        cols = list_columns(admin_ctx, grid_env["version_id"]).data
        assert [c["field_name"] for c in cols] == ["TXN_DATE", "ORG", "AMOUNT"]
        assert [c["display_order"] for c in cols] == [10, 20, 30]

    def test_reorder_validation(self, grid_env, admin_ctx):
        from app.services.report_column import reorder_columns

        ids = _col_ids(grid_env["engine"], grid_env["version_id"])
        # Thiếu cột
        res = reorder_columns(
            admin_ctx, grid_env["version_id"], [ids["AMOUNT"], ids["ORG"]]
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # Trùng id
        res = reorder_columns(
            admin_ctx,
            grid_env["version_id"],
            [ids["AMOUNT"], ids["AMOUNT"], ids["ORG"]],
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # ID lạ
        res = reorder_columns(
            admin_ctx,
            grid_env["version_id"],
            [ids["AMOUNT"], ids["ORG"], 99999],
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
