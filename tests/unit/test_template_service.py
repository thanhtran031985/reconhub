from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_run, recon_template_version
from app.schemas.errors import ErrorCode
from app.schemas.template_config import TemplateConfig
from app.services.template import (
    activate_version,
    archive_template,
    clone_template,
    get_template,
    save_draft_template,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_template.db"
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
def owner_ctx() -> Ctx:
    return Ctx(user_id=2, username="owner", full_name="Template Owner", roles=[Role.TEMPLATE_OWNER])


@pytest.fixture
def viewer_ctx() -> Ctx:
    return Ctx(user_id=4, username="viewer", full_name="Viewer", roles=[Role.VIEWER])


def test_save_draft_creates_new_template_and_version(test_db, owner_ctx) -> None:
    cfg = get_sample_config()
    res = save_draft_template(
        owner_ctx,
        code="DTP_HD",
        name="Hóa đơn DTP",
        description="Mô tả template DTP",
        config=cfg,
        data_source_id=None,
    )
    assert res.ok is True
    assert res.data["code"] == "DTP_HD"
    assert res.data["current_version"] == 1
    assert res.data["status"] == "DRAFT"

    # Đọc lại bằng get_template
    get_res = get_template(owner_ctx, template_id=res.data["id"])
    assert get_res.ok is True
    assert get_res.data["code"] == "DTP_HD"
    assert get_res.data["config"]["schema_version"] == 1


def test_viewer_cannot_save_draft(test_db, viewer_ctx) -> None:
    cfg = get_sample_config()
    res = save_draft_template(
        viewer_ctx,
        code="DTP_HD",
        name="Hóa đơn DTP",
        config=cfg,
    )
    assert res.ok is False
    assert res.code == ErrorCode.FORBIDDEN


def test_save_draft_overwrites_when_draft_has_no_runs(test_db, owner_ctx) -> None:
    cfg = get_sample_config()
    # Tạo v1
    res1 = save_draft_template(owner_ctx, code="DTP_HD", name="Tên 1", config=cfg)
    tmpl_id = res1.data["id"]
    row_ver = res1.data["row_version"]

    # Sửa tên và lưu tiếp khi chưa có run -> vẫn ở v1
    res2 = save_draft_template(
        owner_ctx,
        code="DTP_HD",
        name="Tên 2 Đã Sửa",
        config=cfg,
        row_version=row_ver,
    )
    assert res2.ok is True
    assert res2.data["id"] == tmpl_id
    assert res2.data["current_version"] == 1
    assert res2.data["name"] == "Tên 2 Đã Sửa"

    # Kiểm tra chỉ có đúng 1 version trong DB
    with test_db.connect() as conn:
        vers = (
            conn.execute(select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == tmpl_id))
            .mappings()
            .all()
        )
        assert len(vers) == 1


def test_save_draft_creates_new_version_when_version_has_runs(test_db, owner_ctx) -> None:
    cfg = get_sample_config()
    res1 = save_draft_template(owner_ctx, code="DTP_HD", name="Tên 1", config=cfg)
    tmpl_id = res1.data["id"]

    # Giả lập đã có 1 run ghi nhận ở version 1
    with test_db.begin() as conn:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE",
                DATA_SOURCE_ID=1,
                P_FROM=now,
                P_TO=now,
                CREATED_BY="operator",
                CREATED_AT=now,
            )
        )

    # Lưu nháp tiếp -> tạo version 2
    res2 = save_draft_template(
        owner_ctx,
        code="DTP_HD",
        name="Tên 1 Bản 2",
        config=cfg,
        row_version=res1.data["row_version"],
    )
    assert res2.ok is True
    assert res2.data["current_version"] == 2

    # Kiểm tra trong DB có cả v1 và v2
    with test_db.connect() as conn:
        vers = (
            conn.execute(select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == tmpl_id))
            .mappings()
            .all()
        )
        assert len(vers) == 2


def test_save_draft_stale_data_detection(test_db, owner_ctx) -> None:
    cfg = get_sample_config()
    res1 = save_draft_template(owner_ctx, code="DTP_HD", name="Tên 1", config=cfg)

    # Truyền row_version cũ không khớp
    res_stale = save_draft_template(
        owner_ctx,
        code="DTP_HD",
        name="Tên 1 Bản Sửa Cũ",
        config=cfg,
        row_version=res1.data["row_version"] - 1,
    )
    assert res_stale.ok is False
    assert res_stale.code == ErrorCode.STALE_DATA


def test_activate_version(test_db, admin_ctx) -> None:
    cfg = get_sample_config()
    res1 = save_draft_template(admin_ctx, code="DTP_HD", name="Tên 1", config=cfg)
    tmpl_id = res1.data["id"]

    # Không thể activate nếu DRY_RUN_OK chưa = 'Y'
    act_fail = activate_version(admin_ctx, template_id=tmpl_id, version=1)
    assert act_fail.ok is False
    assert act_fail.code == ErrorCode.DRY_RUN_REQUIRED

    # Cho phép override dry run hoặc đánh dấu DRY_RUN_OK='Y'
    act_ok = activate_version(admin_ctx, template_id=tmpl_id, version=1, dry_run_override=True)
    assert act_ok.ok is True

    # Kiểm tra trạng thái đã chuyển sang ACTIVE
    get_res = get_template(admin_ctx, template_id=tmpl_id)
    assert get_res.ok is True
    assert get_res.data["status"] == "ACTIVE"


def test_clone_and_archive_template(test_db, owner_ctx) -> None:
    cfg = get_sample_config()
    res1 = save_draft_template(owner_ctx, code="DTP_HD", name="Hóa đơn DTP", config=cfg)
    tmpl_id = res1.data["id"]

    # Clone sang mã mới
    clone_res = clone_template(owner_ctx, template_id=tmpl_id, new_code="DTP_HD_CLONE", new_name="Hóa đơn DTP Clone")
    assert clone_res.ok is True
    assert clone_res.data["code"] == "DTP_HD_CLONE"
    assert clone_res.data["current_version"] == 1

    # Thử clone trùng mã -> lỗi TEMPLATE_CODE_EXISTS
    dup_res = clone_template(owner_ctx, template_id=tmpl_id, new_code="DTP_HD_CLONE", new_name="Lỗi trùng")
    assert dup_res.ok is False
    assert dup_res.code == ErrorCode.TEMPLATE_CODE_EXISTS

    # Archive template gốc
    arch_res = archive_template(owner_ctx, template_id=tmpl_id)
    assert arch_res.ok is True

    get_arch = get_template(owner_ctx, template_id=tmpl_id)
    assert get_arch.data["status"] == "ARCHIVED"
