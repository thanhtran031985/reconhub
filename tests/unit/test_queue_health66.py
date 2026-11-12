"""Tests cho task 66 — Tách card sức khỏe thành tab riêng + sửa link run kẹt.

Tests-first: các test này phải đỏ trước khi code (chưa có trang
/queue-health, menu queue_health, link run kẹt vẫn trỏ /runs/<id>,
dashboard vẫn còn card, migration 0009 chưa có).

Follow-up 12/11/2026: bảng Đang chạy / Đang chờ + badge trạng thái +
2 Select lọc (Trạng thái, Loại) trên tab /queue-health.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.unit.test_page_dashboard import dashboard_env
from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import admin_ctx, norole_ctx, operator_ctx, run_env
from tests.unit.test_reporting_menus import menus_env
from tests.unit.test_worker_health62 import _insert_export, _insert_run, health_env

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx", "dashboard_env", "menus_env", "health_env"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def _active_health() -> dict:
    """Health mẫu cho follow-up: 2 mục đang chạy/chờ + 2 mục kẹt."""
    health = _stuck_health()
    health["active"] = [
        {
            "kind": "export",
            "id": 11,
            "run_id": 3,
            "report_name": "Doanh thu",
            "created_by": "operator",
            "created_at": "2026-11-11T12:20:00",
            "age_minutes": 5,
            "status": "RUNNING",
            "stale_heartbeat": False,
            "can_cancel": True,
        },
        {
            "kind": "run",
            "id": 12,
            "run_id": 12,
            "report_name": "Doanh thu",
            "created_by": "admin",
            "created_at": "2026-11-11T12:10:00",
            "age_minutes": 10,
            "status": "QUEUED",
            "stale_heartbeat": False,
            "can_cancel": True,
        },
    ]
    return health


def _badge_labels(component: object) -> list[str]:
    """Thu thập nhãn của mọi dmc.Badge trong cây (duyệt đệ quy)."""
    labels: list[str] = []
    if type(component).__name__ == "Badge":
        children = getattr(component, "children", None)
        if isinstance(children, str):
            labels.append(children)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            labels.extend(_badge_labels(child))
    elif children is not None:
        labels.extend(_badge_labels(children))
    return labels


class TestActiveList:
    """Follow-up: service get_queue_health trả thêm key "active"."""

    def test_active_includes_export_running_queued_and_run_queued(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_q = _insert_run(
            engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=5)
        )
        run_done = _insert_run(
            engine, health_env, status="DONE", created_by="admin", created_at=now - timedelta(minutes=5)
        )
        exp_run = _insert_export(
            engine,
            run_q,
            status="RUNNING",
            created_by="admin",
            created_at=now - timedelta(minutes=5),
            heartbeat_at=now,
            locked_at=now - timedelta(minutes=5),
        )
        exp_q = _insert_export(
            engine, run_q, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=3)
        )
        exp_done = _insert_export(
            engine, run_done, status="DONE", created_by="admin", created_at=now - timedelta(minutes=5)
        )
        res = get_queue_health(admin_ctx, now=now)
        assert res.ok
        active = res.data["active"]
        ids = {(a["kind"], a["id"]) for a in active}
        assert ("export", exp_run) in ids
        assert ("export", exp_q) in ids
        assert ("run", run_q) in ids
        assert ("export", exp_done) not in ids
        assert ("run", run_done) not in ids
        # Không đổi key stuck: chưa mục nào đủ điều kiện kẹt.
        assert res.data["stuck"] == []

    def test_active_sorted_oldest_first(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_old = _insert_run(
            engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=10)
        )
        run_new = _insert_run(
            engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=1)
        )
        _insert_export(
            engine,
            run_old,
            status="RUNNING",
            created_by="admin",
            created_at=now - timedelta(minutes=5),
            heartbeat_at=now,
            locked_at=now - timedelta(minutes=5),
        )
        res = get_queue_health(admin_ctx, now=now)
        created = [a["created_at"] for a in res.data["active"]]
        assert created == sorted(created)
        assert res.data["active"][0]["id"] == run_old
        assert res.data["active"][-1]["id"] == run_new

    def test_active_capped_at_limit(self, health_env, admin_ctx, monkeypatch):
        import app.services.worker_health as wh
        from app.services.worker_health import get_queue_health

        monkeypatch.setattr(wh, "ACTIVE_LIST_LIMIT", 2)
        engine = health_env["engine"]
        now = _now()
        for i in range(3):
            _insert_run(
                engine,
                health_env,
                status="QUEUED",
                created_by="admin",
                created_at=now - timedelta(minutes=10 - i),
            )
        res = get_queue_health(admin_ctx, now=now)
        assert len(res.data["active"]) == 2

    def test_active_owner_scope_for_operator(self, health_env, operator_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        _insert_run(
            engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=5)
        )
        op_run = _insert_run(
            engine, health_env, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=3)
        )
        res = get_queue_health(operator_ctx, now=now)
        assert res.ok
        assert {a["id"] for a in res.data["active"] if a["kind"] == "run"} == {op_run}


class TestActiveTable:
    """Follow-up: body vẽ bảng Đang chạy / Đang chờ + badge + filter."""

    def test_body_shows_active_section_with_badges(self):
        import app.ui.pages.queue_health as page

        body = page._health_card_body(_active_health())
        text = _dump(body)
        assert "Đang chạy / Đang chờ (2)" in text
        assert "Mục kẹt (2)" in text
        # Badge: worker "Đang chạy" + export RUNNING "Đang chạy",
        # run QUEUED "Đang chờ" (khác nhãn mặc định "Chờ chạy" của bảng kẹt).
        labels = _badge_labels(body)
        assert labels.count("Đang chạy") == 2
        assert labels.count("Đang chờ") == 1
        assert labels.count("Chờ chạy") == 2

    def test_body_filters_by_status(self):
        import app.ui.pages.queue_health as page

        body = page._health_card_body(_active_health(), status_filter="RUNNING")
        text = _dump(body)
        assert "#11" in text
        assert "#12" not in text
        assert "Đang chạy / Đang chờ (1)" in text
        body = page._health_card_body(_active_health(), status_filter="QUEUED")
        text = _dump(body)
        assert "#12" in text
        assert "#11" not in text

    def test_body_filters_by_kind(self):
        import app.ui.pages.queue_health as page

        body = page._health_card_body(_active_health(), kind_filter="export")
        text = _dump(body)
        assert "#11" in text
        assert "#12" not in text
        body = page._health_card_body(_active_health(), kind_filter="run")
        text = _dump(body)
        assert "#12" in text
        assert "#11" not in text

    def test_body_empty_active_shows_message(self):
        import app.ui.pages.queue_health as page

        health = _stuck_health()
        health["active"] = []
        body = page._health_card_body(health)
        text = _dump(body)
        assert "Không có mục nào đang chạy hoặc chờ." in text
        assert "Mục kẹt (2)" in text

    def test_stuck_section_still_shown_with_active(self):
        import app.ui.pages.queue_health as page

        body = page._health_card_body(_active_health())
        assert _anchor_hrefs(body) == ["/report-runs"] * 4
        assert "/runs/" not in _dump(body)

    def test_layout_renders_filter_selects(self, health_env, admin_ctx, monkeypatch):
        import app.ui.pages.queue_health as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        node = page.layout()
        status_sel = _find_by_id(node, "queue-health-filter-status")
        kind_sel = _find_by_id(node, "queue-health-filter-kind")
        assert status_sel is not None
        assert kind_sel is not None
        assert status_sel.value == "all"
        assert kind_sel.value == "all"
