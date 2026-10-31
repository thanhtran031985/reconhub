from __future__ import annotations

from datetime import datetime, timezone

import dash
import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user, recon_user_role
from app.ui.app import create_app


@pytest.fixture
def ui_test_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "ui_auth_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-ui-secret-key-123")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Thêm user test
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="uitestuser",
                FULL_NAME="UI Test User",
                PASSWORD_HASH=hash_password("pw123456"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = res.inserted_primary_key[0]
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=user_id,
                ROLE="ADMIN",
                CREATED_AT=now,
            )
        )

    dash_app = create_app()
    server = dash_app.server
    server.config["TESTING"] = True
    return server.test_client(), user_id


def test_login_page_renders_successfully(ui_test_client) -> None:
    client, _ = ui_test_client
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "ReconHub" in resp.text
    assert "Đăng nhập" in resp.text


def test_login_change_step_renders_successfully(ui_test_client) -> None:
    client, _ = ui_test_client
    resp = client.get("/login?step=change")
    assert resp.status_code == 200

    # Lấy layout từ Dash page_registry
    page_info = dash.page_registry.get("pages.login") or dash.page_registry.get("app.ui.pages.login")
    assert page_info is not None
    layout_fn = page_info["layout"]
    comp = layout_fn(step="change")
    comp_str = str(comp)
    assert "Đổi mật khẩu" in comp_str
    assert "change-new-pw" in comp_str
    assert "change-confirm-pw" in comp_str


def test_account_page_renders_for_logged_in_user(ui_test_client) -> None:
    client, user_id = ui_test_client
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "uitestuser"
        sess["full_name"] = "UI Test User"
        sess["roles"] = ["ADMIN"]
        sess["session_version"] = 1
        sess["must_change_pw"] = False

    resp = client.get("/account")
    assert resp.status_code == 200
    assert "Tài khoản" in resp.text


def test_forbidden_page_renders(ui_test_client) -> None:
    client, user_id = ui_test_client
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "uitestuser"
        sess["full_name"] = "UI Test User"
        sess["roles"] = ["ADMIN"]
        sess["session_version"] = 1
        sess["must_change_pw"] = False

    resp = client.get("/forbidden")
    assert resp.status_code == 200
    assert "403" in resp.text or "từ chối" in resp.text
