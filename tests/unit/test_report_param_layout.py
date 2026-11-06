"""Tests cho DISPLAY_ROW/ORDER/GRID_SPAN và tổng row <=12 — Bước 3 task 23 (test viết trước).

validate_layout, move_param, reorder_params, chặn ở activate (T23-06, T23-07, T23-08).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_tpl_ver


@pytest.fixture()
def layout_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_layout.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_param",
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
            "sql_text": "SELECT amount FROM fin_revenue",
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        },
    )
    assert res.ok, res.message
    return {"engine": engine, "ds_id": ds_id, "version_id": res.data["id"]}


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def norole_ctx() -> Ctx:
    return Ctx(user_id=3, username="norole", full_name="norole", roles=[])


def _make_param(admin_ctx, version_id, code, row=1, order=10, span=6, **overrides):
    from app.services.report_param import create_param

    payload = {
        "code": code,
        "label": code,
        "data_type": "STRING",
        "control_type": "TEXT",
        "required": False,
        "default_type": "NONE",
        "display_row": row,
        "display_order": order,
        "grid_span": span,
    }
    payload.update(overrides)
    res = create_param(admin_ctx, version_id, payload)
    assert res.ok, res.message
    return res.data


class TestValidateLayout:
    def test_empty_layout_ok(self, layout_env, admin_ctx):
        from app.services.report_param import validate_layout

        res = validate_layout(admin_ctx, layout_env["version_id"])
        assert res.ok, res.message
        assert res.data["ok"] is True
        assert res.data["violations"] == []

    def test_valid_rows(self, layout_env, admin_ctx):
        from app.services.report_param import validate_layout

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20, span=6)
        _make_param(admin_ctx, layout_env["version_id"], "p_c", row=2, order=10, span=12)
        res = validate_layout(admin_ctx, layout_env["version_id"])
        assert res.ok, res.message
        assert res.data["ok"] is True

    def test_overfull_row_violation(self, layout_env, admin_ctx):
        from app.services.report_param import validate_layout

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20, span=7)
        res = validate_layout(admin_ctx, layout_env["version_id"])
        assert res.ok, res.message
        assert res.data["ok"] is False
        assert len(res.data["violations"]) == 1
        assert res.data["violations"][0]["row"] == 1
        assert res.data["violations"][0]["total"] == 13
        assert set(res.data["violations"][0]["params"]) == {"p_a", "p_b"}

    def test_hidden_param_not_counted(self, layout_env, admin_ctx):
        from app.services.report_param import validate_layout

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(
            admin_ctx,
            layout_env["version_id"],
            "p_b",
            row=1,
            order=20,
            span=7,
            is_visible=False,
        )
        res = validate_layout(admin_ctx, layout_env["version_id"])
        assert res.ok, res.message
        assert res.data["ok"] is True

    def test_create_warns_but_saves_when_overfull(self, layout_env, admin_ctx):
        from app.services.report_param import create_param

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        res = create_param(
            admin_ctx,
            layout_env["version_id"],
            {
                "code": "p_b",
                "label": "p_b",
                "data_type": "STRING",
                "control_type": "TEXT",
                "display_row": 1,
                "display_order": 20,
                "grid_span": 7,
            },
        )
        assert res.ok, res.message
        assert res.data.get("layout_warnings")
        assert res.data["layout_warnings"][0]["row"] == 1

    def test_validate_forbidden_without_menu(self, layout_env, norole_ctx):
        from app.services.report_param import validate_layout

        res = validate_layout(norole_ctx, layout_env["version_id"])
        assert not res.ok and res.code == "FORBIDDEN"


class TestMoveParam:
    def test_move_within_row(self, layout_env, admin_ctx):
        from app.services.report_param import move_param

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        b = _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20)
        c = _make_param(admin_ctx, layout_env["version_id"], "p_c", row=1, order=30)
        res = move_param(admin_ctx, layout_env["version_id"], c["id"], to_row=1, to_index=0)
        assert res.ok, res.message
        assert res.data["display_row"] == 1
        engine = layout_env["engine"]
        with engine.connect() as conn:
            from app.db.metadata import recon_rpt_param

            rows = (
                conn.execute(
                    select(recon_rpt_param)
                    .where(recon_rpt_param.c.VERSION_ID == layout_env["version_id"])
                    .order_by(recon_rpt_param.c.DISPLAY_ORDER)
                )
                .mappings()
                .all()
            )
        assert [r["CODE"] for r in rows] == ["p_c", "p_a", "p_b"]
        assert [int(r["DISPLAY_ORDER"]) for r in rows] == [10, 20, 30]

    def test_move_to_another_row(self, layout_env, admin_ctx):
        from app.services.report_param import move_param

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        b = _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20)
        _make_param(admin_ctx, layout_env["version_id"], "p_c", row=2, order=10)
        res = move_param(admin_ctx, layout_env["version_id"], a["id"], to_row=2, to_index=1)
        assert res.ok, res.message
        assert res.data["display_row"] == 2
        engine = layout_env["engine"]
        with engine.connect() as conn:
            from app.db.metadata import recon_rpt_param

            row2 = (
                conn.execute(
                    select(recon_rpt_param)
                    .where(
                        recon_rpt_param.c.VERSION_ID == layout_env["version_id"],
                        recon_rpt_param.c.DISPLAY_ROW == 2,
                    )
                    .order_by(recon_rpt_param.c.DISPLAY_ORDER)
                )
                .mappings()
                .all()
            )
        assert [r["CODE"] for r in row2] == ["p_c", "p_a"]

    def test_move_to_new_row(self, layout_env, admin_ctx):
        from app.services.report_param import move_param

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        res = move_param(admin_ctx, layout_env["version_id"], a["id"], to_row=3, to_index=0)
        assert res.ok, res.message
        assert res.data["display_row"] == 3
        assert res.data["display_order"] == 10

    def test_move_validation(self, layout_env, admin_ctx, operator_ctx):
        from app.services.report_param import move_param

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        res = move_param(operator_ctx, layout_env["version_id"], a["id"], to_row=1, to_index=0)
        assert not res.ok and res.code == "FORBIDDEN"
        res = move_param(admin_ctx, layout_env["version_id"], a["id"], to_row=0, to_index=0)
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = move_param(admin_ctx, layout_env["version_id"], a["id"], to_row=1, to_index=-1)
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = move_param(admin_ctx, layout_env["version_id"], 99999, to_row=1, to_index=0)
        assert not res.ok and res.code == "NOT_FOUND"

    def test_move_on_non_draft_rejected(self, layout_env, admin_ctx):
        from app.services.report_param import move_param

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        engine = layout_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == layout_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = move_param(admin_ctx, layout_env["version_id"], a["id"], to_row=2, to_index=0)
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestReorderParams:
    def test_reorder_rows(self, layout_env, admin_ctx):
        from app.services.report_param import reorder_params

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        b = _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20)
        c = _make_param(admin_ctx, layout_env["version_id"], "p_c", row=1, order=30)
        res = reorder_params(
            admin_ctx, layout_env["version_id"], [[c["id"], a["id"]], [b["id"]]]
        )
        assert res.ok, res.message
        by_code = {p["code"]: p for p in res.data["params"]}
        assert (by_code["p_c"]["display_row"], by_code["p_c"]["display_order"]) == (1, 10)
        assert (by_code["p_a"]["display_row"], by_code["p_a"]["display_order"]) == (1, 20)
        assert (by_code["p_b"]["display_row"], by_code["p_b"]["display_order"]) == (2, 10)

    def test_reorder_validation(self, layout_env, admin_ctx):
        from app.services.report_param import reorder_params

        a = _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10)
        b = _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20)
        # Thiếu param hiển thị
        res = reorder_params(admin_ctx, layout_env["version_id"], [[a["id"]]])
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # ID lạ
        res = reorder_params(admin_ctx, layout_env["version_id"], [[a["id"], 99999]])
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # Trùng ID
        res = reorder_params(
            admin_ctx, layout_env["version_id"], [[a["id"], a["id"]], [b["id"]]]
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestActivateBlockedByLayout:
    def test_activate_rejected_when_overfull(self, layout_env, admin_ctx):
        from app.services.report_param import validate_layout
        from app.services.report_template import activate_version

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20, span=7)
        engine = layout_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == layout_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = activate_version(admin_ctx, layout_env["version_id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_activate_ok_when_layout_valid(self, layout_env, admin_ctx):
        from app.services.report_template import activate_version

        _make_param(admin_ctx, layout_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, layout_env["version_id"], "p_b", row=1, order=20, span=6)
        engine = layout_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == layout_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = activate_version(admin_ctx, layout_env["version_id"])
        assert res.ok, res.message
