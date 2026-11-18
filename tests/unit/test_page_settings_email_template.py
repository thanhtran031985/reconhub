"""Unit tests for email template tab and callbacks on /settings page."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata
from app.ui.pages.settings import (
    handle_template_editor_events,
    handle_template_nav_click,
    handle_template_preview,
    render_fn_nav_list,
    render_tmpl_header_info,
    render_token_badges,
)
from tests.conftest import seed_perm_basics


@pytest.fixture(autouse=True)
def isolated_tmpl_page_db(tmp_path, monkeypatch):
    db_file = tmp_path / "page_email_tmpl_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine, assignments={1: ["ADMIN"]})
    monkeypatch.setattr("app.services.email_template.get_recon_engine", lambda: engine)
    yield engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin_user", full_name="Admin User", roles=["ADMIN"])


def test_render_token_badges():
    tokens = [
        {"token": "{{user_name}}", "label": "Tên người dùng", "example": "admin"},
        {"token": "{{items_count}}", "label": "Số lượng", "example": "10"},
    ]
    node = render_token_badges(tokens)
    assert node is not None
    text = str(node)
    assert "{{user_name}}" in text
    assert "{{items_count}}" in text


def test_render_token_badges_empty():
    node = render_token_badges([])
    assert "Không có thẻ dữ liệu" in str(node)


def test_render_fn_nav_list():
    links = render_fn_nav_list("GENERAL_EXPORT")
    assert len(links) >= 4
    text = str(links)
    assert "GENERAL_EXPORT" in text
    assert "TEMPLATE_LIST_EXPORT" in text


def test_render_tmpl_header_info():
    tmpl = {"function_code": "GENERAL_EXPORT", "name": "Mẫu chung", "is_fallback": True}
    meta = {"label": "Mẫu mặc định chung (Fallback)"}
    node = render_tmpl_header_info(tmpl, meta)
    assert node is not None
    text = str(node)
    assert "Mẫu mặc định chung (Fallback)" in text
    assert "Fallback" in text


def test_handle_template_nav_click():
    with patch("dash.callback_context") as mock_ctx:
        mock_ctx.triggered = [{"prop_id": '{"code":"USER_LIST_EXPORT","type":"settings-tmpl-fn-nav"}.n_clicks'}]
        mock_ctx.triggered_id = {"type": "settings-tmpl-fn-nav", "code": "USER_LIST_EXPORT"}
        new_code = handle_template_nav_click([1], "GENERAL_EXPORT")
        assert new_code == "USER_LIST_EXPORT"


def test_handle_template_editor_events_initial_load():
    with patch("dash.callback_context") as mock_ctx:
        mock_ctx.triggered_id = "settings-tmpl-selected-fn"
        nav_list, header_info, subj, body, badges, alert = handle_template_editor_events(
            fn_code="GENERAL_EXPORT",
            save_clicks=None,
            reset_clicks=None,
            current_subject=None,
            current_body=None,
        )
        assert len(nav_list) >= 4
        assert header_info is not None
        assert "ReconHub" in subj
        assert "<div" in body
        assert badges is not None
        assert alert is None


def test_handle_template_preview():
    subject_val = "Thông báo [{{items_count}} mục]"
    body_val = "<p>Gửi bởi {{user_name}}</p>"
    preview_subj, preview_body = handle_template_preview(
        subject_val=subject_val,
        body_val=body_val,
        fn_code="GENERAL_EXPORT",
    )
    assert "Thông báo [20 mục]" == preview_subj
    assert "<p>Gửi bởi admin</p>" in preview_body


def test_handle_template_editor_events_save_and_reset(admin_ctx):
    with patch("app.ui.pages.settings.get_current_ctx", return_value=admin_ctx):
        with patch("dash.callback_context") as mock_ctx:
            # Click Save
            mock_ctx.triggered_id = "settings-tmpl-save-btn"
            custom_subj = "Test Subject Custom {{items_count}}"
            custom_body = "<p>Custom Body {{user_name}}</p>"
            navs, hdr, subj, body, _badges, alert = handle_template_editor_events(
                fn_code="GENERAL_EXPORT",
                save_clicks=1,
                reset_clicks=None,
                current_subject=custom_subj,
                current_body=custom_body,
            )
            assert subj == custom_subj
            assert body == custom_body
            assert "Đã lưu mẫu email" in str(alert)

            # Click Reset
            mock_ctx.triggered_id = "settings-tmpl-reset-btn"
            r_navs, r_hdr, r_subj, r_body, _r_badges, r_alert = handle_template_editor_events(
                fn_code="GENERAL_EXPORT",
                save_clicks=None,
                reset_clicks=1,
                current_subject=custom_subj,
                current_body=custom_body,
            )
            assert "ReconHub - Danh sách {{module_name}}" in r_subj
            assert "Đã khôi phục mẫu mặc định" in str(r_alert)
