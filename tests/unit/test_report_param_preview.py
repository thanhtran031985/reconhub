"""Tests cho Auto-layout, drag/drop, preview — Bước 4 task 23 (test viết trước).

auto_layout, build_param_layout, preview_layout (T23-09, T23-10, T23-11).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_param, recon_rpt_tpl_ver


@pytest.fixture()
def preview_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_preview.db"
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


def _db_params(engine, version_id):
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_rpt_param)
                .where(recon_rpt_param.c.VERSION_ID == version_id)
                .order_by(recon_rpt_param.c.DISPLAY_ROW, recon_rpt_param.c.DISPLAY_ORDER)
            )
            .mappings()
            .all()
        )
    return [(r["CODE"], int(r["DISPLAY_ROW"]), int(r["DISPLAY_ORDER"])) for r in rows]


class TestAutoLayout:
    def test_packs_rows_to_12(self, preview_env, admin_ctx):
        from app.services.report_param import auto_layout

        for i, code in enumerate(["p_a", "p_b", "p_c", "p_d"]):
            _make_param(
                admin_ctx, preview_env["version_id"], code, row=1, order=(i + 1) * 10, span=6
            )
        res = auto_layout(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert _db_params(preview_env["engine"], preview_env["version_id"]) == [
            ("p_a", 1, 10),
            ("p_b", 1, 20),
            ("p_c", 2, 10),
            ("p_d", 2, 20),
        ]

    def test_keeps_span_and_order(self, preview_env, admin_ctx):
        from app.services.report_param import auto_layout

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=2, order=10, span=4)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=10, span=4)
        _make_param(admin_ctx, preview_env["version_id"], "p_c", row=1, order=20, span=4)
        _make_param(admin_ctx, preview_env["version_id"], "p_d", row=1, order=30, span=4)
        res = auto_layout(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert _db_params(preview_env["engine"], preview_env["version_id"]) == [
            ("p_b", 1, 10),
            ("p_c", 1, 20),
            ("p_d", 1, 30),
            ("p_a", 2, 10),
        ]

    def test_full_span_own_row_and_hidden_untouched(self, preview_env, admin_ctx):
        from app.services.report_param import auto_layout

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=12)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=20, span=6)
        _make_param(
            admin_ctx,
            preview_env["version_id"],
            "p_h",
            row=1,
            order=30,
            span=6,
            is_visible=False,
        )
        res = auto_layout(admin_ctx, preview_env["version_id"])
        assert res.ok, res.message
        assert _db_params(preview_env["engine"], preview_env["version_id"]) == [
            ("p_a", 1, 10),
            ("p_h", 1, 30),
            ("p_b", 2, 10),
        ]

    def test_auto_layout_validation(self, preview_env, admin_ctx, operator_ctx):
        from app.services.report_param import auto_layout

        res = auto_layout(operator_ctx, preview_env["version_id"])
        assert not res.ok and res.code == "FORBIDDEN"
        engine = preview_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == preview_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = auto_layout(admin_ctx, preview_env["version_id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestBuildParamLayout:
    def test_build_matches_stored_layout(self, preview_env, admin_ctx):
        from app.services.report_param import build_param_layout
        from app.services.report_template import get_version

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=20, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_c", row=2, order=10, span=12)
        detail = get_version(admin_ctx, preview_env["version_id"]).data
        layout = build_param_layout(detail, columns=12)
        assert layout["columns"] == 12
        assert len(layout["rows"]) == 2
        assert [p["code"] for p in layout["rows"][0]["params"]] == ["p_a", "p_b"]
        assert layout["rows"][0]["total_span"] == 12
        assert [p["code"] for p in layout["rows"][1]["params"]] == ["p_c"]
        assert layout["rows"][1]["total_span"] == 12

    def test_build_mobile_one_column(self, preview_env, admin_ctx):
        from app.services.report_param import build_param_layout
        from app.services.report_template import get_version

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=20, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_c", row=2, order=10, span=4)
        detail = get_version(admin_ctx, preview_env["version_id"]).data
        layout = build_param_layout(detail, columns=1)
        assert layout["columns"] == 1
        assert len(layout["rows"]) == 3
        assert [r["params"][0]["code"] for r in layout["rows"]] == ["p_a", "p_b", "p_c"]

    def test_build_does_not_mutate_input(self, preview_env, admin_ctx):
        from app.services.report_param import build_param_layout
        from app.services.report_template import get_version

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=6)
        detail = get_version(admin_ctx, preview_env["version_id"]).data
        snapshot = copy.deepcopy(detail)
        build_param_layout(detail, columns=1)
        assert detail == snapshot

    def test_build_invalid_columns(self, preview_env, admin_ctx):
        from app.schemas.errors import ServiceError
        from app.services.report_param import build_param_layout
        from app.services.report_template import get_version

        detail = get_version(admin_ctx, preview_env["version_id"]).data
        with pytest.raises(ServiceError) as excinfo:
            build_param_layout(detail, columns=5)
        assert excinfo.value.code == "VALIDATION_ERROR"


class TestPreviewLayout:
    def test_preview_matches_viewer_layout(self, preview_env, admin_ctx):
        from app.services.report_param import build_param_layout, preview_layout
        from app.services.report_template import get_version

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=20, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_c", row=2, order=10, span=12)
        res = preview_layout(admin_ctx, preview_env["version_id"], columns=12)
        assert res.ok, res.message
        # Preview dùng cùng cấu trúc Viewer dùng (build_param_layout trên get_version)
        detail = get_version(admin_ctx, preview_env["version_id"]).data
        expected = build_param_layout(detail, columns=12)
        assert res.data["columns"] == expected["columns"]
        assert res.data["rows"] == expected["rows"]

    def test_preview_resolves_defaults(self, preview_env, admin_ctx):
        from app.services.report_param import preview_layout

        _make_param(
            admin_ctx,
            preview_env["version_id"],
            "p_amt",
            row=1,
            order=10,
            span=6,
            data_type="NUMBER",
            control_type="NUMBER",
            default_type="STATIC",
            default_value="100",
        )
        _make_param(
            admin_ctx,
            preview_env["version_id"],
            "p_date",
            row=1,
            order=20,
            span=6,
            data_type="DATE",
            control_type="DATE",
            default_type="TODAY",
        )
        _make_param(
            admin_ctx,
            preview_env["version_id"],
            "p_req",
            row=2,
            order=10,
            span=6,
            required=True,
        )
        res = preview_layout(admin_ctx, preview_env["version_id"], columns=12)
        assert res.ok, res.message
        by_code = {
            p["code"]: p
            for row in res.data["rows"]
            for p in row["params"]
        }
        assert by_code["p_amt"]["value"] == 100
        assert by_code["p_date"]["value"] == datetime.now(timezone.utc).date().isoformat()
        # Required nhưng chưa có giá trị/default: hiện trống, không lỗi
        assert by_code["p_req"]["value"] is None

    def test_preview_mobile_keeps_metadata(self, preview_env, admin_ctx):
        from app.services.report_param import preview_layout

        _make_param(admin_ctx, preview_env["version_id"], "p_a", row=1, order=10, span=6)
        _make_param(admin_ctx, preview_env["version_id"], "p_b", row=1, order=20, span=6)
        before = _db_params(preview_env["engine"], preview_env["version_id"])
        res = preview_layout(admin_ctx, preview_env["version_id"], columns=1)
        assert res.ok, res.message
        assert len(res.data["rows"]) == 2
        after = _db_params(preview_env["engine"], preview_env["version_id"])
        assert before == after

    def test_preview_validation(self, preview_env, admin_ctx, norole_ctx):
        from app.services.report_param import preview_layout

        res = preview_layout(admin_ctx, preview_env["version_id"], columns=5)
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = preview_layout(norole_ctx, preview_env["version_id"], columns=12)
        assert not res.ok and res.code == "FORBIDDEN"
