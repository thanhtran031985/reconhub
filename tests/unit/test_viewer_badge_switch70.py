"""Tests task 70 — viewer: cỡ trang dạng badge, chế độ xuất dạng switch.

- Cỡ trang: dmc.SegmentedControl (giữ id viewer-page-size, value chuỗi
  "50"/"100"/"200", mặc định "50"); đổi cỡ trang vẫn về trang 1.
- Chế độ xuất: dmc.Switch label "Chạy ngầm", tắt = Xuất ngay (mặc định),
  bật = Chạy ngầm; callback xuất map checked -> "background".
"""

from __future__ import annotations

import dash_mantine_components as dmc

from tests.unit.test_export_background52 import (
    _click,
    _run_store,
    admin_ctx,
    export_env,
    operator_ctx,
    run_env,
)
from tests.unit.test_report_export_queue import _done_run, _request
from tests.unit.test_report_viewer_fixes40 import _dump, _find_by_id

__all__ = ["export_env", "operator_ctx", "run_env", "admin_ctx"]


class TestPageSizeSegmentedControl:
    def test_layout_page_size_is_segmented_control(self, export_env, operator_ctx, monkeypatch):
        """Cỡ trang là SegmentedControl 3 mức, mặc định "50"."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout(export_env["report_id"])
        control = _find_by_id(tree, "viewer-page-size")
        assert control is not None
        assert isinstance(control, dmc.SegmentedControl)
        assert control.value == "50"
        assert [(d["label"], d["value"]) for d in (control.data or [])] == [
            ("50 dòng/trang", "50"),
            ("100 dòng/trang", "100"),
            ("200 dòng/trang", "200"),
        ]

    def test_page_size_change_resets_to_page_1(self):
        """Đổi cỡ trang qua SegmentedControl vẫn về trang 1."""
        import app.ui.pages.report_viewer as page

        assert page.handle_page_size_change("100") == 1
        assert page.handle_page_size_change("200") == 1


class TestExportModeSwitch:
    def test_layout_export_mode_is_switch(self, export_env, operator_ctx, monkeypatch):
        """Chế độ xuất là Switch "Chạy ngầm", mặc định tắt (= Xuất ngay)."""
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        tree = page.layout(export_env["report_id"])
        control = _find_by_id(tree, "viewer-export-mode")
        assert control is not None
        assert isinstance(control, dmc.Switch)
        assert control.label == "Chạy ngầm"
        assert control.checked is False

    def test_switch_on_runs_background(self, export_env, operator_ctx, monkeypatch):
        """Bật switch (checked=True) -> chạy ngầm: QUEUED, không poll, không tải."""
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

    def test_switch_off_runs_now(self, export_env, operator_ctx, monkeypatch):
        """Tắt switch (checked=False) -> xuất ngay: vẫn poll như cũ."""
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
