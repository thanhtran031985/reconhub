"""Tests cho Queue/worker export — Bước 1 task 26 (test viết trước).

request_export + claim per-user concurrency (T26-01) + worker poll + stale reset.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db.metadata import recon_rpt_export
from tests.unit.test_report_run_cancel import _add_operator2
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


@pytest.fixture()
def export_env(run_env, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(
        "app.services.report_export.get_recon_engine",
        lambda: run_env["engine"],
    )
    settings = get_settings()
    monkeypatch.setattr(
        settings, "RECON_STORAGE_DIR", str(tmp_path / "storage")
    )
    return run_env


def _done_run(ctx, env, template_key="sql_template_id"):
    from app.services.report_run import create_report_run, execute_report_run

    res = create_report_run(
        ctx,
        env["report_id"],
        template_id=env[template_key],
        values={"p_org": "HN"},
    )
    assert res.ok, res.message
    run = res.data
    conn, _ = _mock_ora_conn(ROWS)
    with patch(
        "app.services.report_source.open_source_connection", return_value=conn
    ):
        assert execute_report_run(ctx, run["id"]).ok
    return run


def _request(ctx, env, run_id, fmt="CSV", force=False):
    from app.services.report_export import request_export

    return request_export(ctx, run_id, fmt, force=force)


def _mock_stream_conn(rows):
    """Mock Oracle cho vòng stream: fetchmany trả rows một lần rồi [].

    (MagicMock fetchmany mặc định trả cùng list mãi — vòng lặp stream
    không bao giờ kết thúc nếu không đặt side_effect.)
    """
    conn, cursor = _mock_ora_conn(rows)
    cursor.fetchmany.side_effect = [rows, []]
    return conn, cursor


class TestRequestExport:
    def test_request_queues(self, export_env, operator_ctx):
        run = _done_run(operator_ctx, export_env)
        res = _request(operator_ctx, export_env, run["id"], "XLSX")
        assert res.ok, res.message
        assert res.data["status"] == "QUEUED"
        assert res.data["format"] == "XLSX"
        assert res.data["run_id"] == run["id"]

    def test_request_dedupes_pending(self, export_env, operator_ctx):
        run = _done_run(operator_ctx, export_env)
        first = _request(operator_ctx, export_env, run["id"], "CSV")
        assert first.ok, first.message
        second = _request(operator_ctx, export_env, run["id"], "CSV")
        assert second.ok, second.message
        assert second.data["id"] == first.data["id"]
        forced = _request(operator_ctx, export_env, run["id"], "CSV", force=True)
        assert forced.ok, forced.message
        assert forced.data["id"] != first.data["id"]

    def test_request_validation(self, export_env, operator_ctx):
        from app.services.report_run import create_report_run

        # Run chưa DONE
        run = create_report_run(
            operator_ctx,
            export_env["report_id"],
            template_id=export_env["sql_template_id"],
            values={"p_org": "HN"},
        ).data
        res = _request(operator_ctx, export_env, run["id"], "CSV")
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # Format lạ
        done = _done_run(operator_ctx, export_env)
        res = _request(operator_ctx, export_env, done["id"], "PDF")
        assert not res.ok and res.code == "VALIDATION_ERROR"
        # Run người khác
        other = _add_operator2(export_env["engine"])
        res = _request(other, export_env, done["id"], "CSV")
        assert not res.ok and res.code == "NOT_FOUND"


class TestClaimConcurrency:
    def test_per_user_limit(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        engine = export_env["engine"]
        runs = [_done_run(operator_ctx, export_env) for _ in range(3)]
        other = _add_operator2(engine)
        other_run = _done_run(other, export_env)
        for run in runs:
            assert _request(operator_ctx, export_env, run["id"]).ok
        assert _request(other, export_env, other_run["id"]).ok
        worker = ReportExportWorker(engine=engine, poll_interval=60)
        claimed = [worker.dialect.claim_next_queued_export("w1") for _ in range(4)]
        # 2 của operator (đủ giới hạn 2) + 1 của operator2 + hết
        assert claimed[0] is not None
        assert claimed[1] is not None
        assert claimed[2] is not None
        assert claimed[3] is None
        with engine.connect() as conn:
            owners = {
                r[0]: r[1]
                for r in conn.execute(
                    select(
                        recon_rpt_export.c.ID, recon_rpt_export.c.CREATED_BY
                    ).where(recon_rpt_export.c.STATUS == "RUNNING")
                ).all()
            }
        assert sorted(owners.values()) == ["operator", "operator", "operator2"]
        # Một export của operator DONE → claim tiếp lấy export thứ 3 của operator
        first_op = min(i for i, o in owners.items() if o == "operator")
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == first_op)
                .values(STATUS="DONE")
            )
        assert worker.dialect.claim_next_queued_export("w1") is not None

    def test_claim_twice_second_none(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        run = _done_run(operator_ctx, export_env)
        assert _request(operator_ctx, export_env, run["id"]).ok
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        first = worker.dialect.claim_next_queued_export("w1")
        assert first is not None
        assert worker.dialect.claim_next_queued_export("w1") is None


class TestWorkerPoll:
    def test_poll_once_end_to_end_csv(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert worker.poll_once() is True
            assert worker.poll_once() is False
        engine = export_env["engine"]
        with engine.connect() as db:
            row = db.execute(
                select(recon_rpt_export).where(
                    recon_rpt_export.c.ID == exp["id"]
                )
            ).mappings().first()
        assert row["STATUS"] == "DONE"
        assert row["ROW_COUNT"] == 3
        assert row["FILE_PATH"] is not None
        assert row["FILE_SIZE"] is not None and row["FILE_SIZE"] > 0
        assert row["FILE_HASH"] is not None
        content = open(str(row["FILE_PATH"]), encoding="utf-8-sig").read()
        assert "AMOUNT,ORG,TXN_DATE" in content
        assert "1000,HN,2026-02-01" in content

    def test_reset_stale_exports(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        with engine.begin() as conn:
            conn.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == exp["id"])
                .values(STATUS="RUNNING", HEARTBEAT_AT=old)
            )
        worker = ReportExportWorker(engine=engine, poll_interval=60)
        assert worker.reset_stale_exports() == 1
        with engine.connect() as db:
            row = db.execute(
                select(recon_rpt_export.c.STATUS).where(
                    recon_rpt_export.c.ID == exp["id"]
                )
            ).scalar_one()
        assert row == "FAILED"
