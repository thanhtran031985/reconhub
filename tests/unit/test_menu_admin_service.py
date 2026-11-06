"""Tests cho service menu_admin — Bước 1 task 20 (test viết trước).

Admin chỉnh hiển thị menu: đổi tên/nhóm/thứ tự, tạm ẩn kèm lý do, khôi phục
mặc định, đánh dấu đã xem menu mới, xem trước thanh bên. Một lần lưu cho
mọi thay đổi, khóa lạc quan ROW_VERSION, audit, tăng PERM_REVISION.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def menus_env(tmp_path, monkeypatch):
    db_path = tmp_path / "menus_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in ["app.services.menu_sync", "app.services.perm"]:
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
        # lookup đang tạm ẩn; batch_def đã gỡ khỏi code (để kiểm tra menu gỡ)
        conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='Bảo trì' WHERE CODE='lookup'"))
        conn.execute(text("UPDATE RECON_MENU SET IS_REMOVED='Y' WHERE CODE='batch_def'"))
    perm_mod.clear_perm_cache()
    yield engine, role_ids
    perm_mod.clear_perm_cache()
    engine.dispose()


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


def _mod(monkeypatch, engine):
    import app.services.menu_admin as m

    monkeypatch.setattr(m, "get_recon_engine", lambda: engine)
    return m


def _revision(engine) -> int:
    from app.services.perm import get_perm_revision

    return get_perm_revision(engine)


def _audit_rows(engine, entity: str) -> list:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT ACTION, OLD_JSON, NEW_JSON FROM RECON_AUDIT_LOG WHERE ENTITY = :e"),
            {"e": entity},
        ).all()


def _menu_of(tree: dict, code: str) -> dict:
    for group in tree["groups"]:
        for menu in group["menus"]:
            if menu["code"] == code:
                return menu
    raise AssertionError(f"không thấy menu {code} trong cây")


def _group_of(tree: dict, code: str) -> dict:
    for group in tree["groups"]:
        if group["code"] == code:
            return group
    raise AssertionError(f"không thấy nhóm {code} trong cây")


class TestListTree:
    def test_list_tree_admin(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.list_menu_tree_admin(_admin())
        assert res.ok
        tree = res.data
        assert [g["code"] for g in tree["groups"]] == ["DOI_SOAT", "CAU_HINH", "QUAN_TRI"]
        assert [g["label"] for g in tree["groups"]] == ["Đối soát", "Cấu hình", "Quản trị"]
        total = sum(len(g["menus"]) for g in tree["groups"])
        assert total == 13
        dash = _menu_of(tree, "dashboard")
        assert dash["label"] == "Dashboard"
        assert dash["source_label"] == "Dashboard"
        assert dash["path"] == "/"
        assert dash["group"] == "DOI_SOAT"
        assert dash["role_count"] == 3  # TEMPLATE_OWNER, OPERATOR, VIEWER
        assert dash["is_hideable"] is True
        assert dash["is_hidden"] is False
        assert dash["is_new"] is True
        assert dash["changed"] is False
        assert dash["row_version"] == 1

    def test_list_tree_includes_removed_and_hidden(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        tree = m.list_menu_tree_admin(_admin()).data
        removed = _menu_of(tree, "batch_def")
        assert removed["is_removed"] is True
        hidden = _menu_of(tree, "lookup")
        assert hidden["is_hidden"] is True
        assert hidden["hidden_reason"] == "Bảo trì"
        assert _menu_of(tree, "menu_admin")["role_count"] == 0

    def test_list_tree_forbidden_for_operator(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.list_menu_tree_admin(_operator())
        assert not res.ok
        assert res.code == "FORBIDDEN"


class TestSave:
    def test_save_rename(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        before = _revision(engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}],
        )
        assert res.ok, res.message
        assert _revision(engine) == before + 1
        tree = m.list_menu_tree_admin(_admin()).data
        dash = _menu_of(tree, "dashboard")
        assert dash["label"] == "Tổng quan"
        assert dash["source_label"] == "Dashboard"
        assert dash["changed"] is True
        assert dash["row_version"] == 2
        rows = _audit_rows(engine, "RECON_MENU")
        assert any("Tổng quan" in str(r[2]) for r in rows)

    def test_save_empty_label_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "dashboard", "label": "   ", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "VALIDATION_ERROR"
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "dashboard")["label"] == "Dashboard"

    def test_save_duplicate_label_rejected_case_insensitive(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "run", "label": "DASHBOARD", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "VALIDATION_ERROR"

    def test_save_change_group_moves_to_end(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "history", "group": "CAU_HINH", "row_version": 1}],
        )
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        history = _menu_of(tree, "history")
        assert history["group"] == "CAU_HINH"
        assert history["source_group"] == "DOI_SOAT"
        orders = [x["order"] for x in _group_of(tree, "CAU_HINH")["menus"]]
        assert history["order"] == max(orders)

    def test_save_invalid_group_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "history", "group": "KHONG_CO", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "MENU_GROUP_INVALID"

    def test_save_reorder(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [
                {"kind": "menu", "code": "dashboard", "order": 20, "row_version": 1},
                {"kind": "menu", "code": "run", "order": 10, "row_version": 1},
            ],
        )
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        codes = [x["code"] for x in _group_of(tree, "DOI_SOAT")["menus"]]
        assert codes.index("run") < codes.index("dashboard")

    def test_save_hide_with_reason(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [
                {
                    "kind": "menu",
                    "code": "issue",
                    "hidden": True,
                    "hidden_reason": "Đang nâng cấp",
                    "row_version": 1,
                }
            ],
        )
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        issue = _menu_of(tree, "issue")
        assert issue["is_hidden"] is True
        assert issue["hidden_reason"] == "Đang nâng cấp"
        from app.services.perm import effective_menus

        assert "issue" not in effective_menus(_operator())
        assert "issue" in effective_menus(_admin())
        rows = _audit_rows(engine, "RECON_MENU")
        assert any("Đang nâng cấp" in str(r[2]) for r in rows)

    def test_save_hide_without_reason_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "issue", "hidden": True, "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "MENU_HIDE_REASON_REQUIRED"

    def test_save_hide_reason_too_long_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "issue", "hidden": True, "hidden_reason": "x" * 301, "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "VALIDATION_ERROR"

    def test_save_hide_not_hideable_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        for code in ["menu_admin", "role", "user"]:
            res = m.save_menu_changes(
                _admin(),
                [{"kind": "menu", "code": code, "hidden": True, "hidden_reason": "x", "row_version": 1}],
            )
            assert not res.ok, code
            assert res.code == "MENU_NOT_HIDEABLE", code

    def test_save_unhide_clears_reason(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "lookup", "hidden": False, "row_version": 1}],
        )
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        lookup = _menu_of(tree, "lookup")
        assert lookup["is_hidden"] is False
        assert lookup["hidden_reason"] is None

    def test_save_stale_version_rejected_nothing_changed(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        before = _revision(engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 99}],
        )
        assert not res.ok
        assert res.code == "STALE_DATA"
        assert _revision(engine) == before
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "dashboard")["label"] == "Dashboard"

    def test_save_unknown_menu_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "khong_co", "label": "X", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "NOT_FOUND"

    def test_save_removed_menu_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "batch_def", "label": "X", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "MENU_REMOVED"

    def test_save_many_changes_one_revision(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        before = _revision(engine)
        res = m.save_menu_changes(
            _admin(),
            [
                {"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1},
                {
                    "kind": "menu",
                    "code": "issue",
                    "hidden": True,
                    "hidden_reason": "Bảo trì",
                    "row_version": 1,
                },
                {"kind": "group", "code": "DOI_SOAT", "label": "Đối soát dữ liệu", "row_version": 1},
            ],
        )
        assert res.ok, res.message
        assert _revision(engine) == before + 1
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "dashboard")["label"] == "Tổng quan"
        assert _menu_of(tree, "issue")["is_hidden"] is True
        assert _group_of(tree, "DOI_SOAT")["label"] == "Đối soát dữ liệu"

    def test_save_group_rename_and_reorder(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [
                {"kind": "group", "code": "QUAN_TRI", "order": 10, "row_version": 1},
                {"kind": "group", "code": "DOI_SOAT", "order": 30, "row_version": 1},
            ],
        )
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        assert [g["code"] for g in tree["groups"]] == ["QUAN_TRI", "CAU_HINH", "DOI_SOAT"]

    def test_save_group_empty_label_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.save_menu_changes(
            _admin(),
            [{"kind": "group", "code": "DOI_SOAT", "label": "  ", "row_version": 1}],
        )
        assert not res.ok
        assert res.code == "VALIDATION_ERROR"


class TestReset:
    def test_reset_one_menu(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        m.save_menu_changes(
            _admin(),
            [{"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1}],
        )
        res = m.reset_menus(_admin(), "dashboard", row_version=2)
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        dash = _menu_of(tree, "dashboard")
        assert dash["label"] == "Dashboard"
        assert dash["changed"] is False

    def test_reset_one_menu_keeps_hidden(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.reset_menus(_admin(), "lookup", row_version=1)
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "lookup")["is_hidden"] is True

    def test_reset_all(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        m.save_menu_changes(
            _admin(),
            [
                {"kind": "menu", "code": "dashboard", "label": "Tổng quan", "row_version": 1},
                {"kind": "group", "code": "DOI_SOAT", "label": "Đối soát dữ liệu", "row_version": 1},
            ],
        )
        res = m.reset_menus(_admin(), "ALL")
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "dashboard")["label"] == "Dashboard"
        assert _group_of(tree, "DOI_SOAT")["label"] == "Đối soát"
        assert _menu_of(tree, "lookup")["is_hidden"] is True  # ẩn giữ nguyên


class TestMarkSeen:
    def test_mark_seen_one(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.mark_seen(_admin(), "dashboard")
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        assert _menu_of(tree, "dashboard")["is_new"] is False
        assert _menu_of(tree, "run")["is_new"] is True

    def test_mark_seen_all(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.mark_seen(_admin(), "ALL")
        assert res.ok, res.message
        tree = m.list_menu_tree_admin(_admin()).data
        assert all(not x["is_new"] for g in tree["groups"] for x in g["menus"])

    def test_mark_seen_unknown_rejected(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.mark_seen(_admin(), "khong_co")
        assert not res.ok
        assert res.code == "NOT_FOUND"


class TestPreviewSidebar:
    def test_preview_applies_unsaved_changes(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.preview_sidebar(
            _admin(),
            [
                {"kind": "menu", "code": "dashboard", "label": "Tổng quan"},
                {"kind": "menu", "code": "history", "hidden": True, "hidden_reason": "Bảo trì"},
            ],
        )
        assert res.ok, res.message
        labels = [item["label"] for g in res.data for item in g["items"]]
        assert "Tổng quan" in labels
        assert "Dashboard" not in labels
        assert "Lịch sử" not in labels
        # menu đã gỡ khỏi code không hiện
        assert "Bộ đối soát" not in labels

    def test_preview_group_rename(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.preview_sidebar(
            _admin(),
            [{"kind": "group", "code": "DOI_SOAT", "label": "Đối soát dữ liệu"}],
        )
        assert res.ok, res.message
        assert res.data[0]["title"] == "ĐỐI SOÁT DỮ LIỆU"

    def test_preview_forbidden_for_operator(self, menus_env, monkeypatch):
        engine, _ = menus_env
        m = _mod(monkeypatch, engine)
        res = m.preview_sidebar(_operator(), [])
        assert not res.ok
        assert res.code == "FORBIDDEN"
