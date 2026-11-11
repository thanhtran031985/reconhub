"""Task 44: /report-runs vừa trong 1 màn hình + icon nút Chạy lại.

Root layout phải dùng calc(100vh - 48px) như các trang khác (height 100%
đẩy phân trang xuống dưới màn hình); nút Chạy lại có icon play-circle
của menu "Chạy đối soát".
"""

from __future__ import annotations

from tests.unit.test_page_report_viewer import _dump, export_env, operator_ctx
from tests.unit.test_report_run_execute import admin_ctx, run_env

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx"]


class TestFitOneScreen:
    def test_layout_height_uses_viewport_rule(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout())
        assert "calc(100vh - 48px)" in text
        # Task 55: grid AG Grid tự lấp đầy khung flex (height 100% nằm
        # TRONG data_grid, không đẩy phân trang ra ngoài như bảng cũ).
        assert "report-runs-grid" in text

    def test_rerun_button_has_menu_icon(self, export_env, operator_ctx):
        import app.ui.pages.report_runs as page

        runs = [
            {
                "id": 1,
                "report_id": 5,
                "report_name": "Báo cáo hóa đơn",
                "category_code": "FINANCE",
                "created_by": "admin",
                "row_count": 10,
                "status": "DONE",
                "params": {},
                "created_at": "2026-11-10 13:09:56",
                "finished_at": "2026-11-10 13:10:08",
            }
        ]
        # Task 55: "Chạy lại" là link do renderer JS vẽ (reconRunsRerunLink);
        # assert columnDefs có cột đó + rowData đủ _report_id để ghép URL.
        rows = page._runs_row_data(runs, {})
        assert rows[0]["_report_id"] == 5
        defs = page._runs_grid_column_defs(can_delete=True)
        by_col = {c.get("colId", c["field"]): c for c in defs}
        assert by_col["rerun_link"]["cellRenderer"] == "reconRunsRerunLink"
