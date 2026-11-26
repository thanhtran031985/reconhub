from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.db.metadata import metadata, recon_login_log
from app.routes.auth_routes import auth_bp
from app.schemas.errors import ServiceResult


@pytest.fixture
def flask_test_app():
    app = Flask(__name__)
    app.secret_key = "test_flask_secret_key"
    app.register_blueprint(auth_bp)
    return app


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def test_sso_login_route_disabled(flask_test_app):
    client = flask_test_app.test_client()
    settings = get_settings()

    with patch.object(settings, "SSO_ENABLED", False):
        res = client.get("/auth/sso/login")
        assert res.status_code == 302
        assert res.headers["Location"].endswith("/login")


def test_sso_login_route_enabled(flask_test_app):
    client = flask_test_app.test_client()
    settings = get_settings()

    with (
        patch.object(settings, "SSO_ENABLED", True),
        patch.object(settings, "SSO_SERVER_URL", "http://localhost:9000"),
    ):
        res = client.get("/auth/sso/login")
        assert res.status_code == 302
        loc = res.headers["Location"]
        assert loc.startswith("http://localhost:9000/login?")
        assert "redirect_uri=" in loc
        assert "state=" in loc

        # Kiểm tra state đã được lưu vào session
        parsed = urlparse(loc)
        query_params = parse_qs(parsed.query)
        sso_state_param = query_params["state"][0]
        with client.session_transaction() as sess:
            assert sess["sso_state"] == sso_state_param


def test_sso_callback_route_state_mismatch(flask_test_app, test_engine):
    client = flask_test_app.test_client()
    with patch("app.routes.auth_routes.get_recon_engine", return_value=test_engine):
        # Trường hợp 1: Không có state trong session
        res1 = client.get("/auth/sso/callback?code=mock_code&state=some_state")
        assert res1.status_code == 302
        assert "error=" in res1.headers["Location"]
        assert "CSRF" in res1.headers["Location"]

        # Trường hợp 2: State không khớp
        with client.session_transaction() as sess:
            sess["sso_state"] = "valid_state_123"

        res2 = client.get("/auth/sso/callback?code=mock_code&state=wrong_state_456")
        assert res2.status_code == 302
        assert "CSRF" in res2.headers["Location"]

        # Kiểm tra có ghi nhận RECON_LOGIN_LOG thất bại
        with test_engine.connect() as conn:
            rows = conn.execute(select(recon_login_log)).mappings().all()
            assert any(r["REASON"] == "SSO_CSRF_STATE_MISMATCH" for r in rows)


def test_sso_callback_route_missing_code(flask_test_app, test_engine):
    client = flask_test_app.test_client()
    with patch("app.routes.auth_routes.get_recon_engine", return_value=test_engine):
        with client.session_transaction() as sess:
            sess["sso_state"] = "valid_state_123"

        res = client.get("/auth/sso/callback?state=valid_state_123")
        assert res.status_code == 302
        assert "error=sso_missing_code" in res.headers["Location"]

        with test_engine.connect() as conn:
            rows = conn.execute(select(recon_login_log)).mappings().all()
            assert any(r["REASON"] == "SSO_MISSING_CODE" for r in rows)


def test_sso_callback_route_success(flask_test_app, test_engine):
    from app.core.auth import LoginData

    client = flask_test_app.test_client()

    fake_profile = {
        "ok": True,
        "username": "sso_tester",
        "full_name": "SSO Tester",
        "email": "tester@company.local",
        "roles": ["OPERATOR"],
    }
    fake_login_data = LoginData(
        user_id=999,
        username="sso_tester",
        full_name="SSO Tester",
        roles=["OPERATOR"],
        must_change_pw=False,
        session_version=1,
    )

    with client.session_transaction() as sess:
        sess["sso_state"] = "csrf_token_test_abc"

    with (
        patch("app.routes.auth_routes.get_recon_engine", return_value=test_engine),
        patch("app.routes.auth_routes.verify_sso_code", return_value=ServiceResult.success(fake_profile)),
        patch("app.routes.auth_routes.sync_sso_user", return_value=ServiceResult.success(fake_login_data)),
    ):
        res = client.get("/auth/sso/callback?code=mock_valid_code&state=csrf_token_test_abc")
        assert res.status_code == 302
        assert res.headers["Location"].endswith("/")

        # Kiểm tra session đã được thiết lập
        with client.session_transaction() as sess:
            assert sess["user_id"] == 999
            assert sess["username"] == "sso_tester"
            assert "OPERATOR" in sess["roles"]

        # Kiểm tra RECON_LOGIN_LOG ghi nhận thành công
        with test_engine.connect() as conn:
            rows = conn.execute(select(recon_login_log)).mappings().all()
            assert any(r["REASON"] == "SSO_LOGIN_SUCCESS" and r["SUCCESS"] == "Y" for r in rows)


def test_multi_provider_oidc_login_and_callback(flask_test_app, test_engine) -> None:
    from datetime import datetime, timezone

    from app.core.crypto import encrypt_secret
    from app.db.metadata import recon_role, recon_sso_provider

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_engine.begin() as conn:
        conn.execute(
            recon_role.insert().values(
                CODE="VIEWER",
                NAME="Chỉ xem",
                IS_SYSTEM="Y",
                IS_ACTIVE="Y",
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_BY="SYSTEM",
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_sso_provider.insert().values(
                CODE="google",
                NAME="Google Workspace",
                PROVIDER_TYPE="OIDC",
                AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth",
                TOKEN_URL="https://oauth2.googleapis.com/token",
                JWKS_URI="https://www.googleapis.com/oauth2/v3/certs",
                CLIENT_ID="g-client-id",
                CLIENT_SECRET_ENC=encrypt_secret("g-secret"),
                SCOPES="openid email profile",
                JIT_ENABLED="Y",
                AUTO_LINK_EMAIL="Y",
                IS_ACTIVE="Y",
                SORT_ORDER=2,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )

    client = flask_test_app.test_client()
    settings = get_settings()

    with (
        patch.object(settings, "SSO_ENABLED", True),
        patch("app.routes.auth_routes.get_recon_engine", return_value=test_engine),
    ):
        res_login = client.get("/auth/sso/google/login")
        assert res_login.status_code == 302
        loc = res_login.headers["Location"]
        assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        qs = parse_qs(urlparse(loc).query)
        assert qs["client_id"] == ["g-client-id"]
        assert qs["code_challenge_method"] == ["S256"]
        state = qs["state"][0]

        fake_oidc_profile = {
            "provider_code": "google",
            "subject": "google-sub-999",
            "email": "user.google@company.com",
            "email_verified": True,
            "full_name": "User Google",
            "username": "user.google@company.com",
            "roles": [],
        }
        with patch("app.routes.auth_routes.exchange_oidc_code", return_value=ServiceResult.success(fake_oidc_profile)):
            res_cb = client.get(f"/auth/sso/google/callback?code=g_code_1&state={state}")
            assert res_cb.status_code == 302
            assert res_cb.headers["Location"].endswith("/")

        with client.session_transaction() as sess:
            assert sess["username"] == "user.google@company.com"


def test_multi_provider_idp_error_redirect(flask_test_app, test_engine) -> None:
    client = flask_test_app.test_client()
    with client.session_transaction() as sess:
        sess["sso_state"] = "state_err_1"

    with patch("app.routes.auth_routes.get_recon_engine", return_value=test_engine):
        res = client.get("/auth/sso/google/callback?error=access_denied&state=state_err_1")
        assert res.status_code == 302
        assert "access_denied" in res.headers["Location"]

