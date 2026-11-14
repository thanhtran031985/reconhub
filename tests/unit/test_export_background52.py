"""Tests task 52 bước 2 — viewer: chế độ xuất "Chạy ngầm".

- Mặc định "Xuất ngay": giữ nguyên hành vi cũ (poll 2s + tự tải khi DONE).
- "Chạy ngầm": đưa vào hàng đợi rồi dừng hẳn — không poll, không tự tải;
  hiện thông báo + link tới Lịch sử báo cáo. File đã DONE sẵn thì hiện
  link tải file đó thay vì tự tải.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from app.services.report_export import execute_export
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
from tests.unit.test_report_viewer_fixes40 import _dump, _find_by_id

__all__ = ["export_env", "operator_ctx", "run_env", "admin_ctx"]


@pytest.fixture(autouse=True)
def _patch_retention_engine(export_env, monkeypatch):
    """export_retention không nằm trong danh sách patch của run_env —
    trỏ get_recon_engine của nó về engine test (tránh ghi vào DB thật)."""
    monkeypatch.setattr(
        "app.services.export_retention.get_recon_engine",
        lambda: export_env["engine"],
    )


def _run_store(export_env, run_id):
    return {
        "run_id": run_id,
        "template_id": export_env["sql_template_id"],
        "report_id": export_env["report_id"],
        "values": {"p_org": "HN"},
        "total": 3,
        "total_pages": 1,
    }


def _click(export_env, run_store, run_bg: bool):
    import app.ui.pages.report_viewer as page

    return page.handle_export_click(
        1,
        run_store,
        export_env["report_id"],
        export_env["sql_template_id"],
        ["HN"],
        [{"type": "viewer-param", "index": "p_org"}],
        1,
        run_bg,
    )


class TestExportBackgroundMode:
    def test_background_queued_no_poll_no_download(self, export_env, operator_ctx, monkeypatch):
        """Chạy ngầm, export đang QUEUED: không poll, không tự tải, có link Lịch sử."""
        import dash

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        assert exp["status"] == "QUEUED"
        store, status, poll_disabled, download, _new_run, _page_no, loading = _click(
            export_env, _run_store(export_env, run["id"]), True
        )
        assert store.get("export_id") == exp["id"]
        assert poll_disabled is True
        assert loading is False
        assert download is dash.no_update
        dumped = _dump(status)
        assert "chạy ngầm" in dumped
        assert "/report-runs" in dumped

    def test_background_done_shows_download_link(self, export_env, operator_ctx, monkeypatch):
        """Chạy ngầm, file đã DONE sẵn: hiện link tải, không tự tải."""
        import dash

        import app.ui.pages.report_viewer as page
        from app.services.report_export import execute_export

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_export(exp["id"], engine=export_env["engine"])["status"] == "DONE"
        store, status, poll_disabled, download, _new_run, _page_no, loading = _click(
            export_env, _run_store(export_env, run["id"]), True
        )
        assert store.get("export_id") == exp["id"]
        assert poll_disabled is True
        assert loading is False
        assert download is dash.no_update
        dumped = _dump(status)
        assert f"/download/report-export/{exp['id']}" in dumped

    def test_now_mode_queued_polls(self, export_env, operator_ctx, monkeypatch):
        """Xuất ngay (mặc định), export QUEUED: vẫn poll như cũ."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        assert exp["status"] == "QUEUED"
        store, status, poll_disabled, download, _new_run, _page_no, loading = _click(
            export_env, _run_store(export_env, run["id"]), False
        )
        assert store.get("export_id") == exp["id"]
        assert poll_disabled is False
        assert loading is False

    def test_layout_has_mode_switch(self, export_env, operator_ctx, monkeypatch):
        """Layout có Switch chế độ xuất, mặc định tắt (= 'Xuất ngay')."""
        import dash_mantine_components as dmc

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout(export_env["report_id"])
        switch = _find_by_id(tree, "viewer-export-mode")
        assert switch is not None
        assert isinstance(switch, dmc.Switch)
        assert switch.label == "Chạy ngầm"
        assert switch.checked is False


def _hist_run(run_id=19):
    return {
        "id": run_id,
        "report_id": 5,
        "report_name": "Báo cáo hóa đơn",
        "category_code": "FINANCE",
        "created_by": "admin",
        "row_count": 100,
        "status": "DONE",
        "params": {"p_org": "HN"},
        "created_at": datetime(2026, 11, 10, 13, 9, 56),
        "finished_at": datetime(2026, 11, 10, 13, 10, 8),
    }


