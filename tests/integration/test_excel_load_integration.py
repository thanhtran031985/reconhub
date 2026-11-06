from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, update

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

    # 3. Nạp dữ liệu tạm lần đầu. DB dùng chung có thể đã có bản nạp cùng
    # nội dung từ lần chạy trước — UQ FILE_SET_HASH (task 18 bước 1) nên
    # dùng lại bản nạp đó; chỉ khẳng định dữ liệu đúng, không khẳng định
    # is_reused (đường nạp mới được kiểm ở bước 5 sau khi purge).
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

    # 5. Giả lập xóa dữ liệu tạm: xóa dòng Excel và đánh dấu PURGED_AT
    # trên bản nạp (như temp_data.purge_run_temp_data làm). Nạp lại
    # cùng file/template/version trước đây lỗi UNIQUE constraint vì
    # unique key không trừ PURGED_AT; giờ phải nạp lại thành công trên
    # đúng bản nạp cũ, không tạo bản nạp mới.
    from datetime import datetime as _dt

    with engine.begin() as conn:
        conn.execute(delete(recon_excel_row).where(recon_excel_row.c.LOAD_ID == load_id))
        conn.execute(update(recon_excel_load).where(recon_excel_load.c.ID == load_id).values(PURGED_AT=_dt.now()))

    load_res_3 = load_excel_to_temp(
        op_ctx,
        file_id=file_id,
        template_id=template_id,
        template_version=template_version,
    )
    assert load_res_3.ok is True
    assert load_res_3.data["load_id"] == load_id
    assert load_res_3.data["is_reused"] is False
    assert load_res_3.data["rows_valid"] == 200

    with engine.connect() as conn:
        row_cnt_reload = conn.scalar(
            select(func.count()).select_from(recon_excel_row).where(recon_excel_row.c.LOAD_ID == load_id)
        )
        assert row_cnt_reload == 200
        load_rec_reload = (
            conn.execute(select(recon_excel_load).where(recon_excel_load.c.ID == load_id)).mappings().one()
        )
        assert load_rec_reload["PURGED_AT"] is None


def test_excel_load_reuses_same_content_under_new_file_id(op_ctx: Ctx, owner_ctx: Ctx) -> None:
    """Task 18 bước 1: cùng nội dung upload 2 lần (2 FILE_ID) chỉ có 1 bản nạp.

    UQ mới trên FILE_SET_HASH nên lần nạp thứ hai dùng lại bản nạp đầu.
    """
    tmpl_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    config = TemplateConfig.model_validate(json.loads(tmpl_path.read_text(encoding="utf-8")))
    save_res = save_draft_template(owner_ctx, code="DTP_LOAD_TEST", name="Template nạp test", config=config)
    assert save_res.ok is True
    template_id = save_res.data["id"]
    template_version = save_res.data["current_version"]

    excel_path = Path("samples/dtp_sample_200.xlsx")
    content = excel_path.read_bytes()
    up1 = upload_file(op_ctx, filename="dtp_a.xlsx", content=content)
    up2 = upload_file(op_ctx, filename="dtp_b.xlsx", content=content)
    assert up1.ok is True and up2.ok is True
    assert up1.data["id"] != up2.data["id"]

    load1 = load_excel_to_temp(
        op_ctx, file_id=up1.data["id"], template_id=template_id, template_version=template_version
    )
    assert load1.ok is True
    load2 = load_excel_to_temp(
        op_ctx, file_id=up2.data["id"], template_id=template_id, template_version=template_version
    )
    assert load2.ok is True
    assert load2.data["load_id"] == load1.data["load_id"]
    assert load2.data["is_reused"] is True
