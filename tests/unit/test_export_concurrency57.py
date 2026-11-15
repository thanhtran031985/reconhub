"""Tests task 57b — export chạy song song.

- Setting EXPORT_MAX_CONCURRENT: mặc định 10, giá trị lưu thắng,
  giá trị sai/vượt khoảng → 10; chỉ ADMIN đổi được.
- Worker: nhóm luồng song song tới N (mặc định theo setting); poll
  đủ N thì trả False; chờ idle xong cả 3 export.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from sqlalchemy import select

from app.db.metadata import recon_app_setting, recon_rpt_export
from tests.unit.test_report_export_queue import (
    _done_run,
    _request,
    export_env,
)
from tests.unit.test_report_run_execute import admin_ctx, operator_ctx, run_env

__all__ = ["export_env", "admin_ctx", "operator_ctx", "run_env"]


def _set_raw(engine, value: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            recon_app_setting.insert().values(
                KEY="EXPORT_MAX_CONCURRENT", VALUE=value,
                UPDATED_BY="admin", UPDATED_AT=datetime(2026, 11, 11),
            )
        )


class TestConcurrencySetting:
    def test_default_is_10(self, export_env):
        from app.services.export_retention import get_export_max_concurrent

        assert get_export_max_concurrent(export_env["engine"]) == 10

    def test_stored_value_wins(self, export_env, admin_ctx):
        from app.services.export_retention import (
            get_export_concurrency_settings,
            get_export_max_concurrent,
            set_export_concurrency,
        )

        assert set_export_concurrency(admin_ctx, 3).ok
        assert get_export_max_concurrent(export_env["engine"]) == 3
        assert get_export_concurrency_settings(admin_ctx).data == {"max_concurrent": 3}

    def test_invalid_stored_value_falls_back_to_10(self, export_env):
        from app.services.export_retention import get_export_max_concurrent

        _set_raw(export_env["engine"], "abc")
        assert get_export_max_concurrent(export_env["engine"]) == 10

    def test_out_of_range_stored_value_falls_back_to_10(self, export_env):
        from app.services.export_retention import get_export_max_concurrent

        _set_raw(export_env["engine"], "99")
        assert get_export_max_concurrent(export_env["engine"]) == 10

    def test_set_invalid_rejected(self, export_env, admin_ctx):
        from app.services.export_retention import set_export_concurrency

        assert not set_export_concurrency(admin_ctx, 0).ok
        assert not set_export_concurrency(admin_ctx, 51).ok
        assert not set_export_concurrency(admin_ctx, "x").ok

    def test_operator_cannot_manage(self, export_env, operator_ctx):
        from app.services.export_retention import (
            get_export_concurrency_settings,
            set_export_concurrency,
        )

        assert not set_export_concurrency(operator_ctx, 5).ok
        assert not get_export_concurrency_settings(operator_ctx).ok


class TestWorkerParallel:
    def _queue_exports(self, export_env, operator_ctx, count: int) -> list[int]:
        ids: list[int] = []
        for _ in range(count):
            run = _done_run(operator_ctx, export_env)
            exp = _request(operator_ctx, export_env, run["id"], "CSV").data
            ids.append(int(exp["id"]))
        return ids

    def test_two_exports_run_concurrently(self, export_env, operator_ctx, monkeypatch):
        from worker.export_runner import ReportExportWorker

        engine = export_env["engine"]
        exp_ids = self._queue_exports(export_env, operator_ctx, 3)
        lock = threading.Lock()
        state = {"current": 0, "max_seen": 0}

        def _fake_execute(export_id: int, engine=None) -> None:
            with lock:
                state["current"] += 1
                state["max_seen"] = max(state["max_seen"], state["current"])
            time.sleep(0.4)
            with engine.begin() as conn:
                conn.execute(
                    recon_rpt_export.update()
                    .where(recon_rpt_export.c.ID == export_id)
                    .values(STATUS="DONE")
                )
            with lock:
                state["current"] -= 1

        monkeypatch.setattr(
            "worker.export_runner.execute_export", _fake_execute
        )
        worker = ReportExportWorker(
            engine=engine, poll_interval=60, max_per_user=2
        )
        assert worker.poll_once() is True
        assert worker.poll_once() is True
        # Đủ 2 luồng → poll tiếp trả False dù còn export trong hàng đợi.
        assert worker.poll_once() is False
        assert worker.wait_for_idle(timeout=30) is True
        assert state["max_seen"] == 2
        # Luồng rảnh → export thứ 3 chạy.
        assert worker.poll_once() is True
        assert worker.wait_for_idle(timeout=30) is True
        with engine.connect() as conn:
            statuses = {
                r[0]
                for r in conn.execute(
                    select(recon_rpt_export.c.STATUS).where(
                        recon_rpt_export.c.ID.in_(exp_ids)
                    )
                ).all()
            }
        assert statuses == {"DONE"}

    def test_setting_limits_pool(self, export_env, operator_ctx, admin_ctx):
        from app.services.export_retention import set_export_concurrency
        from worker.export_runner import ReportExportWorker

        assert set_export_concurrency(admin_ctx, 1).ok
        self._queue_exports(export_env, operator_ctx, 2)
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        assert worker._current_limit() == 1
        assert worker.poll_once() is True
        assert worker.poll_once() is False  # đủ 1 luồng
        assert worker.wait_for_idle(timeout=30) is True

    def test_no_setting_limit_is_10(self, export_env):
        from worker.export_runner import ReportExportWorker

        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        assert worker._current_limit() == 10
