"""Task 43: lịch sử báo cáo — tên + nhóm, lọc, cột mới, chạy lại qua viewer.

Service: list_report_runs JOIN RECON_REPORT (report_name, category_code)
+ lọc theo ngày chạy / nhóm / tên / người chạy.
Page: cột Nhóm, Tham số, Bắt đầu/Kết thúc/Tổng (giây), Dòng 14,585,
icon tải file, không còn nút Xem, link chạy lại ?rerun_from=.
Viewer: layout(rerun_from=...) điền sẵn tham số của run gốc.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text as sa_text

from tests.unit.test_page_report_viewer import (
    _dump,
    _find_by_id,
    export_env,
    operator_ctx,
)
from tests.unit.test_report_export_queue import _done_run, _request
from tests.unit.test_report_run_cancel import _make_run
from tests.unit.test_report_run_execute import admin_ctx, run_env

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx"]


def _set_run_times(engine, run_id: int, created: str, finished: str | None, rows: int | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            sa_text(
                "UPDATE RECON_REPORT_RUN SET CREATED_AT=:c, FINISHED_AT=:f, ROW_COUNT=:r WHERE ID=:i"
            ),
            {"c": created, "f": finished, "r": rows, "i": run_id},
        )


class TestListRunsJoinAndFilters:
    def test_returns_report_name_and_category(self, run_env, operator_ctx):
        from app.services.report_run import list_report_runs

        run = _make_run(operator_ctx, run_env)
        res = list_report_runs(operator_ctx)
        assert res.ok, res.message
        row = res.data["runs"][0]
        assert row["id"] == run["id"]
        assert row["report_name"] == "Doanh thu"
        assert row["category_code"] == "FIN"

    def test_filter_by_run_date(self, run_env, operator_ctx):
        from app.services.report_run import list_report_runs

        r1 = _make_run(operator_ctx, run_env)
        r2 = _make_run(operator_ctx, run_env)
        _set_run_times(run_env["engine"], r1["id"], "2026-11-01 10:00:00", "2026-11-01 10:00:05", 10)
        _set_run_times(run_env["engine"], r2["id"], "2026-11-05 10:00:00", "2026-11-05 10:00:07", 20)
        res = list_report_runs(operator_ctx, from_date="2026-11-02", to_date="2026-11-06")
        assert res.ok, res.message
        assert res.data["total"] == 1
        assert res.data["runs"][0]["id"] == r2["id"]
        res = list_report_runs(operator_ctx, from_date="2026-11-05", to_date="2026-11-05")
        assert res.data["total"] == 1  # đến ngày tính hết ngày

    def test_filter_by_category_and_name(self, run_env, operator_ctx):
        from app.services.report_run import list_report_runs

        _make_run(operator_ctx, run_env)
        res = list_report_runs(operator_ctx, category_code="FIN")
        assert res.data["total"] == 1
        res = list_report_runs(operator_ctx, category_code="OPERATIONS")
        assert res.data["total"] == 0
        res = list_report_runs(operator_ctx, report_name="doanh")
        assert res.data["total"] == 1
        res = list_report_runs(operator_ctx, report_name="không có")
        assert res.data["total"] == 0

    def test_filter_by_runner(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import list_report_runs

        r1 = _make_run(operator_ctx, run_env)
        _make_run(admin_ctx, run_env)
        res = list_report_runs(admin_ctx, created_by="operator")
        assert res.data["total"] == 1
        assert res.data["runs"][0]["id"] == r1["id"]

    def test_list_run_creators(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import list_run_creators

        _make_run(operator_ctx, run_env)
        _make_run(admin_ctx, run_env)
        res = list_run_creators(admin_ctx)
        assert res.ok, res.message
        assert sorted(res.data) == ["admin", "operator"]
        res = list_run_creators(operator_ctx)
        assert res.data == ["operator"]  # owner scope: chỉ thấy mình


class TestRunsTable43:
    def _runs(self):
        return [
            {
                "id": 19,
                "report_id": 5,
                "report_name": "Báo cáo hóa đơn",
                "category_code": "FINANCE",
                "created_by": "admin",
                "row_count": 14585,
                "status": "DONE",
                "params": {"p_from": "2026-11-01", "p_to": "2026-11-11", "p_app": "VTOS", "p_org": None},
                "created_at": datetime(2026, 11, 10, 13, 9, 56),
                "finished_at": datetime(2026, 11, 10, 13, 10, 8, 400000),
            },
            {
                "id": 18,
                "report_id": 5,
                "report_name": "Báo cáo hóa đơn",
                "category_code": "FINANCE",
                "created_by": "admin",
                "row_count": None,
                "status": "QUEUED",
                "params": {},
                "created_at": datetime(2026, 11, 10, 13, 2, 57),
                "finished_at": None,
            },
        ]

    def test_new_columns_and_formats(self, export_env, operator_ctx):
        import app.ui.pages.report_runs as page

        # Task 55: bảng là AG Grid — assert trên rowData (đã format sẵn).
        rows = page._runs_row_data(self._runs(), {})
        assert rows[0]["report"] == "Báo cáo hóa đơn"  # tên, không phải mã 5
        assert rows[0]["category"] == "Tài chính"  # nhóm FINANCE
        assert rows[0]["rows"] == "14,585"  # dòng format dấu phẩy
        assert rows[0]["started"] == "10/11/2026 13:09:56"  # bắt đầu
        assert rows[0]["finished"] == "10/11/2026 13:10:08"  # kết thúc
        assert rows[0]["duration"] == "12,4 giây"  # tổng (12.4s, dấu phẩy thập phân)
        assert "p_from=01/11/2026" in rows[0]["params"]  # tham số, ngày DD/MM/YYYY
        assert "p_org=—" in rows[0]["params"]  # tham số trống
        assert rows[1]["rows"] == "—"  # run chưa xong: dòng trống
        assert rows[1]["finished"] == "—"  # run chưa xong: kết thúc trống
        assert rows[1]["duration"] == "—"  # run chưa xong: tổng trống

    def test_file_icon_and_no_view_button(self, export_env, operator_ctx):
        import app.ui.pages.report_runs as page

        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX")
        assert exp.ok, exp.message
        engine = export_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    "UPDATE RECON_RPT_EXPORT SET STATUS='DONE', "
                    "FILE_PATH=:p, FILE_SIZE=10 WHERE ID=:i"
                ),
                {"p": "/tmp/rpt43-fake.xlsx", "i": exp.data["id"]},
            )
        runs = [dict(self._runs()[0], id=run["id"], report_id=run["report_id"])]
        exports = {run["id"]: [{"id": exp.data["id"], "status": "DONE"}]}
        # Task 55: link tải + icon Excel do renderer JS vẽ theo _export;
        # assert dữ liệu đầu vào của renderer + columnDefs (xem thêm
        # test_history_aggrid55 cho nội dung JS).
        rows = page._runs_row_data(runs, exports)
        assert rows[0]["_export"] == {"id": exp.data["id"], "status": "DONE", "progress_pct": 0}
        defs = page._runs_grid_column_defs(can_delete=True)
        by_col = {c.get("colId", c["field"]): c for c in defs}
        assert by_col["file"]["cellRenderer"] == "reconRunsFileCell"
        assert by_col["rerun_link"]["cellRenderer"] == "reconRunsRerunLink"
        assert "view" not in by_col  # bỏ nút Xem

    def test_layout_has_filters_and_page_size(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout())
        for fid in (
            "report-runs-filter-from",
            "report-runs-filter-to",
            "report-runs-filter-category",
            "report-runs-filter-name",
            "report-runs-filter-runner",
            "report-runs-page-size",
        ):
            assert fid in text, fid
        assert "Tổng" in text and "run" in text


class TestViewerRerunFrom:
    def test_layout_prefills_params_from_run(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        comp = page.layout(report_id=export_env["report_id"], rerun_from=run["id"])
        org_input = _find_by_id(comp, {"type": "viewer-param", "index": "p_org"})
        assert org_input is not None
        assert org_input.value == "HN"

    def test_layout_rerun_missing_run_shows_alert(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout(report_id=export_env["report_id"], rerun_from=999999))
        assert "Không tải được tham số" in text
