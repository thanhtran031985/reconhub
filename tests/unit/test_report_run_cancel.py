"""Tests cho Cancel/timeout/metrics — Bước 3 task 25 (test viết trước).

cancel_report_run (T25-07), count timeout riêng (T25-06), report_run_metrics (T25-11).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.context import Ctx
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _add_operator2(engine):
    """Thêm user 4 (operator2, vai trò OPERATOR) để kiểm tra owner scope."""
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                "VALUES (4, 'operator2', 'operator2', 'hash', 'Y', 'N', 0, 1, "
                "'SEED', :now, :now, 1)"
            ),
            {"now": now},
        )
    seed_perm_basics(engine, {4: ["OPERATOR"]})
    clear_perm_cache()
    return Ctx(user_id=4, username="operator2", full_name="operator2", roles=["OPERATOR"])


def _make_run(ctx, run_env, template_key="sql_template_id"):
    from app.services.report_run import create_report_run

    res = create_report_run(
        ctx,
        run_env["report_id"],
        template_id=run_env[template_key],
        values={"p_org": "HN"},
    )
    assert res.ok, res.message
    return res.data


class TestCancelReportRun:
    def test_cancel_queued(self, run_env, operator_ctx):
        from app.services.report_run import cancel_report_run

        run = _make_run(operator_ctx, run_env)
        res = cancel_report_run(operator_ctx, run["id"])
        assert res.ok, res.message
        assert res.data["status"] == "CANCELLED"
        assert res.data["finished_at"] is not None

    def test_cancel_twice_rejected(self, run_env, operator_ctx):
        from app.services.report_run import cancel_report_run

        run = _make_run(operator_ctx, run_env)
        assert cancel_report_run(operator_ctx, run["id"]).ok
        res = cancel_report_run(operator_ctx, run["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_cancel_done_rejected(self, run_env, operator_ctx):
        from app.services.report_run import cancel_report_run, execute_report_run

        run = _make_run(operator_ctx, run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert execute_report_run(operator_ctx, run["id"]).ok
        res = cancel_report_run(operator_ctx, run["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_cancel_cross_user_not_found(self, run_env, operator_ctx):
        from app.services.report_run import cancel_report_run

        run = _make_run(operator_ctx, run_env)
        other = _add_operator2(run_env["engine"])
        res = cancel_report_run(other, run["id"])
        assert not res.ok and res.code == "NOT_FOUND"


class TestCountTimeout:
    def test_count_timeout_separate(self, run_env, operator_ctx):
        from app.services.report_run import execute_report_run

        # DS timeout 600s: count = min(300, 30) = 30s; data = min(300, 600) = 300s
        engine = run_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE RECON_DATA_SOURCE SET CALL_TIMEOUT_S = 600 "
                    "WHERE ID = :id"
                ),
                {"id": run_env["ds_id"]},
            )
        run = _make_run(operator_ctx, run_env)
        conns = []

        def _factory(ds_id):
            conn, _ = _mock_ora_conn(ROWS)
            conns.append(conn)
            return conn

        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=_factory,
        ):
            res = execute_report_run(operator_ctx, run["id"])
        assert res.ok, res.message
        assert len(conns) == 2
        assert conns[0].call_timeout == 30_000  # count: min(300, 30)
        assert conns[1].call_timeout == 300_000  # data: min(300, 600)


class TestReportRunMetrics:
    def test_metrics_owner_scoped(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import (
            create_report_run,
            execute_report_run,
            report_run_metrics,
        )

        run1 = _make_run(operator_ctx, run_env)
        run2 = _make_run(operator_ctx, run_env)
        run3 = _make_run(admin_ctx, run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert execute_report_run(operator_ctx, run1["id"]).ok
            assert execute_report_run(admin_ctx, run3["id"]).ok
        res = report_run_metrics(operator_ctx)
        assert res.ok, res.message
        assert res.data["total_runs"] == 2
        assert res.data["by_status"]["DONE"] == 1
        assert res.data["by_status"]["QUEUED"] == 1
        assert res.data["avg_query_ms"] is not None
        assert res.data["total_rows"] == 3
        res = report_run_metrics(admin_ctx)
        assert res.ok, res.message
        assert res.data["total_runs"] == 3
        assert res.data["by_status"]["DONE"] == 2
        assert res.data["total_rows"] == 6

    def test_metrics_forbidden_without_menu(self, run_env, norole_ctx):
        from app.services.report_run import report_run_metrics

        res = report_run_metrics(norole_ctx)
        assert not res.ok and res.code == "FORBIDDEN"
