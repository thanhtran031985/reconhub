from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import dash

from app.core.context import Ctx, Role
from app.schemas.errors import ServiceResult
from app.ui.pages.new_run import (
    handle_execute_run,
    handle_progress_tick,
    render_sql_preview_section,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_template_info():
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return {"id": 1, "code": "DTP", "version": 1, "config": cfg}


def test_render_sql_preview_tabs_for_multi_profile():
    tmpl_info = get_template_info()
    # Template DTP có các profile: BY_INVOICE, BY_DAY_POINT, BY_LINE
    profiles = ["BY_INVOICE", "BY_DAY_POINT"]
    params = {"p_from": "2026-01-01 00:00:00", "p_to": "2026-01-02 23:59:59"}

    ui = render_sql_preview_section(tmpl_info, profile_code=profiles, params=params)
    ui_str = str(ui)

    assert "3. Câu lệnh SQL đối soát DB" in ui_str
    assert "2 Profile" in ui_str
    # Có Tabs render cho các profile
    assert "BY_INVOICE" in ui_str
    assert "BY_DAY_POINT" in ui_str


def test_handle_execute_run_multi_profile(monkeypatch):
    tmpl_info = get_template_info()
    file_info = {"id": 10, "name": "sample.xlsx"}

    mock_create_multi = MagicMock(
        return_value=ServiceResult(
            ok=True,
            data={"run_ids": [101, 102], "count": 2, "status": "QUEUED"},
        )
    )
    monkeypatch.setattr("app.ui.pages.new_run.create_multi_run", mock_create_multi)
    monkeypatch.setattr(
        "app.ui.pages.new_run.get_current_ctx",
        lambda: Ctx(user_id=1, username="test_op", full_name="Op", roles=[Role.OPERATOR]),
    )

    # Giả lập callback context
    mock_ctx = MagicMock()
    mock_ctx.triggered = [{"prop_id": "new-run-submit-btn.n_clicks", "value": 1}]
    monkeypatch.setattr(dash, "callback_context", mock_ctx)

    modal_open, new_state, redirect_val, exec_ui = handle_execute_run(
        exec_clicks=1,
        confirm_clicks=None,
        cancel_clicks=None,
        datasource_id="1",
        template_data=tmpl_info,
        file_data=file_info,
        p_from_str="2026-01-01 00:00:00",
        p_to_str="2026-01-02 23:59:59",
        profile_code=["BY_INVOICE", "BY_DAY_POINT"],
        p_org_val="BDP",
        apply_excel_time=False,
    )

    assert modal_open is False
    assert new_state["is_running"] is True
    assert new_state["is_multi"] is True
    assert new_state["run_ids"] == [101, 102]
    mock_create_multi.assert_called_once()
    assert mock_create_multi.call_args[0][1].profile_codes == ["BY_INVOICE", "BY_DAY_POINT"]


def test_handle_progress_tick_multi_profile_redirect(monkeypatch):
    state = {
        "is_running": True,
        "is_multi": True,
        "run_ids": [101, 102],
        "stage": 1,
        "pct": 10,
    }

    # Giả lập fallback unit test (khi pct đạt 100)
    state_done = {**state, "pct": 100}
    ui, next_state, redirect_path = handle_progress_tick(1, state_done)

    assert redirect_path == "/history"
    assert next_state["is_running"] is False
