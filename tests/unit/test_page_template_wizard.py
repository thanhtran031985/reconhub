from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_user, recon_user_role
from app.schemas.template_config import TemplateConfig
from app.ui.pages.template_wizard import (
    config_to_form_state,
    form_state_to_config,
    layout,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def load_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


@pytest.fixture
def wizard_env(monkeypatch, tmp_path):
    db_file = tmp_path / "wizard_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="owner",
                FULL_NAME="Template Owner",
                EMAIL="owner@reconhub.vn",
                PASSWORD_HASH=hash_password("owner123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=1,
                ROLE="TEMPLATE_OWNER",
                CREATED_AT=now,
            )
        )

    return db_url


def test_config_to_form_state_and_reverse() -> None:
    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    assert form_state is not None
    assert len(form_state["fields"]) == len(cfg.fields)
    assert form_state["db_source"]["table"] == "RECON_SRC.SRC_FACT_INVOICE_DTP"
    assert len(form_state["profiles"]) == len(cfg.profiles)

    # Convert back to TemplateConfig
    reconstructed_cfg, errors = form_state_to_config(form_state)
    assert errors == {}
    assert reconstructed_cfg is not None
    assert reconstructed_cfg.schema_version == cfg.schema_version
    assert len(reconstructed_cfg.fields) == len(cfg.fields)
    assert len(reconstructed_cfg.profiles) == len(cfg.profiles)


def test_validation_errors_mapped_to_form_fields() -> None:
    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    # Cố tình gây lỗi tên trường không đúng định dạng
    form_state["fields"][0]["name"] = "123_invalid-name!"

    _, errors = form_state_to_config(form_state)
    assert len(errors) > 0
    # Lỗi phải trỏ tới path trường bị lỗi
    matched_key = any("fields" in k and "name" in k for k in errors.keys())
    assert matched_key or any("fields" in k for k in errors.keys())


def test_template_wizard_layout_renders_for_owner(wizard_env, monkeypatch) -> None:
    owner_ctx = Ctx(user_id=1, username="owner", full_name="Template Owner", roles=[Role.TEMPLATE_OWNER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)

    content = layout()
    assert content is not None
    s = str(content)
    assert "wizard-page-root" in s
    assert "wizard-view-tabs" in s
    assert "wizard-stepper" in s
    assert "wizard-prev-btn" in s
    assert "wizard-save-draft-btn" in s
    assert "wizard-next-btn" in s


def test_template_wizard_forbidden_for_viewer(wizard_env, monkeypatch) -> None:
    viewer_ctx = Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: viewer_ctx)

    content = layout()
    s = str(content)
    assert "/forbidden" in s or "Không có quyền" in s or "dcc.Location" in s
