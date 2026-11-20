from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.core.context import Ctx, Role
from app.schemas.errors import ServiceResult
from app.ui.pages.history import (
    render_filter_bar,
    sync_history_profile_options,
    update_history_table,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def test_render_filter_bar_has_profile_select():
    fb = render_filter_bar([], [])
    fb_str = str(fb)
    assert "history-filter-profile" in fb_str
    assert "Profile" in fb_str


def test_sync_history_profile_options_all():
    options, val = sync_history_profile_options("ALL")
    assert val == "ALL"
    assert options == [{"label": "Tất cả", "value": "ALL"}]


def test_sync_history_profile_options_valid_template(monkeypatch):
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    mock_get_tmpl = MagicMock(
        return_value=ServiceResult(
            ok=True,
            data={"id": 1, "code": "DTP", "config": cfg},
        )
    )
    monkeypatch.setattr("app.services.template.get_template", mock_get_tmpl)
    monkeypatch.setattr(
        "app.ui.pages.history.get_current_ctx",
        lambda: Ctx(user_id=1, username="test_op", full_name="Op", roles=[Role.OPERATOR]),
    )

    options, val = sync_history_profile_options("1")
    assert val == "ALL"
    assert len(options) > 1
    codes = [opt["value"] for opt in options]
    assert "ALL" in codes
    assert "BY_INVOICE" in codes
    assert "BY_DAY_POINT" in codes


def test_update_history_table_with_profile_filter(monkeypatch):
    captured_filter = {}

    def mock_list_runs(ctx, filter_obj):
        captured_filter["profile_code"] = filter_obj.profile_code
        captured_filter["template_id"] = filter_obj.template_id
        return ServiceResult(
            ok=True,
            data={"items": [], "total": 0, "total_pages": 1},
        )

    monkeypatch.setattr("app.ui.pages.history.list_runs", mock_list_runs)
    monkeypatch.setattr(
        "app.ui.pages.history.get_current_ctx",
        lambda: Ctx(user_id=1, username="test_admin", full_name="Admin", roles=[Role.ADMIN]),
    )

    update_history_table(
        tpl_val="1",
        chk_val="ALL",
        purge_val="ALL",
        usr_val="ALL",
        file_val="",
        date_range_or_refresh=None,
        page_or_selected=1,
        refresh_val=0,
        selected_data=[],
        batch_val="ALL",
        profile_val="BY_INVOICE",
    )

    assert captured_filter.get("template_id") == 1
    assert captured_filter.get("profile_code") == "BY_INVOICE"
