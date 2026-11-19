"""Unit tests for Mail Template Studio Page & Callbacks."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata
from app.services.mail_template_studio import create_mail_template
from app.ui.pages.mail_template_studio import (
    handle_property_change,
    handle_validate,
    layout,
    render_canvas,
    sync_properties_panel,
    update_tokens_container,
)
from tests.conftest import seed_perm_basics


@pytest.fixture(autouse=True)
def isolated_page_db(tmp_path, monkeypatch):
    """Cách ly database hoàn toàn trên tmp_path."""
    db_file = tmp_path / "studio_page_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine, assignments={1: ["ADMIN"], 2: ["VIEWER"]})

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


def test_layout_admin_logged_in(admin_ctx, monkeypatch):
    monkeypatch.setattr("app.ui.pages.mail_template_studio.get_current_ctx", lambda: admin_ctx)
    create_mail_template(admin_ctx, "TMPL_LAYOUT_TEST", "Mẫu kiểm tra layout", "BATCH_RUN_COMPLETED")

    page_component = layout()
    assert page_component is not None
    # Component chứa dcc.Store mail-studio-state
    children = getattr(page_component, "children", [])
    has_store = any(getattr(c, "id", None) == "mail-studio-state" for c in children)
    assert has_store


def test_layout_viewer_forbidden(viewer_ctx, monkeypatch):
    monkeypatch.setattr("app.ui.pages.mail_template_studio.get_current_ctx", lambda: viewer_ctx)
    page_component = layout()
    assert page_component is not None
    # Khi không có quyền, render alert/redirect
    children = getattr(page_component, "children", [])
    has_redirect = any(getattr(c, "id", None) == "mail-studio-forbidden-loc" for c in children)
    assert has_redirect


def test_render_canvas_and_sync_properties_callback(admin_ctx, monkeypatch):
    monkeypatch.setattr("app.ui.pages.mail_template_studio.get_current_ctx", lambda: admin_ctx)
    created = create_mail_template(admin_ctx, "TMPL_RENDER", "Mẫu render", "BATCH_RUN_COMPLETED").data
    tmpl_id = created["template"]["id"]

    state = {
        "template_id": tmpl_id,
        "selected_block_id": 1,
        "scenario": "success",
        "device_mode": "desktop",
        "view_mode": "edit",
        "design_json": created["current_version"]["design_json"],
    }

    canvas_children, style, wrapper_style = render_canvas(state)
    assert isinstance(canvas_children, list) and len(canvas_children) > 0
    assert style["maxWidth"] == "600px"
    assert "backgroundColor" in wrapper_style

    props = sync_properties_panel(1, state)
    assert props[0].startswith("Thuộc tính:")

    # Test cập nhật thuộc tính
    updated_state = handle_property_change(
        "Nội dung đã sửa",
        "links.result",
        5,
        ["name", "status"],
        16,
        18,
        18,
        22,
        22,
        "#111827",
        "#f3f4f6",
        "center",
        "always",
        True,
        "dot",
        "#10b981",
        "round",
        "",
        "round",
        "full",
        "target_only",
        state,
    )
    b0 = updated_state["design_json"]["blocks"][0]
    assert b0["text"] == "Nội dung đã sửa"
    assert b0["size"] == 16
    assert b0["has_indicator"] is True
    assert b0["indicator_color"] == "#10b981"
    assert b0["pad_top"] == 18
    assert b0["pad_left"] == 22
    assert b0["button_shape"] == "round"
    assert b0["button_width"] == "full"
    assert b0["table_scope"] == "target_only"


def test_handle_validate_callback(admin_ctx, monkeypatch):
    monkeypatch.setattr("app.ui.pages.mail_template_studio.get_current_ctx", lambda: admin_ctx)
    created = create_mail_template(admin_ctx, "TMPL_VAL_CB", "Mẫu val cb", "BATCH_RUN_COMPLETED").data
    tmpl_id = created["template"]["id"]

    state = {
        "template_id": tmpl_id,
        "subject": "Tiêu đề hợp lệ {{batch.name}}",
        "design_json": created["current_version"]["design_json"],
    }

    opened, content = handle_validate(1, state)
    assert opened is True
    assert content is not None


def test_update_tokens_container(admin_ctx, monkeypatch):
    monkeypatch.setattr("app.ui.pages.mail_template_studio.get_current_ctx", lambda: admin_ctx)
    created = create_mail_template(admin_ctx, "TMPL_TOKENS", "Mẫu tokens", "GENERAL_EXPORT").data
    tmpl_id = created["template"]["id"]

    tokens_div = update_tokens_container({"template_id": tmpl_id})
    assert tokens_div is not None
    # Biến GENERAL_EXPORT phải sinh badges
    children = getattr(tokens_div, "children", [])
    assert len(children) > 0


def test_handle_drag_reorder_and_canvas_bg():
    from app.ui.pages.mail_template_studio import handle_canvas_bg_change, handle_drag_reorder

    state = {
        "selected_block_id": 1,
        "dirty": False,
        "design_json": {
            "canvasSettings": {"bgColor": "#f3f5f9"},
            "blocks": [
                {"id": 1, "type": "header", "text": "Khối 1"},
                {"id": 2, "type": "text", "text": "Khối 2"},
                {"id": 3, "type": "footer", "text": "Khối 3"},
            ],
        },
    }

    # Đổi nền canvas sang trắng tinh
    bg_st = handle_canvas_bg_change("#ffffff", state)
    assert bg_st["dirty"] is True
    assert bg_st["design_json"]["canvasSettings"]["bgColor"] == "#ffffff"

    # Kéo thả block 1 xuống vị trí block 3
    reorder_data = {"from_id": 1, "to_id": 3}
    new_st, sync_cnt = handle_drag_reorder(reorder_data, state, 1)
    new_blocks = new_st["design_json"]["blocks"]
    assert new_blocks[0]["id"] == 2
    assert new_blocks[1]["id"] == 3
    assert new_blocks[2]["id"] == 1
    assert new_st["dirty"] is True
    assert sync_cnt == 2


