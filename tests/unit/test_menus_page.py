"""Tests cho helper thuần của màn /menus — Bước 4 task 20 (test viết trước).

Phạm vi: tính diff lưu (kèm row_version), mô tả thay đổi cho hộp thoại
Lưu, danh sách menu bỏ nhãn Mới, dựng bảng nhóm+menu (lọc/tìm, vạch tím
dòng đổi, nút lên/xuống khóa ở đầu/cuối).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata
from app.ui.pages.menus import describe_changes, diff_changes, new_flips, render_menus_table


def _saved() -> dict:
    return {
        "groups": [
            {
                "code": "DOI_SOAT",
                "label": "Đối soát",
                "source_label": "Đối soát",
                "order": 10,
                "source_order": 10,
                "is_removed": False,
                "row_version": 1,
                "changed": False,
                "menus": [
                    {
                        "code": "dashboard",
                        "label": "Dashboard",
                        "source_label": "Dashboard",
                        "path": "/",
                        "icon": "lucide:layout-dashboard",
                        "group": "DOI_SOAT",
                        "source_group": "DOI_SOAT",
                        "order": 10,
                        "source_order": 10,
                        "is_hideable": True,
                        "is_hidden": False,
                        "hidden_reason": None,
                        "is_new": True,
                        "is_removed": False,
                        "row_version": 1,
                        "role_count": 3,
                        "changed": False,
                    },
                    {
                        "code": "history",
                        "label": "Lịch sử",
                        "source_label": "Lịch sử",
                        "path": "/history",
                        "icon": "lucide:history",
                        "group": "DOI_SOAT",
                        "source_group": "DOI_SOAT",
                        "order": 50,
                        "source_order": 50,
                        "is_hideable": True,
                        "is_hidden": False,
                        "hidden_reason": None,
                        "is_new": False,
                        "is_removed": False,
                        "row_version": 1,
                        "role_count": 3,
                        "changed": False,
                    },
                ],
            },
            {
                "code": "CAU_HINH",
                "label": "Cấu hình",
                "source_label": "Cấu hình",
                "order": 20,
                "source_order": 20,
                "is_removed": False,
                "row_version": 1,
                "changed": False,
                "menus": [
                    {
                        "code": "lookup",
                        "label": "Danh mục hệ thống",
                        "source_label": "Danh mục hệ thống",
                        "path": "/lookups",
                        "icon": "lucide:list",
                        "group": "CAU_HINH",
                        "source_group": "CAU_HINH",
                        "order": 40,
                        "source_order": 40,
                        "is_hideable": True,
                        "is_hidden": False,
                        "hidden_reason": None,
                        "is_new": False,
                        "is_removed": False,
                        "row_version": 1,
                        "role_count": 0,
                        "changed": False,
                    },
                ],
            },
        ],
        "revision": 1,
    }


def _draft() -> dict:
    import copy

    return copy.deepcopy(_saved())


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


class TestDiffChanges:
    def test_no_changes_empty(self):
        assert diff_changes(_saved(), _draft()) == []

    def test_rename_menu(self):
        saved, draft = _saved(), _draft()
        draft["groups"][0]["menus"][0]["label"] = "Tổng quan"
        changes = diff_changes(saved, draft)
        assert changes == [
            {
                "kind": "menu",
                "code": "dashboard",
                "label": "Tổng quan",
                "row_version": 1,
            }
        ]

    def test_hide_menu_with_reason(self):
        saved, draft = _saved(), _draft()
        menu = draft["groups"][0]["menus"][1]
        menu["is_hidden"] = True
        menu["hidden_reason"] = "Bảo trì"
        changes = diff_changes(saved, draft)
        assert changes == [
            {
                "kind": "menu",
                "code": "history",
                "hidden": True,
                "hidden_reason": "Bảo trì",
                "row_version": 1,
            }
        ]

    def test_unhide_menu(self):
        saved, draft = _saved(), _draft()
        menu = draft["groups"][1]["menus"][0]
        menu["is_hidden"] = True
        menu["hidden_reason"] = "Bảo trì"
        saved["groups"][1]["menus"][0]["is_hidden"] = True
        saved["groups"][1]["menus"][0]["hidden_reason"] = "Bảo trì"
        menu["is_hidden"] = False
        menu["hidden_reason"] = None
        changes = diff_changes(saved, draft)
        assert changes == [{"kind": "menu", "code": "lookup", "hidden": False, "row_version": 1}]

    def test_group_move_sends_group_and_order(self):
        saved, draft = _saved(), _draft()
        menu = draft["groups"][0]["menus"][1]
        menu["group"] = "CAU_HINH"
        menu["order"] = 60
        changes = diff_changes(saved, draft)
        assert changes == [
            {
                "kind": "menu",
                "code": "history",
                "group": "CAU_HINH",
                "order": 60,
                "row_version": 1,
            }
        ]

    def test_group_rename(self):
        saved, draft = _saved(), _draft()
        draft["groups"][0]["label"] = "Đối soát dữ liệu"
        changes = diff_changes(saved, draft)
        assert changes == [
            {
                "kind": "group",
                "code": "DOI_SOAT",
                "label": "Đối soát dữ liệu",
                "row_version": 1,
            }
        ]

    def test_new_flag_change_not_in_save_payload(self):
        saved, draft = _saved(), _draft()
        draft["groups"][0]["menus"][0]["is_new"] = False
        assert diff_changes(saved, draft) == []
        assert new_flips(saved, draft) == ["dashboard"]


class TestDescribeChanges:
    def test_describes_each_change(self):
        saved, draft = _saved(), _draft()
        draft["groups"][0]["menus"][0]["label"] = "Tổng quan"
        draft["groups"][0]["menus"][1]["is_hidden"] = True
        draft["groups"][0]["menus"][1]["hidden_reason"] = "Bảo trì"
        lines = describe_changes(saved, draft)
        assert any("Dashboard" in line and "Tổng quan" in line for line in lines)
        assert any("Lịch sử" in line and "ẩn" in line for line in lines)

    def test_empty_when_no_changes(self):
        assert describe_changes(_saved(), _draft()) == []


class TestRenderMenusTable:
    def test_renders_groups_and_menus(self):
        text = _dump(render_menus_table(_saved(), _draft(), q="", filter_value="all"))
        assert "Đối soát" in text
        assert "Dashboard" in text
        assert "Lịch sử" in text
        assert "Danh mục hệ thống" in text
        assert "Mặc định: Dashboard" in text

    def test_changed_row_marked(self):
        draft = _draft()
        draft["groups"][0]["menus"][0]["label"] = "Tổng quan"
        text = _dump(render_menus_table(_saved(), draft, q="", filter_value="all"))
        assert "Tổng quan" in text

    def test_search_filters_rows(self):
        text = _dump(render_menus_table(_saved(), _draft(), q="lịch", filter_value="all"))
        assert "Lịch sử" in text
        assert "Dashboard" not in text

    def test_filter_hidden(self):
        draft = _draft()
        draft["groups"][0]["menus"][1]["is_hidden"] = True
        draft["groups"][0]["menus"][1]["hidden_reason"] = "Bảo trì"
        text = _dump(render_menus_table(_saved(), draft, q="", filter_value="hidden"))
        assert "Lịch sử" in text
        assert "Dashboard" not in text

    def test_filter_new(self):
        text = _dump(render_menus_table(_saved(), _draft(), q="", filter_value="new"))
        assert "Dashboard" in text
        assert "Lịch sử" not in text

    def test_empty_filter_state(self):
        text = _dump(render_menus_table(_saved(), _draft(), q="không-có", filter_value="all"))
        assert "Không có menu khớp bộ lọc" in text

    def test_first_menu_up_disabled_last_down_disabled(self):
        def _find(node, target_id, out):
            node_id = getattr(node, "id", None)
            if node_id == target_id:
                out.append(node)
            children = getattr(node, "children", None)
            if isinstance(children, (list, tuple)):
                for child in children:
                    _find(child, target_id, out)
            elif children is not None:
                _find(children, target_id, out)

        comp = render_menus_table(_saved(), _draft(), q="", filter_value="all")
        up_first: list = []
        _find(comp, {"type": "menus-menu-up", "index": "dashboard"}, up_first)
        assert up_first and up_first[0].disabled is True
        down_last: list = []
        _find(comp, {"type": "menus-menu-down", "index": "history"}, down_last)
        assert down_last and down_last[0].disabled is True
        up_second: list = []
        _find(comp, {"type": "menus-menu-up", "index": "history"}, up_second)
        assert up_second and up_second[0].disabled is not True


# ---------- Layout với DB thật (kiểm tra nội dung HTTP không thấy được) ----------


@pytest.fixture()
def menus_env(tmp_path, monkeypatch):
    db_path = tmp_path / "menus_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.menu_admin",
        "app.ui.layout.shell",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod
    import app.services.perm as perm_mod

    sync_mod.sync_from_code(engine)
    perm_mod.clear_perm_cache()
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
    perm_mod.clear_perm_cache()
    yield engine
    perm_mod.clear_perm_cache()
    engine.dispose()


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


class TestMenusLayout:
    def test_layout_renders_for_admin(self, menus_env, monkeypatch):
        import app.ui.pages.menus as menus_page

        monkeypatch.setattr(menus_page, "get_current_ctx", lambda: _admin())
        text = _dump(menus_page.layout())
        assert "Danh sách menu" in text
        assert "Tìm menu" in text
        assert "Dashboard" in text
        assert "menu mới" in text
        assert "Xem trước thanh bên" in text

    def test_layout_forbidden_for_operator(self, menus_env, monkeypatch):
        import app.ui.pages.menus as menus_page

        monkeypatch.setattr(menus_page, "get_current_ctx", lambda: _operator())
        text = _dump(menus_page.layout())
        assert "/forbidden" in text
        assert "Tìm menu" not in text

    def test_layout_hidden_menu_shows_reason(self, menus_env, monkeypatch):
        import app.ui.pages.menus as menus_page
        from app.services.menu_admin import save_menu_changes

        assert save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "lookup", "hidden": True, "hidden_reason": "Bảo trì", "row_version": 1}],
        ).ok
        monkeypatch.setattr(menus_page, "get_current_ctx", lambda: _admin())
        text = _dump(menus_page.layout())
        assert "Đang ẩn" in text
        assert "Bảo trì" in text

    def test_layout_removed_menu_shows_note(self, menus_env, monkeypatch):
        import app.ui.pages.menus as menus_page

        with menus_env.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET IS_REMOVED='Y' WHERE CODE='batch_def'"))
        monkeypatch.setattr(menus_page, "get_current_ctx", lambda: _admin())
        dumped = _dump(menus_page.layout())
        assert "Đã gỡ khỏi code" in dumped

    def test_layout_rename_reflected(self, menus_env, monkeypatch):
        import app.ui.pages.menus as menus_page
        from app.services.menu_admin import save_menu_changes

        assert save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}],
        ).ok
        monkeypatch.setattr(menus_page, "get_current_ctx", lambda: _admin())
        text = _dump(menus_page.layout())
        assert "Tổng quan" in text

    def test_sidebar_has_menus_link_for_admin(self, menus_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        items = get_nav_items_for_menus(effective_menus(_admin()), is_admin=True)
        hrefs = [item["href"] for g in items for item in g["items"]]
        assert "/menus" in hrefs

    def test_sidebar_no_menus_link_for_operator(self, menus_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        items = get_nav_items_for_menus(effective_menus(_operator()), is_admin=False)
        hrefs = [item["href"] for g in items for item in g["items"]]
        assert "/menus" not in hrefs

    def test_preview_follows_draft_rename(self, menus_env):
        import app.ui.pages.menus as menus_page
        from app.services.menu_admin import list_menu_tree_admin

        tree = list_menu_tree_admin(_admin()).data
        draft = copy.deepcopy(tree)
        draft["groups"][0]["menus"][0]["label"] = "Tổng quan"
        text = _dump(menus_page.render_menus_preview(_admin(), tree, draft))
        assert "Tổng quan" in text
        assert "Dashboard" not in text
