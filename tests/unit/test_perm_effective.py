"""Tests cho tính quyền hiệu lực — Bước 3 task 19 (test viết trước)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def perm_env(tmp_path, monkeypatch):
    db_path = tmp_path / "perm_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    monkeypatch.setattr("app.db.engine.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod
    import app.services.perm as perm_mod

    monkeypatch.setattr("app.services.menu_sync.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.perm.get_recon_engine", lambda: engine)
    sync_mod.sync_from_code(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Seed vai trò + vai trò-menu từ bảng seed 11a mục 7
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
        for uid, username, role_code in users:
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
    yield engine, perm_mod
    perm_mod.clear_perm_cache()
    engine.dispose()


def _ctx(uid: int, username: str, roles: list[str]) -> Ctx:
    return Ctx(user_id=uid, username=username, full_name=username, roles=roles)


class TestEffectiveMenus:
    def test_admin_has_all_menus(self, perm_env):
        _, perm = perm_env
        assert perm.effective_menus(_ctx(1, "admin", ["ADMIN"])) == {
            m.code for m in __import__("app.ui.menus", fromlist=["MENUS"]).MENUS
        }

    def test_owner_menus(self, perm_env):
        _, perm = perm_env
        assert perm.effective_menus(_ctx(2, "owner", ["TEMPLATE_OWNER"])) == {
            "dashboard",
            "run",
            "result",
            "batch_run",
            "history",
            "issue",
            "template",
            "batch_def",
            "report_center",
            "report_history",
        }

    def test_operator_menus(self, perm_env):
        _, perm = perm_env
        assert perm.effective_menus(_ctx(3, "operator", ["OPERATOR"])) == {
            "dashboard",
            "run",
            "result",
            "batch_run",
            "history",
            "issue",
            "report_center",
            "report_history",
        }

    def test_viewer_menus(self, perm_env):
        _, perm = perm_env
        assert perm.effective_menus(_ctx(4, "viewer", ["VIEWER"])) == {
            "dashboard",
            "result",
            "history",
            "template",
            "batch_def",
            "report_center",
            "report_history",
        }

    def test_inactive_user_has_no_menus(self, perm_env):
        engine, perm = perm_env
        with engine.begin() as conn:
            conn.execute(text("UPDATE RECON_USER SET IS_ACTIVE='N' WHERE USERNAME='operator'"))
        assert perm.effective_menus(_ctx(3, "operator", ["OPERATOR"])) == set()

    def test_hidden_menu_excluded_for_non_admin_kept_for_admin(self, perm_env):
        engine, perm = perm_env
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='Tạm ẩn để kiểm thử', "
                    "HIDDEN_BY='admin', HIDDEN_AT=:now WHERE CODE='issue'"
                ),
                {"now": datetime.now(timezone.utc).replace(tzinfo=None)},
            )
            conn.execute(text("UPDATE RECON_APP_SETTING SET VALUE='2' WHERE KEY='PERM_REVISION'"))
        assert "issue" not in perm.effective_menus(_ctx(3, "operator", ["OPERATOR"]))
        assert "issue" in perm.effective_menus(_ctx(1, "admin", ["ADMIN"]))

    def test_removed_menu_excluded_for_everyone(self, perm_env):
        engine, perm = perm_env
        with engine.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET IS_REMOVED='Y' WHERE CODE='issue'"))
            conn.execute(text("UPDATE RECON_APP_SETTING SET VALUE='2' WHERE KEY='PERM_REVISION'"))
        assert "issue" not in perm.effective_menus(_ctx(3, "operator", ["OPERATOR"]))
        assert "issue" not in perm.effective_menus(_ctx(1, "admin", ["ADMIN"]))

    def test_revision_bump_invalidates_cache(self, perm_env):
        engine, perm = perm_env
        assert "issue" in perm.effective_menus(_ctx(3, "operator", ["OPERATOR"]))
        with engine.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='x' WHERE CODE='issue'"))
            conn.execute(text("UPDATE RECON_APP_SETTING SET VALUE='2' WHERE KEY='PERM_REVISION'"))
        # Cache revision đọc tối đa 1 lần/giây, menu cache 5 giây: xóa cache
        # để mô phỏng thời gian đã trôi qua.
        perm.clear_perm_cache()
        assert "issue" not in perm.effective_menus(_ctx(3, "operator", ["OPERATOR"]))

    def test_unknown_user_falls_back_to_ctx_roles(self, perm_env):
        _, perm = perm_env
        # ctx nội bộ (CLI/worker) không có user trong DB
        assert perm.effective_menus(_ctx(1, "cli_admin", ["ADMIN"])) == {
            m.code for m in __import__("app.ui.menus", fromlist=["MENUS"]).MENUS
        }
        assert perm.effective_menus(_ctx(9, "system", ["OPERATOR"])) == {
            "dashboard",
            "run",
            "result",
            "batch_run",
            "history",
            "issue",
            "report_center",
            "report_history",
        }

    def test_is_admin(self, perm_env):
        _, perm = perm_env
        assert perm.is_admin(_ctx(1, "admin", ["ADMIN"])) is True
        assert perm.is_admin(_ctx(3, "operator", ["OPERATOR"])) is False

    def test_require_admin_raises(self, perm_env):
        from app.schemas.errors import ServiceError

        _, perm = perm_env
        perm.require_admin(_ctx(1, "admin", ["ADMIN"]))
        with pytest.raises(ServiceError) as exc:
            perm.require_admin(_ctx(3, "operator", ["OPERATOR"]))
        assert exc.value.code == "FORBIDDEN"

    def test_requires_menu_decorator(self, perm_env):
        from app.services import service
        from app.services.perm import requires_menu

        _, perm = perm_env

        @service
        @requires_menu("template")
        def _fn(ctx: Ctx) -> str:
            return "ok"

        assert _fn(_ctx(2, "owner", ["TEMPLATE_OWNER"])).ok
        res = _fn(_ctx(3, "operator", ["OPERATOR"]))
        assert not res.ok and res.code == "FORBIDDEN"

    def test_requires_menu_hidden_code(self, perm_env):
        from app.services import service
        from app.services.perm import requires_menu

        engine, perm = perm_env
        with engine.begin() as conn:
            conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='x' WHERE CODE='issue'"))
            conn.execute(text("UPDATE RECON_APP_SETTING SET VALUE='2' WHERE KEY='PERM_REVISION'"))

        @service
        @requires_menu("issue")
        def _fn(ctx: Ctx) -> str:
            return "ok"

        res = _fn(_ctx(3, "operator", ["OPERATOR"]))
        assert not res.ok and res.code == "MENU_HIDDEN"

    def test_requires_menu_any_of(self, perm_env):
        from app.services import service
        from app.services.perm import requires_menu

        _, perm = perm_env

        @service
        @requires_menu("template", "issue", any_of=True)
        def _fn(ctx: Ctx) -> str:
            return "ok"

        assert _fn(_ctx(3, "operator", ["OPERATOR"])).ok  # có issue
        assert _fn(_ctx(4, "viewer", ["VIEWER"])).ok  # có template
        res = _fn(_ctx(1, "admin", ["ADMIN"]))
        assert res.ok

    def test_owner_filter(self, perm_env):
        _, perm = perm_env
        assert perm.owner_filter(_ctx(1, "admin", ["ADMIN"])) == {
            "is_admin": True,
            "username": None,
        }
        assert perm.owner_filter(_ctx(3, "operator", ["OPERATOR"])) == {
            "is_admin": False,
            "username": "operator",
        }
