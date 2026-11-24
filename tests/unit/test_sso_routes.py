from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from app.core.config import get_settings
from app.routes.auth_routes import auth_bp
from app.schemas.errors import ServiceResult


@pytest.fixture
def flask_test_app():
    app = Flask(__name__)
    app.secret_key = "test_flask_secret_key"
    app.register_blueprint(auth_bp)
    return app


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

    with patch.object(settings, "SSO_ENABLED", True), patch.object(settings, "SSO_SERVER_URL", "http://localhost:9000"):
        res = client.get("/auth/sso/login")
        assert res.status_code == 302
        loc = res.headers["Location"]
        assert loc.startswith("http://localhost:9000/login?redirect_uri=")


def test_sso_callback_route_missing_code(flask_test_app):
    client = flask_test_app.test_client()
    res = client.get("/auth/sso/callback")
    assert res.status_code == 302
    assert "error=sso_missing_code" in res.headers["Location"]


def test_sso_callback_route_success(flask_test_app, monkeypatch):
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

    with (
        patch("app.routes.auth_routes.verify_sso_code", return_value=ServiceResult.success(fake_profile)),
        patch("app.routes.auth_routes.sync_sso_user", return_value=ServiceResult.success(fake_login_data)),
    ):
        res = client.get("/auth/sso/callback?code=mock_valid_code")
        assert res.status_code == 302
        assert res.headers["Location"].endswith("/")

        # Kiểm tra session đã được thiết lập
        with client.session_transaction() as sess:
            assert sess["user_id"] == 999
            assert sess["username"] == "sso_tester"
            assert "OPERATOR" in sess["roles"]
