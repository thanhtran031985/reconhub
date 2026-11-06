"""E2E cho wizard chạy bộ + kết quả — Bước 9 task 18 (test viết trước).

Màn /batch-runs/new, /batch-runs/<id> và /batch-runs/<id>/result mở được;
luồng service tạo bộ → tạo lần chạy → tải file DTP → ma trận.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_data_source, recon_template, recon_template_version, recon_user
from app.ui.app import create_app


@pytest.fixture
def batch_run_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_batch_run.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-e2e-secret-key-123")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        user_id = res.inserted_primary_key[0]
        seed_perm_basics(engine, {user_id: ["ADMIN"]}, conn=conn)

        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_TEST",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XE",
                CALL_TIMEOUT_S=600,
                MAX_ROWS=1000000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]
        cfg = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
        cfg["db_source"]["params"] = [
            {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
            {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
            {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
            {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
        ]
        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_TMPL",
                NAME="DTP_TMPL",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        ).inserted_primary_key[0]
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON=cfg,
                DATA_SOURCE_ID=ds_id,
                CREATED_BY="admin",
                CREATED_AT=now,
            )
        )

    app = create_app()
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "admin"
        sess["session_version"] = 1
        sess["roles"] = ["ADMIN"]
        sess["must_change_pw"] = False
    return client


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _make_active_def(admin_ctx, tmpl_id: int) -> int:
    from app.services.batch_def import (
        activate_batch_def,
        add_batch_def_items,
        create_batch_def,
    )

    created = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "Doanh thu", "max_parallel_per_ds": 2})
    assert created.ok is True
    def_id = created.data["id"]
    added = add_batch_def_items(
        admin_ctx,
        def_id,
        [
            {
                "template_id": tmpl_id,
                "file_pattern": "*DTP*",
                "multi_file": False,
                "is_required": True,
                "priority": 10,
                "params_override": {"p_ky": "{ky.thang}"},
            }
        ],
    )
    assert added.ok is True
    activated = activate_batch_def(admin_ctx, def_id)
    assert activated.ok is True
    return def_id


def test_batch_runs_new_page_accessible(batch_run_client) -> None:
    res = batch_run_client.get("/batch-runs/new")
    assert res.status_code == 200


def test_batch_run_wizard_page_accessible(batch_run_client, admin_ctx) -> None:
    from app.services.batch_def import get_batch_def
    from app.services.batch_run import create_batch_run
    from app.services.template import list_templates

    templates = list_templates(admin_ctx)
    tmpl_id = next(t["id"] for t in templates.data if t["code"] == "DTP_TMPL")
    def_id = _make_active_def(admin_ctx, tmpl_id)
    detail = get_batch_def(admin_ctx, def_id)
    assert detail.ok is True
    run = create_batch_run(admin_ctx, def_id, "2026-02")
    assert run.ok is True
    res = batch_run_client.get(f"/batch-runs/{run.data['id']}")
    assert res.status_code == 200


def test_batch_run_result_page_accessible(batch_run_client, admin_ctx) -> None:
    from app.services.batch_run import create_batch_run, matrix
    from app.services.template import list_templates

    templates = list_templates(admin_ctx)
    tmpl_id = next(t["id"] for t in templates.data if t["code"] == "DTP_TMPL")
    def_id = _make_active_def(admin_ctx, tmpl_id)
    run = create_batch_run(admin_ctx, def_id, "2026-02")
    assert run.ok is True
    run_id = run.data["id"]
    res = batch_run_client.get(f"/batch-runs/{run_id}/result")
    assert res.status_code == 200
    m = matrix(admin_ctx, run_id)
    assert m.ok is True
    assert m.data["total_items"] == 1
    assert m.data["def_code"] == "DOANH_THU"


def test_batch_runs_new_requires_login(tmp_path, monkeypatch) -> None:
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_batch_run_nologin.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-e2e-secret-key-123")
    get_settings.cache_clear()
    engine = create_engine(db_url)
    metadata.create_all(engine)
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)
    app = create_app()
    client = app.server.test_client()
    res = client.get("/batch-runs/new", follow_redirects=False)
    assert res.status_code in (302, 303)


def test_batch_run_flow_upload_matches_template(batch_run_client, admin_ctx) -> None:
    from app.services.batch_run import add_files, create_batch_run, get_batch_run
    from app.services.template import list_templates

    templates = list_templates(admin_ctx)
    tmpl_id = next(t["id"] for t in templates.data if t["code"] == "DTP_TMPL")
    def_id = _make_active_def(admin_ctx, tmpl_id)
    run = create_batch_run(admin_ctx, def_id, "2026-02")
    assert run.ok is True
    run_id = run.data["id"]
    content = Path("samples/dtp_sample_200.xlsx").read_bytes()
    added = add_files(admin_ctx, run_id, [{"filename": "dtp_02.xlsx", "content": content}])
    assert added.ok is True
    assert len(added.data["added"]) == 1
    detail = get_batch_run(admin_ctx, run_id)
    assert detail.ok is True
    assert detail.data["items"][0]["template_code"] == "DTP_TMPL"
    assert detail.data["items"][0]["files"][0]["match_state"] == "MATCHED"
    res = batch_run_client.get(f"/batch-runs/{run_id}")
    assert res.status_code == 200


def test_history_page_accessible_with_batch_filter(batch_run_client) -> None:
    res = batch_run_client.get("/history")
    assert res.status_code == 200
