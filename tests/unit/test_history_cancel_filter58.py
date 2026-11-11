"""Tests task 58: hủy export đang chạy, nút giữ chỗ, lọc theo trạng thái.

- Fix 1: checkpoint hủy mỗi batch (không còn mỗi 10 batch); chốt DONE
  chỉ khi export còn QUEUED/RUNNING — hủy rơi vào đoạn chốt không bị
  ghi đè thành DONE; _fail_export cũng vậy.
- Fix 2: cột Hành động giữ cố định 4 vị trí; nút không phù hợp vẽ ẩn
  cùng kích thước (JS, kiểm tra live ở check-58.py).
- Fix 3: lọc trạng thái run — _filters_to_kwargs + list_report_runs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, update

from app.db.metadata import recon_report_run, recon_rpt_export
from tests.unit.test_export_queue54 import _queued_run
from tests.unit.test_report_export_download import _set_status
from tests.unit.test_report_export_queue import (
    _done_run,
    _request,
    export_env,
)
from tests.unit.test_report_export_write import _fake_conn
from tests.unit.test_report_run_cancel import _make_run
from tests.unit.test_report_run_execute import operator_ctx, run_env

__all__ = ["export_env", "operator_ctx", "run_env"]


def _export_row(engine, export_id):
    with engine.connect() as conn:
        return conn.execute(
            select(recon_rpt_export).where(recon_rpt_export.c.ID == export_id)
        ).mappings().first()


def _set_run_status(engine, run_id, status):
    with engine.begin() as conn:
        conn.execute(
            update(recon_report_run)
            .where(recon_report_run.c.ID == run_id)
            .values(STATUS=status)
        )


class TestCancelMidRun:
    def test_cancel_first_batch_stays_cancelled(self, export_env, operator_ctx):
        """Hủy ngay batch đầu (1 batch duy nhất): code cũ kiểm tra mỗi
        10 batch nên không thấy hủy và chốt DONE; code mới kiểm tra mỗi
        batch nên dừng ngay, giữ CANCELLED, xóa file dở."""
        from app.services.report_export import _export_dir, execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        conn = _fake_conn(3)
        cursor = conn.cursor.return_value
        orig_fetchmany = cursor.fetchmany

        def _fetchmany(n):
            rows = orig_fetchmany(n)
            if len(cursor.fetchmany_calls) == 1:
                _set_status(engine, exp["id"], "CANCELLED")
            return rows

        cursor.fetchmany = _fetchmany
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=engine)
        assert result["status"] == "CANCELLED", result
        assert result["file_path"] is None
        assert not _export_dir(exp["id"]).exists()
        assert _export_row(engine, exp["id"])["STATUS"] == "CANCELLED"


class TestCancelAtFinalize:
    def test_cancel_at_finalize_stays_cancelled(self, export_env, operator_ctx, monkeypatch):
        """Hủy đúng lúc chốt (pct=90, sau vòng lặp, trước UPDATE DONE):
        chốt DONE có điều kiện nên không ghi đè CANCELLED; run QUEUED
        cũng không bị chốt DONE theo."""
        from app.services.report_export import _update_export_progress, execute_export

        run = _queued_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        conn = _fake_conn(3)

        def _progress_and_cancel(eng, export_id, pct, step):
            out = _update_export_progress(eng, export_id, pct, step)
            if pct == 90:
                _set_status(eng, export_id, "CANCELLED")
            return out

        monkeypatch.setattr(
            "app.services.report_export._update_export_progress",
            _progress_and_cancel,
        )
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=engine)
        assert result["status"] == "CANCELLED", result
        assert _export_row(engine, exp["id"])["STATUS"] == "CANCELLED"
        with engine.connect() as db:
            run_row = db.execute(
                select(recon_report_run).where(recon_report_run.c.ID == run["id"])
            ).mappings().first()
        assert run_row["STATUS"] == "QUEUED", run_row["STATUS"]


class TestFailAfterCancel:
    def test_fail_export_keeps_cancelled(self, export_env, operator_ctx):
        """Lỗi xảy ra sau khi user hủy: _fail_export không ghi đè
        CANCELLED thành FAILED."""
        from app.schemas.errors import ErrorCode, ServiceError
        from app.services.report_export import _fail_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        _set_status(engine, exp["id"], "CANCELLED")
        _fail_export(engine, exp["id"], ServiceError(ErrorCode.INTERNAL_ERROR, "lỗi giả"))
        assert _export_row(engine, exp["id"])["STATUS"] == "CANCELLED"


class TestStatusFilter:
    def test_filters_to_kwargs_status(self):
        from app.ui.pages.report_runs import _filters_to_kwargs

        kw = _filters_to_kwargs(None, None, "all", "", "all", status="FAILED")
        assert kw["status"] == "FAILED"
        assert _filters_to_kwargs(None, None, "all", "", "all", status="all")["status"] is None
        assert _filters_to_kwargs(None, None, "all", "", "all", status=None)["status"] is None
        assert _filters_to_kwargs(None, None, "all", "", "all", status="")["status"] is None
        # Không truyền status vẫn chạy như cũ (mặc định None).
        assert _filters_to_kwargs(None, None, "all", "", "all")["status"] is None

    def test_list_runs_filters_by_status(self, run_env, operator_ctx):
        from app.services.report_run import list_report_runs

        done_run = _done_run(operator_ctx, run_env)
        failed_run = _make_run(operator_ctx, run_env)
        _set_run_status(run_env["engine"], failed_run["id"], "FAILED")
        res = list_report_runs(operator_ctx, status="FAILED")
        assert res.ok, res.message
        assert [r["id"] for r in res.data["runs"]] == [failed_run["id"]]
        res = list_report_runs(operator_ctx, status="DONE")
        assert [r["id"] for r in res.data["runs"]] == [done_run["id"]]
        res = list_report_runs(operator_ctx)
        assert {r["id"] for r in res.data["runs"]} == {done_run["id"], failed_run["id"]}


class TestActionsCellPlaceholders:
    def test_js_has_hidden_placeholder_buttons(self):
        """Nút giữ chỗ: cùng DMC Button, ẩn bằng visibility + disabled
        (kiểm tra vị trí thật bằng Playwright ở check-58.py)."""
        js = (Path("app/ui/assets/dashAgGridFunctions.js")).read_text(encoding="utf-8")
        cell = js.split("reconRunsActionsCell", 1)[1]
        assert "visibility: 'hidden'" in cell
        assert "btnProps.disabled = true" in cell
        order = [cell.index(label) for label in ("'Hủy'", "'Xóa'", "'Xuất lại'", "'Chạy lại'")]
        assert order == sorted(order), order
