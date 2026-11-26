from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user, recon_user_identity
from app.schemas.errors import ServiceResult
from app.schemas.sso import SsoProviderCreateDTO
from app.services.sso_provider import create_sso_provider
from app.ui.app import create_app
from tests.conftest import seed_perm_basics


@pytest.fixture
def sso_e2e_env(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "sso_multi_e2e.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-e2e-sso-multi-secret")
    monkeypatch.setenv("RECON_SECRET_KEY", "test-e2e-recon-secret-key-123456")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                EMAIL="admin@company.com",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = int(res_adm.inserted_primary_key[0])  # type: ignore[index]
        seed_perm_basics(engine, {adm_id: ["ADMIN"]}, conn=conn)

        conn.execute(
            recon_user.insert().values(
                USERNAME="existing_staff",
                FULL_NAME="Nhân viên sẵn có",
                EMAIL="staff@company.com",
                PASSWORD_HASH=hash_password("staff123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    dash_app = create_app()
    return {
        "client": dash_app.server.test_client(),
        "engine": engine,
        "admin_ctx": Ctx(user_id=adm_id, username="admin", full_name="Quản trị viên", roles=["ADMIN"]),
    }


def test_sso_multi_provider_e2e_flow(sso_e2e_env) -> None:
    client = sso_e2e_env["client"]
    engine = sso_e2e_env["engine"]
    admin_ctx = sso_e2e_env["admin_ctx"]
    settings = get_settings()

    # 1. Admin đăng ký Google SSO
    res_g = create_sso_provider(
        admin_ctx,
        SsoProviderCreateDTO(
            code="google",
            name="Đăng nhập với Google",
            provider_type="OIDC",
            icon="lucide:globe",
            issuer="https://accounts.google.com",
            auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
            client_id="google-e2e-id",
            client_secret="google-e2e-secret",
            allowed_domains="company.com",
        ),
    )
    assert res_g.ok is True

    # 2. Admin đăng nhập kiểm tra trang /sso-flow và /data-model
    with client.session_transaction() as sess:
        sess["user_id"] = admin_ctx.user_id
        sess["username"] = "admin"
        sess["roles"] = ["ADMIN"]
        sess["session_version"] = 1

    assert client.get("/sso-flow").status_code == 200
    assert client.get("/data-model").status_code == 200

    # 3. Đăng xuất và kiểm tra trang /login + luồng OIDC tự động liên kết theo email
    client.get("/logout")
    assert client.get("/login").status_code == 200

    with patch.object(settings, "SSO_ENABLED", True):
        res_login = client.get("/auth/sso/google/login")
        assert res_login.status_code == 302
        state = parse_qs(urlparse(res_login.headers["Location"]).query)["state"][0]

        with patch(
            "app.routes.auth_routes.exchange_oidc_code",
            return_value=ServiceResult.success(
                {
                    "provider_code": "google",
                    "subject": "google-e2e-sub-staff",
                    "email": "staff@company.com",
                    "email_verified": True,
                    "full_name": "Nhân viên sẵn có",
                    "username": "staff@company.com",
                    "roles": [],
                }
            ),
        ):
            res_cb = client.get(f"/auth/sso/google/callback?code=e2e-code&state={state}")
            assert res_cb.status_code == 302
            assert res_cb.headers["Location"].endswith("/")

        with engine.connect() as conn:
            ident = conn.execute(
                select(recon_user_identity).where(
                    recon_user_identity.c.PROVIDER_CODE == "google",
                    recon_user_identity.c.SUBJECT == "google-e2e-sub-staff",
                )
            ).mappings().first()
            assert ident is not None
            assert ident["EMAIL_AT_PROVIDER"] == "staff@company.com"
