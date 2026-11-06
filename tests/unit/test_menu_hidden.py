"""Tests cho áp dụng ẩn menu — Bước 2 task 20 (test viết trước).

Phạm vi: page_gate trả /suspended cho vai trò thường, ADMIN vẫn vào được
menu ẩn; sidebar ADMIN hiện menu ẩn kèm nhãn "Đang ẩn"; trang chủ bị ẩn
thì chuyển tới menu đầu tiên người dùng có (Q2).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from dash import dcc
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def hidden_env(tmp_path, monkeypatch):
    db_path = tmp_path / "menu_hidden_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod

    monkeypatch.setattr("app.services.menu_sync.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.perm.get_recon_engine", lambda: engine)
    # requires_menu lấy engine từ namespace của module chứa hàm service
    # (_engine_for), nên phải patch cả namespace của dashboard.
    monkeypatch.setattr("app.services.dashboard.get_recon_engine", lambda: engine)
    sync_mod.sync_from_code(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        role_ids: dict[str, int] = {}
        for code, is_system in [
            ("ADMIN", "Y"),
            ("TEMPLATE_OWNER", "N"),
            ("OPERATOR", "N"),
            ("VIEWER", "N"),
        ]:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_ROLE (CODE, NAME, IS_SYSTEM, IS_ACTIVE, "
                    "CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:code, :code, :sys, 'Y', 'SEED', :now, 'SEED', :now, 1)"
                ),
                {"code": code, "sys": is_system, "now": now},
            )
            role_ids[code] = int(res.lastrowid)
        from app.ui.menus import ROLE_MENUS_SEED

        for role_code, menus in ROLE_MENUS_SEED.items():
            for menu in menus:
                conn.execute(
                    text(
                        "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                        "VALUES (:rid, :menu, 'SEED', :now)"
                    ),
                    {"rid": role_ids[role_code], "menu": menu, "now": now},
                )
        users = [
            (1, "admin", "ADMIN"),
            (2, "owner", "TEMPLATE_OWNER"),
            (3, "operator", "OPERATOR"),
            (4, "viewer", "VIEWER"),
        ]
        for user_id, username, role in users:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :username, :username, 'hash', 'Y', 'N', 0, 1, "
                    "'SEED', :now, :now, 1)"
                ),
                {"id": user_id, "username": username, "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE_ID, ASSIGNED_BY, ASSIGNED_AT, CREATED_AT) "
                    "VALUES (:uid, :rid, 'SEED', :now, :now)"
                ),
                {"uid": user_id, "rid": role_ids[role], "now": now},
            )
        # Dashboard tạm ẩn; issue đã gỡ khỏi code.
        conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='Bảo trì' WHERE CODE='dashboard'"))
        conn.execute(text("UPDATE RECON_MENU SET IS_REMOVED='Y' WHERE CODE='issue'"))
    return engine


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="Operator", roles=["OPERATOR"])


def _ghost() -> Ctx:
    return Ctx(user_id=99, username="ghost", full_name="Ghost", roles=[])


def _all_hrefs(groups: list[dict]) -> list[str]:
    return [item["href"] for g in groups for item in g["items"]]


def _all_labels(groups: list[dict]) -> list[str]:
    return [item["label"] for g in groups for item in g["items"]]


class TestPageGateHidden:
    def test_operator_hidden_menu_goes_to_suspended(self, hidden_env):
        from app.services.perm import page_gate

        assert page_gate(_operator(), "dashboard") == "/suspended"

    def test_admin_hidden_menu_allowed(self, hidden_env):
        from app.services.perm import page_gate

        assert page_gate(_admin(), "dashboard") is None

    def test_operator_visible_menu_allowed(self, hidden_env):
        from app.services.perm import page_gate

        assert page_gate(_operator(), "history") is None

    def test_operator_ungranted_menu_forbidden(self, hidden_env):
        from app.services.perm import page_gate

        assert page_gate(_operator(), "template") == "/forbidden"

    def test_service_hidden_menu_error(self, hidden_env):
        from app.services.dashboard import get_dashboard_summary

        res = get_dashboard_summary(_operator())
        assert not res.ok and res.code == "MENU_HIDDEN"
        assert get_dashboard_summary(_admin()).ok


class TestSidebarHidden:
    def test_operator_sidebar_excludes_hidden(self, hidden_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        groups = get_nav_items_for_menus(effective_menus(_operator()), engine=hidden_env)
        assert "/" not in _all_hrefs(groups)

    def test_admin_sidebar_shows_hidden_with_label(self, hidden_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        groups = get_nav_items_for_menus(effective_menus(_admin()), engine=hidden_env, is_admin=True)
        assert "/" in _all_hrefs(groups)
        labels = _all_labels(groups)
        assert any("Đang ẩn" in label for label in labels)

    def test_hidden_not_shown_without_admin_flag(self, hidden_env):
        from app.ui.layout.shell import get_nav_items_for_menus

        groups = get_nav_items_for_menus({"dashboard", "history"}, engine=hidden_env)
        assert "/" not in _all_hrefs(groups)

    def test_removed_menu_never_shown_for_admin(self, hidden_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        groups = get_nav_items_for_menus(effective_menus(_admin()), engine=hidden_env, is_admin=True)
        assert "/issues" not in _all_hrefs(groups)


class TestFirstNavHref:
    def test_operator_first_menu_when_dashboard_hidden(self, hidden_env):
        from app.ui.layout.shell import first_nav_href

        assert first_nav_href(_operator(), engine=hidden_env) == "/runs/new"

    def test_admin_first_menu_is_dashboard(self, hidden_env):
        from app.ui.layout.shell import first_nav_href

        assert first_nav_href(_admin(), engine=hidden_env) == "/"

    def test_no_menus_returns_none(self, hidden_env):
        from app.ui.layout.shell import first_nav_href

        assert first_nav_href(_ghost(), engine=hidden_env) is None


def _locations(node, out=None):
    out = [] if out is None else out
    if isinstance(node, dcc.Location):
        out.append(node)
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            _locations(child, out)
    elif children is not None:
        _locations(children, out)
    return out


class TestDashboardLayoutRedirect:
    def test_dashboard_hidden_redirects_to_first_menu(self, hidden_env, monkeypatch):
        import app.ui.pages.dashboard as dash_mod

        monkeypatch.setattr(dash_mod, "get_current_ctx", lambda: _operator())
        node = dash_mod.layout()
        locs = _locations(node)
        assert len(locs) == 1
        assert locs[0].href == "/runs/new"

    def test_dashboard_visible_renders_normally(self, hidden_env, monkeypatch):
        import app.ui.pages.dashboard as dash_mod
        from app.services.perm import clear_perm_cache

        with hidden_env.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='N' WHERE CODE='dashboard'"))
        clear_perm_cache()
        monkeypatch.setattr(dash_mod, "get_current_ctx", lambda: _operator())
        node = dash_mod.layout()
        assert _locations(node) == []
