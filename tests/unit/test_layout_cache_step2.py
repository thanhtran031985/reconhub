"""Tests cho Task 104 Bước 2 — Skeleton-first, gộp N+1 query và Server Layout Cache."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text

from app.core.context import Ctx
from app.db.metadata import (
    metadata,
    recon_report_template,
    recon_rpt_export,
    recon_template,
    recon_template_version,
)
from app.services.menu_sync import sync_from_code
from app.services.perm import clear_perm_cache


@pytest.fixture()
def step2_env(tmp_path, monkeypatch):
    db_file = tmp_path / "step2.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", echo=False)
    metadata.create_all(engine)
    sync_from_code(engine)
    from tests.conftest import seed_perm_basics

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "operator")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": uname, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]})
    clear_perm_cache()

    for mod in (
        "app.services.perm",
        "app.services.data_source",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_run",
        "app.services.report_export",
        "app.services.template",
        "app.services.batch_def",
        "app.ui.pages.report_runs",
        "app.ui.pages.reports",
        "app.ui.pages.templates",
        "app.ui.pages.batch_defs",
        "app.ui.pages.dashboard",
    ):
        try:
            monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
        except AttributeError:
            pass

    yield engine
    clear_perm_cache()


def test_list_exports_by_runs_batches_into_single_query(step2_env) -> None:
    from app.services.report_export import list_exports_by_runs

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with step2_env.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_REPORT (ID, CODE, NAME, CATEGORY_CODE, OWNER, "
                "DEFAULT_FAVORITE, IS_VISIBLE, IS_ACTIVE, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (1, 'R1', 'Report 1', 'FINANCE', 'admin', 'N', 'Y', 'Y', 'admin', :now, 'admin', :now, 1)"
            ),
            {"now": now},
        )
        for rid in range(1, 7):
            conn.execute(
                text(
                    "INSERT INTO RECON_REPORT_RUN (ID, REPORT_ID, TEMPLATE_ID, VERSION_ID, "
                    "PARAMS_JSON, STATUS, CREATED_BY, CREATED_AT) "
                    "VALUES (:id, 1, 1, 1, '{}', 'DONE', :owner, :now)"
                ),
                {"id": rid, "owner": "operator" if rid <= 3 else "admin", "now": now},
            )
            conn.execute(
                recon_rpt_export.insert().values(
                    RUN_ID=rid,
                    FORMAT="XLSX",
                    STATUS="DONE",
                    PROGRESS_PCT=100,
                    CREATED_BY="operator" if rid <= 3 else "admin",
                    CREATED_AT=now,
                )
            )

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    op_ctx = Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])

    queries: list[str] = []

    @event.listens_for(step2_env, "before_cursor_execute")
    def _spy(_conn, _cur, stmt, *_a):
        queries.append(stmt)

    # Làm ấm is_admin nếu cần rồi đếm truy vấn vào RECON_RPT_EXPORT
    queries.clear()
    res = list_exports_by_runs(admin_ctx, [1, 2, 3, 4, 5, 6])
    assert res.ok, res.message
    assert set(res.data.keys()) == {1, 2, 3, 4, 5, 6}
    export_sqls = [q for q in queries if "RECON_RPT_EXPORT" in q]
    assert len(export_sqls) == 1  # Chỉ 1 câu SELECT IN (...) thay vì 6*2 câu

    # Không rò rỉ export của admin sang operator
    res_op = list_exports_by_runs(op_ctx, [1, 2, 3, 4, 5, 6])
    assert res_op.ok
    assert set(res_op.data.keys()) == {1, 2, 3}

    # Danh sách rỗng -> 0 truy vấn
    queries.clear()
    res_empty = list_exports_by_runs(admin_ctx, [])
    assert res_empty.ok and res_empty.data == {}
    assert [q for q in queries if "RECON_RPT_EXPORT" in q] == []


def test_report_runs_layout_is_skeleton_first_and_cached(step2_env, monkeypatch) -> None:
    import app.ui.layout_cache as layout_cache
    import app.ui.pages.report_runs as page
    from tests.unit.test_report_viewer_fixes40 import _find_by_id

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
    layout_cache.clear_layout_cache()

    queries: list[str] = []

    @event.listens_for(step2_env, "before_cursor_execute")
    def _spy(_conn, _cur, stmt, *_a):
        queries.append(stmt)

    tree1 = page.layout()
    assert not any("RECON_REPORT_RUN" in q or "RECON_RPT_EXPORT" in q for q in queries), queries
    grid = _find_by_id(tree1, "report-runs-grid")
    assert grid is not None
    assert grid.rowData is None

    # Lần gọi thứ 2 trả từ Server Layout Cache
    queries.clear()
    tree2 = page.layout()
    assert tree2 is tree1


def test_static_page_layouts_cached_by_capability_and_cleared(step2_env, monkeypatch) -> None:
    import app.ui.layout_cache as layout_cache
    import app.ui.pages.batch_defs as bdefs
    import app.ui.pages.dashboard as dash_page
    import app.ui.pages.templates as tmpl_page

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    op_ctx = Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])
    for pmod in (tmpl_page, bdefs, dash_page):
        monkeypatch.setattr(pmod, "get_current_ctx", lambda: admin_ctx)

    layout_cache.clear_layout_cache()
    t1 = tmpl_page.layout()
    t2 = tmpl_page.layout()
    assert t1 is t2

    b1 = bdefs.layout()
    b2 = bdefs.layout()
    assert b1 is b2

    d1 = dash_page.layout()
    d2 = dash_page.layout()
    assert d1 is d2

    # Operator không có quyền ghi batch_defs -> key khác admin
    monkeypatch.setattr(bdefs, "get_current_ctx", lambda: op_ctx)
    b_op = bdefs.layout()
    assert b_op is not b1

    # clear_perm_cache() xóa luôn layout cache
    clear_perm_cache()
    monkeypatch.setattr(bdefs, "get_current_ctx", lambda: admin_ctx)
    b3 = bdefs.layout()
    assert b3 is not b1


def test_list_reports_batches_template_count_no_n_plus_1(step2_env, monkeypatch) -> None:
    import app.ui.pages.reports as reports_page

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with step2_env.begin() as conn:
        for i in range(1, 7):
            conn.execute(
                text(
                    "INSERT INTO RECON_REPORT (ID, CODE, NAME, CATEGORY_CODE, OWNER, "
                    "DEFAULT_FAVORITE, IS_VISIBLE, IS_ACTIVE, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :code, :name, 'FINANCE', 'admin', 'N', 'Y', 'Y', 'admin', :now, 'admin', :now, 1)"
                ),
                {"id": i, "code": f"RPT_{i}", "name": f"Báo cáo {i}", "now": now},
            )
            conn.execute(
                recon_report_template.insert().values(
                    REPORT_ID=i,
                    CODE=f"TPL_{i}",
                    NAME="Default",
                    DISPLAY_ORDER=1,
                    CREATED_BY="admin",
                    CREATED_AT=now,
                    UPDATED_BY="admin",
                    UPDATED_AT=now,
                )
            )

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    monkeypatch.setattr(reports_page, "get_current_ctx", lambda: admin_ctx)

    queries: list[str] = []

    @event.listens_for(step2_env, "before_cursor_execute")
    def _spy(_conn, _cur, stmt, *_a):
        queries.append(stmt)

    tree = reports_page.layout()
    assert "RPT_6" in str(tree)
    tpl_queries = [q for q in queries if "RECON_RPT_TEMPLATE" in q]
    assert len(tpl_queries) <= 1  # Chỉ 1 câu GROUP BY cho cả 6 báo cáo


def test_list_templates_batches_queries_no_n_plus_1(step2_env) -> None:
    from app.services.template import list_templates

    sample_cfg = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with step2_env.begin() as conn:
        for i in range(1, 9):
            res = conn.execute(
                recon_template.insert().values(
                    CODE=f"TMPL_{i:02d}",
                    NAME=f"Template {i}",
                    OWNER="admin",
                    STATUS="ACTIVE",
                    CURRENT_VERSION=1,
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            tid = int(res.inserted_primary_key[0])
            conn.execute(
                recon_template_version.insert().values(
                    TEMPLATE_ID=tid,
                    VERSION=1,
                    CONFIG_JSON=sample_cfg,
                    STATUS="ACTIVE",
                    CREATED_BY="admin",
                    CREATED_AT=now,
                )
            )

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    queries: list[str] = []

    @event.listens_for(step2_env, "before_cursor_execute")
    def _spy(_conn, _cur, stmt, *_a):
        queries.append(stmt)

    res = list_templates(admin_ctx)
    assert res.ok and len(res.data) == 8
    # Batch query: số query vào VERSION và RUN không tăng theo N=8
    ver_queries = [q for q in queries if "RECON_TEMPLATE_VERSION" in q]
    run_queries = [q for q in queries if "RECON_RUN" in q]
    assert len(ver_queries) <= 1
    assert len(run_queries) <= 1
