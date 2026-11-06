"""E2E cho màn Bộ đối soát — Bước 8 task 18 (test viết trước).

Màn /batches và /batches/<id> mở được; luồng service tạo bộ → thêm
template → kích hoạt → xem trước tham số.
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
def batch_def_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_batch_def.db"
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


def test_batches_page_accessible(batch_def_client) -> None:
    res = batch_def_client.get("/batches")
    assert res.status_code == 200


def test_batch_def_page_accessible(batch_def_client, admin_ctx) -> None:
    from app.services.batch_def import create_batch_def

    created = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "Doanh thu", "max_parallel_per_ds": 2})
    assert created.ok is True
    res = batch_def_client.get(f"/batches/{created.data['id']}")
    assert res.status_code == 200


def test_batches_page_requires_login(tmp_path, monkeypatch) -> None:
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_batch_def_nologin.db"
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
    res = client.get("/batches", follow_redirects=False)
    assert res.status_code in (302, 303)


def test_batch_def_flow_create_add_activate_preview(batch_def_client, admin_ctx) -> None:
    from app.services.batch_def import (
        activate_batch_def,
        add_batch_def_items,
        create_batch_def,
        get_batch_def,
        preview_params,
    )
    from app.services.template import list_templates

    templates = list_templates(admin_ctx)
    assert templates.ok is True
    tmpl_id = next(t["id"] for t in templates.data if t["code"] == "DTP_TMPL")
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
                "multi_file": True,
                "is_required": True,
                "priority": 10,
                "params_override": {"p_ky": "{ky.thang}"},
            }
        ],
    )
    assert added.ok is True
    assert len(added.data) == 1
    activated = activate_batch_def(admin_ctx, def_id)
    assert activated.ok is True
    assert activated.data["status"] == "ACTIVE"
    detail = get_batch_def(admin_ctx, def_id)
    assert detail.ok is True
    assert len(detail.data["items"]) == 1
    preview = preview_params(admin_ctx, def_id, "2026-02")
    assert preview.ok is True
    assert len(preview.data["items"]) == 1
    assert preview.data["items"][0]["params"]["p_ky"] == "202602"
    assert preview.data["items"][0]["errors"] == []
