"""Tests cho hiển thị theo DISPLAY_* — Bước 3 task 20 (test viết trước).

Phạm vi: thanh bên dùng tên/nhóm/thứ tự hiển thị từ DB (kèm nhãn Mới
cho ADMIN); màn Vai trò khôi phục nhãn Mới, xem trước dùng tên hiển thị;
role.update tự bỏ nhãn Mới cho menu vừa bật cho vai trò (Q7).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def display_env(tmp_path, monkeypatch):
    db_path = tmp_path / "menu_display_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod

    monkeypatch.setattr("app.services.menu_sync.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.perm.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.menu_admin.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.role.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.ui.layout.shell.get_recon_engine", lambda: engine)
    sync_mod.sync_from_code(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    role_ids: dict[str, int] = {}
    with engine.begin() as conn:
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
        for uid, username, role_code in [
            (1, "admin", "ADMIN"),
            (3, "operator", "OPERATOR"),
            (4, "viewer", "VIEWER"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE_ID, ASSIGNED_BY, ASSIGNED_AT, CREATED_AT) "
                    "VALUES (:id, :rid, 'SEED', :now, :now)"
                ),
                {"id": uid, "rid": role_ids[role_code], "now": now},
            )
        # Tắt hết nhãn Mới để từng test bật có chủ đích.
        conn.execute(text("UPDATE RECON_MENU SET IS_NEW='N'"))
    return engine, role_ids


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="Operator", roles=["OPERATOR"])


def _viewer() -> Ctx:
    return Ctx(user_id=4, username="viewer", full_name="Viewer", roles=["VIEWER"])


def _sidebar(ctx: Ctx, engine, is_admin: bool) -> list[dict]:
    from app.services.perm import effective_menus
    from app.ui.layout.shell import get_nav_items_for_menus

    return get_nav_items_for_menus(effective_menus(ctx), engine=engine, is_admin=is_admin)


def _titles(groups: list[dict]) -> list[str]:
    return [g["title"] for g in groups]


def _group(groups: list[dict], title: str) -> dict:
    return next(g for g in groups if g["title"] == title)


def _labels(group: dict) -> list[str]:
    return [item["label"] for item in group["items"]]


def _hrefs(group: dict) -> list[str]:
    return [item["href"] for item in group["items"]]


def _set_new(engine, code: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE RECON_MENU SET IS_NEW='Y' WHERE CODE=:c"), {"c": code})


def _is_new(engine, code: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT IS_NEW FROM RECON_MENU WHERE CODE=:c"), {"c": code}).scalar_one()
    return row == "Y"


def _dump(component) -> str:
    def conv(obj):
        if hasattr(obj, "to_plotly_json"):
            return obj.to_plotly_json()
        if isinstance(obj, (list, tuple)):
            return [conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        return obj

    return json.dumps(conv(component), ensure_ascii=False, default=str)


class TestSidebarDisplayValues:
    def test_sidebar_uses_display_label(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes

        res = save_menu_changes(
            _admin(), [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}]
        )
        assert res.ok
        assert "Tổng quan" in _labels(_group(_sidebar(_admin(), engine, True), "ĐỐI SOÁT"))
        assert "Dashboard" not in _labels(_group(_sidebar(_operator(), engine, False), "ĐỐI SOÁT"))

    def test_sidebar_group_move(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes

        res = save_menu_changes(_admin(), [{"kind": "menu", "code": "history", "group": "CAU_HINH", "row_version": 1}])
        assert res.ok
        groups = _sidebar(_admin(), engine, True)
        assert "Lịch sử" not in _labels(_group(groups, "ĐỐI SOÁT"))
        assert _labels(_group(groups, "CẤU HÌNH"))[-1] == "Lịch sử"

    def test_sidebar_group_rename(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes

        res = save_menu_changes(
            _admin(),
            [{"kind": "group", "code": "DOI_SOAT", "label": "Đối soát dữ liệu", "row_version": 1}],
        )
        assert res.ok
        assert "ĐỐI SOÁT DỮ LIỆU" in _titles(_sidebar(_admin(), engine, True))

    def test_sidebar_menu_reorder(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes

        res = save_menu_changes(
            _admin(),
            [
                {"kind": "menu", "code": "run", "order": 5, "row_version": 1},
                {"kind": "menu", "code": "history", "order": 15, "row_version": 1},
            ],
        )
        assert res.ok
        hrefs = _hrefs(_group(_sidebar(_operator(), engine, False), "ĐỐI SOÁT"))
        # Task 27 (Q8): 3 menu report đã hiện ở thanh bên (order 70/80).
        assert hrefs == ["/runs/new", "/", "/history", "/issues", "/reports", "/report-runs"]

    def test_sidebar_empty_group_hidden(self, display_env):
        engine, _ = display_env

        assert "QUẢN TRỊ" not in _titles(_sidebar(_viewer(), engine, False))

    def test_sidebar_reset_restores_source_label(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import reset_menus, save_menu_changes

        assert save_menu_changes(
            _admin(), [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}]
        ).ok
        assert "Tổng quan" in _labels(_group(_sidebar(_admin(), engine, True), "ĐỐI SOÁT"))
        assert reset_menus(_admin(), "dashboard", row_version=2).ok
        labels = _labels(_group(_sidebar(_admin(), engine, True), "ĐỐI SOÁT"))
        assert "Dashboard" in labels and "Tổng quan" not in labels

    def test_admin_sidebar_new_badge(self, display_env):
        engine, _ = display_env
        _set_new(engine, "history")

        admin_items = _group(_sidebar(_admin(), engine, True), "ĐỐI SOÁT")["items"]
        history = next(i for i in admin_items if i["href"] == "/history")
        dashboard = next(i for i in admin_items if i["href"] == "/")
        assert history.get("is_new") is True
        assert "is_new" not in dashboard
        op_items = _group(_sidebar(_operator(), engine, False), "ĐỐI SOÁT")["items"]
        op_history = next(i for i in op_items if i["href"] == "/history")
        assert "is_new" not in op_history

    def test_sidebar_hidden_label_kept(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes

        assert save_menu_changes(
            _admin(),
            [
                {
                    "kind": "menu",
                    "code": "lookup",
                    "hidden": True,
                    "hidden_reason": "Bảo trì",
                    "row_version": 1,
                }
            ],
        ).ok
        labels = _labels(_group(_sidebar(_admin(), engine, True), "CẤU HÌNH"))
        assert "Danh mục hệ thống (Đang ẩn)" in labels
        # Operator không có menu nào ở nhóm Cấu hình nên nhóm này ẩn hẳn.
        assert "CẤU HÌNH" not in _titles(_sidebar(_operator(), engine, False))


class TestRolesNewBadge:
    def test_roles_checkboxes_show_new_badge(self, display_env):
        engine, role_ids = display_env
        _set_new(engine, "template")
        from app.ui.pages.roles import render_menu_checkboxes

        text_out = _dump(render_menu_checkboxes(_admin(), role_ids["OPERATOR"]))
        assert "Mới" in text_out

    def test_roles_checkboxes_no_new_badge_when_none_new(self, display_env):
        engine, role_ids = display_env
        from app.ui.pages.roles import render_menu_checkboxes

        assert "Mới" not in _dump(render_menu_checkboxes(_admin(), role_ids["OPERATOR"]))

    def test_roles_preview_uses_display_label(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes
        from app.ui.pages.roles import render_sidebar_preview

        assert save_menu_changes(
            _admin(), [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}]
        ).ok
        text_out = _dump(render_sidebar_preview(_admin(), ["dashboard", "history"]))
        assert "Tổng quan" in text_out and "Dashboard" not in text_out

    def test_roles_preview_admin_shows_hidden(self, display_env):
        engine, _ = display_env
        from app.services.menu_admin import save_menu_changes
        from app.ui.pages.roles import render_sidebar_preview

        assert save_menu_changes(
            _admin(),
            [
                {
                    "kind": "menu",
                    "code": "dashboard",
                    "hidden": True,
                    "hidden_reason": "Bảo trì",
                    "row_version": 1,
                }
            ],
        ).ok
        assert "Dashboard (Đang ẩn)" in _dump(render_sidebar_preview(_admin(), ["dashboard", "history"], is_admin=True))
        assert "Dashboard" not in _dump(render_sidebar_preview(_admin(), ["dashboard", "history"]))


class TestRoleUpdateClearsNew:
    def test_update_role_clears_new_for_newly_granted(self, display_env):
        engine, role_ids = display_env
        _set_new(engine, "template")
        _set_new(engine, "lookup")
        from app.services.role import get_role, update_role

        old = get_role(_admin(), role_ids["OPERATOR"]).data
        menus = list(old["menus"]) + ["template"]
        assert update_role(_admin(), role_ids["OPERATOR"], menus=menus).ok
        assert not _is_new(engine, "template")
        assert _is_new(engine, "lookup")

    def test_update_role_name_only_keeps_new(self, display_env):
        engine, role_ids = display_env
        _set_new(engine, "template")
        from app.services.role import update_role

        assert update_role(_admin(), role_ids["OPERATOR"], name="Operator mới").ok
        assert _is_new(engine, "template")

    def test_create_role_clears_new_for_granted(self, display_env):
        engine, _ = display_env
        _set_new(engine, "template")
        from app.services.role import create_role

        assert create_role(_admin(), "TESTER", "Tester", menus=["template"]).ok
        assert not _is_new(engine, "template")
