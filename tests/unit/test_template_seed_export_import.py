from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.cli import seed_cmd
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_template, recon_template_version
from app.schemas.errors import ErrorCode
from app.schemas.template_config import TemplateConfig
from app.services.template import save_draft_template
from app.services.template_export_import import export_template, import_template

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


@pytest.fixture
def test_db_env(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_export_import.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine


@pytest.fixture
def owner_ctx() -> Ctx:
    return Ctx(user_id=2, username="owner", full_name="Template Owner", roles=[Role.TEMPLATE_OWNER])


def test_export_and_import_template(test_db_env, owner_ctx) -> None:
    cfg = get_sample_config()
    save_res = save_draft_template(owner_ctx, code="DTP_EXP", name="DTP Export Test", config=cfg)
    assert save_res.ok is True
    tmpl_id = save_res.data["id"]

    # 1. Export
    exp_res = export_template(owner_ctx, template_id=tmpl_id)
    assert exp_res.ok is True
    exp_data = exp_res.data
    assert exp_data["code"] == "DTP_EXP"
    assert exp_data["name"] == "DTP Export Test"
    assert exp_data["config"]["schema_version"] == 1

    # 2. Import với mã khác -> thành công
    exp_data["code"] = "DTP_IMP_NEW"
    exp_data["name"] = "DTP Imported New"
    imp_res = import_template(owner_ctx, data=exp_data, overwrite=False)
    assert imp_res.ok is True
    assert imp_res.data["code"] == "DTP_IMP_NEW"

    # 3. Import trùng mã khi overwrite=False -> lỗi TEMPLATE_CODE_EXISTS
    dup_res = import_template(owner_ctx, data=exp_data, overwrite=False)
    assert dup_res.ok is False
    assert dup_res.code == ErrorCode.TEMPLATE_CODE_EXISTS

    # 4. Import trùng mã khi overwrite=True -> cập nhật thành công
    exp_data["name"] = "DTP Imported Overwrite"
    ow_res = import_template(owner_ctx, data=exp_data, overwrite=True)
    assert ow_res.ok is True
    assert ow_res.data["name"] == "DTP Imported Overwrite"


def test_seed_loads_dtp_template(test_db_env) -> None:
    # Chạy CLI seed_cmd
    args = argparse.Namespace()
    seed_cmd(args)

    with test_db_env.connect() as conn:
        tmpl = (
            conn.execute(select(recon_template).where(recon_template.c.CODE == "DTP_HOA_DON_TAC_NGHIEP"))
            .mappings()
            .first()
        )
        assert tmpl is not None
        assert tmpl["STATUS"] == "DRAFT"
        assert tmpl["CURRENT_VERSION"] == 1

        ver = (
            conn.execute(select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == tmpl["ID"]))
            .mappings()
            .first()
        )
        assert ver is not None
        assert ver["STATUS"] == "DRAFT"

    # Chạy lại seed_cmd -> idempotent, không tạo trùng
    seed_cmd(args)
    with test_db_env.connect() as conn:
        all_tmpls = (
            conn.execute(select(recon_template).where(recon_template.c.CODE == "DTP_HOA_DON_TAC_NGHIEP"))
            .mappings()
            .all()
        )
        assert len(all_tmpls) == 1
