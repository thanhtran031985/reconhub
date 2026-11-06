"""Tests cho audit reporting — Bước 4 task 21 (test viết trước).

Mọi thao tác metadata report/template/version ghi audit cùng
transaction (T21-06): thành công thì có dòng audit, thất bại thì không
có, lỗi giữa transaction thì rollback cả dữ liệu lẫn audit.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.db.metadata import metadata, recon_audit_log


@pytest.fixture()
def audit_env(tmp_path, monkeypatch):
    db_path = tmp_path / "reporting_audit.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                "VALUES (1, 'admin', 'admin', 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
            ),
            {"now": now},
        )
    seed_perm_basics(engine, {1: ["ADMIN"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _audit_rows(engine, entity: str | None = None) -> list:
    stmt = select(recon_audit_log)
    if entity is not None:
        stmt = stmt.where(recon_audit_log.c.ENTITY == entity)
    with engine.connect() as conn:
        return conn.execute(stmt.order_by(recon_audit_log.c.ID)).mappings().all()


def _make_report(admin_ctx, code="FIN_REVENUE"):
    from app.services.report import create_report

    res = create_report(
        admin_ctx,
        {
            "code": code,
            "name": "Doanh thu",
            "category_code": "FIN",
            "owner": "admin",
            "description": None,
            "default_favorite": False,
            "is_visible": True,
        },
    )
    assert res.ok, res.message
    return res.data


def _make_template(admin_ctx, report_id):
    from app.services.report_template import create_template

    res = create_template(
        admin_ctx,
        report_id,
        {
            "code": "MAIN",
            "name": "Mẫu chính",
            "display_order": 10,
            "source_type": "CUSTOM_SQL",
            "sql_text": "SELECT 1 FROM DUAL",
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        },
    )
    assert res.ok, res.message
    return res.data


def _insert_version(engine, template_id, version_no, status):
    from app.db.metadata import recon_rpt_tpl_ver

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=version_no,
                STATUS=status,
                DATA_SOURCE_ID=None,
                SOURCE_TYPE="CUSTOM_SQL",
                SQL_TEXT="SELECT 1 FROM DUAL",
                SOURCE_OWNER=None,
                SOURCE_OBJECT=None,
                TIMEOUT_SEC=300,
                PREVIEW_MAX_ROWS=100,
                EXPORT_MAX_ROWS=1000000,
                SQL_HASH=None,
                ACTIVATED_BY=None,
                ACTIVATED_AT=None,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        return int(res.inserted_primary_key[0])


class TestReportingAudit:
    def test_create_report_writes_audit(self, audit_env, admin_ctx):
        report = _make_report(admin_ctx)
        rows = _audit_rows(audit_env, "RECON_REPORT")
        assert len(rows) == 1
        assert rows[0]["ACTION"] == "CREATE_REPORT"
        assert rows[0]["ACTOR"] == "admin"
        assert str(rows[0]["ENTITY_ID"]) == str(report["id"])
        assert rows[0]["NEW_JSON"]["code"] == "FIN_REVENUE"

    def test_update_and_archive_report_write_audit(self, audit_env, admin_ctx):
        from app.services.report import archive_report, update_report

        report = _make_report(admin_ctx)
        assert update_report(admin_ctx, report["id"], {"name": "Doanh thu mới"}).ok
        assert archive_report(admin_ctx, report["id"]).ok
        rows = _audit_rows(audit_env, "RECON_REPORT")
        actions = [r["ACTION"] for r in rows]
        assert actions == ["CREATE_REPORT", "UPDATE_REPORT", "ARCHIVE_REPORT"]
        assert rows[1]["OLD_JSON"]["name"] == "Doanh thu"
        assert rows[1]["NEW_JSON"]["name"] == "Doanh thu mới"

    def test_create_template_writes_audit(self, audit_env, admin_ctx):
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        rows = _audit_rows(audit_env, "RECON_REPORT_TEMPLATE")
        assert len(rows) == 1
        assert rows[0]["ACTION"] == "CREATE_TEMPLATE"
        assert str(rows[0]["ENTITY_ID"]) == str(tpl["id"])

    def test_clone_writes_audit(self, audit_env, admin_ctx):
        from app.services.report_template import clone_version

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        old_id = _insert_version(audit_env, tpl["id"], 2, "ACTIVE")
        res = clone_version(admin_ctx, old_id)
        assert res.ok
        rows = _audit_rows(audit_env, "RECON_RPT_TPL_VER")
        assert len(rows) == 1
        assert rows[0]["ACTION"] == "CLONE_VERSION"
        assert str(rows[0]["ENTITY_ID"]) == str(res.data["id"])
        assert rows[0]["NEW_JSON"]["from_version_id"] == old_id

    def test_activate_writes_audit(self, audit_env, admin_ctx):
        from app.services.report_template import activate_version

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        old_id = _insert_version(audit_env, tpl["id"], 2, "ACTIVE")
        new_id = _insert_version(audit_env, tpl["id"], 3, "DRY_RUN_OK")
        assert activate_version(admin_ctx, new_id).ok
        rows = _audit_rows(audit_env, "RECON_RPT_TPL_VER")
        actions = {(r["ACTION"], str(r["ENTITY_ID"])) for r in rows}
        assert ("ACTIVATE_VERSION", str(new_id)) in actions
        assert ("ARCHIVE_VERSION", str(old_id)) in actions

    def test_archive_version_writes_audit(self, audit_env, admin_ctx):
        from app.services.report_template import archive_version

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        draft_id = _insert_version(audit_env, tpl["id"], 2, "DRAFT")
        assert archive_version(admin_ctx, draft_id).ok
        rows = _audit_rows(audit_env, "RECON_RPT_TPL_VER")
        assert len(rows) == 1
        assert rows[0]["ACTION"] == "ARCHIVE_VERSION"

    def test_failed_op_writes_no_audit(self, audit_env, admin_ctx):
        """T21-06: thao tác lỗi không để lại dòng audit."""
        from app.services.report import create_report, update_report

        _make_report(admin_ctx)
        res = create_report(
            admin_ctx,
            {
                "code": "FIN_REVENUE",
                "name": "Trùng mã",
                "category_code": "FIN",
                "owner": "admin",
                "description": None,
                "default_favorite": False,
                "is_visible": True,
            },
        )
        assert not res.ok
        report = _make_report(admin_ctx, code="FIN_OTHER")
        stale = update_report(admin_ctx, report["id"], {"name": "X"}, row_version=99)
        assert not stale.ok
        rows = _audit_rows(audit_env, "RECON_REPORT")
        assert len(rows) == 2  # chỉ 2 lần tạo thành công

    def test_audit_rolls_back_with_transaction(self, audit_env, admin_ctx, monkeypatch):
        """T21-06: lỗi giữa transaction thì rollback cả dữ liệu lẫn audit."""
        import app.services.report_template as tpl_mod
        from app.services.report_template import activate_version, get_version

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        new_id = _insert_version(audit_env, tpl["id"], 2, "DRY_RUN_OK")
        real_audit = tpl_mod.write_audit_log

        def _boom(*args, **kwargs):
            raise RuntimeError("audit lỗi giả lập")

        monkeypatch.setattr(tpl_mod, "write_audit_log", _boom)
        res = activate_version(admin_ctx, new_id)
        assert not res.ok
        monkeypatch.setattr(tpl_mod, "write_audit_log", real_audit)
        assert get_version(admin_ctx, new_id).data["status"] == "DRY_RUN_OK"
        assert _audit_rows(audit_env, "RECON_RPT_TPL_VER") == []
