"""Tests cho service vai trò — Bước 5 task 19 (test viết trước)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def role_env(tmp_path, monkeypatch):
    db_path = tmp_path / "role_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in ["app.services.menu_sync", "app.services.perm", "app.services.role"]:
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
    yield engine, role_ids
    perm_mod.clear_perm_cache()
    engine.dispose()


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


class TestListRoles:
    def test_list_roles_admin(self, role_env):
        from app.services.role import list_roles

        _, role_ids = role_env
        res = list_roles(_admin())
        assert res.ok
        codes = {r["code"] for r in res.data}
        assert codes == {"ADMIN", "TEMPLATE_OWNER", "OPERATOR", "VIEWER"}
        admin_row = next(r for r in res.data if r["code"] == "ADMIN")
        assert admin_row["is_system"] is True
        assert admin_row["user_count"] == 1
        op_row = next(r for r in res.data if r["code"] == "OPERATOR")
        assert sorted(op_row["menus"]) == [
            "batch_run",
            "dashboard",
            "history",
            "issue",
            "report_center",
            "report_history",
            "result",
            "run",
        ]

    def test_list_roles_forbidden_for_operator(self, role_env):
        from app.services.role import list_roles

        res = list_roles(_operator())
        assert not res.ok and res.code == "FORBIDDEN"


class TestCreateRole:
    def test_create_role(self, role_env):
        from app.services.role import create_role

        res = create_role(_admin(), code="auditor", name="Kiểm toán viên", menus=["dashboard", "result"])
        assert res.ok, res.message
        assert res.data["code"] == "AUDITOR"
        assert sorted(res.data["menus"]) == ["dashboard", "result"]

    def test_create_duplicate_code(self, role_env):
        from app.services.role import create_role

        res = create_role(_admin(), code="OPERATOR", name="Tên khác")
        assert not res.ok and res.code == "ROLE_CODE_EXISTS"

    def test_create_duplicate_name(self, role_env):
        from app.services.role import create_role

        res = create_role(_admin(), code="NEW_X", name="OPERATOR")
        assert not res.ok and res.code == "ROLE_NAME_EXISTS"

    def test_create_invalid_code(self, role_env):
        from app.services.role import create_role

        res = create_role(_admin(), code="vai trò mới", name="Tên")
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_create_unknown_menu(self, role_env):
        from app.services.role import create_role

        res = create_role(_admin(), code="NEW_X", name="Tên", menus=["khong_co"])
        assert not res.ok and res.code == "VALIDATION_ERROR"


class TestUpdateRole:
    def test_update_menus_changes_effective(self, role_env):
        from app.services.perm import effective_menus
        from app.services.role import get_role, update_role

        _, role_ids = role_env
        op_id = role_ids["OPERATOR"]
        before = get_role(_admin(), op_id)
        assert before.ok
        res = update_role(
            _admin(),
            op_id,
            name="Chuyên viên đối soát",
            menus=["dashboard", "result", "history"],
            row_version=before.data["row_version"],
        )
        assert res.ok, res.message
        assert sorted(res.data["menus"]) == ["dashboard", "history", "result"]
        assert effective_menus(_operator()) == {"dashboard", "result", "history"}

    def test_update_stale_row_version(self, role_env):
        from app.services.role import update_role

        _, role_ids = role_env
        res = update_role(_admin(), role_ids["OPERATOR"], name="Tên mới", row_version=99)
        assert not res.ok and res.code == "STALE_DATA"

    def test_update_system_role_locked(self, role_env):
        from app.services.role import update_role

        _, role_ids = role_env
        res = update_role(_admin(), role_ids["ADMIN"], name="Tên khác", row_version=1)
        assert not res.ok and res.code == "ROLE_SYSTEM_LOCKED"
        res = update_role(_admin(), role_ids["ADMIN"], menus=["dashboard"], row_version=1)
        assert not res.ok and res.code == "ROLE_SYSTEM_LOCKED"

    def test_update_role_audit_records_before_after(self, role_env):
        from app.services.role import update_role

        engine, role_ids = role_env
        update_role(_admin(), role_ids["OPERATOR"], menus=["dashboard"], row_version=1)
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT OLD_JSON, NEW_JSON FROM RECON_AUDIT_LOG "
                        "WHERE ENTITY='ROLE' AND ACTION='UPDATE_ROLE' ORDER BY ID DESC LIMIT 1"
                    )
                )
                .mappings()
                .first()
            )
        assert row is not None
        assert "result" in str(row["OLD_JSON"])
        assert "result" not in str(row["NEW_JSON"])


class TestDeleteAndClone:
    def test_delete_role_in_use(self, role_env):
        from app.services.role import delete_role

        _, role_ids = role_env
        res = delete_role(_admin(), role_ids["OPERATOR"])
        assert not res.ok and res.code == "ROLE_IN_USE"

    def test_delete_unused_role(self, role_env):
        from app.services.role import create_role, delete_role

        created = create_role(_admin(), code="TMP_X", name="Tạm")
        assert created.ok
        res = delete_role(_admin(), created.data["id"])
        assert res.ok

    def test_delete_system_role_locked(self, role_env):
        from app.services.role import delete_role

        _, role_ids = role_env
        res = delete_role(_admin(), role_ids["ADMIN"])
        assert not res.ok and res.code == "ROLE_SYSTEM_LOCKED"

    def test_clone_role(self, role_env):
        from app.services.role import clone_role

        _, role_ids = role_env
        res = clone_role(_admin(), role_ids["OPERATOR"], new_code="OPERATOR_2", new_name="Chuyên viên 2")
        assert res.ok, res.message
        assert sorted(res.data["menus"]) == [
            "batch_run",
            "dashboard",
            "history",
            "issue",
            "report_center",
            "report_history",
            "result",
            "run",
        ]


class TestUsersAndEffective:
    def test_users_of_role(self, role_env):
        from app.services.role import users_of

        _, role_ids = role_env
        res = users_of(_admin(), role_ids["OPERATOR"])
        assert res.ok
        assert [u["username"] for u in res.data] == ["operator"]

    def test_effective_of_user(self, role_env):
        from app.services.role import effective_of_user

        res = effective_of_user(_admin(), 3)
        assert res.ok
        assert set(res.data["menus"]) == {
            "dashboard",
            "run",
            "result",
            "batch_run",
            "history",
            "issue",
            "report_center",
            "report_history",
        }
        assert res.data["roles"] == ["OPERATOR"]
