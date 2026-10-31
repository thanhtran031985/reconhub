from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_result_row,
    recon_template,
    recon_template_version,
)
from app.schemas.errors import ErrorCode
from app.schemas.template_config import TemplateConfig
from app.services.run_service import dry_run
from app.services.template import activate_version, save_draft_template

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_dryrun.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        db_url,
        connect_args={"timeout": 30},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")

    metadata.create_all(engine)
    return engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def draft_template_setup(test_db, admin_ctx):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        ds_id = conn.execute(
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

        f_id = conn.execute(
            recon_file.insert().values(
                SHA256="dummy_sha256",
                ORIGINAL_NAME="dtp_sample_200.xlsx",
                SIZE_BYTES=1024,
                STORAGE_PATH="samples/dtp_sample_200.xlsx",
                SHEETS_JSON=["BÁO CÁO DTP"],
                UPLOADED_BY="admin",
                UPLOADED_AT=now,
            )
        ).inserted_primary_key[0]

    cfg_dict = get_sample_config()
    cfg = TemplateConfig.model_validate(cfg_dict)

    res = save_draft_template(
        admin_ctx,
        code="DTP_HOA_DON",
        name="DTP Hóa đơn",
        config=cfg,
        data_source_id=ds_id,
    )
    assert res.ok
    tmpl_id = res.data["id"]

    return {
        "ds_id": ds_id,
        "file_id": f_id,
        "template_id": tmpl_id,
        "config": cfg,
    }


def test_dry_run_and_activate_lifecycle(draft_template_setup, admin_ctx, test_db):
    tmpl_id = draft_template_setup["template_id"]
    file_id = draft_template_setup["file_id"]

    # 1. Chưa dry-run mà activate -> DRY_RUN_REQUIRED
    act_res = activate_version(admin_ctx, template_id=tmpl_id, version=1)
    assert not act_res.ok
    assert act_res.code == ErrorCode.DRY_RUN_REQUIRED

    # 2. Thực hiện dry-run với mock fetcher
    db_df = pl.read_parquet(Path("tests/golden/G01_dtp_by_invoice/db.parquet"))

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    dry_res = dry_run(
        admin_ctx,
        template_id=tmpl_id,
        version=1,
        file_id=file_id,
        p_from=datetime(2026, 2, 1, 0, 0, 0),
        p_to=datetime(2026, 2, 5, 23, 59, 59),
        mock_fetcher=mock_fetcher,
    )
    assert dry_res.ok
    assert dry_res.data["dry_run_ok"] is True

    # Xác minh không lưu vào bảng RECON_RESULT_ROW (persist=False)
    with test_db.connect() as conn:
        res_rows = conn.execute(select(recon_result_row)).all()
        assert len(res_rows) == 0

        # RECON_TEMPLATE_VERSION đã lưu DRY_RUN_OK='Y'
        tv = conn.execute(
            select(recon_template_version).where(
                recon_template_version.c.TEMPLATE_ID == tmpl_id,
                recon_template_version.c.VERSION == 1,
            )
        ).mappings().first()
        assert tv is not None
        assert tv["DRY_RUN_OK"] == "Y"
        assert tv["DRY_RUN_JSON"] is not None

    # 3. Sửa cấu hình bản nháp sau khi đã dry-run
    modified_dict = get_sample_config()
    modified_dict["fields"][0]["label"] = "Điểm thu phí (Đã sửa)"
    mod_cfg = TemplateConfig.model_validate(modified_dict)

    save_res = save_draft_template(
        admin_ctx,
        code="DTP_HOA_DON",
        name="DTP Hóa đơn",
        config=mod_cfg,
        data_source_id=draft_template_setup["ds_id"],
        row_version=1,
    )
    assert save_res.ok

    # Kiểm tra DRY_RUN_OK đã bị reset về 'N'
    with test_db.connect() as conn:
        tv_after = conn.execute(
            select(recon_template_version).where(
                recon_template_version.c.TEMPLATE_ID == tmpl_id,
                recon_template_version.c.VERSION == 1,
            )
        ).mappings().first()
        assert tv_after is not None
        assert tv_after["DRY_RUN_OK"] == "N"

    # Thử kích hoạt lại -> bị chặn DRY_RUN_REQUIRED
    act_fail = activate_version(admin_ctx, template_id=tmpl_id, version=1)
    assert not act_fail.ok
    assert act_fail.code == ErrorCode.DRY_RUN_REQUIRED

    # 4. Dry-run lại
    dry_res2 = dry_run(
        admin_ctx,
        template_id=tmpl_id,
        version=1,
        file_id=file_id,
        p_from=datetime(2026, 2, 1, 0, 0, 0),
        p_to=datetime(2026, 2, 5, 23, 59, 59),
        mock_fetcher=mock_fetcher,
    )
    assert dry_res2.ok

    # Kích hoạt thành công
    act_success = activate_version(admin_ctx, template_id=tmpl_id, version=1)
    assert act_success.ok

    with test_db.connect() as conn:
        tmpl_row = conn.execute(select(recon_template).where(recon_template.c.ID == tmpl_id)).mappings().first()
        assert tmpl_row is not None
        assert tmpl_row["STATUS"] == "ACTIVE"
