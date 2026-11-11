"""Task 53: Lịch sử báo cáo không vẽ lại bảng khi tick 10s mà dữ liệu không đổi."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import dash

from app.core.context import Ctx
from app.ui.pages.report_runs import _runs_fingerprint, handle_runs_refresh

ADMIN = Ctx(
    user_id=1,
    username="admin",
    full_name="Admin",
    roles=frozenset({"ADMIN"}),
    permissions=frozenset(),
)

RUNS = [
    {
        "id": 1,
        "report_id": 1,
        "status": "DONE",
        "row_count": 55,
        "created_at": "2026-11-01 10:00:00",
        "finished_at": "2026-11-01 10:00:05",
        "report_name": "BC RM Updated",
    }
]
EXPORTS = {1: [{"id": 1, "status": "QUEUED", "progress_pct": 0}]}


def _fingerprint(**overrides: Any) -> str:
    runs = overrides.get("runs", RUNS)
    exports = overrides.get("exports", EXPORTS)
    total = overrides.get("total", 1)
    page = overrides.get("page", 1)
    return _runs_fingerprint(runs, exports, total, page)


class TestFingerprint:
    def test_same_data_same_fingerprint(self):
        assert _fingerprint() == _fingerprint()

    def test_run_status_change(self):
        runs = [dict(RUNS[0], status="RUNNING")]
        assert _fingerprint(runs=runs) != _fingerprint()

    def test_row_count_change(self):
        runs = [dict(RUNS[0], row_count=56)]
        assert _fingerprint(runs=runs) != _fingerprint()

    def test_finished_at_change(self):
        runs = [dict(RUNS[0], finished_at="2026-11-01 10:00:06")]
        assert _fingerprint(runs=runs) != _fingerprint()

    def test_export_status_change(self):
        exports = {1: [{"id": 1, "status": "RUNNING", "progress_pct": 10}]}
        assert _fingerprint(exports=exports) != _fingerprint()

    def test_export_progress_change(self):
        exports = {1: [{"id": 1, "status": "RUNNING", "progress_pct": 45}]}
        assert _fingerprint(exports=exports) != _fingerprint()

    def test_total_or_page_change(self):
        assert _fingerprint(total=2) != _fingerprint()
        assert _fingerprint(page=2) != _fingerprint()

    def test_report_name_not_in_fingerprint(self):
        # Tên/nhóm/tham số không đổi sau khi tạo nên không đưa vào vân tay.
        runs = [dict(RUNS[0], report_name="Tên khác")]
        assert _fingerprint(runs=runs) == _fingerprint()


def _call_refresh(monkeypatch, triggered_id, last_fingerprint, loader=None):
    """Gọi handle_runs_refresh trực tiếp với callback_context giả."""
    monkeypatch.setattr("app.ui.pages.report_runs.get_current_ctx", lambda: ADMIN)
    monkeypatch.setattr(
        "app.ui.pages.report_runs._load_page_data",
        loader or (lambda *a, **k: (RUNS, 1, EXPORTS)),
    )
    monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered_id=triggered_id))
    return handle_runs_refresh(
        1, "50", None, None, "all", "", "all", None, 1, 1, None, 0, 1, last_fingerprint
    )


class TestRefreshGate:
    def test_interval_tick_unchanged_returns_no_update(self, monkeypatch):
        out = _call_refresh(monkeypatch, "report-runs-auto-refresh", _fingerprint())
        assert len(out) == 11
        assert all(item is dash.no_update for item in out), out

    def test_interval_tick_changed_rerenders(self, monkeypatch):
        out = _call_refresh(monkeypatch, "report-runs-auto-refresh", "khac")
        assert out[0] is not dash.no_update
        assert out[9] == _fingerprint()

    def test_first_tick_rerenders(self, monkeypatch):
        # Store vân tay mới khởi tạo "" → tick đầu luôn vẽ lại.
        out = _call_refresh(monkeypatch, "report-runs-auto-refresh", "")
        assert out[0] is not dash.no_update
        assert out[9] == _fingerprint()

    def test_manual_refresh_button_forces_rerender(self, monkeypatch):
        out = _call_refresh(monkeypatch, "report-runs-refresh-btn", _fingerprint())
        assert out[0] is not dash.no_update
        assert out[9] == _fingerprint()

    def test_filter_change_rerenders(self, monkeypatch):
        out = _call_refresh(monkeypatch, "report-runs-filter-name", _fingerprint())
        assert out[0] is not dash.no_update

    def test_error_branch_keeps_fingerprint(self, monkeypatch):
        def _raise(*a, **k):
            raise ValueError("Không tải được lịch sử.")

        out = _call_refresh(
            monkeypatch, "report-runs-auto-refresh", _fingerprint(), loader=_raise
        )
        assert out[9] is dash.no_update
        assert out[0] == []  # task 55: grid rỗng khi lỗi
        assert "Không tải được" in str(out[10])  # task 55: lỗi vào alert
