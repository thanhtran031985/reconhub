"""Tests cho task 62 — Sức khỏe hàng đợi & worker (test viết trước).

Nhịp tim worker (ghi/đọc, ngưỡng 30s), thống kê hàng đợi, danh sách kẹt
(QUEUED quá 30 phút; RUNNING export quá hạn heartbeat 300s), quyền Hủy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.metadata import recon_report_run, recon_rpt_export
from tests.unit.test_page_dashboard import dashboard_env
from tests.unit.test_page_report_viewer import _dump, _find_by_id
from tests.unit.test_report_run_execute import admin_ctx, operator_ctx, run_env

__all__ = ["run_env", "admin_ctx", "operator_ctx", "dashboard_env"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def health_env(run_env, monkeypatch):
    monkeypatch.setattr("app.services.worker_health.get_recon_engine", lambda: run_env["engine"])
    monkeypatch.setattr("app.services.report_export.get_recon_engine", lambda: run_env["engine"])
    return run_env


def _insert_run(engine, env, *, status, created_by, created_at):
    with engine.begin() as conn:
        res = conn.execute(
            recon_report_run.insert().values(
                REPORT_ID=env["report_id"],
                TEMPLATE_ID=env["sql_template_id"],
                VERSION_ID=env["sql_version_id"],
                PARAMS_JSON="{}",
                STATUS=status,
                CREATED_BY=created_by,
                CREATED_AT=created_at,
            )
        )
        return int(res.inserted_primary_key[0])


def _insert_export(engine, run_id, *, status, created_by, created_at, heartbeat_at=None, locked_at=None):
    with engine.begin() as conn:
        res = conn.execute(
            recon_rpt_export.insert().values(
                RUN_ID=run_id,
                FORMAT="CSV",
                STATUS=status,
                PART_COUNT=1,
                PROGRESS_PCT=0,
                CREATED_BY=created_by,
                CREATED_AT=created_at,
                HEARTBEAT_AT=heartbeat_at,
                LOCKED_AT=locked_at,
            )
        )
        return int(res.inserted_primary_key[0])


class TestHeartbeat:
    def test_write_then_read_alive(self, health_env):
        from app.services.worker_health import get_worker_health, write_worker_heartbeat

        engine = health_env["engine"]
        now = _now()
        write_worker_heartbeat(engine, "export-worker-1", "export", now=now)
        write_worker_heartbeat(engine, "worker-2", "recon", now=now)
        health = get_worker_health(engine, now=now)
        assert health["status"] == "running"
        assert health["workers"]["export"]["alive"] is True
        assert health["workers"]["export"]["worker_id"] == "export-worker-1"
        assert health["workers"]["recon"]["alive"] is True
        assert health["workers"]["recon"]["worker_id"] == "worker-2"

    def test_no_heartbeat_is_down(self, health_env):
        from app.services.worker_health import get_worker_health

        health = get_worker_health(health_env["engine"], now=_now())
        assert health["status"] == "down"
        assert health["workers"]["export"]["alive"] is False
        assert health["workers"]["export"]["last_seen"] is None
        assert health["workers"]["recon"]["alive"] is False

    def test_stale_heartbeat_is_down(self, health_env):
        from app.services.worker_health import get_worker_health, write_worker_heartbeat

        engine = health_env["engine"]
        old = _now() - timedelta(seconds=31)
        write_worker_heartbeat(engine, "export-worker-1", "export", now=old)
        write_worker_heartbeat(engine, "worker-2", "recon", now=old)
        health = get_worker_health(engine, now=_now())
        assert health["status"] == "down"

    def test_one_stale_is_partial(self, health_env):
        from app.services.worker_health import get_worker_health, write_worker_heartbeat

        engine = health_env["engine"]
        now = _now()
        write_worker_heartbeat(engine, "export-worker-1", "export", now=now)
        write_worker_heartbeat(engine, "worker-2", "recon", now=now - timedelta(seconds=60))
        health = get_worker_health(engine, now=now)
        assert health["status"] == "partial"
        assert health["workers"]["export"]["alive"] is True
        assert health["workers"]["recon"]["alive"] is False

    def test_write_bad_kind_raises(self, health_env):
        from app.services.worker_health import write_worker_heartbeat

        with pytest.raises(ValueError):
            write_worker_heartbeat(health_env["engine"], "w-1", "bogus")


class TestWorkerLoopHeartbeat:
    def test_recon_worker_writes_heartbeat(self, health_env, monkeypatch):
        import threading
        import time

        from app.db.metadata import recon_app_setting

        monkeypatch.setattr("worker.runner.get_db_engine", lambda: health_env["engine"])
        from worker.runner import ReconWorker

        worker = ReconWorker(poll_interval=0.05)
        stop_event = threading.Event()
        thread = threading.Thread(target=worker.run, args=(stop_event,), daemon=True)
        thread.start()
        time.sleep(0.4)
        stop_event.set()
        thread.join(timeout=5)
        with health_env["engine"].connect() as conn:
            row = (
                conn.execute(select(recon_app_setting).where(recon_app_setting.c.KEY == "WORKER_HEARTBEAT_RECON"))
                .mappings()
                .first()
            )
        assert row is not None
        assert row["UPDATED_BY"] == worker.worker_id
        age = (_now() - datetime.fromisoformat(str(row["VALUE"]))).total_seconds()
        assert age < 30

    def test_export_worker_writes_heartbeat(self, health_env):
        import threading
        import time

        from app.db.metadata import recon_app_setting
        from worker.export_runner import ReportExportWorker

        worker = ReportExportWorker(poll_interval=0.05, engine=health_env["engine"])
        stop_event = threading.Event()
        thread = threading.Thread(target=worker.run, args=(stop_event,), daemon=True)
        thread.start()
        time.sleep(0.4)
        stop_event.set()
        thread.join(timeout=5)
        with health_env["engine"].connect() as conn:
            row = (
                conn.execute(select(recon_app_setting).where(recon_app_setting.c.KEY == "WORKER_HEARTBEAT_EXPORT"))
                .mappings()
                .first()
            )
        assert row is not None
        assert row["UPDATED_BY"] == worker.worker_id
        age = (_now() - datetime.fromisoformat(str(row["VALUE"]))).total_seconds()
        assert age < 30


class TestQueueHealth:
    def test_counts_by_status_admin(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="admin", created_at=now)
        _insert_run(engine, health_env, status="QUEUED", created_by="operator", created_at=now)
        _insert_export(engine, run_id, status="QUEUED", created_by="admin", created_at=now)
        _insert_export(engine, run_id, status="RUNNING", created_by="operator", created_at=now, heartbeat_at=now)
        _insert_export(engine, run_id, status="DONE", created_by="admin", created_at=now)
        res = get_queue_health(admin_ctx)
        assert res.ok, res.message
        data = res.data
        assert data["runs"]["QUEUED"] == 1
        assert data["runs"]["DONE"] == 1
        assert data["exports"]["QUEUED"] == 1
        assert data["exports"]["RUNNING"] == 1
        assert data["exports"]["DONE"] == 1
        assert data["max_concurrent"] == 10

    def test_counts_owner_scope(self, health_env, operator_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="admin", created_at=now)
        _insert_run(engine, health_env, status="QUEUED", created_by="operator", created_at=now)
        _insert_export(engine, run_id, status="QUEUED", created_by="admin", created_at=now)
        res = get_queue_health(operator_ctx)
        assert res.ok, res.message
        # Operator chỉ thấy mục của mình: 1 run QUEUED, 0 export.
        assert res.data["runs"]["QUEUED"] == 1
        assert res.data["runs"].get("DONE", 0) == 0
        assert res.data["exports"].get("QUEUED", 0) == 0

    def test_stuck_queued_run(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        old_id = _insert_run(
            engine,
            health_env,
            status="QUEUED",
            created_by="admin",
            created_at=now - timedelta(minutes=40),
        )
        _insert_run(engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=5))
        res = get_queue_health(admin_ctx, now=now)
        stuck = [s for s in res.data["stuck"] if s["kind"] == "run"]
        assert [s["id"] for s in stuck] == [old_id]
        assert stuck[0]["age_minutes"] == 40

    def test_stuck_queued_export(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="admin", created_at=now)
        old_id = _insert_export(
            engine,
            run_id,
            status="QUEUED",
            created_by="admin",
            created_at=now - timedelta(minutes=31),
        )
        _insert_export(engine, run_id, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=5))
        res = get_queue_health(admin_ctx, now=now)
        stuck = [s for s in res.data["stuck"] if s["kind"] == "export"]
        assert [s["id"] for s in stuck] == [old_id]

    def test_stale_running_export_listed(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="admin", created_at=now)
        stale_id = _insert_export(
            engine,
            run_id,
            status="RUNNING",
            created_by="admin",
            created_at=now,
            heartbeat_at=now - timedelta(minutes=10),
        )
        _insert_export(engine, run_id, status="RUNNING", created_by="admin", created_at=now, heartbeat_at=now)
        res = get_queue_health(admin_ctx, now=now)
        stuck = [s for s in res.data["stuck"] if s["kind"] == "export"]
        assert [s["id"] for s in stuck] == [stale_id]
        assert stuck[0]["stale_heartbeat"] is True

    def test_running_run_not_listed_as_stuck(self, health_env, admin_ctx):
        """Run RUNNING không có cột heartbeat để đánh giá nên không liệt kê kẹt."""
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        _insert_run(engine, health_env, status="RUNNING", created_by="admin", created_at=now - timedelta(hours=2))
        res = get_queue_health(admin_ctx, now=now)
        assert res.data["stuck"] == []

    def test_stuck_list_capped_oldest_first(self, health_env, admin_ctx):
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        ids = [
            _insert_run(
                engine, health_env, status="QUEUED", created_by="admin", created_at=now - timedelta(minutes=31 + i)
            )
            for i in range(25)
        ]
        res = get_queue_health(admin_ctx, now=now)
        stuck = res.data["stuck"]
        assert len(stuck) == 20
        assert [s["id"] for s in stuck] == sorted(ids, reverse=True)[:20]

    def test_can_cancel_rules(self, health_env, admin_ctx, operator_ctx):
        """Export: chỉ chủ mới hủy được (kể cả ADMIN cũng chỉ hủy của mình);
        run: ADMIN hoặc chủ mới hủy được."""
        from app.services.worker_health import get_queue_health

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="admin", created_at=now)
        exp_id = _insert_export(
            engine, run_id, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=40)
        )
        run_stuck = _insert_run(
            engine, health_env, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=40)
        )
        res = get_queue_health(admin_ctx, now=now)
        by_id = {(s["kind"], s["id"]): s for s in res.data["stuck"]}
        assert by_id[("export", exp_id)]["can_cancel"] is False
        assert by_id[("run", run_stuck)]["can_cancel"] is True
        res_op = get_queue_health(operator_ctx, now=now)
        by_id_op = {(s["kind"], s["id"]): s for s in res_op.data["stuck"]}
        assert by_id_op[("export", exp_id)]["can_cancel"] is True


class TestHealthCardBody:
    def test_body_shows_down_when_no_heartbeat(self):
        import app.ui.pages.dashboard as page

        body = page._health_card_body(
            {
                "worker": {
                    "status": "down",
                    "workers": {
                        "recon": {"alive": False, "last_seen": None, "worker_id": None},
                        "export": {"alive": False, "last_seen": None, "worker_id": None},
                    },
                },
                "max_concurrent": 10,
                "exports": {},
                "runs": {},
                "stuck": [],
            }
        )
        text = str(body)
        assert "Không phản hồi" in text
        assert "Chưa từng chạy" in text
        assert "Không có mục kẹt" in text

    def test_body_shows_stuck_items_with_cancel(self):
        import app.ui.pages.dashboard as page

        body = page._health_card_body(
            {
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
        )
        assert "Đang chạy" in str(body)
        assert "Doanh thu" in str(body)
        assert "40 phút" in str(body)
        btn = _find_by_id(body, {"type": "health-cancel", "kind": "export", "id": 7})
        assert btn is not None
        # Run không có quyền hủy thì không có nút Hủy.
        assert _find_by_id(body, {"type": "health-cancel", "kind": "run", "id": 9}) is None


class TestHealthCardPage:
    def test_health_card_in_render(self, dashboard_env, monkeypatch):
        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: dashboard_env["ctx"])
        node = page.render_dashboard(0)
        body = _find_by_id(node, "dashboard-health-card-body")
        assert body is not None
        assert "Sức khỏe hàng đợi" in _dump(node)

    def test_health_card_in_empty_branch(self, dashboard_env, monkeypatch):
        """D7: chưa có run nào (total == 0) thì thẻ vẫn hiện."""
        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: dashboard_env["ctx"])
        monkeypatch.setattr(page, "fetch_dashboard_stats", lambda ctx: {})
        node = page.render_dashboard(0)
        assert _find_by_id(node, "dashboard-health-card-body") is not None
        assert "Sức khỏe hàng đợi" in _dump(node)


class TestHealthCancelCallback:
    def _mock_ctx(self, monkeypatch, triggered_id, value):
        from types import SimpleNamespace

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id=triggered_id, triggered=[{"prop_id": "x", "value": value}]),
        )

    def test_guard_no_trigger(self, health_env, operator_ctx, monkeypatch):
        import dash

        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        self._mock_ctx(monkeypatch, None, None)
        assert page.handle_health_actions(None, []) is dash.no_update

    def test_guard_redraw_refire(self, health_env, operator_ctx, monkeypatch):
        import dash

        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        self._mock_ctx(monkeypatch, {"type": "health-cancel", "kind": "export", "id": 5}, 0)
        assert page.handle_health_actions(None, [0]) is dash.no_update

    def test_refresh_button(self, health_env, operator_ctx, monkeypatch):
        import dash

        import app.ui.pages.dashboard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        self._mock_ctx(monkeypatch, "dashboard-health-refresh-btn", 1)
        body = page.handle_health_actions(1, [])
        assert body is not dash.no_update
        # health_env chưa từng ghi nhịp tim nên worker đang "Không phản hồi".
        assert "Không phản hồi" in str(body)

    def test_cancel_stuck_export(self, health_env, operator_ctx, monkeypatch):
        import dash

        import app.ui.pages.dashboard as page

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="operator", created_at=now)
        exp_id = _insert_export(
            engine, run_id, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=40)
        )
        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        self._mock_ctx(monkeypatch, {"type": "health-cancel", "kind": "export", "id": exp_id}, 1)
        body = page.handle_health_actions(None, [1])
        assert body is not dash.no_update
        assert "Đã hủy" in str(body)
        with engine.connect() as conn:
            status = conn.execute(select(recon_rpt_export.c.STATUS).where(recon_rpt_export.c.ID == exp_id)).scalar_one()
        assert status == "CANCELLED"

    def test_cancel_forbidden_keeps_export(self, health_env, admin_ctx, monkeypatch):
        import dash

        import app.ui.pages.dashboard as page

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(engine, health_env, status="DONE", created_by="operator", created_at=now)
        exp_id = _insert_export(
            engine, run_id, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=40)
        )
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        self._mock_ctx(monkeypatch, {"type": "health-cancel", "kind": "export", "id": exp_id}, 1)
        body = page.handle_health_actions(None, [1])
        assert body is not dash.no_update
        with engine.connect() as conn:
            status = conn.execute(select(recon_rpt_export.c.STATUS).where(recon_rpt_export.c.ID == exp_id)).scalar_one()
        assert status == "QUEUED"

    def test_cancel_stuck_run(self, health_env, operator_ctx, monkeypatch):
        import app.ui.pages.dashboard as page

        engine = health_env["engine"]
        now = _now()
        run_id = _insert_run(
            engine, health_env, status="QUEUED", created_by="operator", created_at=now - timedelta(minutes=40)
        )
        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        self._mock_ctx(monkeypatch, {"type": "health-cancel", "kind": "run", "id": run_id}, 1)
        body = page.handle_health_actions(None, [1])
        assert "Đã hủy" in str(body)
        with engine.connect() as conn:
            status = conn.execute(select(recon_report_run.c.STATUS).where(recon_report_run.c.ID == run_id)).scalar_one()
        assert status == "CANCELLED"
