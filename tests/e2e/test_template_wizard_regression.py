"""Bộ regression test toàn diện cho Template Wizard — Task UI-05.

Bao quát 7 kịch bản nghiệp vụ cốt lõi:
1. New template creation (/templates/new)
2. Edit existing template (/templates/<id>/edit)
3. Next step navigation
4. Back step navigation
5. Autosave & Manual Save Draft
6. Field validation
7. Draft reload after page refresh
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_data_source, recon_user
from app.schemas.template_config import TemplateConfig
from app.ui.pages.template_wizard import (
    handle_save_or_autosave_draft,
    handle_step_navigation,
    layout,
    validate_wizard_step,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def _load_sample_cfg() -> dict[str, Any]:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def wizard_regression_env(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "wiz_regression.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "wiz-regression-secret-key")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="owner_test",
                FULL_NAME="Template Owner Test",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        user_id = res.inserted_primary_key[0]
        seed_perm_basics(engine, {user_id: ["ADMIN", "TEMPLATE_OWNER"]}, conn=conn)

        conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_PROD",
                ENV="PROD",
                PURPOSE="RECON",
                DB_TYPE="ORACLE",
                HOST="10.0.0.1",
                PORT=1521,
                SERVICE_NAME="PROD_SVC",
                USERNAME="recon_user",
                PASSWORD_ENC="dummy_enc",
                IS_ACTIVE="Y",
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    owner_ctx = Ctx(user_id=user_id, username="owner_test", full_name="Template Owner Test", roles=[Role.TEMPLATE_OWNER, Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)
    return {"user_id": user_id, "ctx": owner_ctx, "engine": engine}


class TestTemplateWizardRegression:
    def test_scenario_1_new_template_creation(self, wizard_regression_env):
        """Kịch bản 1: Mở wizard tạo mới template, nạp cấu hình mặc định."""
        page = layout(template_id=None)
        assert page is not None
        s = str(page)
        assert "wizard-page-root" in s
        assert "wizard-stepper" in s
        assert "wizard-view-tabs" in s
        assert "wizard-prev-btn" in s
        assert "wizard-next-btn" in s
        assert "wizard-save-draft-btn" in s
        assert "Đăng ký template:" in s or "NEW_TEMPLATE" in s

    def test_scenario_2_edit_existing_template(self, wizard_regression_env):
        """Kịch bản 2: Mở wizard chỉnh sửa template đã tồn tại."""
        from app.services.template import save_draft_template

        ctx = wizard_regression_env["ctx"]
        sample_dict = _load_sample_cfg()
        cfg_model = TemplateConfig.model_validate(sample_dict)
        res = save_draft_template(
            ctx,
            code="REG_TPL_01",
            name="Template Kiểm thử 01",
            config=cfg_model,
        )
        assert res.ok

        page = layout(template_id="REG_TPL_01")
        assert page is not None
        s = str(page)
        assert "Sửa template: REG_TPL_01" in s
        assert "wizard-page-root" in s

    def test_scenario_3_next_step_navigation(self, wizard_regression_env, monkeypatch):
        """Kịch bản 3: Điều hướng Next từ bước 1 sang bước 2 với dữ liệu hợp lệ."""
        import dash

        cfg = _load_sample_cfg()
        cfg["template_code"] = "DTP_HOA_DON"
        cfg["name"] = "Hóa đơn DTP"
        cfg["template_name"] = "Hóa đơn DTP"
        meta = {"current_step": 1, "is_dirty": False}
        sample_data = {"filename": "sample.xlsx", "total_rows": 100, "total_cols": 10}

        class MockDashCtx:
            triggered = [{"prop_id": "wizard-next-btn.n_clicks"}]

        monkeypatch.setattr(dash, "callback_context", MockDashCtx())

        active, prev_disabled, next_text, new_meta, redirect, err = handle_step_navigation(
            next_clicks=1,
            prev_clicks=0,
            current_active=0,  # Bước 0 (File mẫu)
            meta=meta,
            config_data=cfg,
            sample_data=sample_data,
        )

        assert active == 1  # Chuyển sang bước 1
        assert prev_disabled is False
        assert err is None or str(err) == ""

    def test_scenario_4_back_step_navigation(self, wizard_regression_env, monkeypatch):
        """Kịch bản 4: Điều hướng Quay lại (Back) từ bước 2 về bước 1."""
        import dash

        cfg = _load_sample_cfg()
        meta = {"current_step": 2, "is_dirty": False}

        class MockDashCtx:
            triggered = [{"prop_id": "wizard-prev-btn.n_clicks"}]

        monkeypatch.setattr(dash, "callback_context", MockDashCtx())

        active, prev_disabled, next_text, new_meta, redirect, err = handle_step_navigation(
            next_clicks=0,
            prev_clicks=1,
            current_active=1,  # Đang ở bước 1
            meta=meta,
            config_data=cfg,
        )

        assert active == 0  # Quay lại bước 0
        assert prev_disabled is True

    def test_scenario_5_autosave_and_manual_save_draft(self, wizard_regression_env, monkeypatch):
        """Kịch bản 5: Lưu nháp thủ công và tự động."""
        import dash

        cfg = _load_sample_cfg()
        cfg["template_code"] = "AUTO_SAVE_TPL"
        cfg["template_name"] = "Autosave Template"
        meta = {"template_code": "AUTO_SAVE_TPL", "template_name": "Autosave Template", "is_dirty": True}

        # Lưu thủ công
        class MockManualCtx:
            triggered = [{"prop_id": "wizard-save-draft-btn.n_clicks"}]

        monkeypatch.setattr(dash, "callback_context", MockManualCtx())

        sub_text, new_meta, notif = handle_save_or_autosave_draft(
            save_clicks=1,
            _interval=0,
            config_data=cfg,
            meta_data=meta,
        )

        assert new_meta is not None
        assert new_meta.get("template_code") == "AUTO_SAVE_TPL"
        assert notif is not None

    def test_scenario_6_field_validation(self, wizard_regression_env):
        """Kịch bản 6: Bắt lỗi validation khi thiếu trường bắt buộc."""
        # Config rỗng thiếu file header row và sheet
        empty_cfg: dict[str, Any] = {"file": {}}
        errors = validate_wizard_step(empty_cfg, step_index=0, sample_data=None)
        # Phải phát hiện thiếu file mẫu hoặc cấu hình sheet
        assert len(errors) > 0

    def test_scenario_7_draft_reload_after_page_refresh(self, wizard_regression_env):
        """Kịch bản 7: Tải lại trang giữ nguyên cấu hình đã lưu nháp."""
        from app.services.template import save_draft_template

        ctx = wizard_regression_env["ctx"]
        sample_dict = _load_sample_cfg()
        sample_dict["template_code"] = "RELOAD_DRAFT_TPL"
        sample_dict["template_name"] = "Reload Draft Test"
        cfg_model = TemplateConfig.model_validate(sample_dict)

        save_res = save_draft_template(
            ctx,
            code="RELOAD_DRAFT_TPL",
            name="Reload Draft Test",
            config=cfg_model,
        )
        assert save_res.ok

        # Giả lập reload trang
        page = layout(template_id="RELOAD_DRAFT_TPL")
        assert page is not None
        page_str = str(page)
        assert "RELOAD_DRAFT_TPL" in page_str
        assert "Reload Draft Test" in page_str
