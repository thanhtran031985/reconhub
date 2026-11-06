"""Tests cho Download/history/cache/security — Bước 4 task 26.

T26-09 (retry), T26-10 (user B download A → NOT_FOUND), T26-11 (file mất).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from app.db.metadata import recon_rpt_export
from tests.unit.test_report_export_queue import (
    _done_run,
    _mock_stream_conn,
    _request,
    export_env,
    operator_ctx,
)
from tests.unit.test_report_run_cancel import _add_operator2
from tests.unit.test_report_run_execute import ROWS, admin_ctx, run_env

__all__ = ["export_env", "operator_ctx", "admin_ctx", "run_env"]


def _done_export(export_env, operator_ctx, fmt="CSV"):
    from app.services.report_export import execute_export

    run = _done_run(operator_ctx, export_env)
    exp = _request(operator_ctx, export_env, run["id"], fmt).data
    conn, _ = _mock_stream_conn(ROWS)
    with patch(
        "app.services.report_source.open_source_connection",
        return_value=conn,
    ):
        result = execute_export(exp["id"], engine=export_env["engine"])
    assert result["status"] == "DONE", result
    return result


def _set_status(engine, export_id, status):
    with engine.begin() as conn:
        conn.execute(
            recon_rpt_export.update()
            .where(recon_rpt_export.c.ID == export_id)
            .values(STATUS=status)
        )


class TestRetry:
    def test_retry_failed_to_queued(self, export_env, operator_ctx):
        from app.services.report_export import retry_export

        exp = _done_export(export_env, operator_ctx)
        _set_status(export_env["engine"], exp["id"], "FAILED")
        res = retry_export(operator_ctx, exp["id"])
        assert res.ok, res.message
        assert res.data["status"] == "QUEUED"
        assert res.data["file_path"] is None
        assert res.data["file_hash"] is None
        assert res.data["row_count"] is None

    def test_retry_wrong_status(self, export_env, operator_ctx):
        from app.services.report_export import retry_export

        exp = _done_export(export_env, operator_ctx)
        res = retry_export(operator_ctx, exp["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_retry_other_user_not_found(self, export_env, operator_ctx):
        from app.services.report_export import retry_export

        exp = _done_export(export_env, operator_ctx)
        _set_status(export_env["engine"], exp["id"], "FAILED")
        other = _add_operator2(export_env["engine"])
        res = retry_export(other, exp["id"])
        assert not res.ok and res.code == "NOT_FOUND"


class TestDownloadSecurity:
    def test_user_b_download_a_not_found(self, export_env, operator_ctx):
        from app.services.report_export import download_export

        exp = _done_export(export_env, operator_ctx)
        other = _add_operator2(export_env["engine"])
        res = download_export(other, exp["id"])
        assert not res.ok and res.code == "NOT_FOUND"

    def test_admin_downloads_any(self, export_env, operator_ctx, admin_ctx):
        from app.services.report_export import download_export

        exp = _done_export(export_env, operator_ctx)
        res = download_export(admin_ctx, exp["id"])
        assert res.ok, res.message
        assert res.data["file_path"] == exp["file_path"]

    def test_expired_missing_file(self, export_env, operator_ctx):
        from app.services.report_export import download_export

        exp = _done_export(export_env, operator_ctx)
        shutil.rmtree(Path(exp["file_path"]).parent)
        res = download_export(operator_ctx, exp["id"])
        assert not res.ok and res.code == "NOT_FOUND"
        assert "không còn" in res.message


class TestListHistory:
    def test_list_owner_scoped(self, export_env, operator_ctx, admin_ctx):
        from app.services.report_export import list_exports

        exp = _done_export(export_env, operator_ctx)
        other = _add_operator2(export_env["engine"])
        own = list_exports(operator_ctx)
        assert own.ok and len(own.data["exports"]) == 1
        assert own.data["exports"][0]["id"] == exp["id"]
        assert list_exports(other).data["exports"] == []
        all_exports = list_exports(admin_ctx)
        assert len(all_exports.data["exports"]) == 1
        by_run = list_exports(operator_ctx, run_id=exp["run_id"])
        assert len(by_run.data["exports"]) == 1
        by_run_empty = list_exports(operator_ctx, run_id=999_999)
        assert by_run_empty.data["exports"] == []


class TestCancel:
    def test_cancel_queued(self, export_env, operator_ctx):
        from app.services.report_export import cancel_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        res = cancel_export(operator_ctx, exp["id"])
        assert res.ok, res.message
        assert res.data["status"] == "CANCELLED"

    def test_cancel_done_rejected(self, export_env, operator_ctx):
        from app.services.report_export import cancel_export

        exp = _done_export(export_env, operator_ctx)
        res = cancel_export(operator_ctx, exp["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_worker_skips_cancelled(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        _set_status(export_env["engine"], exp["id"], "CANCELLED")
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        assert worker.poll_once() is False

    def test_executor_stops_on_cancel(self, export_env, operator_ctx):
        from app.services.report_export import execute_export
        from tests.unit.test_report_export_write import _fake_conn

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        conn = _fake_conn(60_000)
        cursor = conn.cursor.return_value
        orig_fetchmany = cursor.fetchmany

        def _fetchmany(n):
            rows = orig_fetchmany(n)
            if len(cursor.fetchmany_calls) == 10:
                _set_status(engine, exp["id"], "CANCELLED")
            return rows

        cursor.fetchmany = _fetchmany
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(
                exp["id"], engine=engine, max_rows_per_file=1_000_000
            )
        assert result["status"] == "CANCELLED"
        assert result["file_path"] is None
        from app.services.report_export import _export_dir

        assert not _export_dir(exp["id"]).exists()
