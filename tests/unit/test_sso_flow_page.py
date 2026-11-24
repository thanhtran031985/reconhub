from __future__ import annotations

from app.core.context import Ctx
from app.ui.pages.sso_flow import handle_toggle_sso, layout


def test_sso_flow_page_layout(monkeypatch):
    # Mock current context as admin
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.sso_flow.get_current_ctx", lambda: admin_ctx)

    container = layout()
    assert container is not None


def test_sso_flow_toggle_switch():
    badge_on, notif_on = handle_toggle_sso(True)
    assert badge_on is not None
    assert notif_on is not None

    badge_off, notif_off = handle_toggle_sso(False)
    assert badge_off is not None
    assert notif_off is not None