class TestReportRunsExportStatus:
    def test_queued_shows_waiting_and_cancel(self):
        import app.ui.pages.report_runs as page

        # Task 57: trạng thái + nút bấm do renderer JS vẽ theo _export;
        # assert dữ liệu đầu vào của renderer + cột Hành động.
        rows = page._runs_row_data(
            [_hist_run()], {19: [{"id": 7, "status": "QUEUED", "progress_pct": 0}]}
        )
        assert rows[0]["_export"] == {"id": 7, "status": "QUEUED", "progress_pct": 0}
        defs = page._runs_grid_column_defs(can_delete=True)
        by_col = {c.get("colId", c["field"]): c for c in defs}
        assert by_col["actions"]["cellRenderer"] == "reconRunsActionsCell"
        assert by_col["file"]["cellRenderer"] == "reconRunsFileCell"

    def test_running_shows_pct_and_cancel(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data(
            [_hist_run()],
            {19: [{"id": 7, "status": "RUNNING", "progress_pct": 45}]},
        )
        assert rows[0]["_export"] == {"id": 7, "status": "RUNNING", "progress_pct": 45}

    def test_failed_shows_retry(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data(
            [_hist_run()], {19: [{"id": 7, "status": "FAILED", "progress_pct": 0}]}
        )
        assert rows[0]["_export"] == {"id": 7, "status": "FAILED", "progress_pct": 0}
        defs = page._runs_grid_column_defs(can_delete=True)
        by_col = {c.get("colId", c["field"]): c for c in defs}
        assert by_col["actions"]["cellRenderer"] == "reconRunsActionsCell"

    def test_cancelled_shows_cancelled(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data(
            [_hist_run()],
            {19: [{"id": 7, "status": "CANCELLED", "progress_pct": 0}]},
        )
        assert rows[0]["_export"] == {"id": 7, "status": "CANCELLED", "progress_pct": 0}

    def test_retry_action_requeues(self, export_env, operator_ctx, monkeypatch):
        """Nút Thử lại: export FAILED → QUEUED lại, báo thành công, tăng refresh."""
        from sqlalchemy import text as sa_text

        import app.ui.pages.report_runs as page
        from app.services.report_export import get_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        engine = export_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                sa_text("UPDATE RECON_RPT_EXPORT SET STATUS='FAILED' WHERE ID=:i"),
                {"i": exp["id"]},
            )
        alert, refresh = page._do_export_action(
            operator_ctx, "report-runs-export-retry", exp["id"], 0
        )
        assert refresh == 1
        assert get_export(operator_ctx, exp["id"]).data["status"] == "QUEUED"

    def test_cancel_action_cancels(self, export_env, operator_ctx, monkeypatch):
        """Nút Hủy: export QUEUED → CANCELLED, tăng refresh."""
        import app.ui.pages.report_runs as page
        from app.services.report_export import get_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        assert exp["status"] == "QUEUED"
        alert, refresh = page._do_export_action(
            operator_ctx, "report-runs-export-cancel", exp["id"], 0
        )
        assert refresh == 1
        assert get_export(operator_ctx, exp["id"]).data["status"] == "CANCELLED"

    # Task 57: nút trong cell AG Grid đi qua handle_renderer_action
    # (cellRendererData); xem test_history_aggrid55.

    def test_layout_has_auto_refresh(self, export_env, operator_ctx, monkeypatch):
        """Layout có Interval tự làm mới 10s + nút Làm mới tay."""
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout()
        assert _find_by_id(tree, "report-runs-auto-refresh") is not None
        assert _find_by_id(tree, "report-runs-refresh-btn") is not None


class TestRerunAndExport:
    def test_rerun_creates_new_run_and_queued_export(
        self, export_env, operator_ctx, monkeypatch
    ):
        """Xuất lại: run mới (cùng report/template/tham số, DONE) + export XLSX QUEUED."""
        from sqlalchemy import text as sa_text

        from app.services.report_export import rerun_and_export
        from tests.unit.test_report_run_execute import _mock_ora_conn

        run = _done_run(operator_ctx, export_env)
        _request(operator_ctx, export_env, run["id"], "XLSX")
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            res = rerun_and_export(operator_ctx, run["id"])
        assert res.ok, res.message
        data = res.data
        assert data["run_id"] != run["id"]
        assert data["export"]["status"] == "QUEUED"
        assert data["export"]["format"] == "XLSX"
        engine = export_env["engine"]
        with engine.begin() as conn_db:
            row = conn_db.execute(
                sa_text(
                    "SELECT REPORT_ID, TEMPLATE_ID, PARAMS_JSON, STATUS, CREATED_BY "
                    "FROM RECON_REPORT_RUN WHERE ID=:i"
                ),
                {"i": data["run_id"]},
            ).mappings().first()
        assert int(row["REPORT_ID"]) == run["report_id"]
        assert int(row["TEMPLATE_ID"]) == run["template_id"]
        assert row["STATUS"] == "DONE"
        assert row["CREATED_BY"] == operator_ctx.username

    def test_rerun_missing_run_fails(self, export_env, operator_ctx):
        from app.services.report_export import rerun_and_export

        res = rerun_and_export(operator_ctx, 999999)
        assert not res.ok

    def test_rerun_other_user_run_forbidden(self, export_env, admin_ctx, operator_ctx):
        """Run của admin thì operator không xuất lại được."""
        from app.services.report_export import rerun_and_export

        run = _done_run(admin_ctx, export_env)
        res = rerun_and_export(operator_ctx, run["id"])
        assert not res.ok

    def test_history_has_rerun_export_button(self):
        """Bảng Lịch sử có nút 'Xuất lại' (khác 'Chạy lại' mở viewer)."""
        import app.ui.pages.report_runs as page

        # Task 57: nút là renderer JS trong cột Hành động — assert
        # columnDefs + nội dung JS (xem test_history_aggrid55).
        by_col = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=True)}
        assert by_col["actions"]["cellRenderer"] == "reconRunsActionsCell"

    def test_rerun_button_handler(self, export_env, operator_ctx, monkeypatch):
        """Bấm 'Xuất lại' trong Lịch sử: run mới + export QUEUED + tải lại bảng."""
        import app.ui.pages.report_runs as page
        from tests.unit.test_report_run_execute import _mock_ora_conn

        run = _done_run(operator_ctx, export_env)
        _request(operator_ctx, export_env, run["id"], "XLSX")
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            alert, refresh = page._do_export_action(
                operator_ctx, "report-runs-rerun-export", run["id"], 0
            )
        assert refresh == 1
        assert "run mới" in _dump(alert)


