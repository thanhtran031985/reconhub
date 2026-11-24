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
