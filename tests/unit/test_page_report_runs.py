"""Tests cho trang Lịch sử báo cáo — Bước 2 task 27 (test viết trước).

T27-06 (server pagination lịch sử), Q4 (Chạy lại với tham số cũ).
"""

from __future__ import annotations

from app.core.context import Ctx
from tests.unit.test_page_report_viewer import _dump
from tests.unit.test_report_export_queue import (
    _done_run,
    _request,
    export_env,
    run_env,
)
from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
)

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


class TestRunsLayout:
    def test_operator_sees_only_own_runs(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        own = _done_run(operator_ctx, export_env)
        other = _done_run(
            Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"]),
            export_env,
        )
        text = _dump(page.layout())
        assert f"#{own['id']}" in text
        assert f"#{other['id']}" not in text
        assert "Lịch sử báo cáo" in text

    def test_admin_sees_all_runs(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        admin = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin)
        own = _done_run(operator_ctx, export_env)
        other = _done_run(admin, export_env)
        text = _dump(page.layout())
        assert f"#{own['id']}" in text
        assert f"#{other['id']}" in text

    def test_forbidden_for_norole(self, export_env, norole_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: norole_ctx)
        text = _dump(page.layout())
        assert "không có quyền" in text

    def test_empty_state(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout())
        assert "Chưa có run nào." in text


class TestRunsTable:
    def test_actions_and_file_link(self, export_env, operator_ctx, monkeypatch):
        from sqlalchemy import text as sa_text

        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        exp = _request(operator_ctx, export_env, run["id"], "XLSX")
        assert exp.ok, exp.message
        # Đánh DONE + file giả để hiện link tải.
        engine = export_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    "UPDATE RECON_RPT_EXPORT SET STATUS='DONE', "
                    "FILE_PATH=:p, FILE_SIZE=10 WHERE ID=:i"
                ),
                {"p": "/tmp/rpt27-fake.xlsx", "i": exp.data["id"]},
            )
        runs = [{"id": run["id"], "report_id": run["report_id"],
                 "report_code": "FIN_REVENUE", "created_by": "operator",
                 "row_count": 3, "status": "DONE", "created_at": "2026-11-06"}]
        exports = {run["id"]: [{"id": exp.data["id"], "status": "DONE"}]}
        text = _dump(page.render_runs_table(runs, exports))
        assert "Chạy lại" in text
        assert f"?rerun_from={run['id']}" in text
        # Task 43: bỏ nút Xem, nút tải thành icon Excel + mũi tên xuống
        # (tooltip "Tải file Excel" vẫn có, nhưng không còn link chữ).
        assert "children='Tải file'" not in text
        assert "file-spreadsheet" in text
        assert f"/download/report-export/{exp.data['id']}" in text

    def test_no_file_when_no_done_export(self, export_env, operator_ctx):
        import app.ui.pages.report_runs as page

        runs = [{"id": 7, "report_id": 1, "report_code": "FIN_REVENUE",
                 "created_by": "operator", "row_count": None,
                 "status": "QUEUED", "created_at": "2026-11-06"}]
        text = _dump(page.render_runs_table(runs, {}))
        assert "—" in text


class TestRerun:
    """Task 43: 'Chạy lại' không chạy luôn nữa — chỉ là link sang viewer
    với ?rerun_from= để điền sẵn tham số (người dùng tự bấm Xem)."""

    def test_rerun_is_link_to_viewer(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        orig = _done_run(operator_ctx, export_env)
        text = _dump(page.layout())
        assert f"/reports/{orig['report_id']}?rerun_from={orig['id']}" in text
        assert not hasattr(page, "handle_rerun")
