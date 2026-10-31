from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.context import Ctx, Role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_excel_load, recon_excel_row
from app.schemas.template_config import TemplateConfig
from app.services.excel_load import load_excel_to_temp
from app.services.file_service import upload_file
from app.services.template import save_draft_template


@pytest.fixture
def op_ctx() -> Ctx:
    return Ctx(
        user_id=1,
        username="operator",
        full_name="Operator User",
        roles=[Role.OPERATOR],
    )


@pytest.fixture
def owner_ctx() -> Ctx:
    return Ctx(
        user_id=2,
        username="owner",
        full_name="Template Owner",
        roles=[Role.TEMPLATE_OWNER],
    )


def test_excel_load_lifecycle_and_idempotency(op_ctx: Ctx, owner_ctx: Ctx) -> None:
    # 1. Tạo template từ JSON mẫu
    tmpl_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    tmpl_data = json.loads(tmpl_path.read_text(encoding="utf-8"))
    config = TemplateConfig.model_validate(tmpl_data)

    save_res = save_draft_template(
        owner_ctx,
        code="DTP_LOAD_TEST",
        name="Template nạp test",
        config=config,
    )
    assert save_res.ok is True
    template_id = save_res.data["id"]
    template_version = save_res.data["current_version"]

    # 2. Upload file DTP
    excel_path = Path("samples/dtp_sample_200.xlsx")
    up_res = upload_file(op_ctx, filename="dtp_sample_200.xlsx", content=excel_path.read_bytes())
    assert up_res.ok is True
    file_id = up_res.data["id"]

    # 3. Nạp dữ liệu tạm lần đầu
    load_res = load_excel_to_temp(
        op_ctx,
        file_id=file_id,
        template_id=template_id,
        template_version=template_version,
    )
    assert load_res.ok is True
    load_data = load_res.data
    load_id = load_data["load_id"]
    assert load_id > 0
    assert load_data["is_reused"] is False
    assert load_data["rows_read"] == 201
    assert load_data["rows_valid"] == 200
    assert load_data["rows_invalid"] == 0
    assert load_data["control_total_matched"] is True
    assert load_data["control_total_file"] == Decimal("366732000")
    assert load_data["control_total_calc"] == Decimal("366732000")

    # Kiểm tra trực tiếp bảng DB
    engine = get_recon_engine()
    with engine.connect() as conn:
        row_cnt = conn.scalar(
            select(func.count()).select_from(recon_excel_row).where(recon_excel_row.c.LOAD_ID == load_id)
        )
        assert row_cnt == 200

        load_rec = conn.execute(select(recon_excel_load).where(recon_excel_load.c.ID == load_id)).mappings().one()
        assert load_rec["ROWS_READ"] == 201
        assert load_rec["ROWS_INVALID"] == 0

    # 4. Nạp lại lần 2 (cùng file_id, template_id, version) -> Tái sử dụng, không sinh thêm dòng
    load_res_2 = load_excel_to_temp(
        op_ctx,
        file_id=file_id,
        template_id=template_id,
        template_version=template_version,
    )
    assert load_res_2.ok is True
    assert load_res_2.data["load_id"] == load_id
    assert load_res_2.data["is_reused"] is True

    with engine.connect() as conn:
        row_cnt_after = conn.scalar(
            select(func.count()).select_from(recon_excel_row).where(recon_excel_row.c.LOAD_ID == load_id)
        )
        assert row_cnt_after == 200
