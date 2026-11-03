from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_app_setting,
    recon_audit_log,
    recon_data_source,
    recon_file,
    recon_run,
    recon_run_queue,
    recon_template,
    recon_template_version,
)
from app.schemas.errors import ErrorCode
from app.schemas.run import CreateRunParams, PrecheckParams
from app.services.run_service import create_run, precheck

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_run.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="Operator", roles=[Role.OPERATOR])


@pytest.fixture
def viewer_ctx() -> Ctx:
    return Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER])


@pytest.fixture
def seed_data(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        # 1. Tạo Data Source DEV và PROD
        ds_dev = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_DEV",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="orcl",
                USERNAME="RECON_SRC_RO",
                PASSWORD_ENC="dummy",
                DEFAULT_SCHEMA="RECON_SRC",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        ds_prod = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_PROD",
                ENV="PROD",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="prod-host",
                PORT=1521,
                SERVICE_NAME="orcl",
                USERNAME="RECON_SRC_RO",
                PASSWORD_ENC="dummy",
                DEFAULT_SCHEMA="RECON_SRC",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        # 2. Tạo File
        f_id = conn.execute(
            recon_file.insert().values(
                SHA256="dummy_sha256",
                ORIGINAL_NAME="dtp_sample_200.xlsx",
                SIZE_BYTES=1024,
                STORAGE_PATH="samples/dtp_sample_200.xlsx",
                SHEETS_JSON=["Sheet1"],
                UPLOADED_BY="operator",
                UPLOADED_AT=now,
            )
        ).inserted_primary_key[0]

        # 3. Tạo Template & Active Version
        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON",
                NAME="DTP Hóa đơn",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        cfg = get_sample_config()
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON=cfg,
                DATA_SOURCE_ID=ds_dev,
                DRY_RUN_OK="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                ACTIVATED_AT=now,
            )
        )

    return {
        "ds_dev": ds_dev,
        "ds_prod": ds_prod,
        "file_id": f_id,
        "template_id": tmpl_id,
    }


def test_precheck_invalid_range(seed_data, operator_ctx):
    p_from = datetime(2026, 1, 10, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)

    res = precheck(
        operator_ctx,
        PrecheckParams(
            template_id=seed_data["template_id"],
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert not res.ok
    assert res.code == ErrorCode.INVALID_RANGE


def test_precheck_range_too_large(seed_data, operator_ctx):
    # Template max_range_days = 93
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = p_from + timedelta(days=100)

    res = precheck(
        operator_ctx,
        PrecheckParams(
            template_id=seed_data["template_id"],
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert not res.ok
    assert res.code == ErrorCode.RANGE_TOO_LARGE


def test_precheck_prod_confirm_required(seed_data, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)

    res = precheck(
        operator_ctx,
        PrecheckParams(
            template_id=seed_data["template_id"],
            data_source_id=seed_data["ds_prod"],
            p_from=p_from,
            p_to=p_to,
            confirm_prod=False,
        ),
    )
    assert not res.ok
    assert res.code == ErrorCode.PROD_CONFIRM_REQUIRED


def test_precheck_maintenance_mode(seed_data, test_db, operator_ctx, admin_ctx):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        conn.execute(
            recon_app_setting.insert().values(
                KEY="MAINTENANCE",
                VALUE="Y",
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        )

    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)

    # Operator bị chặn
    res_op = precheck(
        operator_ctx,
        PrecheckParams(
            template_id=seed_data["template_id"],
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert not res_op.ok
    assert res_op.code == ErrorCode.MAINTENANCE_MODE

    # Admin không bị chặn
    res_admin = precheck(
        admin_ctx,
        PrecheckParams(
            template_id=seed_data["template_id"],
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert res_admin.ok


def test_create_run_blocks_duplicate_queued_run(seed_data, test_db, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)
    params = CreateRunParams(
        template_id=seed_data["template_id"],
        file_id=seed_data["file_id"],
        profile_code="BY_INVOICE",
        sheet_name="Sheet1",
        p_from=p_from,
        p_to=p_to,
    )
    first = create_run(operator_ctx, params)
    assert first.ok

    second = create_run(operator_ctx, params)
    assert not second.ok
    assert second.code == ErrorCode.VALIDATION_ERROR
    assert second.details and second.details.get("existing_run_id") == first.data["run_id"]


def test_create_run_forbidden_for_viewer(seed_data, viewer_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)

    res = create_run(
        viewer_ctx,
        CreateRunParams(
            template_id=seed_data["template_id"],
            file_id=seed_data["file_id"],
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert not res.ok
    assert res.code == ErrorCode.FORBIDDEN


def test_create_run_success(seed_data, test_db, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 5, 0, 0, 0)

    res = create_run(
        operator_ctx,
        CreateRunParams(
            template_id=seed_data["template_id"],
            file_id=seed_data["file_id"],
            profile_code="BY_INVOICE",
            sheet_name="Sheet1",
            p_from=p_from,
            p_to=p_to,
        ),
    )
    assert res.ok
    run_id = res.data["run_id"]
    assert run_id > 0

    # Kiểm tra RECON_RUN và RECON_RUN_QUEUE
    with test_db.connect() as conn:
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        assert run_row is not None
        assert run_row["STATUS"] == "QUEUED"
        assert run_row["CREATED_BY"] == "operator"

        queue_row = conn.execute(select(recon_run_queue).where(recon_run_queue.c.RUN_ID == run_id)).mappings().first()
        assert queue_row is not None
        assert queue_row["STATUS"] == "READY"

        audit_row = (
            conn.execute(
                select(recon_audit_log).where(
                    recon_audit_log.c.ENTITY == "RECON_RUN",
                    recon_audit_log.c.ENTITY_ID == str(run_id),
                )
            )
            .mappings()
            .first()
        )
        assert audit_row is not None
        assert audit_row["ACTION"] == "CREATE_RUN"
