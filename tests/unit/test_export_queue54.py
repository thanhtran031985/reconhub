"""Tests task 54: bấm Xuất (Chạy ngầm) thì vào hàng đợi luôn, không chạy
báo cáo trước.

- request_export nhận run QUEUED (worker tự chạy query ở nền).
- execute_export trên run QUEUED → export DONE + run chốt DONE/ROW_COUNT.
- Viewer chạy ngầm không gọi execute_report_run, grid/run-store giữ nguyên;
  bấm lại cùng tham số không tạo run mới.
"""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import select, update

from app.db.metadata import recon_report_run, recon_rpt_export
from tests.unit.test_report_export_queue import (
    _done_run,
    _mock_stream_conn,
    _request,
    export_env,
)
from tests.unit.test_report_run_execute import (
    ROWS,
    admin_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["export_env", "operator_ctx", "run_env", "admin_ctx"]


def _queued_run(ctx, env):
    from app.services.report_run import create_report_run

    res = create_report_run(
        ctx,
        env["report_id"],
        template_id=env["sql_template_id"],
        values={"p_org": "HN"},
    )
    assert res.ok, res.message
    return res.data


def _run_row(engine, run_id):
    with engine.connect() as conn:
        return conn.execute(
            select(recon_report_run).where(recon_report_run.c.ID == run_id)
        ).mappings().first()


class TestRequestExportQueued:
    def test_queued_run_ok(self, export_env, operator_ctx):
        run = _queued_run(operator_ctx, export_env)
        assert _run_row(export_env["engine"], run["id"])["STATUS"] == "QUEUED"
        res = _request(operator_ctx, export_env, run["id"], "XLSX")
        assert res.ok, res.message
        assert res.data["status"] == "QUEUED"

    def test_failed_run_rejected(self, export_env, operator_ctx):
        run = _queued_run(operator_ctx, export_env)
        with export_env["engine"].begin() as conn:
            conn.execute(
                update(recon_report_run)
                .where(recon_report_run.c.ID == run["id"])
                .values(STATUS="FAILED")
            )
        res = _request(operator_ctx, export_env, run["id"], "CSV", force=True)
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestExecuteExportQueuedRun:
    def test_worker_finishes_queued_run(self, export_env, operator_ctx, monkeypatch):
        from worker.export_runner import ReportExportWorker

        run = _queued_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        assert _run_row(export_env["engine"], run["id"])["ROW_COUNT"] is None
        steps: list[str] = []
        orig_progress = __import__(
            "app.services.report_export", fromlist=["_update_export_progress"]
        )._update_export_progress

        def _record(engine, export_id, pct, step):
            steps.append(step)
            return orig_progress(engine, export_id, pct, step)

        monkeypatch.setattr(
            "app.services.report_export._update_export_progress", _record
        )
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert worker.poll_once() is True
        engine = export_env["engine"]
        with engine.connect() as db:
            export_row = db.execute(
                select(recon_rpt_export).where(recon_rpt_export.c.ID == exp["id"])
            ).mappings().first()
            assert export_row["STATUS"] == "DONE"
            assert export_row["ROW_COUNT"] == len(ROWS)
        finished = _run_row(engine, run["id"])
        assert finished["STATUS"] == "DONE"
        assert finished["ROW_COUNT"] == len(ROWS)
        assert finished["FINISHED_AT"] is not None
        # Task 54: chưa biết tổng thì text không hiện "/ 0 dòng".
        assert not any("/ 0" in s for s in steps), steps

    def test_done_run_row_count_untouched(self, export_env, operator_ctx):
        from worker.export_runner import ReportExportWorker

        run = _done_run(operator_ctx, export_env)
        before = _run_row(export_env["engine"], run["id"])
        assert _request(operator_ctx, export_env, run["id"], "CSV").ok
        worker = ReportExportWorker(engine=export_env["engine"], poll_interval=60)
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert worker.poll_once() is True
        after = _run_row(export_env["engine"], run["id"])
        assert after["STATUS"] == "DONE"
        assert after["ROW_COUNT"] == before["ROW_COUNT"]


def _click_bg(export_env, run_store, export_store=None):
    import app.ui.pages.report_viewer as page

    return page.handle_export_click(
        1,
        run_store,
        export_env["report_id"],
        export_env["sql_template_id"],
        ["HN"],
        [{"type": "viewer-param", "index": "p_org"}],
        1,
        "background",
        export_store,
    )


class TestViewerBackgroundQueueNow:
    def test_no_execute_no_grid_change(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        def _forbid(*a, **k):
            raise AssertionError("execute_report_run bị gọi")

        monkeypatch.setattr(page, "execute_report_run", _forbid)
        out = _click_bg(export_env, {})
        assert "chạy ngầm" in str(out[1]), out[1]
        assert out[4] == {}  # run-store giữ nguyên — grid không đổi
        assert out[5] == 1
        assert out[0]["run_id"] and out[0]["values"] == {"p_org": "HN"}
        engine = export_env["engine"]
        run = _run_row(engine, int(out[0]["run_id"]))
        assert run["STATUS"] == "QUEUED"
        assert run["ROW_COUNT"] is None
        with engine.connect() as conn:
            export_row = conn.execute(
                select(recon_rpt_export).where(
                    recon_rpt_export.c.ID == int(out[0]["export_id"])
                )
            ).mappings().first()
            assert export_row["STATUS"] == "QUEUED"

    def test_double_click_same_values_one_run(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        first = _click_bg(export_env, {})
        second = _click_bg(export_env, {}, export_store=first[0])
        assert second[0]["export_id"] == first[0]["export_id"]
        assert second[0]["run_id"] == first[0]["run_id"]
        engine = export_env["engine"]
        with engine.connect() as conn:
            count = conn.execute(
                select(recon_report_run).where(
                    recon_report_run.c.REPORT_ID == export_env["report_id"]
                )
            ).mappings().all()
            assert len(count) == 1

    def test_now_mode_still_executes(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            out = page.handle_export_click(
                1,
                {},
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                1,
                "now",
            )
        # "Xuất ngay" vẫn chạy báo cáo trước: run-store có run DONE + tổng.
        assert out[4].get("run_id")
        assert out[4].get("total") == len(ROWS)
