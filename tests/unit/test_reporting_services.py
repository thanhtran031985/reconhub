"""Tests cho services Reporting Core — Bước 2 task 21 (test viết trước).

Report Master CRUD + Template/Version clone/activate/archive (T21-03,
T21-04, T21-05). Fixture theo mẫu tests/unit/test_menu_admin_service.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def reporting_env(tmp_path, monkeypatch):
    db_path = tmp_path / "reporting_services.db"
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
        for uid, username in [(1, "admin"), (2, "operator"), (3, "viewer")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"], 3: ["VIEWER"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def viewer_ctx() -> Ctx:
    return Ctx(user_id=3, username="viewer", full_name="viewer", roles=["VIEWER"])


def _report_payload(**overrides) -> dict:
    payload = {
        "code": "FIN_REVENUE",
        "name": "Doanh thu",
        "category_code": "FIN",
        "owner": "admin",
        "description": "Báo cáo doanh thu",
        "default_favorite": False,
        "is_visible": True,
    }
    payload.update(overrides)
    return payload


def _template_payload(**overrides) -> dict:
    payload = {
        "code": "MAIN",
        "name": "Mẫu chính",
        "display_order": 10,
        "source_type": "CUSTOM_SQL",
        "sql_text": "SELECT AMOUNT FROM FIN_REVENUE",
        "timeout_sec": 300,
        "preview_max_rows": 100,
        "export_max_rows": 1000000,
    }
    payload.update(overrides)
    return payload


def _make_report(admin_ctx, **overrides):
    from app.services.report import create_report

    res = create_report(admin_ctx, _report_payload(**overrides))
    assert res.ok, res.message
    return res.data


def _make_template(admin_ctx, report_id, **overrides):
    from app.services.report_template import create_template

    res = create_template(admin_ctx, report_id, _template_payload(**overrides))
    assert res.ok, res.message
    return res.data


def _insert_version(engine, template_id, version_no, status, source_type="CUSTOM_SQL"):
    from app.db.metadata import recon_rpt_tpl_ver

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=version_no,
                STATUS=status,
                DATA_SOURCE_ID=None,
                SOURCE_TYPE=source_type,
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


def _insert_param(engine, version_id, code="P_FROM", grid_span=6, display_row=1):
    from app.db.metadata import recon_rpt_param, recon_rpt_param_lov

    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_param.insert().values(
                VERSION_ID=version_id,
                CODE=code,
                LABEL=code,
                DATA_TYPE="STRING",
                CONTROL_TYPE="TEXT",
                REQUIRED="N",
                DEFAULT_TYPE=None,
                DEFAULT_VALUE=None,
                DISPLAY_ROW=display_row,
                DISPLAY_ORDER=10,
                GRID_SPAN=grid_span,
                FILTER_COLUMN=None,
                FILTER_OPERATOR=None,
                IS_VISIBLE="Y",
            )
        )
        pid = int(res.inserted_primary_key[0])
        conn.execute(
            recon_rpt_param_lov.insert().values(
                PARAM_ID=pid,
                LOV_TYPE="STATIC",
                DATA_SOURCE_ID=None,
                SQL_TEXT=None,
                LOOKUP_TYPE=None,
                STATIC_JSON=[{"value": "HN", "label": "Hà Nội"}],
                CACHE_SECONDS=300,
                MAX_ROWS=5000,
            )
        )
        return pid


def _insert_column(engine, version_id, field="AMOUNT"):
    from app.db.metadata import recon_rpt_column

    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_column.insert().values(
                VERSION_ID=version_id,
                FIELD_NAME=field,
                LABEL=field,
                DATA_TYPE="NUMBER",
                DISPLAY_ORDER=10,
                WEB_VISIBLE="Y",
                EXCEL_VISIBLE="Y",
                FORMAT_MASK=None,
                ALIGNMENT="RIGHT",
                WIDTH=120,
                IS_TOTAL="N",
            )
        )
        return int(res.inserted_primary_key[0])


class TestReportMaster:
    def test_create_and_get(self, reporting_env, admin_ctx):
        from app.services.report import get_report

        created = _make_report(admin_ctx)
        got = get_report(admin_ctx, created["id"])
        assert got.ok
        assert got.data["code"] == "FIN_REVENUE"
        assert got.data["name"] == "Doanh thu"

    def test_create_duplicate_code(self, reporting_env, admin_ctx):
        from app.services.report import create_report

        _make_report(admin_ctx)
        res = create_report(admin_ctx, _report_payload())
        assert not res.ok and res.code == "CONFLICT"

    def test_create_invalid_code(self, reporting_env, admin_ctx):
        from app.services.report import create_report

        res = create_report(admin_ctx, _report_payload(code="fin-revenue"))
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_create_forbidden_for_operator(self, reporting_env, operator_ctx):
        from app.services.report import create_report

        res = create_report(operator_ctx, _report_payload())
        assert not res.ok and res.code == "FORBIDDEN"

    def test_list_visible_only_for_non_admin(self, reporting_env, admin_ctx, viewer_ctx):
        from app.services.report import archive_report, list_reports

        _make_report(admin_ctx, code="FIN_A")
        _make_report(admin_ctx, code="FIN_B", is_visible=False)
        archived = _make_report(admin_ctx, code="FIN_C")
        assert archive_report(admin_ctx, archived["id"]).ok
        mine = list_reports(viewer_ctx)
        assert mine.ok
        assert [r["code"] for r in mine.data] == ["FIN_A"]
        all_rows = list_reports(admin_ctx)
        assert all_rows.ok and len(all_rows.data) == 3

    def test_get_not_found_and_hidden(self, reporting_env, admin_ctx, viewer_ctx):
        from app.services.report import get_report

        hidden = _make_report(admin_ctx, code="FIN_H", is_visible=False)
        assert get_report(admin_ctx, 999999).code == "NOT_FOUND"
        assert get_report(viewer_ctx, hidden["id"]).code == "NOT_FOUND"

    def test_update_stale(self, reporting_env, admin_ctx):
        from app.services.report import get_report, update_report

        created = _make_report(admin_ctx)
        res = update_report(admin_ctx, created["id"], {"name": "Doanh thu mới"}, row_version=99)
        assert not res.ok and res.code == "STALE_DATA"
        ok = update_report(admin_ctx, created["id"], {"name": "Doanh thu mới"}, row_version=1)
        assert ok.ok and ok.data["name"] == "Doanh thu mới"
        assert ok.data["row_version"] == 2
        assert get_report(admin_ctx, created["id"]).data["name"] == "Doanh thu mới"

    def test_favorite_add_remove(self, reporting_env, admin_ctx, viewer_ctx):
        from app.services.report import list_reports, set_report_favorite

        created = _make_report(admin_ctx)
        assert set_report_favorite(viewer_ctx, created["id"], True).ok
        listed = list_reports(viewer_ctx)
        assert listed.data[0]["is_favorite"] is True
        assert set_report_favorite(viewer_ctx, created["id"], False).ok
        assert list_reports(viewer_ctx).data[0]["is_favorite"] is False


def _insert_run(engine, report_id, template_id, version_id, status="DONE"):
    from app.db.metadata import recon_report_run

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_report_run.insert().values(
                REPORT_ID=report_id,
                TEMPLATE_ID=template_id,
                VERSION_ID=version_id,
                PARAMS_JSON={},
                STATUS=status,
                ROW_COUNT=5,
                QUERY_MS=10,
                CREATED_BY="admin",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )
        return int(res.inserted_primary_key[0])


def _insert_export(engine, run_id):
    from app.db.metadata import recon_rpt_export

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_export.insert().values(
                RUN_ID=run_id,
                FORMAT="XLSX",
                STATUS="DONE",
                CREATED_BY="admin",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )
        return int(res.inserted_primary_key[0])


def _insert_preset(engine, report_id, template_id, user_id=1):
    from app.db.metadata import recon_rpt_preset

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_preset.insert().values(
                USER_ID=user_id,
                REPORT_ID=report_id,
                TEMPLATE_ID=template_id,
                NAME="Mặc định",
                PARAMS_JSON={},
                IS_DEFAULT="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        return int(res.inserted_primary_key[0])


class TestDeleteReport:
    """Task 32: xóa hẳn Report Master kèm toàn bộ dữ liệu liên quan."""

    def test_delete_empty_report(self, reporting_env, admin_ctx):
        from app.services.report import delete_report, get_report, list_reports

        created = _make_report(admin_ctx)
        res = delete_report(admin_ctx, created["id"])
        assert res.ok, res.message
        assert res.data["code"] == "FIN_REVENUE"
        assert res.data["deleted_templates"] == 0
        assert res.data["deleted_versions"] == 0
        assert res.data["deleted_runs"] == 0
        assert res.data["deleted_exports"] == 0
        assert get_report(admin_ctx, created["id"]).code == "NOT_FOUND"
        assert list_reports(admin_ctx).data == []

    def test_delete_report_cascades_template(self, reporting_env, admin_ctx, viewer_ctx):
        from sqlalchemy import select

        from app.db.metadata import (
            recon_report_template,
            recon_rpt_column,
            recon_rpt_param,
            recon_rpt_param_lov,
            recon_rpt_preset,
            recon_rpt_tpl_ver,
        )
        from app.services.report import delete_report, set_report_favorite
        from app.services.report_template import get_template

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        ver1 = get_template(admin_ctx, tpl["id"]).data["versions"][0]["id"]
        ver2 = _insert_version(engine, tpl["id"], 2, "DRY_RUN_OK")
        _insert_param(engine, ver1)
        _insert_param(engine, ver2, code="P_TO")
        _insert_column(engine, ver1)
        _insert_column(engine, ver2, field="QTY")
        assert set_report_favorite(viewer_ctx, report["id"], True).ok
        _insert_preset(engine, report["id"], tpl["id"])

        res = delete_report(admin_ctx, report["id"])
        assert res.ok, res.message
        assert res.data["deleted_templates"] == 1
        assert res.data["deleted_versions"] == 2
        with engine.connect() as conn:
            for table, col, val in [
                (recon_report_template, recon_report_template.c.REPORT_ID, report["id"]),
                (recon_rpt_tpl_ver, recon_rpt_tpl_ver.c.TEMPLATE_ID, tpl["id"]),
                (recon_rpt_param, recon_rpt_param.c.VERSION_ID, ver1),
                (recon_rpt_param, recon_rpt_param.c.VERSION_ID, ver2),
                (recon_rpt_column, recon_rpt_column.c.VERSION_ID, ver1),
                (recon_rpt_preset, recon_rpt_preset.c.REPORT_ID, report["id"]),
            ]:
                assert conn.execute(select(table).where(col == val)).first() is None
            assert conn.execute(select(recon_rpt_param_lov)).first() is None
            from app.db.metadata import recon_rpt_favorite

            assert conn.execute(select(recon_rpt_favorite)).first() is None

    def test_delete_report_with_runs_deletes_runs(self, reporting_env, admin_ctx):
        from sqlalchemy import select

        from app.db.metadata import recon_report_run, recon_rpt_export
        from app.services.report import delete_report
        from app.services.report_template import get_template

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        ver1 = get_template(admin_ctx, tpl["id"]).data["versions"][0]["id"]
        run_id = _insert_run(engine, report["id"], tpl["id"], ver1)
        _insert_export(engine, run_id)

        res = delete_report(admin_ctx, report["id"])
        assert res.ok, res.message
        assert res.data["deleted_runs"] == 1
        assert res.data["deleted_exports"] == 1
        assert res.data["deleted_templates"] == 1
        with engine.connect() as conn:
            assert conn.execute(select(recon_report_run)).first() is None
            assert conn.execute(select(recon_rpt_export)).first() is None

    def test_delete_forbidden_for_operator(self, reporting_env, admin_ctx, operator_ctx):
        from app.services.report import delete_report

        created = _make_report(admin_ctx)
        res = delete_report(operator_ctx, created["id"])
        assert not res.ok and res.code == "FORBIDDEN"

    def test_delete_not_found(self, reporting_env, admin_ctx):
        from app.services.report import delete_report

        res = delete_report(admin_ctx, 999999)
        assert not res.ok and res.code == "NOT_FOUND"


class TestReportTemplate:
    def test_create_template_with_draft_v1(self, reporting_env, admin_ctx):
        from app.services.report_template import get_template

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        assert tpl["code"] == "MAIN"
        got = get_template(admin_ctx, tpl["id"])
        assert got.ok
        assert len(got.data["versions"]) == 1
        assert got.data["versions"][0]["version_no"] == 1
        assert got.data["versions"][0]["status"] == "DRAFT"

    def test_create_template_duplicate_code(self, reporting_env, admin_ctx):
        from app.services.report_template import create_template

        report = _make_report(admin_ctx)
        other = _make_report(admin_ctx, code="FIN_OTHER")
        _make_template(admin_ctx, report["id"])
        res = create_template(admin_ctx, report["id"], _template_payload())
        assert not res.ok and res.code == "CONFLICT"
        assert create_template(admin_ctx, other["id"], _template_payload()).ok

    def test_create_template_invalid_source(self, reporting_env, admin_ctx):
        from app.services.report_template import create_template

        report = _make_report(admin_ctx)
        assert not create_template(
            admin_ctx, report["id"], _template_payload(sql_text=None)
        ).ok
        assert not create_template(
            admin_ctx, report["id"], _template_payload(source_type="VIEW", sql_text=None)
        ).ok
        assert not create_template(
            admin_ctx, report["id"], _template_payload(source_type="PROCEDURE")
        ).ok
        assert not create_template(
            admin_ctx, report["id"], _template_payload(timeout_sec=0)
        ).ok
        assert not create_template(
            admin_ctx, report["id"], _template_payload(timeout_sec=601)
        ).ok

    def test_create_template_forbidden(self, reporting_env, operator_ctx, admin_ctx):
        from app.services.report_template import create_template

        report = _make_report(admin_ctx)
        res = create_template(operator_ctx, report["id"], _template_payload())
        assert not res.ok and res.code == "FORBIDDEN"

    def test_update_template_stale(self, reporting_env, admin_ctx):
        from app.services.report_template import update_template

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        res = update_template(admin_ctx, tpl["id"], {"name": "Mẫu khác"}, row_version=99)
        assert not res.ok and res.code == "STALE_DATA"
        assert update_template(admin_ctx, tpl["id"], {"name": "Mẫu khác"}, row_version=1).ok


class TestVersionCloneActivateArchive:
    def test_clone_active_creates_draft(self, reporting_env, admin_ctx):
        from app.services.report_template import clone_version, get_version

        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        engine = reporting_env
        active_id = _insert_version(engine, tpl["id"], 2, "ACTIVE")
        _insert_param(engine, active_id, "P_FROM")
        _insert_column(engine, active_id, "AMOUNT")
        res = clone_version(admin_ctx, active_id)
        assert res.ok, res.message
        assert res.data["version_no"] == 3
        assert res.data["status"] == "DRAFT"
        assert res.data["source_type"] == "CUSTOM_SQL"
        cloned = get_version(admin_ctx, res.data["id"])
        assert cloned.ok
        assert [p["code"] for p in cloned.data["params"]] == ["P_FROM"]
        assert cloned.data["params"][0]["lov"]["lov_type"] == "STATIC"
        assert [c["field_name"] for c in cloned.data["columns"]] == ["AMOUNT"]

    def test_clone_not_found(self, reporting_env, admin_ctx):
        from app.services.report_template import clone_version

        assert clone_version(admin_ctx, 999999).code == "NOT_FOUND"

    def test_activate_dry_run_ok(self, reporting_env, admin_ctx):
        from app.services.report_template import activate_version, get_template

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        _insert_version(engine, tpl["id"], 2, "ACTIVE")
        new_id = _insert_version(engine, tpl["id"], 3, "DRY_RUN_OK")
        res = activate_version(admin_ctx, new_id)
        assert res.ok, res.message
        assert res.data["status"] == "ACTIVE"
        got = get_template(admin_ctx, tpl["id"])
        versions = {v["version_no"]: v["status"] for v in got.data["versions"]}
        assert versions[2] == "ARCHIVED"
        assert versions[3] == "ACTIVE"
        assert got.data["active_version_id"] == new_id

    def test_activate_draft_rejected(self, reporting_env, admin_ctx):
        from app.services.report_template import activate_version

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        draft_id = _insert_version(engine, tpl["id"], 2, "DRAFT")
        res = activate_version(admin_ctx, draft_id)
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_activate_locked_conflict(self, reporting_env, admin_ctx):
        from app.services.report_template import activate_version

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        new_id = _insert_version(engine, tpl["id"], 2, "DRY_RUN_OK")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_APP_SETTING (KEY, VALUE, UPDATED_BY, UPDATED_AT) "
                    "VALUES ('REPORT_ACTIVATE_LOCK', :v, 'test', :now)"
                ),
                {"v": now.isoformat(), "now": now},
            )
        res = activate_version(admin_ctx, new_id)
        assert not res.ok and res.code == "CONFLICT"

    def test_archive_version(self, reporting_env, admin_ctx):
        from app.services.report_template import archive_version, get_version

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        draft_id = _insert_version(engine, tpl["id"], 2, "DRAFT")
        active_id = _insert_version(engine, tpl["id"], 3, "ACTIVE")
        assert archive_version(admin_ctx, draft_id).ok
        assert get_version(admin_ctx, draft_id).data["status"] == "ARCHIVED"
        res = archive_version(admin_ctx, active_id)
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_archive_template(self, reporting_env, admin_ctx):
        from app.services.report_template import archive_template, get_template

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        _insert_version(engine, tpl["id"], 2, "ACTIVE")
        assert archive_template(admin_ctx, tpl["id"]).ok
        got = get_template(admin_ctx, tpl["id"])
        assert got.data["active_version_id"] is None
        versions = {v["version_no"]: v["status"] for v in got.data["versions"]}
        assert versions[1] == "ARCHIVED"
        assert versions[2] == "ARCHIVED"

    def test_run_keeps_old_version(self, reporting_env, admin_ctx):
        """T21-05: run cũ giữ VERSION_ID cũ sau khi version mới ACTIVE."""
        from sqlalchemy import select

        from app.db.metadata import recon_report_run
        from app.services.report_template import activate_version

        engine = reporting_env
        report = _make_report(admin_ctx)
        tpl = _make_template(admin_ctx, report["id"])
        old_id = _insert_version(engine, tpl["id"], 2, "ACTIVE")
        new_id = _insert_version(engine, tpl["id"], 3, "DRY_RUN_OK")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with engine.begin() as conn:
            res = conn.execute(
                recon_report_run.insert().values(
                    REPORT_ID=report["id"],
                    TEMPLATE_ID=tpl["id"],
                    VERSION_ID=old_id,
                    PARAMS_JSON={},
                    STATUS="DONE",
                    ROW_COUNT=5,
                    QUERY_MS=10,
                    CREATED_BY="admin",
                    CREATED_AT=now,
                    FINISHED_AT=now,
                )
            )
            run_id = int(res.inserted_primary_key[0])
        assert activate_version(admin_ctx, new_id).ok
        with engine.connect() as conn:
            kept = conn.execute(
                select(recon_report_run.c.VERSION_ID).where(recon_report_run.c.ID == run_id)
            ).scalar_one()
        assert kept == old_id
