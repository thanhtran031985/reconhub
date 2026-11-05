from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_template,
    recon_template_version,
    recon_user,
)
from app.ui.pages.template_diagram import layout, render_diagram_card

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


@pytest.fixture
def diagram_env(tmp_path, monkeypatch):
    db_file = tmp_path / "diagram_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Đồng bộ menu + vai trò seed (task 19) trước khi chèn user
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample_cfg = json.load(f)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_diag",
                FULL_NAME="Quản Trị Viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = res_adm.inserted_primary_key[0]
        seed_perm_basics(engine, {adm_id: ["ADMIN"]}, conn=conn)

        res_tpl = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON_TAC_NGHIEP",
                NAME="Hóa đơn tác nghiệp DTP",
                OWNER="admin_diag",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tpl_id = res_tpl.inserted_primary_key[0]

        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tpl_id,
                VERSION=1,
                CONFIG_JSON=sample_cfg,
                STATUS="ACTIVE",
                CREATED_BY="admin_diag",
                CREATED_AT=now,
            )
        )

    admin_ctx = Ctx(user_id=adm_id, username="admin_diag", full_name="Quản Trị Viên", roles=[Role.ADMIN])
    return {"admin_ctx": admin_ctx, "tpl_id": tpl_id, "tpl_code": "DTP_HOA_DON_TAC_NGHIEP"}


def test_render_diagram_card():
    card = render_diagram_card(
        title="Test Diagram Title",
        subtitle="Test subtitle explanation",
        diagram_code="flowchart LR\n A --> B",
        card_id="test-card",
    )
    assert card is not None
    card_str = str(card)
    assert "Test Diagram Title" in card_str
    assert "flowchart LR" in card_str


def test_template_diagram_layout(diagram_env, monkeypatch):
    # 1. Chưa đăng nhập
    monkeypatch.setattr("app.ui.pages.template_diagram.get_current_ctx", lambda: None)
    node_no_login = layout("DTP_HOA_DON_TAC_NGHIEP")
    assert "Bạn cần đăng nhập" in str(node_no_login)

    # 2. Template ID rỗng
    monkeypatch.setattr("app.ui.pages.template_diagram.get_current_ctx", lambda: diagram_env["admin_ctx"])
    node_no_id = layout(None)
    assert "Không tìm thấy template" in str(node_no_id)

    # 3. Đăng nhập và nạp template thành công theo code
    node_ok = layout("DTP_HOA_DON_TAC_NGHIEP")
    assert node_ok is not None
    node_str = str(node_ok)
    assert "DTP_HOA_DON_TAC_NGHIEP" in node_str
    assert "Quy trình đăng ký template" in node_str
    assert "Ba lớp mapping" in node_str
    assert "Tham số thời gian" in node_str
    assert "Profile: gộp → ghép → so" in node_str
    assert "Trình tự thực thi" in node_str

    # 4. Nạp template theo ID số
    node_id_ok = layout(str(diagram_env["tpl_id"]))
    assert node_id_ok is not None
    assert "DTP_HOA_DON_TAC_NGHIEP" in str(node_id_ok)
