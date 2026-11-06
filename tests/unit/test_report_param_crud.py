"""Tests cho Parameter CRUD/validation/default resolution — Bước 1 task 23 (test viết trước).

create/update/delete param + resolve_param_values (T23-01, T23-05, T23-06).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_param, recon_rpt_param_lov


@pytest.fixture()
def param_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_param.db"
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
            "sql_text": "SELECT amount, org, txn_date FROM fin_revenue "
            "WHERE org = :p_org AND txn_date >= :p_from",
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


def _payload(**overrides):
    payload = {
        "code": "p_org",
        "label": "Đơn vị",
        "data_type": "STRING",
        "control_type": "TEXT",
        "required": False,
        "default_type": "NONE",
        "display_row": 1,
        "display_order": 10,
        "grid_span": 6,
        "filter_column": "ORG",
        "filter_operator": "=",
    }
    payload.update(overrides)
    return payload


def _make_param(admin_ctx, version_id, **overrides):
    from app.services.report_param import create_param

    res = create_param(admin_ctx, version_id, _payload(**overrides))
    assert res.ok, res.message
    return res.data


class TestCreateParam:
    def test_create_minimal(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(admin_ctx, param_env["version_id"], _payload())
        assert res.ok, res.message
        assert res.data["code"] == "p_org"
        assert res.data["grid_span"] == 6
        assert res.data["lov"]["lov_type"] == "NONE"
        engine = param_env["engine"]
        with engine.connect() as conn:
            lov = (
                conn.execute(
                    select(recon_rpt_param_lov).where(
                        recon_rpt_param_lov.c.PARAM_ID == res.data["id"]
                    )
                )
                .mappings()
                .first()
            )
        assert lov is not None and lov["LOV_TYPE"] == "NONE"

    def test_create_with_static_lov(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            param_env["version_id"],
            _payload(
                control_type="SELECT",
                lov={
                    "lov_type": "STATIC",
                    "static_json": [
                        {"value": "BDP", "label": "Bình Dương"},
                        {"value": "HCM", "label": "TP.HCM"},
                    ],
                },
            ),
        )
        assert res.ok, res.message
        assert res.data["lov"]["lov_type"] == "STATIC"
        assert len(res.data["lov"]["static_json"]) == 2

    def test_invalid_code(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        for bad in ["1abc", "p-org", "p org", ""]:
            res = create_param(
                admin_ctx, param_env["version_id"], _payload(code=bad)
            )
            assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_duplicate_code_conflict(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        _make_param(admin_ctx, param_env["version_id"])
        res = create_param(admin_ctx, param_env["version_id"], _payload())
        assert not res.ok and res.code == "CONFLICT"

    def test_invalid_data_and_control_type(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx, param_env["version_id"], _payload(data_type="CLOB")
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = create_param(
            admin_ctx, param_env["version_id"], _payload(control_type="SLIDER")
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_select_requires_lov(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx, param_env["version_id"], _payload(control_type="SELECT")
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_date_range_requires_date_type(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            param_env["version_id"],
            _payload(data_type="STRING", control_type="DATE_RANGE"),
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_grid_span_and_row_bounds(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        for bad in ({"grid_span": 0}, {"grid_span": 13}, {"display_row": 0}):
            res = create_param(admin_ctx, param_env["version_id"], _payload(**bad))
            assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_default_type_rules(self, param_env, admin_ctx):
        from app.services.report_param import create_param

        # TODAY chỉ cho DATE/DATETIME
        res = create_param(
            admin_ctx,
            param_env["version_id"],
            _payload(data_type="STRING", default_type="TODAY"),
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # FIRST_LOV cần LOV khác NONE
        res = create_param(
            admin_ctx, param_env["version_id"], _payload(default_type="FIRST_LOV")
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # STATIC default phải đúng kiểu
        res = create_param(
            admin_ctx,
            param_env["version_id"],
            _payload(
                data_type="NUMBER", default_type="STATIC", default_value="abc"
            ),
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_create_forbidden_for_operator(self, param_env, operator_ctx):
        from app.services.report_param import create_param

        res = create_param(operator_ctx, param_env["version_id"], _payload())
        assert not res.ok and res.code == "FORBIDDEN"

    def test_create_on_non_draft_rejected(self, param_env, admin_ctx):
        from app.db.metadata import recon_rpt_tpl_ver
        from app.services.report_param import create_param

        engine = param_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == param_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = create_param(admin_ctx, param_env["version_id"], _payload())
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestUpdateDeleteParam:
    def test_update_label_span_default(self, param_env, admin_ctx):
        from app.services.report_param import update_param

        created = _make_param(admin_ctx, param_env["version_id"])
        res = update_param(
            admin_ctx,
            param_env["version_id"],
            created["id"],
            {
                "label": "Đơn vị kinh doanh",
                "grid_span": 4,
                "required": True,
                "default_type": "STATIC",
                "default_value": "BDP",
            },
        )
        assert res.ok, res.message
        assert res.data["label"] == "Đơn vị kinh doanh"
        assert res.data["grid_span"] == 4
        assert res.data["required"] is True
        assert res.data["default_value"] == "BDP"

    def test_update_code_forbidden(self, param_env, admin_ctx):
        from app.services.report_param import update_param

        created = _make_param(admin_ctx, param_env["version_id"])
        res = update_param(
            admin_ctx, param_env["version_id"], created["id"], {"code": "p_other"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_update_lov(self, param_env, admin_ctx):
        from app.services.report_param import update_param

        created = _make_param(admin_ctx, param_env["version_id"])
        res = update_param(
            admin_ctx,
            param_env["version_id"],
            created["id"],
            {
                "control_type": "SELECT",
                "lov": {
                    "lov_type": "STATIC",
                    "static_json": [{"value": "BDP", "label": "Bình Dương"}],
                },
            },
        )
        assert res.ok, res.message
        assert res.data["lov"]["lov_type"] == "STATIC"

    def test_delete_blocked_when_bind_in_sql(self, param_env, admin_ctx):
        from app.services.report_param import delete_param

        created = _make_param(admin_ctx, param_env["version_id"])
        res = delete_param(admin_ctx, param_env["version_id"], created["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_delete_ok_and_lov_gone(self, param_env, admin_ctx):
        from app.services.report_param import delete_param

        created = _make_param(
            admin_ctx, param_env["version_id"], code="p_unused"
        )
        res = delete_param(admin_ctx, param_env["version_id"], created["id"])
        assert res.ok, res.message
        engine = param_env["engine"]
        with engine.connect() as conn:
            param = (
                conn.execute(
                    select(recon_rpt_param).where(
                        recon_rpt_param.c.ID == created["id"]
                    )
                )
                .mappings()
                .first()
            )
            lov = (
                conn.execute(
                    select(recon_rpt_param_lov).where(
                        recon_rpt_param_lov.c.PARAM_ID == created["id"]
                    )
                )
                .mappings()
                .first()
            )
        assert param is None and lov is None


class TestResolveParamValues:
    def _setup_params(self, admin_ctx, version_id):
        _make_param(
            admin_ctx,
            version_id,
            code="p_org",
            label="Đơn vị",
            required=True,
        )
        _make_param(
            admin_ctx,
            version_id,
            code="p_date",
            label="Ngày",
            data_type="DATE",
            control_type="DATE",
            default_type="TODAY",
            display_order=20,
        )
        _make_param(
            admin_ctx,
            version_id,
            code="p_amt",
            label="Số tiền",
            data_type="NUMBER",
            control_type="NUMBER",
            default_type="STATIC",
            default_value="100",
            display_order=30,
        )

    def test_defaults_filled_and_required_checked(self, param_env, admin_ctx):
        from app.services.report_param import resolve_param_values

        version_id = param_env["version_id"]
        self._setup_params(admin_ctx, version_id)
        # Thiếu p_org (required) -> lỗi
        res = resolve_param_values(admin_ctx, version_id, {})
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # Đủ p_org -> default TODAY/STATIC được điền
        res = resolve_param_values(admin_ctx, version_id, {"p_org": "BDP"})
        assert res.ok, res.message
        today = datetime.now(timezone.utc).date().isoformat()
        assert res.data["p_org"] == "BDP"
        assert res.data["p_date"] == today
        assert res.data["p_amt"] == 100
        assert isinstance(res.data["p_amt"], (int, float))

    def test_type_validation(self, param_env, admin_ctx):
        from app.services.report_param import resolve_param_values

        version_id = param_env["version_id"]
        self._setup_params(admin_ctx, version_id)
        res = resolve_param_values(
            admin_ctx, version_id, {"p_org": "BDP", "p_amt": "abc"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = resolve_param_values(
            admin_ctx, version_id, {"p_org": "BDP", "p_date": "2026-13-45"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_between_and_in_range(self, param_env, admin_ctx):
        from app.services.report_param import resolve_param_values

        version_id = param_env["version_id"]
        _make_param(
            admin_ctx,
            version_id,
            code="p_rng",
            label="Khoảng tiền",
            data_type="NUMBER",
            control_type="NUMBER",
            filter_operator="BETWEEN",
            display_order=10,
        )
        _make_param(
            admin_ctx,
            version_id,
            code="p_orgs",
            label="Các đơn vị",
            control_type="MULTI_SELECT",
            filter_operator="IN",
            display_order=20,
            lov={
                "lov_type": "STATIC",
                "static_json": [{"value": "BDP", "label": "Bình Dương"}],
            },
        )
        # BETWEEN ngược -> lỗi
        res = resolve_param_values(
            admin_ctx, version_id, {"p_rng": [500, 100], "p_orgs": ["BDP"]}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # BETWEEN đúng + IN hợp lệ
        res = resolve_param_values(
            admin_ctx, version_id, {"p_rng": [100, 500], "p_orgs": ["BDP", "HCM"]}
        )
        assert res.ok, res.message
        assert res.data["p_rng"] == [100, 500]
        assert res.data["p_orgs"] == ["BDP", "HCM"]
        # IN rỗng khi required -> lỗi; khi không required -> bỏ qua
        res = resolve_param_values(admin_ctx, version_id, {"p_orgs": []})
        assert res.ok, res.message
        assert "p_orgs" not in res.data

    def test_first_lov_default_via_resolver(self, param_env, admin_ctx):
        from app.services.report_param import resolve_param_values

        version_id = param_env["version_id"]
        _make_param(
            admin_ctx,
            version_id,
            code="p_chan",
            label="Kênh",
            control_type="SELECT",
            default_type="FIRST_LOV",
            lov={
                "lov_type": "STATIC",
                "static_json": [
                    {"value": "ONLINE", "label": "Online"},
                    {"value": "OFFLINE", "label": "Offline"},
                ],
            },
        )

        def fake_resolver(_version_id, _param_id):
            return [
                {"value": "ONLINE", "label": "Online"},
                {"value": "OFFLINE", "label": "Offline"},
            ]

        res = resolve_param_values(
            admin_ctx, version_id, {}, lov_resolver=fake_resolver
        )
        assert res.ok, res.message
        assert res.data["p_chan"] == "ONLINE"

    def test_resolve_forbidden_without_menu(self, param_env, norole_ctx):
        from app.services.report_param import resolve_param_values

        res = resolve_param_values(
            norole_ctx, param_env["version_id"], {"p_org": "BDP"}
        )
        assert not res.ok and res.code == "FORBIDDEN"

    def test_resolve_allowed_for_operator(self, param_env, operator_ctx):
        from app.services.report_param import resolve_param_values

        res = resolve_param_values(
            operator_ctx, param_env["version_id"], {"p_org": "BDP"}
        )
        assert res.ok, res.message
