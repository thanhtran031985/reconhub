"""Tests cho task 66 — Tách card sức khỏe thành tab riêng + sửa link run kẹt.

Tests-first: các test này phải đỏ trước khi code (chưa có trang
/queue-health, menu queue_health, link run kẹt vẫn trỏ /runs/<id>,
dashboard vẫn còn card, migration 0009 chưa có).
"""

from __future__ import annotations

from tests.unit.test_page_dashboard import dashboard_env
from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import admin_ctx, norole_ctx, operator_ctx, run_env
from tests.unit.test_reporting_menus import menus_env
from tests.unit.test_worker_health62 import health_env

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx", "dashboard_env", "menus_env", "health_env"]


def _anchor_hrefs(component: object) -> list[str]:
    """Thu thập mọi href trong cây component (duyệt đệ quy)."""
    hrefs: list[str] = []
    href = getattr(component, "href", None)
    if isinstance(href, str):
        hrefs.append(href)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            hrefs.extend(_anchor_hrefs(child))
    elif children is not None:
        hrefs.extend(_anchor_hrefs(children))
    return hrefs


def _stuck_health() -> dict:
    return {
        "worker": {
            "status": "running",
            "workers": {
                "recon": {"alive": True, "last_seen": "2026-11-11T13:00:00", "worker_id": "w-1"},
                "export": {"alive": True, "last_seen": "2026-11-11T13:00:00", "worker_id": "w-2"},
            },
        },
        "max_concurrent": 10,
        "exports": {"QUEUED": 1},
        "runs": {"QUEUED": 1},
        "stuck": [
            {
                "kind": "export",
                "id": 7,
                "run_id": 3,
                "report_name": "Doanh thu",
                "created_by": "operator",
                "created_at": "2026-11-11T12:20:00",
                "age_minutes": 40,
                "status": "QUEUED",
                "stale_heartbeat": False,
                "can_cancel": True,
            },
            {
                "kind": "run",
                "id": 9,
                "run_id": 9,
                "report_name": "Doanh thu",
                "created_by": "admin",
                "created_at": "2026-11-11T12:10:00",
                "age_minutes": 50,
                "status": "QUEUED",
                "stale_heartbeat": False,
                "can_cancel": False,
            },
        ],
    }


class TestQueueHealthMenu:
    def test_menu_def_in_code(self):
        from app.ui.menus import MENU_BY_CODE

        menu = MENU_BY_CODE["queue_health"]
        assert menu.label == "Hàng đợi & worker"
        assert menu.group == "DOI_SOAT"
        assert menu.path == "/queue-health"
        assert menu.order == 90
        assert menu.icon == "lucide:activity"

    def test_role_seed_includes_queue_health(self):
        from app.ui.menus import ROLE_MENUS_SEED

        for role in ("TEMPLATE_OWNER", "OPERATOR", "VIEWER"):
            assert "queue_health" in ROLE_MENUS_SEED[role]

    def test_page_menu_code(self):
        import app.ui.pages.queue_health as page

        assert page.MENU_CODE == "queue_health"

    def test_service_menu_code(self):
        from app.services.worker_health import get_queue_health

        assert getattr(get_queue_health, "menu_codes", None) == ["queue_health"]

    def test_sidebar_shows_queue_health(self, menus_env):
        from app.ui.layout.shell import get_nav_items_for_menus

        items = get_nav_items_for_menus(
            {"dashboard", "queue_health"},
            engine=menus_env,
            is_admin=True,
        )
        hrefs = [item["href"] for group in items for item in group["items"]]
        assert "/queue-health" in hrefs
        assert "/" in hrefs


class TestQueueHealthPage:
    def test_layout_renders_card_admin(self, health_env, admin_ctx, monkeypatch):
        import app.ui.pages.queue_health as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        node = page.layout()
        assert _find_by_id(node, "queue-health-card-body") is not None
        assert _find_by_id(node, "queue-health-refresh-btn") is not None
        assert "Hàng đợi & worker" in _dump(node)

    def test_layout_gate_forbidden_without_menu(self, health_env, norole_ctx, monkeypatch):
        import app.ui.pages.queue_health as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: norole_ctx)
        node = page.layout()
        assert _find_by_id(node, "queue-health-card-body") is None
        assert "không có quyền" in _dump(node).lower()


class TestStuckLinks:
    def test_stuck_run_and_export_link_to_report_runs(self):
        import app.ui.pages.queue_health as page

        body = page._health_card_body(_stuck_health())
        hrefs = _anchor_hrefs(body)
        assert hrefs == ["/report-runs", "/report-runs"]
        assert "/runs/" not in _dump(body)


class TestDashboardWithoutCard:
    def test_render_no_health_card(self, dashboard_env, monkeypatch):
        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: dashboard_env["ctx"])
        node = page.render_dashboard(0)
        assert _find_by_id(node, "dashboard-health-card-body") is None
        assert "Sức khỏe hàng đợi" not in _dump(node)

    def test_empty_branch_no_health_card(self, dashboard_env, monkeypatch):
        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: dashboard_env["ctx"])
        monkeypatch.setattr(page, "fetch_dashboard_stats", lambda ctx: {})
        node = page.render_dashboard(0)
        assert _find_by_id(node, "dashboard-health-card-body") is None
        assert "Sức khỏe hàng đợi" not in _dump(node)
