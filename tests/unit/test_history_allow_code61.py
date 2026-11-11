"""Tests cho task 61 — grid Lịch sử báo cáo thiếu dangerously_allow_code.

Nguyên nhân: dash-ag-grid 35.3.1 chặn chuỗi ở vị trí hàm khi grid thiếu
cờ này; grid /report-runs truyền overlayNoRowsTemplate là chuỗi tĩnh
("Chưa có run nào...") qua dashGridOptions nên mỗi lần mở trang console
báo: {prop: overlayNoRowsTemplate} Blocked a string that AG Grid would
evaluate... (chỉ console.error, không throw — check cũ chỉ quét pageerror
nên lọt từ task 55). Viewer và admin grid đã có cờ này từ task 39.
"""

from __future__ import annotations

from tests.unit.test_page_report_viewer import _find_by_id
from tests.unit.test_report_export_queue import export_env, run_env
from tests.unit.test_report_run_execute import admin_ctx, operator_ctx

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx"]


class TestRunsGridAllowCode:
    def test_grid_has_dangerously_allow_code(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        grid = _find_by_id(page.layout(), "report-runs-grid")
        assert grid is not None
        assert getattr(grid, "dangerously_allow_code", False) is True

    def test_empty_overlay_text_kept(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_runs as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        grid = _find_by_id(page.layout(), "report-runs-grid")
        assert grid is not None
        options = getattr(grid, "dashGridOptions", {}) or {}
        assert options.get("overlayNoRowsTemplate", "").startswith("Chưa có run nào.")
