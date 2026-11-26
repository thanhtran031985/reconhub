"""Tests task 55 — Lịch sử báo cáo sang AG Grid (sửa task 57).

- rowData: 1 run → 1 dòng, trường hiển thị đã format sẵn, `_export`
  là export mới nhất để renderer JS vẽ.
- columnDefs: 1 cột "Hành động" (nút DMC có icon) thay 5 cột nút cũ;
  sort/filter trong grid tắt.
- JS: renderer reconRunsFileCell/StatusCell/ActionsCell trong
  dashAgGridFunctions.js tồn tại + đúng nội dung.
- cellRendererData: bấm nút trong cell dispatch sang _do_export_action;
  action lạ / nút không áp dụng thì im lặng.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dash.exceptions import PreventUpdate

from tests.unit.test_report_export_queue import _done_run, _request, export_env
from tests.unit.test_report_run_execute import operator_ctx, run_env

__all__ = ["export_env", "operator_ctx", "run_env"]

JS_PATH = Path("app/ui/assets/dashAgGridFunctions.js")


def _hist_run(run_id=19):
    return {
        "id": run_id,
        "report_id": 5,
        "report_name": "Báo cáo hóa đơn",
        "category_code": "FINANCE",
        "created_by": "admin",
        "row_count": 14585,
        "status": "DONE",
        "params": {"p_from": "2026-11-01", "p_org": None},
        "created_at": "2026-11-10 13:09:56",
        "finished_at": "2026-11-10 13:10:08",
    }


class TestRowData:
    def test_row_data_fields(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data(
            [_hist_run()], {19: [{"id": 7, "status": "RUNNING", "progress_pct": 45}]}
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == 19
        assert row["run"] == "#19"
        assert row["report"] == "Báo cáo hóa đơn"
        assert row["category"] == "Tài chính"
        assert row["runner"] == "admin"
        assert row["rows"] == "14,585"
        assert row["status"] == "Hoàn tất"
        assert row["status_code"] == "DONE"
        assert row["started"] == "10/11/2026 13:09:56"
        assert row["finished"] == "10/11/2026 13:10:08"
        assert row["duration"] == "12,0 giây"
        assert row["params"] == "p_from=01/11/2026 · p_org=—"
        assert row["_export"] == {"id": 7, "status": "RUNNING", "progress_pct": 45}
        assert row["_report_id"] == 5

    def test_row_data_picks_latest_export(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data(
            [_hist_run()],
            {19: [{"id": 9, "status": "FAILED"}, {"id": 8, "status": "DONE"}]},
        )
        assert rows[0]["_export"]["id"] == 9  # export mới nhất đứng đầu

    def test_row_data_no_export(self):
        import app.ui.pages.report_runs as page

        rows = page._runs_row_data([_hist_run()], {})
        assert rows[0]["_export"] is None


class TestColumnDefs:
    def test_actions_column_width_by_role(self):
        import app.ui.pages.report_runs as page

        admin = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=True)}
        op = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=False)}
        assert admin["actions"]["width"] == 340
        assert admin["actions"]["cellRendererParams"] == {"canDelete": True}
        assert op["actions"]["width"] == 280
        assert op["actions"]["cellRendererParams"] == {"canDelete": False}
        # Task 57: không còn cột nút riêng (cancel/retry/delete/rerun/rerun_link).
        for gone in ("cancel", "retry", "delete", "rerun", "rerun_link"):
            assert gone not in admin and gone not in op

    def test_columns_no_sort_no_filter(self):
        import app.ui.pages.report_runs as page

        defs = page._runs_grid_column_defs(can_delete=True)
        assert len(defs) == 12
        assert all(c.get("sortable") is False for c in defs)
        assert all(c.get("filter") is False for c in defs)

    def test_action_columns_use_js_renderers(self):
        import app.ui.pages.report_runs as page

        by_col = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=True)}
        assert by_col["status"]["cellRenderer"] == "reconRunsStatusCell"
        assert by_col["file"]["cellRenderer"] == "reconRunsFileCell"
        assert by_col["file"]["field"] == "_export"  # cell vẽ lại khi export đổi
        assert by_col["actions"]["cellRenderer"] == "reconRunsActionsCell"
        assert by_col["actions"]["field"] == "_export"
        assert by_col["actions"]["headerName"] == "Hành động"


class TestJsRenderers:
    def test_renderers_exist_in_js(self):
        js = JS_PATH.read_text(encoding="utf-8")
        for name in (
            "reconRunsFileCell",
            "reconRunsStatusCell",
            "reconRunsActionsCell",
        ):
            assert name in js
        assert "reconRunsActionCell" not in js
        assert "reconRunsRerunLink" not in js
        # Nội dung renderer vẽ: trạng thái file, link tải, link chạy lại.
        assert "Đang chờ" in js
        assert "Đang xuất " in js
        assert "Tải file" in js
        assert "/download/report-export/" in js
        assert "Chạy lại" in js
        assert "?rerun_from=" in js
        assert "Hủy" in js and "Thử lại" in js and "Xuất lại" in js
        # Task 57: nút DMC thật có icon, bấm gọi setData(action).
        assert "dash_mantine_components.Button" in js
        assert "dash_iconify.DashIconify" in js
        assert "setData" in js
        for icon in (
            "lucide:x",
            "lucide:rotate-ccw",
            "lucide:trash-2",
            "lucide:file-spreadsheet",
            "lucide:play-circle",
        ):
            assert icon in js


class TestUi56:
    """Task 56: font 12px, Tham số về cuối, width đã rà, nút/link có CSS."""

    def test_params_column_is_last(self):
        import app.ui.pages.report_runs as page

        defs = page._runs_grid_column_defs(can_delete=True)
        order = [c.get("colId", c["field"]) for c in defs]
        assert order[-1] == "params"
        assert order.index("params") > order.index("actions")
        assert order[:5] == ["run", "report", "category", "runner", "rows"]

    def test_reviewed_column_widths(self):
        import app.ui.pages.report_runs as page

        by_col = {c.get("colId", c["field"]): c for c in page._runs_grid_column_defs(can_delete=True)}
        assert by_col["category"]["width"] == 80
        assert by_col["status"]["width"] == 90
        assert by_col["started"]["width"] == 140
        assert by_col["finished"]["width"] == 140
        assert by_col["report"]["flex"] == 1
        assert by_col["report"]["minWidth"] == 130
        assert by_col["params"]["flex"] == 2
        assert by_col["params"]["minWidth"] == 140

    def test_layout_grid_has_runs_class(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page
        from tests.unit.test_report_viewer_fixes40 import _find_by_id

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        grid = _find_by_id(page.layout(), "report-runs-grid")
        assert grid is not None
        assert "rh-runs-grid" in str(getattr(grid, "className", ""))

    def test_css_has_runs_font(self):
        css = Path("app/ui/assets/custom.css").read_text(encoding="utf-8")
        assert ".rh-runs-grid" in css
        assert "--ag-font-size: 12px" in css

    def test_js_renderers_use_dmc_buttons(self):
        js = JS_PATH.read_text(encoding="utf-8")
        assert "dash_mantine_components.Button" in js
        assert "setData" in js


class TestRendererAction:
    """Task 57: bấm nút trong cột Hành động → cellRendererData dispatch."""

    def _rows(self, run_id, export):
        import app.ui.pages.report_runs as page

        return page._runs_row_data(
            [_hist_run(run_id)], {run_id: [export]} if export else {}
        )

    @staticmethod
    def _payload(value: str, run_id: int) -> dict[str, object]:
        return {"value": value, "colId": "actions", "rowId": str(run_id), "timestamp": 1}

    def test_cancel_dispatches(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page
        from app.services.report_export import get_export

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        assert exp["status"] == "QUEUED"
        rows = self._rows(run["id"], {"id": exp["id"], "status": "QUEUED", "progress_pct": 0})
        alert, refresh = page.handle_renderer_action(
            self._payload("cancel", run["id"]), rows, 0
        )
        assert refresh == 1
        assert get_export(operator_ctx, exp["id"]).data["status"] == "CANCELLED"

    def test_retry_dispatches(self, export_env, operator_ctx, monkeypatch):
        from sqlalchemy import text as sa_text

        import app.ui.pages.report_runs as page
        from app.services.report_export import get_export

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        with export_env["engine"].begin() as conn:
            conn.execute(
                sa_text("UPDATE RECON_RPT_EXPORT SET STATUS='FAILED' WHERE ID=:i"),
                {"i": exp["id"]},
            )
        rows = self._rows(run["id"], {"id": exp["id"], "status": "FAILED", "progress_pct": 0})
        alert, refresh = page.handle_renderer_action(
            self._payload("retry", run["id"]), rows, 0
        )
        assert refresh == 1
        assert get_export(operator_ctx, exp["id"]).data["status"] == "QUEUED"

    def test_unknown_action_noop(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        rows = self._rows(19, {"id": 7, "status": "QUEUED", "progress_pct": 0})
        with pytest.raises(PreventUpdate):
            page.handle_renderer_action(self._payload("report", 19), rows, 0)

    def test_cancel_on_done_export_noop(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX").data
        rows = self._rows(run["id"], {"id": exp["id"], "status": "DONE", "progress_pct": 100})
        with pytest.raises(PreventUpdate):
            page.handle_renderer_action(
                self._payload("cancel", run["id"]), rows, 0
            )

    def test_unknown_row_noop(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        rows = self._rows(19, {"id": 7, "status": "QUEUED", "progress_pct": 0})
        with pytest.raises(PreventUpdate):
            page.handle_renderer_action(self._payload("cancel", 999), rows, 0)


class TestSavedViewsToolbar:
    """Thanh Template/View cho AG Grid /report-runs (giữ nguyên AG Grid & command_bar)."""

    def test_layout_has_view_toolbar_modals_and_keeps_aggrid_and_command_bar(
        self, export_env, operator_ctx, monkeypatch
    ):
        import app.ui.pages.report_runs as page
        from tests.unit.test_report_viewer_fixes40 import _find_by_id

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout()
        assert _find_by_id(tree, "report-runs-grid") is not None
        assert _find_by_id(tree, "report-runs-filter-name") is not None
        for cid in (
            "rruns-view-select",
            "rruns-btn-save-view",
            "rruns-btn-save-as-view",
            "rruns-btn-set-default",
            "rruns-btn-reset-default",
            "rruns-btn-delete-view",
            "rruns-grid-notification",
            "rruns-save-view-modal",
            "rruns-new-view-name",
            "rruns-new-view-default",
            "rruns-delete-view-modal",
            "rruns-view-init-trigger",
        ):
            assert _find_by_id(tree, cid) is not None, cid

    def test_js_controller_uses_aggrid_column_state_api(self):
        js = Path("app/ui/assets/report_runs_views.js").read_text(encoding="utf-8")
        assert "getApiAsync" in js
        assert "getColumnState" in js
        assert "applyColumnState" in js
        assert "resetColumnState" in js
        assert "reconhub_report_runs_views" in js
