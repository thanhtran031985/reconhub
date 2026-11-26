"""Tests cho Bước 4 của task 104-layout-cache-perf: Client-side SWR & Fingerprint."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import dash
from dash import dcc

from app.core.context import Ctx
from app.schemas.errors import ServiceResult


def _find_by_id(comp, target_id: str):
    if getattr(comp, "id", None) == target_id:
        return comp
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            found = _find_by_id(child, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


def test_list_pages_use_session_storage_stores(monkeypatch) -> None:
    """Các màn danh sách (/templates, /batches, /report-runs) phải dùng dcc.Store session."""
    from app.services.perm import clear_perm_cache
    from app.ui.pages import batch_defs, report_runs, templates

    clear_perm_cache()
    admin = Ctx(user_id=1, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())

    monkeypatch.setattr(templates, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(templates, "page_gate", lambda ctx, code: None)
    t_store = _find_by_id(templates.layout(), "tmpl-store-list")
    assert isinstance(t_store, dcc.Store)
    assert getattr(t_store, "storage_type", None) == "session"

    monkeypatch.setattr(batch_defs, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(batch_defs, "page_gate", lambda ctx, code: None)
    b_store = _find_by_id(batch_defs.layout(), "bdef-store-list")
    assert isinstance(b_store, dcc.Store)
    assert getattr(b_store, "storage_type", None) == "session"

    monkeypatch.setattr(report_runs, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(report_runs, "page_gate", lambda ctx, code: None)
    monkeypatch.setattr(report_runs, "is_admin", lambda ctx, engine=None: True)
    r_store = _find_by_id(report_runs.layout(), "report-runs-swr-store")
    assert isinstance(r_store, dcc.Store)
    assert getattr(r_store, "storage_type", None) == "session"


def test_templates_swr_skips_update_when_fingerprint_matches_and_updates_on_change(monkeypatch) -> None:
    from app.ui.pages import templates

    admin = Ctx(user_id=10, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
    items_v1 = [{"id": 1, "code": "T1", "name": "Mau 1", "status": "ACTIVE", "current_version": 1}]
    items_v2 = [{"id": 1, "code": "T1", "name": "Mau 1", "status": "ACTIVE", "current_version": 2}]
    current_items = [items_v1]

    monkeypatch.setattr(templates, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(templates, "list_templates", lambda ctx: ServiceResult(ok=True, data=current_items[0]))

    # Lần đầu chưa có cache → trả payload có fingerprint & user_id
    first = templates.load_templates_data(None, [], None)
    assert first is not dash.no_update
    assert first["user_id"] == 10
    assert first["items"] == items_v1
    assert first["fingerprint"]

    # Lần sau dữ liệu không đổi → trả no_update
    second = templates.load_templates_data(None, [], first)
    assert second is dash.no_update

    # User khác dùng cùng sessionStorage → không bỏ qua, phải nạp mới
    other_user = Ctx(user_id=99, username="op", full_name="Op", roles=frozenset({"OPERATOR"}), permissions=frozenset())
    monkeypatch.setattr(templates, "get_current_ctx", lambda: other_user)
    third = templates.load_templates_data(None, [], first)
    assert third is not dash.no_update
    assert third["user_id"] == 99

    # Render khi store của user khác → phải hiện skeleton thay vì lộ dữ liệu
    rendered_mismatch = templates.update_templates_table(first)
    assert "tmpl-tabulator-table" not in str(rendered_mismatch)

    # Dữ liệu đổi cùng user → cập nhật payload và fingerprint mới
    monkeypatch.setattr(templates, "get_current_ctx", lambda: admin)
    current_items[0] = items_v2
    fourth = templates.load_templates_data(None, [], first)
    assert fourth is not dash.no_update
    assert fourth["items"] == items_v2
    assert fourth["fingerprint"] != first["fingerprint"]


def test_batches_swr_skips_update_when_fingerprint_matches_and_updates_on_change(monkeypatch) -> None:
    from app.ui.pages import batch_defs

    admin = Ctx(user_id=7, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
    items_v1 = [{"id": 1, "code": "B1", "name": "Bo 1", "status": "ACTIVE", "cnt_items": 2}]
    items_v2 = [{"id": 1, "code": "B1", "name": "Bo 1", "status": "DRAFT", "cnt_items": 2}]
    current_items = [items_v1]

    monkeypatch.setattr(batch_defs, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(batch_defs, "list_batch_defs", lambda ctx: ServiceResult(ok=True, data=current_items[0]))

    first = batch_defs._load_list(None, [], None)
    assert first is not dash.no_update
    assert first["user_id"] == 7
    assert first["items"] == items_v1
    assert first["fingerprint"]

    # Fingerprint khớp → no_update
    assert batch_defs._load_list(None, [], first) is dash.no_update

    # User khác → ép cập nhật & chặn lộ dữ liệu ở _render_list
    other = Ctx(user_id=8, username="u8", full_name="U8", roles=frozenset({"VIEWER"}), permissions=frozenset())
    monkeypatch.setattr(batch_defs, "get_current_ctx", lambda: other)
    assert batch_defs._load_list(None, [], first) is not dash.no_update
    rendered_mismatch = batch_defs._render_list(first)
    assert "bdef-tabulator-table" not in str(rendered_mismatch)

    # Dữ liệu đổi → trả payload mới
    monkeypatch.setattr(batch_defs, "get_current_ctx", lambda: admin)
    current_items[0] = items_v2
    updated = batch_defs._load_list(None, [], first)
    assert updated is not dash.no_update
    assert updated["items"] == items_v2
    assert updated["fingerprint"] != first["fingerprint"]


def test_report_runs_swr_initial_load_skips_when_fingerprint_matches(monkeypatch) -> None:
    from app.ui.pages import report_runs

    admin = Ctx(user_id=5, username="admin", full_name="Admin", roles=frozenset({"ADMIN"}), permissions=frozenset())
    runs = [
        {
            "id": 11,
            "report_id": 1,
            "report_name": "Bao cao",
            "status": "DONE",
            "row_count": 100,
            "created_at": datetime(2026, 11, 25, 10, 0, 0),
            "finished_at": datetime(2026, 11, 25, 10, 0, 2),
        }
    ]
    exports: dict[int, list] = {}
    fp = report_runs._runs_fingerprint(runs, exports, 1, 1)

    monkeypatch.setattr(report_runs, "get_current_ctx", lambda: admin)
    monkeypatch.setattr(report_runs, "_load_page_data", lambda *a, **k: (runs, 1, exports))
    monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id=None))

    swr_match = {"user_id": 5, "fingerprint": fp}
    out_match = report_runs.handle_runs_refresh(
        1, "50", None, None, "all", "", "all", "all", None, None, None, None, 0, fp, swr_match
    )
    assert len(out_match) == 12
    assert all(item is dash.no_update for item in out_match)

    # Khi dữ liệu đổi (fingerprint khác) hoặc user khác → nạp lại rowData mới
    swr_stale = {"user_id": 5, "fingerprint": "outdated-fp"}
    out_changed = report_runs.handle_runs_refresh(
        1, "50", None, None, "all", "", "all", "all", None, None, None, None, 0, "outdated-fp", swr_stale
    )
    assert len(out_changed) == 12
    assert out_changed[0] is not dash.no_update
    assert out_changed[10] == fp

    swr_other_user = {"user_id": 999, "fingerprint": fp}
    out_other = report_runs.handle_runs_refresh(
        1, "50", None, None, "all", "", "all", "all", None, None, None, None, 0, fp, swr_other_user
    )
    assert out_other[0] is not dash.no_update
