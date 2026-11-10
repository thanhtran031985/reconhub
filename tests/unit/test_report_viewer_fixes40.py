"""Tests task 40 — report-viewer-fixes (test viết trước).

1. Nút Xem/Xuất sang loading, chặn bấm trùng.
2. Tab SQL thực hiện (chỉ ADMIN) + cảnh báo SQL thiếu điều kiện NULL.
3. Export progress % thật theo bước (migration 0007).
4. Xuất xong tự tải file, bỏ link "Tải file Excel".
5. Font AG Grid viewer 13px (header + ô).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from app.db.metadata import recon_rpt_export
from tests.unit.test_report_export_queue import (
    _done_run,
    _mock_stream_conn,
    _request,
    export_env,
)
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _dump(component) -> str:
    import json

    def conv(obj):
        if hasattr(obj, "to_plotly_json"):
            return obj.to_plotly_json()
        if isinstance(obj, (list, tuple)):
            return [conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        return obj

    return json.dumps(conv(component), ensure_ascii=False, default=str)


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            found = _find_by_id(child, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


class TestRunSqlService:
    def test_admin_gets_sql_and_binds(self, export_env, admin_ctx):
        from app.services.report_run import get_run_sql

        run = _done_run(admin_ctx, export_env)
        res = get_run_sql(admin_ctx, run["id"])
        assert res.ok, res.message
        data = res.data
        assert "fin_revenue" in data["sql_text"]
        assert data["binds"]["p_org"] == "HN"
        assert "COUNT(*)" in data["count_sql"]
        assert "ORDER BY" in data["paged_sql"]

    def test_admin_sql_warns_when_null_guard_missing(self, export_env, admin_ctx):
        """SQL fixture `org = :p_org` (không IS NULL/NVL): Org trống bind
        NULL thì `org = NULL` cho 0 dòng — đúng ca người dùng báo."""
        from app.services.report_run import get_run_sql

        run = _done_run(admin_ctx, export_env)
        res = get_run_sql(admin_ctx, run["id"])
        assert res.ok, res.message
        assert "p_org" in res.data["null_guard_missing"]
        assert "NULL" in res.data["warning"]

    def test_operator_cannot_see_sql(self, export_env, operator_ctx):
        from app.services.report_run import get_run_sql

        run = _done_run(operator_ctx, export_env)
        res = get_run_sql(operator_ctx, run["id"])
        assert not res.ok

    def test_empty_org_binds_null(self, export_env, admin_ctx):
        from app.services.report_run import (
            create_report_run,
            execute_report_run,
            get_run_sql,
        )

        # Fixture để p_org bắt buộc; báo cáo thật (/reports/5) thì Org
        # không bắt buộc — nới lỏng ở đây để mô phỏng đúng ca đó.
        engine = export_env["engine"]
        with engine.begin() as conn_db:
            conn_db.execute(text("UPDATE RECON_RPT_PARAM SET REQUIRED='N' WHERE CODE='p_org'"))
        created = create_report_run(
            admin_ctx,
            export_env["report_id"],
            template_id=export_env["sql_template_id"],
            values={},
        )
        assert created.ok, created.message
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_report_run(admin_ctx, created.data["id"]).ok
        res = get_run_sql(admin_ctx, created.data["id"])
        assert res.ok, res.message
        assert res.data["binds"]["p_org"] is None


class TestExportProgress:
    def test_request_export_progress_zero(self, export_env, operator_ctx):
        run = _done_run(operator_ctx, export_env)
        res = _request(operator_ctx, export_env, run["id"], "CSV")
        assert res.ok, res.message
        assert res.data["progress_pct"] == 0
        assert res.data["progress_step"] in (None, "")

    def test_execute_export_progress_reaches_100(self, export_env, operator_ctx):
        from app.services.report_export import execute_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE"
        assert result["progress_pct"] == 100
        assert "Hoàn tất" in (result["progress_step"] or "")

    def test_execute_export_reports_intermediate_progress(self, export_env, operator_ctx):
        from app.services import report_export as export_mod
        from app.services.report_export import execute_export

        seen: list[tuple[int, str]] = []
        orig = export_mod._update_export_progress

        def spy(engine, export_id, pct, step):
            seen.append((pct, step))
            return orig(engine, export_id, pct, step)

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        conn, _ = _mock_stream_conn(ROWS)
        with (
            patch.object(export_mod, "_update_export_progress", spy),
            patch(
                "app.services.report_source.open_source_connection",
                return_value=conn,
            ),
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE"
        # 100% cuối ghi cùng lúc với DONE (không qua helper) nên helper
        # chỉ thấy tới 90%; % cuối kiểm tra ở result.
        assert result["progress_pct"] == 100
        pcts = [p for p, _ in seen]
        assert pcts, "worker phải cập nhật tiến độ trong lúc chạy"
        assert pcts == sorted(pcts)
        assert pcts[-1] == 90
        assert any(0 < p < 100 for p in pcts)
        assert any("ghi file" in s.lower() for _, s in seen)

    def test_retry_resets_progress(self, export_env, operator_ctx):
        from app.services.report_export import execute_export, retry_export

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_export(exp["id"], engine=export_env["engine"])["status"] == "DONE"
        engine = export_env["engine"]
        with engine.begin() as conn_db:
            conn_db.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == exp["id"])
                .values(STATUS="FAILED", ERROR_MESSAGE="lỗi giả")
            )
        res = retry_export(operator_ctx, exp["id"])
        assert res.ok, res.message
        assert res.data["progress_pct"] == 0

    def test_metadata_has_progress_columns(self):
        assert "PROGRESS_PCT" in recon_rpt_export.c
        assert "PROGRESS_STEP" in recon_rpt_export.c


class TestViewerLoadingDownloadSqlTab:
    def test_layout_admin_shows_sql_tab(self, export_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        text = _dump(page.layout(report_id=export_env["report_id"]))
        assert "SQL thực hiện" in text
        assert _find_by_id(page.layout(report_id=export_env["report_id"]), "viewer-sql-tab") is not None

    def test_layout_operator_hides_sql_tab(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        comp = page.layout(report_id=export_env["report_id"])
        assert "SQL thực hiện" not in _dump(comp)
        assert _find_by_id(comp, "viewer-sql-tab") is None

    def test_layout_has_download_component(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        comp = page.layout(report_id=export_env["report_id"])
        assert _find_by_id(comp, "viewer-download") is not None

    def test_run_click_returns_loading_false_on_success(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            run_store, page_no, _error, loading = page.handle_run_click(
                1,
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                50,
            )
        assert run_store["run_id"] is not None
        assert loading is False

    def test_run_click_returns_loading_false_on_failure(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=RuntimeError("ORA-12154: TNS:could not resolve"),
        ):
            run_store, _page_no, error, loading = page.handle_run_click(
                1,
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                50,
            )
        assert run_store == {}
        assert loading is False
        assert "ORA-12154" in _dump(error)

    def test_export_click_done_auto_downloads_no_link(self, export_env, operator_ctx, monkeypatch):
        """Export đã DONE (cache): bấm Xuất trả file tải ngay, không link."""
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
        run_store = {
            "run_id": run["id"],
            "template_id": export_env["sql_template_id"],
            "report_id": export_env["report_id"],
            "values": {"p_org": "HN"},
            "total": 3,
            "total_pages": 1,
        }
        store, status, poll_disabled, download, _new_run, _page_no, loading = page.handle_export_click(
            1,
            run_store,
            export_env["report_id"],
            export_env["sql_template_id"],
            ["HN"],
            [{"type": "viewer-param", "index": "p_org"}],
            1,
        )
        assert store.get("export_id") == exp["id"]
        assert poll_disabled is True
        assert loading is False
        assert "Tải file Excel" not in _dump(status)
        assert download is not None
        assert "xlsx" in _dump(download).lower()

    def test_export_poll_done_auto_downloads_no_link(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page
        from app.services.report_export import execute_export

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            assert execute_export(exp["id"], engine=export_env["engine"])["status"] == "DONE"
        status, poll_disabled, download = page.handle_export_poll(1, {"export_id": exp["id"]})
        assert poll_disabled is True
        assert "Tải file Excel" not in _dump(status)
        assert download is not None

    def test_export_poll_running_shows_pct_and_step(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "CSV").data
        engine = export_env["engine"]
        with engine.begin() as conn_db:
            conn_db.execute(
                recon_rpt_export.update()
                .where(recon_rpt_export.c.ID == exp["id"])
                .values(
                    STATUS="RUNNING",
                    PROGRESS_PCT=45,
                    PROGRESS_STEP="Đang ghi file Excel: 10 / 20 dòng",
                )
            )
        status, poll_disabled, download = page.handle_export_poll(1, {"export_id": exp["id"]})
        assert poll_disabled is False
        import dash

        assert download is dash.no_update
        dumped = _dump(status)
        assert "45" in dumped
        assert "Đang ghi file Excel: 10 / 20 dòng" in dumped

    def test_sql_tab_renders_sql_for_admin(self, export_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        run = _done_run(admin_ctx, export_env)
        children = page.handle_sql_tab_render({"run_id": run["id"]})
        dumped = _dump(children)
        assert "fin_revenue" in dumped
        assert "p_org" in dumped

    def test_sql_tab_hidden_for_operator(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        children = page.handle_sql_tab_render({"run_id": run["id"]})
        assert "fin_revenue" not in _dump(children)

    def test_grid_font_13px(self):
        from app.ui.components.report_widgets import render_result_grid

        layout = {
            "columns": [
                {
                    "field_name": "AMOUNT",
                    "label": "Số tiền",
                    "data_type": "NUMBER",
                    "format_mask": "#,##0",
                    "alignment": "RIGHT",
                    "width": 120,
                    "is_total": False,
                }
            ]
        }
        text = _dump(render_result_grid(layout, [{"AMOUNT": 1000}]))
        assert "rh-viewer-grid" in text
        css = (Path(__file__).parents[2] / "app" / "ui" / "assets" / "custom.css").read_text(encoding="utf-8")
        assert ".rh-viewer-grid" in css
        assert "--ag-font-size: 13px" in css