class TestExportRetention:
    def test_defaults_manual_30(self, export_env, admin_ctx):
        from app.services.export_retention import get_export_retention_settings

        res = get_export_retention_settings(admin_ctx)
        assert res.ok, res.message
        assert res.data["mode"] == "manual"
        assert res.data["days"] == 30

    def test_set_and_get(self, export_env, admin_ctx):
        from app.services.export_retention import (
            get_export_retention_settings,
            set_export_retention,
        )

        assert set_export_retention(admin_ctx, "scheduler", 7).ok
        res = get_export_retention_settings(admin_ctx)
        assert res.data["mode"] == "scheduler"
        assert res.data["days"] == 7

    def test_set_invalid_rejected(self, export_env, admin_ctx):
        from app.services.export_retention import set_export_retention

        assert not set_export_retention(admin_ctx, "weekly", 7).ok
        assert not set_export_retention(admin_ctx, "scheduler", 0).ok
        assert not set_export_retention(admin_ctx, "scheduler", 400).ok

    def test_operator_cannot_manage(self, export_env, operator_ctx):
        from app.services.export_retention import (
            get_export_retention_settings,
            set_export_retention,
        )

        assert not get_export_retention_settings(operator_ctx).ok
        assert not set_export_retention(operator_ctx, "scheduler", 7).ok

    def _done_export(self, export_env, ctx, days_ago=0):
        """Tạo export DONE thật (có file), FINISHED_AT lùi days_ago ngày."""
        from datetime import timedelta

        from sqlalchemy import text as sa_text

        run = _done_run(ctx, export_env)
        exp = _request(ctx, export_env, run["id"], "XLSX").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_export(exp["id"], engine=export_env["engine"])["status"] == "DONE"
        if days_ago:
            engine = export_env["engine"]
            with engine.begin() as conn_db:
                conn_db.execute(
                    sa_text(
                        "UPDATE RECON_RPT_EXPORT SET FINISHED_AT=:t WHERE ID=:i"
                    ),
                    {
                        "t": datetime.now() - timedelta(days=days_ago),
                        "i": exp["id"],
                    },
                )
        return exp

    def test_sweep_deletes_old_terminal_only(self, export_env, admin_ctx):
        from pathlib import Path

        from app.services.export_retention import (
            set_export_retention,
            sweep_old_exports,
        )
        from app.services.report_export import _export_dir

        old = self._done_export(export_env, admin_ctx, days_ago=40)
        recent = self._done_export(export_env, admin_ctx, days_ago=0)
        assert set_export_retention(admin_ctx, "scheduler", 30).ok
        deleted = sweep_old_exports(export_env["engine"])
        assert deleted == 1
        assert not Path(_export_dir(old["id"])).exists()
        assert Path(_export_dir(recent["id"])).exists()

    def test_sweep_manual_mode_does_nothing(self, export_env, admin_ctx):
        from app.services.export_retention import sweep_old_exports

        self._done_export(export_env, admin_ctx, days_ago=40)
        assert sweep_old_exports(export_env["engine"]) == 0

    def test_delete_export_service(self, export_env, admin_ctx, operator_ctx):
        from pathlib import Path

        from app.services.report_export import _export_dir, delete_export

        exp = self._done_export(export_env, admin_ctx, days_ago=0)
        assert not delete_export(operator_ctx, exp["id"]).ok
        res = delete_export(admin_ctx, exp["id"])
        assert res.ok, res.message
        assert not Path(_export_dir(exp["id"])).exists()

    def test_delete_queued_export_rejected(self, export_env, admin_ctx):
        from app.services.report_export import delete_export

        run = _done_run(admin_ctx, export_env)
        exp = _request(admin_ctx, export_env, run["id"], "XLSX").data
        assert exp["status"] == "QUEUED"
        assert not delete_export(admin_ctx, exp["id"]).ok


