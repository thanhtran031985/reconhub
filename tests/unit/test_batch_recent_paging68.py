"""Tests cho task 68 — phân trang card "Lần chạy gần đây của bộ" (/batch-runs).

Tests-first: các test này phải đỏ trước khi code (card hiện chỉ vẽ 5 dòng
đầu, không có Pagination, không có Select cỡ trang, không có callback
phân trang).
"""

from __future__ import annotations

from types import SimpleNamespace

import dash_mantine_components as dmc
import pytest


def _run_row(i: int) -> dict:
    return {
        "id": 100 + i,
        "name": f"Run {i:02d}",
        "def_code": "DOANH_THU",
        "period": "2026-07",
        "status": "DONE",
        "created_by": "admin",
    }


def _rows(n: int) -> list[dict]:
    return [_run_row(i) for i in range(1, n + 1)]


def _texts(comp) -> list[str]:
    out: list[str] = []
    if isinstance(comp, str):
        out.append(comp)
    elif isinstance(comp, (list, tuple)):
        for c in comp:
            out.extend(_texts(c))
    elif hasattr(comp, "children"):
        out.extend(_texts(comp.children))
    return out


def _find_all(comp, typ) -> list:
    found: list = []
    if isinstance(comp, typ):
        found.append(comp)
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found.extend(_find_all(c, typ))
    elif children is not None:
        found.extend(_find_all(children, typ))
    return found


def _find_by_id(comp, target_id: str):
    if getattr(comp, "id", None) == target_id:
        return comp
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found = _find_by_id(c, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


class TestRecentRunsCardPaging:
    def test_page1_shows_first_10_and_pagination(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card(_rows(12), total=12, page=1, page_size=10)
        texts = _texts(card)
        assert "#101 Run 01" in texts
        assert "#110 Run 10" in texts
        assert "#111 Run 11" not in texts
        assert "#112 Run 12" not in texts
        assert "Hiển thị 1 – 10 trong tổng số 12 lần chạy" in texts
        pagers = _find_all(card, dmc.Pagination)
        assert len(pagers) == 1
        assert pagers[0].total == 2
        assert pagers[0].value == 1
        sel = _find_by_id(card, "brw-recent-page-size")
        assert sel is not None
        assert sel.value == "10"
        assert _find_by_id(card, "brw-recent-showing") is not None
        assert _find_by_id(card, "brw-recent-card-body") is not None

    def test_page2_shows_rest(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card(_rows(12), total=12, page=2, page_size=10)
        texts = _texts(card)
        assert "#111 Run 11" in texts
        assert "#112 Run 12" in texts
        assert "#101 Run 01" not in texts
        assert "Hiển thị 11 – 12 trong tổng số 12 lần chạy" in texts
        pagers = _find_all(card, dmc.Pagination)
        assert len(pagers) == 1
        assert pagers[0].total == 2
        assert pagers[0].value == 2

    def test_empty_shows_message_and_single_page(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card([], total=0, page=1, page_size=10)
        texts = _texts(card)
        assert "Chưa có lần chạy bộ nào." in texts
        assert "Hiển thị 0 – 0 trong tổng số 0 lần chạy" in texts
        pagers = _find_all(card, dmc.Pagination)
        assert len(pagers) == 1
        assert pagers[0].total == 1

    def test_page_clamped_to_last(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card(_rows(12), total=12, page=99, page_size=10)
        texts = _texts(card)
        assert "#111 Run 11" in texts
        assert "Hiển thị 11 – 12 trong tổng số 12 lần chạy" in texts
        pagers = _find_all(card, dmc.Pagination)
        assert pagers[0].value == 2

    def test_total_defaults_to_len(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card(_rows(3))
        texts = _texts(card)
        assert "Hiển thị 1 – 3 trong tổng số 3 lần chạy" in texts
        pagers = _find_all(card, dmc.Pagination)
        assert pagers[0].total == 1

    def test_page_size_options(self):
        from app.ui.pages.batch_run_wizard import render_recent_runs_card

        card = render_recent_runs_card(_rows(12), total=12, page=1, page_size=20)
        texts = _texts(card)
        assert "Hiển thị 1 – 12 trong tổng số 12 lần chạy" in texts
        sel = _find_by_id(card, "brw-recent-page-size")
        assert sel is not None
        assert sel.value == "20"
        values = [d["value"] for d in sel.data]
        assert values == ["10", "20", "50", "100"]


class TestRecentRunsPagingCallback:
    @pytest.fixture()
    def _mock(self, monkeypatch):
        import app.ui.pages.batch_run_wizard as page

        calls: list[dict] = []
        all_rows = _rows(12)

        def fake_list(ctx, page=1, page_size=10):
            calls.append({"page": page, "page_size": page_size})
            start = (page - 1) * page_size
            return SimpleNamespace(
                ok=True,
                data={"items": all_rows[start : start + page_size], "total": 12, "page": page, "page_size": page_size},
            )

        monkeypatch.setattr(page, "list_batch_runs", fake_list)
        monkeypatch.setattr(page, "get_current_ctx", lambda: SimpleNamespace(username="admin"))
        return page, calls

    def _mock_ctx(self, monkeypatch, triggered_id):
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id=triggered_id, triggered=[{"prop_id": "x", "value": 1}]),
        )

    def test_pagination_click_fetches_page_2(self, _mock, monkeypatch):
        page, calls = _mock
        self._mock_ctx(monkeypatch, "brw-recent-pagination")
        body, showing, total, value = page._update_recent_runs(2, "10")
        assert calls == [{"page": 2, "page_size": 10}]
        texts = _texts(body)
        assert "#111 Run 11" in texts
        assert "#112 Run 12" in texts
        assert "#101 Run 01" not in texts
        assert showing == "Hiển thị 11 – 12 trong tổng số 12 lần chạy"
        assert total == 2
        assert value == 2

    def test_page_size_change_resets_to_page_1(self, _mock, monkeypatch):
        page, calls = _mock
        self._mock_ctx(monkeypatch, "brw-recent-page-size")
        body, showing, total, value = page._update_recent_runs(2, "20")
        assert calls == [{"page": 1, "page_size": 20}]
        texts = _texts(body)
        assert "#101 Run 01" in texts
        assert "#112 Run 12" in texts
        assert showing == "Hiển thị 1 – 12 trong tổng số 12 lần chạy"
        assert total == 1
        assert value == 1

    def test_invalid_page_size_defaults_to_10(self, _mock, monkeypatch):
        page, calls = _mock
        self._mock_ctx(monkeypatch, "brw-recent-page-size")
        _body, _showing, _total, value = page._update_recent_runs(1, "999")
        assert calls == [{"page": 1, "page_size": 10}]
        assert value == 1

    def test_no_login_returns_no_update(self, _mock, monkeypatch):
        import dash

        import app.ui.pages.batch_run_wizard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: None)
        self._mock_ctx(monkeypatch, "brw-recent-pagination")
        res = page._update_recent_runs(2, "10")
        assert res == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_service_error_shows_alert(self, _mock, monkeypatch):
        import dash

        import app.ui.pages.batch_run_wizard as page

        monkeypatch.setattr(
            page, "list_batch_runs", lambda ctx, page=1, page_size=10: SimpleNamespace(ok=False, message="Lỗi DB")
        )
        self._mock_ctx(monkeypatch, "brw-recent-pagination")
        body, showing, total, value = page._update_recent_runs(2, "10")
        assert "Lỗi DB" in str(body)
        assert showing is dash.no_update
        assert total is dash.no_update
        assert value is dash.no_update
