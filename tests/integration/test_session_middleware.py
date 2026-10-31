from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user, recon_user_role
from app.ui.app import create_app


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "test_recon_app.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key-1234567890")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Thêm user mẫu
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="active_user",
                FULL_NAME="Active User",
                PASSWORD_HASH=hash_password("pw123"),
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
                ROLE="OPERATOR",
                CREATED_AT=now,
            )
        )

        # User bắt buộc đổi mật khẩu
        res2 = conn.execute(
            recon_user.insert().values(
                USERNAME="must_change_user",
                FULL_NAME="Must Change PW",
                PASSWORD_HASH=hash_password("pw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="Y",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id2 = res2.inserted_primary_key[0]
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=user_id2,
                ROLE="OPERATOR",
                CREATED_AT=now,
            )
        )

    dash_app = create_app()
    server = dash_app.server
    server.config["TESTING"] = True
    return server.test_client(), engine


def test_unauthenticated_redirects_to_login(app_client) -> None:
    client, _ = app_client
    # Truy cập trang chủ khi chưa đăng nhập
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_public_routes_accessible_without_login(app_client) -> None:
    client, _ = app_client
    # /health mở công khai
    resp = client.get("/health")
    assert resp.status_code == 200

    # /login mở công khai
    resp = client.get("/login")
    assert resp.status_code == 200


def test_authenticated_access_allowed(app_client) -> None:
    client, _ = app_client
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "active_user"
        sess["full_name"] = "Active User"
        sess["roles"] = ["OPERATOR"]
        sess["session_version"] = 1
        sess["must_change_pw"] = False

    resp = client.get("/")
    assert resp.status_code == 200


def test_session_version_mismatch_logs_out(app_client) -> None:
    client, engine = app_client
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "active_user"
        sess["full_name"] = "Active User"
        sess["roles"] = ["OPERATOR"]
        sess["session_version"] = 1
        sess["must_change_pw"] = False

    # Giả sử admin tăng SESSION_VERSION trong DB lên 2
    from sqlalchemy import update

    with engine.begin() as conn:
        conn.execute(update(recon_user).where(recon_user.c.ID == 1).values(SESSION_VERSION=2))
    invalidate_user_session_cache(1)

    # Request tiếp theo phát hiện mismatch -> bị redirect sang /login
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_must_change_pw_redirects_to_change_step(app_client) -> None:
    client, _ = app_client
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["username"] = "must_change_user"
        sess["full_name"] = "Must Change PW"
        sess["roles"] = ["OPERATOR"]
        sess["session_version"] = 1
        sess["must_change_pw"] = True

    # Truy cập trang chủ bị chặn và chuyển sang /login?step=change
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login?step=change" in resp.headers["Location"]

    # Nhưng truy cập /login?step=change hoặc /account thì được
    resp = client.get("/login?step=change")
    assert resp.status_code == 200


def test_dash_component_origin_check(app_client) -> None:
    client, _ = app_client
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "active_user"
        sess["roles"] = ["OPERATOR"]
        sess["session_version"] = 1

    # Request với Origin giả mạo lạ bị 403
    resp = client.post(
        "/_dash-update-component",
        headers={"Origin": "https://malicious-site.com"},
    )
    assert resp.status_code == 403