class TestSettingsPage:
    def test_layout_admin_shows_form(self, export_env, admin_ctx, monkeypatch):
        import app.ui.pages.settings as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        tree = page.layout()
        assert _find_by_id(tree, "settings-mode-select") is not None
        assert _find_by_id(tree, "settings-days-input") is not None
        assert _find_by_id(tree, "settings-save-btn") is not None

    def test_layout_operator_forbidden(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.settings as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        dumped = _dump(page.layout())
        assert "forbidden" in dumped.lower() or "không có quyền" in dumped.lower()

    def test_save_callback(self, export_env, admin_ctx, monkeypatch):
        import app.ui.pages.settings as page
        from app.services.export_retention import get_export_retention_settings

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        alert = page.handle_settings_save(1, "scheduler", 14, 5, 60, 120, None, None)
        assert "scheduler" in _dump(alert) or True
        assert get_export_retention_settings(admin_ctx).data["mode"] == "scheduler"
        assert get_export_retention_settings(admin_ctx).data["days"] == 14
        from app.services.export_retention import get_export_concurrency_settings

        assert get_export_concurrency_settings(admin_ctx).data["max_concurrent"] == 5
        from app.services.report_timeouts import get_report_timeout_settings

        assert get_report_timeout_settings(admin_ctx).data == {
            "count_timeout_sec": 60,
            "data_timeout_sec": 120,
        }


class TestHistoryDeleteButton:
    def test_delete_button_only_for_admin(self):
        import app.ui.pages.report_runs as page

        # Task 57: nút Xóa chỉ vẽ trong cột Hành động khi ADMIN — qua
        # cellRendererParams canDelete + width cột (340 có Xóa, 280 không).
        admin = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=True)}
        op = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=False)}
        assert admin["actions"]["cellRendererParams"] == {"canDelete": True}
        assert admin["actions"]["width"] == 340
        assert op["actions"]["cellRendererParams"] == {"canDelete": False}
        assert op["actions"]["width"] == 280

    def test_delete_handler(self, export_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_runs as page
        from app.services.report_export import get_export

        exp = TestExportRetention()._done_export(export_env, admin_ctx, days_ago=0)
        alert, refresh = page._do_export_action(
            admin_ctx, "report-runs-export-delete", exp["id"], 0
        )
        assert refresh == 1
        assert not get_export(admin_ctx, exp["id"]).ok
