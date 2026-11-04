from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_login_log, recon_user, recon_user_role
from app.schemas.errors import ErrorCode
from app.services.user import (
    set_active,
    unlock_user,
)


@pytest.fixture
def users_env(monkeypatch, tmp_path):
    db_file = tmp_path / "page_users_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        # 1 Admin
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                EMAIL="admin@reconhub.vn",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=1,
                ROLE="ADMIN",
                CREATED_AT=now,
            )
        )
        # 1 Operator locked
        locked_time = now + timedelta(minutes=15)
        conn.execute(
            recon_user.insert().values(
                ID=2,
                USERNAME="operator_locked",
                FULL_NAME="Nguyễn Văn Khóa",
                EMAIL="locked@reconhub.vn",
                PASSWORD_HASH=hash_password("pw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                FAILED_COUNT=5,
                LOCKED_UNTIL=locked_time,
                SESSION_VERSION=1,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=2,
                ROLE="OPERATOR",
                CREATED_AT=now,
            )
        )
        # Login log for operator
        conn.execute(
            recon_login_log.insert().values(
                USER_ID=2,
                USERNAME="operator_locked",
                SUCCESS="N",
                IP="10.0.8.21",
                REASON="WRONG_PASSWORD",
                CREATED_AT=now,
            )
        )
        # 1 Inactive user
        conn.execute(
            recon_user.insert().values(
                ID=3,
                USERNAME="user_disabled",
                FULL_NAME="Lê Thị Tắt",
                EMAIL=None,
                PASSWORD_HASH=hash_password("pw123"),
                IS_ACTIVE="N",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=3,
                ROLE="VIEWER",
                CREATED_AT=now,
            )
        )

    return db_url


def test_users_layout_renders_for_admin(users_env, monkeypatch):
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.users.get_current_ctx", lambda: admin_ctx)

    from app.ui.pages.users import layout

    content = layout()
    assert content is not None
    s = str(content)
    assert "users-page-root" in s
    assert "users-search-input" in s
    assert "users-role-filter" in s
    assert "users-status-filter" in s
    assert "users-add-btn" in s


def test_login_history_table_looks_like_a_table() -> None:
    from types import SimpleNamespace

    from app.ui.pages.users import _render_login_history_table

    logs = SimpleNamespace(
        ok=True,
        data=[
            {"CREATED_AT": "2026-11-04 08:00:00", "SUCCESS": "Y", "IP": "127.0.0.1"},
            {"CREATED_AT": "2026-11-04 07:00:00", "SUCCESS": "N", "IP": None},
        ],
    )
    table = _render_login_history_table(logs)
    text = str(table)
    assert "Thời gian" in text and "Kết quả" in text and "IP" in text
    assert "Thành công" in text and "Sai mật khẩu" in text
    # Nền header + kẻ dòng: 2 thứ khiến bảng nhìn ra bảng.
    assert "var(--bg-subtle" in text
    assert "borderBottom" in text

    empty = _render_login_history_table(SimpleNamespace(ok=True, data=[]))
    assert "Chưa có lịch sử đăng nhập" in str(empty)


def _find_parent_of(node: object, target_id: str) -> object | None:
    children = getattr(node, "children", None)
    if isinstance(children, list):
        for child in children:
            if getattr(child, "id", None) == target_id:
                return node
            found = _find_parent_of(child, target_id)
            if found is not None:
                return found
    elif children is not None and not isinstance(children, str):
        if getattr(children, "id", None) == target_id:
            return node
        return _find_parent_of(children, target_id)
    return None


def test_users_drawer_save_cancel_buttons_are_sticky(users_env, monkeypatch):
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.users.get_current_ctx", lambda: admin_ctx)

    from app.ui.pages.users import layout

    content = layout()
    footer = _find_parent_of(content, "users-drawer-save-btn")
    assert footer is not None
    style = getattr(footer, "style", None) or {}
    assert style.get("position") == "sticky"
    assert style.get("bottom") == 0


def test_users_forbidden_for_non_admin(users_env, monkeypatch):
    viewer_ctx = Ctx(user_id=2, username="operator_locked", full_name="Nguyễn Văn Khóa", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.users.get_current_ctx", lambda: viewer_ctx)

    from app.ui.pages.users import layout

    content = layout()
    s = str(content)
    # Should redirect or render forbidden notice
    assert "/forbidden" in s or "Không có quyền" in s or "dcc.Location" in s


def test_render_users_table_states(users_env, monkeypatch):
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.users.get_current_ctx", lambda: admin_ctx)

    from app.ui.pages.users import render_users_table

    # Normal state with users
    table = render_users_table(admin_ctx, q=None, role=None, status_filter=None)
    assert table is not None
    s = str(table)
    assert "admin" in s
    assert "operator_locked" in s
    assert "user_disabled" in s
    assert "Tạm khóa đến" in s
    assert "Đã tắt" in s

    # Empty state (search with non-matching query)
    empty_content = render_users_table(admin_ctx, q="nonexistent_user_xyz", role=None, status_filter=None)
    s_empty = str(empty_content)
    assert "Chỉ có tài khoản của bạn" in s_empty or "Không tìm thấy" in s_empty


def test_last_admin_protection_and_unlock(users_env, monkeypatch):
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.users.get_current_ctx", lambda: admin_ctx)

    # 1. Admin attempts to disable the only active admin
    res = set_active(admin_ctx, 1, is_active=False)
    assert not res.ok
    assert res.code == ErrorCode.LAST_ADMIN

    # 2. Unlock the locked operator
    unlock_res = unlock_user(admin_ctx, 2)
    assert unlock_res.ok
    assert unlock_res.data.locked_until is None
    assert unlock_res.data.failed_count == 0
