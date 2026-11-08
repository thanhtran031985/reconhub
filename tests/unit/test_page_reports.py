"""Tests cho trang Trung tâm báo cáo — Bước 1 task 27 (test viết trước).

T27-01 (search/category/favorite), T27-02 (active only).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata
from tests.conftest import seed_perm_basics


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def reports_env(tmp_path, monkeypatch):
    db_path = tmp_path / "reports.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.report import create_report
    from app.services.report_template import create_template

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator"), (3, "norole")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]})
    reports = {}
    for code, name, cat in [
        ("FIN_REVENUE", "Báo cáo doanh thu", "FINANCE"),
        ("FIN_AR", "Báo cáo công nợ", "FINANCE"),
        ("ACC_INV", "Báo cáo hóa đơn", "ACCOUNTING"),
    ]:
        res = create_report(
            _admin(),
            {
                "code": code,
                "name": name,
                "category_code": cat,
                "owner": "FIN",
                "description": f"Mô tả {name}",
            },
        )
        assert res.ok, res.message
        reports[code] = res.data
        create_template(
            _admin(),
            res.data["id"],
            {
                "code": f"{code}_D",
                "name": "Chi tiết",
                "display_order": 10,
                "timeout_sec": 300,
                "preview_max_rows": 100,
                "export_max_rows": 1000000,
                "source_type": "CUSTOM_SQL",
                "sql_text": "SELECT amount FROM fin_revenue",
            },
        )
    # Báo cáo ẩn + báo cáo không active (user thường không thấy — T27-02).
    hidden = create_report(
        _admin(),
        {
            "code": "HIDDEN_RPT",
            "name": "Báo cáo ẩn",
            "category_code": "FINANCE",
            "owner": "FIN",
            "is_visible": False,
        },
    )
    assert hidden.ok, hidden.message
    reports["HIDDEN_RPT"] = hidden.data
    return {"engine": engine, "reports": reports}


def _dump(component) -> str:
    """Chuỗi hoá component Dash để assert nội dung hiển thị."""
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


class TestFilter:
    def test_search_by_name_code_desc(self, reports_env):
        import app.ui.pages.reports as page

        reports = [
            {"id": 1, "code": "FIN_REVENUE", "name": "Báo cáo doanh thu",
             "description": "Chi tiết doanh thu", "category_code": "FINANCE",
             "is_favorite": False, "template_count": 1},
            {"id": 2, "code": "FIN_AR", "name": "Báo cáo công nợ",
             "description": "Công nợ phải thu", "category_code": "FINANCE",
             "is_favorite": True, "template_count": 2},
        ]
        assert len(page._filter_reports(reports, "doanh thu", "all", False)) == 1
        assert len(page._filter_reports(reports, "fin_ar", "all", False)) == 1
        assert len(page._filter_reports(reports, "phải thu", "all", False)) == 1
        assert len(page._filter_reports(reports, "", "all", False)) == 2
        assert len(page._filter_reports(reports, "không có", "all", False)) == 0

    def test_category_and_favorite_filter(self, reports_env):
        import app.ui.pages.reports as page

        reports = [
            {"id": 1, "code": "A", "name": "A", "description": "",
             "category_code": "FINANCE", "is_favorite": False, "template_count": 1},
            {"id": 2, "code": "B", "name": "B", "description": "",
             "category_code": "ACCOUNTING", "is_favorite": True, "template_count": 1},
        ]
        assert len(page._filter_reports(reports, "", "ACCOUNTING", False)) == 1
        assert len(page._filter_reports(reports, "", "all", True)) == 1
        assert len(page._filter_reports(reports, "", "FINANCE", True)) == 0

    def test_handle_reports_filter(self, reports_env):
        import app.ui.pages.reports as page

        reports = [
            {"id": 1, "code": "A", "name": "Báo cáo A", "description": "",
             "category_code": "FINANCE", "is_favorite": False, "template_count": 1},
            {"id": 2, "code": "B", "name": "Báo cáo B", "description": "",
             "category_code": "ACCOUNTING", "is_favorite": True, "template_count": 1},
        ]
        body, meta = page.handle_reports_filter("Báo cáo A", "all", False, reports)
        text = _dump(body)
        assert "Báo cáo A" in text
        assert "Báo cáo B" not in text
        assert meta == "1 báo cáo"


class TestLayout:
    def test_layout_admin_sees_all_and_create_button(
        self, reports_env, monkeypatch
    ):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _admin())
        text = _dump(page.layout())
        assert "Trung tâm báo cáo" in text
        assert "FIN_REVENUE" in text
        assert "Báo cáo ẩn" in text  # ADMIN thấy cả report ẩn
        assert "Đăng ký báo cáo" in text

    def test_layout_operator_active_only_no_create(
        self, reports_env, monkeypatch
    ):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _operator())
        text = _dump(page.layout())
        assert "FIN_REVENUE" in text
        assert "Báo cáo ẩn" not in text  # T27-02
        assert "Đăng ký báo cáo" not in text

    def test_layout_forbidden_for_norole(self, reports_env, monkeypatch):
        import app.ui.pages.reports as page

        norole = Ctx(user_id=3, username="norole", full_name="norole", roles=[])
        monkeypatch.setattr(page, "get_current_ctx", lambda: norole)
        text = _dump(page.layout())
        assert "không có quyền" in text

    def test_sections_grouped_by_category(self, reports_env, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _operator())
        text = _dump(page.layout())
        assert "Tài chính" in text
        assert "Kế toán" in text

    def test_empty_state(self, reports_env, monkeypatch):
        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _operator())
        text = _dump(page.render_reports_sections([]))
        assert "Không có báo cáo phù hợp." in text


class TestFavoriteToggle:
    def test_toggle_favorite_updates_store(self, reports_env, monkeypatch):
        from types import SimpleNamespace

        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _operator())
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(
                triggered=[{"prop_id": "x.n_clicks"}],
                triggered_id={"type": "reports-fav-btn", "index": 1},
            ),
        )
        store = [
            {"id": 1, "code": "FIN_REVENUE", "name": "Báo cáo doanh thu",
             "description": "", "category_code": "FINANCE",
             "is_favorite": False, "template_count": 1},
        ]
        out = page.handle_favorite_toggle([1], store)
        assert out[0]["is_favorite"] is True
        # Bấm lần 2 → bỏ yêu thích.
        out = page.handle_favorite_toggle([1], out)
        assert out[0]["is_favorite"] is False

    def test_toggle_without_click_noop(self, reports_env, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.reports as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: _operator())
        with pytest.raises(PreventUpdate):
            page.handle_favorite_toggle([None], [])
        with pytest.raises(PreventUpdate):
            page.handle_favorite_toggle([0], [])
