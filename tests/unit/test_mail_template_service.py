"""Unit tests for Mail Template Studio Service."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata
from app.schemas.errors import ErrorCode
from app.services.mail_template_studio import (
    activate_version,
    clone_version,
    create_mail_template,
    get_active_template_for_event,
    list_mail_templates,
    save_draft_version,
)
from app.services.mail_template_studio import (
    test_send_template as exec_test_send_template,
)
from tests.conftest import seed_perm_basics


@pytest.fixture(autouse=True)
def isolated_studio_db(tmp_path, monkeypatch):
    """Cách ly database hoàn toàn trên tmp_path."""
    db_file = tmp_path / "studio_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine, assignments={1: ["ADMIN"], 2: ["VIEWER"]})

    # Mock get_recon_engine cho các modules liên quan
    monkeypatch.setattr("app.services.mail_template_studio.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.perm.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.smtp_settings.get_recon_engine", lambda: engine)
    yield engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])


@pytest.fixture
def viewer_ctx() -> Ctx:
    return Ctx(user_id=2, username="viewer", full_name="Viewer", roles=["VIEWER"])


def test_create_and_get_mail_template(admin_ctx):
    # Tạo mới template
    res = create_mail_template(
        admin_ctx,
        code="TMPL_TEST_BATCH",
        name="Mẫu chạy bộ thử nghiệm",
        event_code="BATCH_RUN_COMPLETED",
        description="Mô tả mẫu",
    )
    assert res.ok
    data = res.data
    assert data["template"]["code"] == "TMPL_TEST_BATCH"
    assert data["template"]["event_code"] == "BATCH_RUN_COMPLETED"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_no"] == 1
    assert data["versions"][0]["status"] == "DRAFT"
    assert data["current_version"]["version_no"] == 1

    # Thử tạo trùng mã CODE -> Báo lỗi DUPLICATE
    res_dup = create_mail_template(
        admin_ctx,
        code="TMPL_TEST_BATCH",
        name="Trùng mã",
        event_code="BATCH_RUN_COMPLETED",
    )
    assert not res_dup.ok
    assert res_dup.code == ErrorCode.TEMPLATE_CODE_EXISTS


def test_list_and_search_templates(admin_ctx):
    create_mail_template(admin_ctx, "TMPL_ONE", "Báo cáo doanh thu", "REPORT_EXPORT_COMPLETED")
    create_mail_template(admin_ctx, "TMPL_TWO", "Bộ chạy cuối tháng", "BATCH_RUN_COMPLETED")

    # List all
    res = list_mail_templates(admin_ctx)
    assert res.ok
    assert len(res.data) >= 2

    # Search keyword
    res_search = list_mail_templates(admin_ctx, search="doanh thu")
    assert res_search.ok
    assert len(res_search.data) == 1
    assert res_search.data[0]["code"] == "TMPL_ONE"

    # Filter by event
    res_event = list_mail_templates(admin_ctx, event_code="BATCH_RUN_COMPLETED")
    assert res_event.ok
    assert any(t["code"] == "TMPL_TWO" for t in res_event.data)


def test_save_draft_and_auto_clone_on_active(admin_ctx):
    created = create_mail_template(
        admin_ctx,
        code="TMPL_EDIT_FLOW",
        name="Mẫu kiểm tra sửa đổi",
        event_code="BATCH_RUN_COMPLETED",
    ).data
    tmpl_id = created["template"]["id"]
    v1_id = created["current_version"]["id"]

    # 1. Sửa version DRAFT: ghi đè trực tiếp
    design_v1 = dict(created["current_version"]["design_json"])
    design_v1["blocks"][0]["text"] = "Tiêu đề đã sửa v1"
    save_res = save_draft_version(
        admin_ctx,
        template_id=tmpl_id,
        version_id=v1_id,
        subject="Tiêu đề email v1 mới",
        preheader="Preheader v1",
        design_json=design_v1,
    )
    assert save_res.ok
    assert save_res.data["current_version"]["id"] == v1_id
    assert save_res.data["current_version"]["version_no"] == 1
    assert save_res.data["current_version"]["status"] == "DRAFT"

    # 2. Kích hoạt v1 thành ACTIVE
    act_res = activate_version(admin_ctx, template_id=tmpl_id, version_id=v1_id)
    assert act_res.ok
    assert act_res.data["current_version"]["status"] == "ACTIVE"
    assert act_res.data["template"]["current_active_version_id"] == v1_id

    # 3. Sửa version đang ACTIVE: tự động clone thành v2 DRAFT!
    design_v2 = dict(design_v1)
    design_v2["blocks"][0]["text"] = "Tiêu đề chuẩn bị cho v2"
    clone_draft_res = save_draft_version(
        admin_ctx,
        template_id=tmpl_id,
        version_id=v1_id,  # Lưu trên bản Active
        subject="Tiêu đề dự thảo v2",
        preheader="Preheader v2",
        design_json=design_v2,
    )
    assert clone_draft_res.ok
    v2_data = clone_draft_res.data
    assert v2_data["current_version"]["version_no"] == 2
    assert v2_data["current_version"]["status"] == "DRAFT"
    # Bản v1 vẫn giữ trạng thái ACTIVE
    v1_check = [v for v in v2_data["versions"] if v["version_no"] == 1][0]
    assert v1_check["status"] == "ACTIVE"
    assert v2_data["template"]["current_active_version_id"] == v1_id


def test_activate_version_archives_previous(admin_ctx):
    created = create_mail_template(
        admin_ctx,
        code="TMPL_ARCHIVE_FLOW",
        name="Mẫu test archive",
        event_code="BATCH_RUN_COMPLETED",
    ).data
    tmpl_id = created["template"]["id"]
    v1_id = created["current_version"]["id"]

    # Kích hoạt v1
    activate_version(admin_ctx, tmpl_id, v1_id)

    # Nhân bản thành v2
    v2_data = clone_version(admin_ctx, tmpl_id, v1_id).data
    v2_id = v2_data["current_version"]["id"]

    # Kích hoạt v2
    act_v2_res = activate_version(admin_ctx, tmpl_id, v2_id)
    assert act_v2_res.ok
    detail = act_v2_res.data

    # v2 là ACTIVE, v1 chuyển sang ARCHIVED
    v_map = {v["version_no"]: v["status"] for v in detail["versions"]}
    assert v_map[2] == "ACTIVE"
    assert v_map[1] == "ARCHIVED"
    assert detail["template"]["current_active_version_id"] == v2_id


def test_activate_version_fails_on_validation_errors(admin_ctx):
    created = create_mail_template(
        admin_ctx,
        code="TMPL_INVALID",
        name="Mẫu lỗi",
        event_code="BATCH_RUN_COMPLETED",
    ).data
    tmpl_id = created["template"]["id"]
    v1_id = created["current_version"]["id"]

    # Tạo thiết kế lỗi (không có block nào)
    save_res = save_draft_version(
        admin_ctx,
        template_id=tmpl_id,
        version_id=v1_id,
        subject="",  # Tiêu đề rỗng
        preheader="",
        design_json={"blocks": []},
    )
    assert save_res.ok
    assert len(save_res.data["current_version"]["validation_errors"]) > 0

    # Kích hoạt phải bị từ chối
    act_res = activate_version(admin_ctx, tmpl_id, v1_id)
    assert not act_res.ok
    assert act_res.code == ErrorCode.VALIDATION_ERROR


def test_test_send_template_safe_mock(admin_ctx):
    created = create_mail_template(
        admin_ctx,
        code="TMPL_TEST_SEND",
        name="Mẫu gửi thử",
        event_code="BATCH_RUN_COMPLETED",
    ).data
    tmpl_id = created["template"]["id"]
    v1_id = created["current_version"]["id"]

    with (
        patch("app.services.mail_template_studio.get_smtp_config_internal") as mock_smtp,
        patch("app.services.mail_template_studio.send_smtp_email") as mock_send,
    ):
        mock_smtp.return_value = {
            "host": "smtp.test.local",
            "port": 587,
            "security": "STARTTLS",
            "username": "user",
            "password": "pw",
            "from_email": "noreply@test.local",
            "from_name": "ReconHub",
        }
        mock_send.return_value = {"ok": True}

        res = exec_test_send_template(
            admin_ctx,
            template_id=tmpl_id,
            version_id=v1_id,
            recipient_email="tester@test.local",
            scenario="error",
        )
        assert res.ok
        assert res.data["recipient"] == "tester@test.local"
        assert res.data["subject"].startswith("[TEST] ")
        mock_send.assert_called_once()


def test_get_active_template_for_event_and_fallback(admin_ctx):
    # Sự kiện chưa có template trong DB -> trả về fallback default
    fallback = get_active_template_for_event("GENERAL_EXPORT")
    assert fallback is not None
    assert fallback["code"] == "TMPL_GENERAL_EXPORT_FALLBACK"
    assert fallback["design_json"] is not None

    # Tạo và kích hoạt template mới cho GENERAL_EXPORT
    created = create_mail_template(
        admin_ctx,
        code="TMPL_MY_GEN",
        name="Mẫu chung tùy biến",
        event_code="GENERAL_EXPORT",
    ).data
    tmpl_id = created["template"]["id"]
    v1_id = created["current_version"]["id"]
    activate_version(admin_ctx, tmpl_id, v1_id)

    # Lấy lại -> trả về chính template vừa kích hoạt
    active = get_active_template_for_event("GENERAL_EXPORT")
    assert active["code"] == "TMPL_MY_GEN"
    assert active["version_id"] == v1_id


def test_unauthorized_user_forbidden(viewer_ctx):
    # Viewer không có quyền menu mail_template_studio -> FORBIDDEN
    res = list_mail_templates(viewer_ctx)
    assert not res.ok
    assert res.code == ErrorCode.FORBIDDEN
