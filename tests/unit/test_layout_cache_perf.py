"""Tests cho Task 104 Bước 1 — Persistent AppShell & Cache Metadata/Sidebar."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from dash.exceptions import PreventUpdate
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata, recon_app_setting
from app.services.menu_sync import sync_from_code
from app.services.perm import clear_perm_cache


@pytest.fixture()
def perf_env(tmp_path, monkeypatch):
    db_file = tmp_path / "perf_shell.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", echo=False)
    metadata.create_all(engine)
    sync_from_code(engine)
    from tests.conftest import seed_perm_basics

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                "VALUES (1, 'admin', 'Admin User', 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
            ),
            {"now": now},
        )
    seed_perm_basics(engine, {1: ["ADMIN"]})
    clear_perm_cache()

    for mod in (
        "app.services.perm",
        "app.services.data_source",
        "app.services.temp_data",
        "app.services.metadata_migration",
        "app.ui.layout.shell",
    ):
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)

    yield engine
    clear_perm_cache()


def test_persistent_shell_skips_rebuild_on_same_user_route_change(perf_env, monkeypatch) -> None:
    import app.ui.layout.shell as shell

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin User", roles=["ADMIN"])
    monkeypatch.setattr(shell, "get_current_ctx", lambda: admin_ctx)

    build_calls: list[str | None] = []
    orig_render = shell.render_app_shell

    def _spy_render(pathname, is_collapsed):
        build_calls.append(pathname)
        return orig_render(pathname, is_collapsed)

    monkeypatch.setattr(shell, "render_app_shell", _spy_render)

    # 1. Lần đầu mở trang có shell -> dựng full shell
    tree, state = shell.update_app_shell_container("/templates", False, None)
    assert state == {"mode": "shell", "user_id": 1}
    assert "app-header-breadcrumbs" in str(tree)
    assert build_calls == ["/templates"]

    # 2. Chuyển sang route khác cùng user -> PreventUpdate, không gọi render_app_shell
    with pytest.raises(PreventUpdate):
        shell.update_app_shell_container("/report-runs", False, state)
    assert build_calls == ["/templates"]

    # 3. Đổi user trong cùng session -> dựng lại shell
    tree2, state2 = shell.update_app_shell_container("/batches", False, {"mode": "shell", "user_id": 99})
    assert state2 == {"mode": "shell", "user_id": 1}
    assert build_calls == ["/templates", "/batches"]

    # 4. Vào /login -> đổi sang chế độ shellless
    tree_login, state_login = shell.update_app_shell_container("/login", False, state2)
    assert state_login == {"mode": "shellless", "user_id": 1}
    assert "AppShellHeader" not in str(tree_login)

    # 5. Chuyển qua /forgot-password khi đang shellless -> giữ nguyên (PreventUpdate)
    with pytest.raises(PreventUpdate):
        shell.update_app_shell_container("/forgot-password", False, state_login)


def test_sync_shell_on_navigate_updates_breadcrumb_navbar_and_resets_search(perf_env, monkeypatch) -> None:
    import app.ui.layout.shell as shell

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin User", roles=["ADMIN"])
    monkeypatch.setattr(shell, "get_current_ctx", lambda: admin_ctx)

    bc_children, navbar_children, search_val, search_res, search_style = shell.sync_shell_on_navigate(
        "/templates", False, {"mode": "shell", "user_id": 1}
    )
    assert "Templates" in str(bc_children)
    assert "Templates" in str(navbar_children)
    assert search_val == ""
    assert search_res == []
    assert search_style.get("display") == "none"

    # Không chạy khi chưa ở mode shell, hoặc đi vào shellless, hoặc đổi user
    with pytest.raises(PreventUpdate):
        shell.sync_shell_on_navigate("/templates", False, None)
    with pytest.raises(PreventUpdate):
        shell.sync_shell_on_navigate("/login", False, {"mode": "shell", "user_id": 1})
    with pytest.raises(PreventUpdate):
        shell.sync_shell_on_navigate("/templates", False, {"mode": "shell", "user_id": 2})


def test_sidebar_tree_and_tables_exist_cached_by_revision(perf_env, monkeypatch) -> None:
    import app.services.menu_sync as menu_sync
    import app.services.perm as perm
    import app.ui.layout.shell as shell

    inspect_calls = 0
    orig_inspect = perm.inspect

    def _spy_inspect(eng):
        nonlocal inspect_calls
        inspect_calls += 1
        return orig_inspect(eng)

    tree_reads = 0
    orig_read_tree = menu_sync.read_display_tree

    def _spy_read_tree(conn):
        nonlocal tree_reads
        tree_reads += 1
        return orig_read_tree(conn)

    monkeypatch.setattr(perm, "inspect", _spy_inspect)
    monkeypatch.setattr(shell, "inspect", _spy_inspect)
    monkeypatch.setattr(menu_sync, "read_display_tree", _spy_read_tree)

    # Gọi nhiều lần cùng revision -> chỉ inspect và đọc DB 1 lần
    assert perm._tables_exist(perf_env) is True
    assert perm._tables_exist(perf_env) is True
    t1 = shell._sidebar_tree(perf_env)
    t2 = shell._sidebar_tree(perf_env)
    assert t1 is not None and t1 == t2
    assert inspect_calls <= 2  # tối đa 1 lần cho perm + 1 lần cho shell (hoặc dùng chung 1 lần)
    assert tree_reads == 1

    # Khi xóa cache hoặc tăng revision -> nạp lại từ DB
    clear_perm_cache()
    t3 = shell._sidebar_tree(perf_env)
    assert t3 is not None
    assert tree_reads == 2


def test_get_active_environment_cached_and_invalidated(perf_env, monkeypatch) -> None:
    import app.services.data_source as ds_svc

    ds_svc.invalidate_active_environment_cache()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with perf_env.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, PORT, "
                "SERVICE_NAME, USERNAME, PASSWORD_ENC, DEFAULT_SCHEMA, CALL_TIMEOUT_S, MAX_ROWS, "
                "IS_CURRENT_METADATA, IS_ACTIVE, CREATED_BY, CREATED_AT, UPDATED_AT) "
                "VALUES ('SRC_UAT', 'UAT', 'SOURCE', 'ORACLE', '10.0.0.1', 1521, 'ORCL', "
                "'ro', 'enc', 'FIN', 30, 1000, 'N', 'Y', 'admin', :now, :now)"
            ),
            {"now": now},
        )

    assert ds_svc.get_active_environment() == "UAT"

    # Cập nhật trực tiếp DB nhưng chưa invalidate -> trả từ cache "UAT"
    with perf_env.begin() as conn:
        conn.execute(text("UPDATE RECON_DATA_SOURCE SET ENV='PROD' WHERE NAME='SRC_UAT'"))
    assert ds_svc.get_active_environment() == "UAT"

    # Sau khi invalidate -> đọc giá trị mới "PROD"
    ds_svc.invalidate_active_environment_cache()
    assert ds_svc.get_active_environment() == "PROD"


def test_render_app_shell_caches_usage_maintenance_and_avoids_double_sidebar(perf_env, monkeypatch) -> None:
    import app.ui.layout.shell as shell

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin User", roles=["ADMIN"])
    monkeypatch.setattr(shell, "get_current_ctx", lambda: admin_ctx)
    shell.invalidate_shell_meta_cache()

    usage_calls = 0

    def _fake_usage(_ctx):
        nonlocal usage_calls
        usage_calls += 1
        return SimpleNamespace(
            ok=True,
            data={"total_bytes": 3 * 1024**3, "warn_gb": 2.0, "is_warning": True},
        )

    monkeypatch.setattr(shell, "usage", _fake_usage)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with perf_env.begin() as conn:
        conn.execute(
            recon_app_setting.insert().values(
                KEY="MAINTENANCE",
                VALUE="Y",
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        )

    sidebar_calls = 0
    orig_get_nav = shell.get_nav_items_for_menus

    def _spy_get_nav(*args, **kwargs):
        nonlocal sidebar_calls
        sidebar_calls += 1
        return orig_get_nav(*args, **kwargs)

    monkeypatch.setattr(shell, "get_nav_items_for_menus", _spy_get_nav)

    # Render shell lần 1: đọc maintenance="Y", tính usage 1 lần, dựng nav_groups 1 lần dùng chung header+navbar
    tree1 = shell.render_app_shell("/templates", False)
    tree1_str = str(tree1)
    assert "Hệ thống đang bảo trì" in tree1_str
    assert "Cảnh báo dung lượng dữ liệu tạm" in tree1_str
    assert usage_calls == 1
    assert sidebar_calls == 1

    # Render shell lần 2: usage không chạy lại (đã cache 300s)
    shell.render_app_shell("/batches", False)
    assert usage_calls == 1
