"""Tests cho trang /roles và thanh bên theo menu — Bước 6 task 19 (test viết trước)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def roles_env(tmp_path, monkeypatch):
    db_path = tmp_path / "roles_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.role",
        "app.services.user",
        "app.services.run_service",
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
        # Tạm ẩn menu lookup để kiểm tra nhãn "Đang ẩn" ở trang /roles
        conn.execute(text("UPDATE RECON_MENU SET IS_HIDDEN='Y', HIDDEN_REASON='Bảo trì' WHERE CODE='lookup'"))
        # 2 run: run 1 của admin, run 2 của operator (cho tab mô phỏng)
        from app.db.metadata import recon_data_source, recon_run, recon_template

        conn.execute(
            recon_template.insert().values(
                ID=1,
                CODE="TPL1",
                NAME="Template 1",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_data_source.insert().values(
                ID=1,
                NAME="DS1",
                ENV="UAT",
                PURPOSE="RECON",
                DB_TYPE="ORACLE",
                CREATED_BY="SEED",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        for rid, creator in [(1, "admin"), (2, "operator")]:
            conn.execute(
                recon_run.insert().values(
                    ID=rid,
                    TEMPLATE_ID=1,
                    TEMPLATE_VERSION=1,
                    DATA_SOURCE_ID=1,
                    PROFILE_CODE="P1",
                    P_FROM=now,
                    P_TO=now,
                    PARAMS_JSON={},
                    CREATED_BY=creator,
                    CREATED_AT=now,
                    STATUS="DONE",
                )
            )
    perm_mod.clear_perm_cache()
    yield engine, role_ids
    perm_mod.clear_perm_cache()
    engine.dispose()


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


def _operator() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


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


class TestRolesLayout:
    def test_layout_renders_for_admin(self, roles_env, monkeypatch):
        import app.ui.pages.roles as roles_page

        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        layout = roles_page.layout()
        text = _dump(layout)
        assert "Vai trò và phân quyền" in text
        assert "Quyền thực tế của người dùng" in text
        assert "Mô phỏng phạm vi dữ liệu" in text
        assert "Vai trò thường: chỉ thấy run do mình chạy" in text
        assert "Phạm vi dữ liệu và thao tác đặc biệt" not in text
        assert "OPERATOR" in text
        assert "Thêm vai trò" in text

    def test_layout_forbidden_for_operator(self, roles_env, monkeypatch):
        import app.ui.pages.roles as roles_page

        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _operator())
        layout = roles_page.layout()
        assert _dump(layout).find("/forbidden") >= 0

    def test_roles_list_search_filters(self, roles_env):
        import app.ui.pages.roles as roles_page

        comp = roles_page.render_roles_list(_admin(), q="oper")
        text = _dump(comp)
        assert "OPERATOR" in text
        assert "VIEWER" not in text

    def test_menu_checkboxes_from_db(self, roles_env):
        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        comp = roles_page.render_menu_checkboxes(_admin(), role_ids["OPERATOR"])
        text = _dump(comp)
        for code in ["dashboard", "run", "result", "history", "issue", "template", "user", "role"]:
            assert code in text, f"thiếu checkbox menu {code}"
        assert "Đang ẩn" in text  # menu_admin đang ẩn nhưng vẫn gán được
        assert "Mới" in text

    def test_effective_panel(self, roles_env):
        import app.ui.pages.roles as roles_page

        comp = roles_page.render_effective_panel(_admin(), 3)
        text = _dump(comp)
        assert "operator" in text
        assert "OPERATOR" in text
        assert "dashboard" in text

    def test_sim_panel_scoped(self, roles_env):
        import app.ui.pages.roles as roles_page

        comp = roles_page.render_sim_panel(_admin(), 3)
        text = _dump(comp)
        assert "Run #2" in text
        assert "Run #1" not in text


class TestSidebarFromMenus:
    def test_admin_sidebar_has_roles_no_menu_admin(self, roles_env):
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        groups = get_nav_items_for_menus(effective_menus(_admin()))
        hrefs = [it["href"] for g in groups for it in g["items"]]
        assert "/roles" in hrefs
        assert "/users" in hrefs
        assert "/menus" not in hrefs  # menu_admin đang ẩn (Q7)
        assert "/batch-runs" not in hrefs  # task 18 chưa làm
        assert "/runs/<id>" not in hrefs  # trang chi tiết, không lên thanh bên

    def test_viewer_sidebar_scoped(self, roles_env):
        from app.core.context import Ctx as _Ctx
        from app.services.perm import effective_menus
        from app.ui.layout.shell import get_nav_items_for_menus

        viewer = _Ctx(user_id=4, username="viewer", full_name="viewer", roles=["VIEWER"])
        groups = get_nav_items_for_menus(effective_menus(viewer))
        hrefs = [it["href"] for g in groups for it in g["items"]]
        assert "/templates" in hrefs
        assert "/users" not in hrefs
        assert "/roles" not in hrefs
        assert "/runs/new" not in hrefs

    def test_shell_layout_has_revision_interval(self, roles_env):
        from app.ui.layout.shell import create_shell_layout

        text = _dump(create_shell_layout())
        assert "app-perm-revision-check" in text
        assert "app-perm-revision" in text


class TestRolesDetailRemountGuards:
    """Bug /roles: click chọn vai trò vẽ lại cột chi tiết nên các nút trong
    cột bị tạo lại, Dash kích hoạt lại callback của chúng với n_clicks=None
    -> mở modal xóa/lưu và nhân bản vai trò dù người dùng không bấm gì.
    Các callback này phải chặn n_clicks rỗng như handle_create_modal."""

    def test_delete_modal_stays_closed_without_click(self):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.roles as roles_page

        with pytest.raises(PreventUpdate):
            roles_page.handle_delete_modal(None, None, False)

    def test_delete_modal_opens_on_real_click(self, monkeypatch):
        from types import SimpleNamespace

        import app.ui.pages.roles as roles_page

        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id="roles-delete-btn"),
        )
        assert roles_page.handle_delete_modal(1, None, False) is True
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id="roles-delete-modal-cancel"),
        )
        assert roles_page.handle_delete_modal(None, 1, True) is False

    def test_save_modal_stays_closed_without_click(self, roles_env, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        res = roles_page.get_role(_admin(), role_ids["OPERATOR"])
        snapshot = roles_page._role_snapshot(_admin(), res.data)
        with pytest.raises(PreventUpdate):
            roles_page.handle_save_modal_open(None, role_ids["OPERATOR"], "OPERATOR", "", True, [], snapshot)

    def test_clone_does_not_run_without_click(self, roles_env, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.roles as roles_page

        engine, role_ids = roles_env
        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        with engine.connect() as conn:
            before = conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar_one()
        with pytest.raises(PreventUpdate):
            roles_page.handle_clone_role(None, role_ids["OPERATOR"])
        with engine.connect() as conn:
            after = conn.execute(text("SELECT COUNT(*) FROM RECON_ROLE")).scalar_one()
        assert after == before

    def test_clone_runs_on_real_click(self, roles_env, monkeypatch):
        import app.ui.pages.roles as roles_page

        engine, role_ids = roles_env
        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        roles_page.handle_clone_role(1, role_ids["OPERATOR"])
        with engine.connect() as conn:
            codes = [r[0] for r in conn.execute(text("SELECT CODE FROM RECON_ROLE"))]
        assert "OPERATOR_2" in codes

    def test_discard_stays_put_without_click(self, roles_env, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        with pytest.raises(PreventUpdate):
            roles_page.handle_discard_role(None, role_ids["OPERATOR"])

    def test_select_all_menus_stays_put_without_click(self, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.roles as roles_page

        with pytest.raises(PreventUpdate):
            roles_page.handle_select_all_menus(None, None)

    def test_select_all_menus_runs_on_real_click(self, roles_env, monkeypatch):
        from types import SimpleNamespace

        import app.ui.pages.roles as roles_page

        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id="roles-select-all-menus"),
        )
        codes = roles_page.handle_select_all_menus(1, None)
        assert "dashboard" in codes
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id="roles-deselect-all-menus"),
        )
        assert roles_page.handle_select_all_menus(None, 1) == []


class TestRolesSidebarPreview:
    """Preview thanh bên phải lấy đúng menu hiệu lực (ADMIN hệ thống
    không lưu dòng role_menu nhưng luôn có mọi menu) và ghi chú các
    menu đã chọn nhưng không có mục trên thanh bên."""

    def test_admin_detail_preview_shows_all_sidebar_menus(self, roles_env):
        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        text = _dump(roles_page.render_role_detail(_admin(), role_ids["ADMIN"]))
        assert "Không thấy menu nào ở thanh bên." not in text
        for label in ["Dashboard", "Chạy đối soát", "Lịch sử", "Templates", "Người dùng", "Vai trò và phân quyền"]:
            assert label in text, f"preview ADMIN thiếu {label}"

    def test_admin_detail_preview_notes_non_sidebar_menus(self, roles_env):
        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        text = _dump(roles_page.render_role_detail(_admin(), role_ids["ADMIN"]))
        assert "Không hiện ở thanh bên" in text
        assert "Kết quả run" in text

    def test_preview_lists_only_sidebar_items_and_notes_rest(self, roles_env):
        import app.ui.pages.roles as roles_page

        comp = roles_page.render_sidebar_preview(_admin(), ["dashboard", "result", "batch_run"])
        text = _dump(comp)
        assert "Dashboard" in text
        assert "Lịch sử" not in text
        assert "Không hiện ở thanh bên" in text
        assert "Kết quả run" in text
        assert "Chạy bộ đối soát" in text

    def test_preview_empty_role_shows_empty_note(self, roles_env):
        import app.ui.pages.roles as roles_page

        text = _dump(roles_page.render_sidebar_preview(_admin(), []))
        assert "Không thấy menu nào ở thanh bên." in text
        assert "Không hiện ở thanh bên" not in text

    def test_preview_follows_live_selection(self, roles_env, monkeypatch):
        import app.ui.pages.roles as roles_page

        _, role_ids = roles_env
        monkeypatch.setattr(roles_page, "get_current_ctx", lambda: _admin())
        res = roles_page.get_role(_admin(), role_ids["OPERATOR"])
        snapshot = roles_page._role_snapshot(_admin(), res.data)
        _, _, _, preview = roles_page.handle_role_form_change(
            "OPERATOR",
            "",
            True,
            ["dashboard", "run", "result", "batch_run", "history", "issue"],
            snapshot,
            role_ids["OPERATOR"],
        )
        assert "Lịch sử" in _dump(preview)
        _, _, _, preview2 = roles_page.handle_role_form_change(
            "OPERATOR",
            "",
            True,
            ["dashboard", "run", "result", "batch_run", "issue"],
            snapshot,
            role_ids["OPERATOR"],
        )
        assert "Lịch sử" not in _dump(preview2)
