from __future__ import annotations

import json
from datetime import datetime, timezone
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
from app.schemas.run import CreateMultiRunParams
from app.services.run_service import create_multi_run

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_multi_profile_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Đảm bảo config có ít nhất 2 profile
    if len(cfg.get("profiles", [])) < 2:
        cfg["profiles"].append(
            {
                "code": "BY_CUSTOMER",
                "name": "Theo khách hàng",
                "is_default": False,
                "group_by": ["MA_KH"],
                "measures": [
                    {
                        "name": "TIEN_TRUOC_THUE",
                        "label": "Tổng tiền",
                        "agg": "sum",
                        "field": "TIEN_TRUOC_THUE",
                        "compare": "exact",
                    }
                ],
            }
        )
    return cfg


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_multi_run.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine


@pytest.fixture
def operator_ctx() -> Ctx:
    return Ctx(user_id=1, username="test_op", full_name="Test Operator", roles=[Role.OPERATOR])


@pytest.fixture
def seed_data(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        ds_res = conn.execute(
            recon_data_source.insert().values(
                NAME="Test DS",
                ENV="UAT",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="ORCL",
                USERNAME="u",
                PASSWORD_ENC="p",
                DEFAULT_SCHEMA="TEST",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = int(ds_res.inserted_primary_key[0])

        cfg = get_multi_profile_config()
        tmpl_res = conn.execute(
            recon_template.insert().values(
                CODE="TMPL_MULTI",
                NAME="Test Template Multi Profile",
                DESCRIPTION="desc",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tmpl_id = int(tmpl_res.inserted_primary_key[0])

        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                CONFIG_JSON=cfg,
                DATA_SOURCE_ID=ds_id,
                STATUS="ACTIVE",
                CREATED_BY="admin",
                CREATED_AT=now,
            )
        )

        f_res = conn.execute(
            recon_file.insert().values(
                STORAGE_PATH="/tmp/test.xlsx",
                ORIGINAL_NAME="test.xlsx",
                SIZE_BYTES=1024,
                SHA256="abc",
                UPLOADED_BY="test_op",
                UPLOADED_AT=now,
            )
        )
        file_id = int(f_res.inserted_primary_key[0])

        conn.execute(
            recon_app_setting.insert().values(
                KEY="SOURCE_TIMEOUT_S",
                VALUE="30",
                UPDATED_BY="system",
                UPDATED_AT=now,
            )
        )

    return {"template_id": tmpl_id, "data_source_id": ds_id, "file_id": file_id}


def test_create_multi_run_success(seed_data, test_db, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 2, 23, 59, 59)

    params = CreateMultiRunParams(
        template_id=seed_data["template_id"],
        file_id=seed_data["file_id"],
        profile_codes=["BY_INVOICE", "BY_DAY_POINT"],
        p_from=p_from,
        p_to=p_to,
    )

    res = create_multi_run(operator_ctx, params)
    assert res.ok is True
    assert res.data["status"] == "QUEUED"
    assert res.data["count"] == 2
    assert len(res.data["run_ids"]) == 2

    # Kiểm tra trong DB
    with test_db.connect() as conn:
        runs = conn.execute(
            select(recon_run).where(recon_run.c.ID.in_(res.data["run_ids"])).order_by(recon_run.c.ID)
        ).mappings().all()

        assert len(runs) == 2
        assert runs[0]["PROFILE_CODE"] == "BY_INVOICE"
        assert runs[1]["PROFILE_CODE"] == "BY_DAY_POINT"
        assert runs[0]["FILE_ID"] == seed_data["file_id"]
        assert runs[1]["FILE_ID"] == seed_data["file_id"]

        # Kiểm tra hàng đợi
        queues = conn.execute(
            select(recon_run_queue).where(recon_run_queue.c.RUN_ID.in_(res.data["run_ids"]))
        ).fetchall()
        assert len(queues) == 2

        # Kiểm tra audit log
        audits = conn.execute(
            select(recon_audit_log).where(
                recon_audit_log.c.ENTITY == "RECON_RUN",
                recon_audit_log.c.ENTITY_ID.in_([str(i) for i in res.data["run_ids"]]),
            )
        ).fetchall()
        assert len(audits) == 2


def test_create_multi_run_invalid_profile(seed_data, test_db, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 2, 23, 59, 59)

    params = CreateMultiRunParams(
        template_id=seed_data["template_id"],
        file_id=seed_data["file_id"],
        profile_codes=["BY_INVOICE", "INVALID_CODE_123"],
        p_from=p_from,
        p_to=p_to,
    )

    res = create_multi_run(operator_ctx, params)
    assert res.ok is False
    assert res.code == ErrorCode.VALIDATION_ERROR
    assert "INVALID_CODE_123" in res.message


def test_create_multi_run_duplicate_blocked(seed_data, test_db, operator_ctx):
    p_from = datetime(2026, 1, 1, 0, 0, 0)
    p_to = datetime(2026, 1, 2, 23, 59, 59)

    params = CreateMultiRunParams(
        template_id=seed_data["template_id"],
        file_id=seed_data["file_id"],
        profile_codes=["BY_INVOICE"],
        p_from=p_from,
        p_to=p_to,
    )

    res1 = create_multi_run(operator_ctx, params)
    assert res1.ok is True

    # Chạy lại cùng profile đang QUEUED -> phải bị chặn
    res2 = create_multi_run(operator_ctx, params)
    assert res2.ok is False
    assert res2.code == ErrorCode.VALIDATION_ERROR
    assert "đang chờ hoặc đang chạy" in res2.message
