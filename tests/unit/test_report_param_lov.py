"""Tests cho LOV NONE/STATIC/SQL/LOOKUP + cache — Bước 2 task 23 (test viết trước).

resolve_lov (T23-02, T23-03, T23-04), cache, invalidate khi activate (Q7).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_rpt_lov_cache, recon_rpt_tpl_ver


@pytest.fixture()
def lov_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_lov.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_param",
        "app.services.report_source",
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
        conn.execute(
            text(
                "INSERT INTO RECON_LOOKUP_TYPE (LOOKUP_TYPE, TYPE_NAME, DESCRIPTION, "
                "IS_SYSTEM, IS_ACTIVE) VALUES ('ORG', 'Đơn vị', '', 'N', 'Y')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO RECON_LOOKUP_TYPE (LOOKUP_TYPE, TYPE_NAME, DESCRIPTION, "
                "IS_SYSTEM, IS_ACTIVE) VALUES ('OLD_TYPE', 'Loại cũ', '', 'N', 'N')"
            )
        )
        for code, meaning, order, active in [
            ("BDP", "Bình Dương", 10, "Y"),
            ("HCM", "TP.HCM", 20, "Y"),
            ("OLD", "Ngừng dùng", 30, "N"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO RECON_LOOKUP_CODE (LOOKUP_TYPE, LOOKUP_CODE, MEANING, "
                    "DESCRIPTION, DISPLAY_ORDER, IS_DEFAULT, IS_SYSTEM, IS_ACTIVE) "
                    "VALUES ('ORG', :c, :m, '', :o, 'N', 'N', :a)"
                ),
                {"c": code, "m": meaning, "o": order, "a": active},
            )
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
            "sql_text": "SELECT amount, org FROM fin_revenue WHERE org = :p_org",
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
    }
    payload.update(overrides)
    return payload


def _make_param(admin_ctx, version_id, **overrides):
    from app.services.report_param import create_param

    res = create_param(admin_ctx, version_id, _payload(**overrides))
    assert res.ok, res.message
    return res.data


def _sql_conn(lov_rows=None, description=None, fetchmany_side_effect=None):
    """Kết nối Oracle giả lập cho LOV SQL: describe (parse) + execute (fetchmany).

    fetchall: chỉ dùng cho kiểm tra read-only (USER_SYS_PRIVS rỗng).
    fetchmany: trả dòng LOV (giới hạn ở phía cursor, không fetchall rồi cắt).
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.description = description or [
        ("VALUE", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 60, 0, True),
        ("LABEL", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 200, 0, True),
    ]
    if fetchmany_side_effect is not None:
        mock_cursor.fetchmany.side_effect = fetchmany_side_effect
    else:
        mock_cursor.fetchmany.return_value = lov_rows or []
    mock_cursor.execute.return_value = None
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestStaticLov:
    def test_static_options(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "STATIC",
                "static_json": [
                    {"value": "BDP", "label": "Bình Dương"},
                    {"value": "", "label": "Tất cả"},
                ],
            },
        )
        res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
        assert res.ok, res.message
        assert res.data == [
            {"value": "BDP", "label": "Bình Dương"},
            {"value": "", "label": "Tất cả"},
        ]

    def test_static_duplicate_value_rejected(self, lov_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            lov_env["version_id"],
            _payload(
                control_type="SELECT",
                lov={
                    "lov_type": "STATIC",
                    "static_json": [
                        {"value": "BDP", "label": "Bình Dương"},
                        {"value": "BDP", "label": "Trùng"},
                    ],
                },
            ),
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_none_lov_returns_empty(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(admin_ctx, lov_env["version_id"])
        res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
        assert res.ok, res.message
        assert res.data == []


class TestLookupLov:
    def test_only_active_codes(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={"lov_type": "LOOKUP", "lookup_type": "ORG"},
        )
        res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
        assert res.ok, res.message
        assert res.data == [
            {"value": "BDP", "label": "Bình Dương"},
            {"value": "HCM", "label": "TP.HCM"},
        ]

    def test_inactive_lookup_type_rejected_at_create(self, lov_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            lov_env["version_id"],
            _payload(
                control_type="SELECT",
                lov={"lov_type": "LOOKUP", "lookup_type": "OLD_TYPE"},
            ),
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_missing_lookup_type_rejected(self, lov_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            lov_env["version_id"],
            _payload(
                control_type="SELECT",
                lov={"lov_type": "LOOKUP", "lookup_type": "NOPE"},
            ),
        )
        assert not res.ok and res.code == "NOT_FOUND"


class TestSqlLov:
    def test_sql_lov_returns_options_and_caches(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org",
                "cache_seconds": 300,
            },
        )
        mock_conn, mock_cursor = _sql_conn([("BDP", "Bình Dương"), ("HCM", "TP.HCM")])
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
            assert res.ok, res.message
            assert res.data == [
                {"value": "BDP", "label": "Bình Dương"},
                {"value": "HCM", "label": "TP.HCM"},
            ]
            calls_after_first = mock_conn.cursor.call_count
            res2 = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
            assert res2.ok and res2.data == res.data
            # Lần 2 hit cache: không mở kết nối Oracle mới
            assert mock_conn.cursor.call_count == calls_after_first

    def test_sql_lov_cache_expired_reexecutes(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org",
                "cache_seconds": 300,
            },
        )
        mock_conn, mock_cursor = _sql_conn(
            fetchmany_side_effect=[[("BDP", "Bình Dương")], [("BDP", "Bình Dương"), ("HCM", "TP.HCM")]]
        )
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
            assert res.ok and len(res.data) == 1
            # Làm hết hạn cache rồi resolve lại -> chạy query lại
            engine = lov_env["engine"]
            past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=10)
            with engine.begin() as conn:
                conn.execute(
                    recon_rpt_lov_cache.update().values(EXPIRES_AT=past)
                )
            res2 = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
            assert res2.ok and len(res2.data) == 2

    def test_sql_lov_no_cache_when_zero(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org",
                "cache_seconds": 0,
            },
        )
        mock_conn, mock_cursor = _sql_conn([("BDP", "Bình Dương")])
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            assert resolve_lov(admin_ctx, lov_env["version_id"], param["id"]).ok
            assert resolve_lov(admin_ctx, lov_env["version_id"], param["id"]).ok
        engine = lov_env["engine"]
        with engine.connect() as conn:
            rows = conn.execute(select(recon_rpt_lov_cache)).mappings().all()
        assert rows == []

    def test_sql_lov_limit_5000(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org",
                "cache_seconds": 300,
                "max_rows": 2,
            },
        )
        mock_conn, mock_cursor = _sql_conn([("A", "a"), ("B", "b"), ("C", "c")])
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
        assert res.ok, res.message
        assert len(res.data) == 2

    def test_sql_lov_missing_value_label_alias(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code, org_name FROM dim_org",
                "cache_seconds": 300,
            },
        )
        mock_conn, mock_cursor = _sql_conn(
            None,
            description=[
                ("ORG_CODE", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 60, 0, True),
                ("ORG_NAME", SimpleNamespace(name="DB_TYPE_VARCHAR"), 0, 0, 200, 0, True),
            ],
        )
        mock_cursor.fetchall.return_value = []
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            res = resolve_lov(admin_ctx, lov_env["version_id"], param["id"])
        assert not res.ok and res.code == "SQL_DESCRIBE_FAILED"

    def test_sql_lov_non_select_rejected_at_create(self, lov_env, admin_ctx):
        from app.services.report_param import create_param

        res = create_param(
            admin_ctx,
            lov_env["version_id"],
            _payload(
                control_type="SELECT",
                lov={
                    "lov_type": "SQL",
                    "data_source_id": lov_env["ds_id"],
                    "sql_text": "DELETE FROM dim_org",
                },
            ),
        )
        assert not res.ok and res.code == "SQL_NOT_ALLOWED"

    def test_sql_lov_with_dep_bind(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org WHERE region = :p_region",
                "cache_seconds": 300,
            },
        )
        mock_conn, mock_cursor = _sql_conn([("BDP", "Bình Dương")])
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            res = resolve_lov(
                admin_ctx,
                lov_env["version_id"],
                param["id"],
                dep_values={"p_region": "SOUTH"},
            )
        assert res.ok, res.message
        executed_sql, executed_binds = mock_cursor.execute.call_args[0][:2]
        assert "dim_org" in executed_sql
        assert executed_binds == {"p_region": "SOUTH"}


class TestLovCacheInvalidate:
    def test_activate_clears_lov_cache(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_lov
        from app.services.report_template import activate_version

        param = _make_param(
            admin_ctx,
            lov_env["version_id"],
            control_type="SELECT",
            lov={
                "lov_type": "SQL",
                "data_source_id": lov_env["ds_id"],
                "sql_text": "SELECT org_code AS VALUE, org_name AS LABEL FROM dim_org",
                "cache_seconds": 300,
            },
        )
        mock_conn, mock_cursor = _sql_conn([("BDP", "Bình Dương")])
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=mock_conn,
        ):
            assert resolve_lov(admin_ctx, lov_env["version_id"], param["id"]).ok
        engine = lov_env["engine"]
        with engine.connect() as conn:
            assert len(conn.execute(select(recon_rpt_lov_cache)).mappings().all()) == 1
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == lov_env["version_id"])
                .values(STATUS="DRY_RUN_OK")
            )
        res = activate_version(admin_ctx, lov_env["version_id"])
        assert res.ok, res.message
        with engine.connect() as conn:
            assert conn.execute(select(recon_rpt_lov_cache)).mappings().all() == []


class TestResolveLovPermissions:
    def test_forbidden_without_menu(self, lov_env, norole_ctx):
        from app.services.report_param import resolve_lov

        res = resolve_lov(norole_ctx, lov_env["version_id"], 1)
        assert not res.ok and res.code == "FORBIDDEN"

    def test_first_lov_default_without_explicit_resolver(self, lov_env, admin_ctx):
        from app.services.report_param import resolve_param_values

        _make_param(
            admin_ctx,
            lov_env["version_id"],
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
        res = resolve_param_values(admin_ctx, lov_env["version_id"], {})
        assert res.ok, res.message
        assert res.data["p_chan"] == "ONLINE"
