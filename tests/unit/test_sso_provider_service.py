from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import hash_password
from app.core.context import Ctx
from app.db.metadata import (
    metadata,
    recon_audit_log,
    recon_sso_provider,
    recon_user,
)
from app.schemas.errors import ErrorCode
from app.schemas.sso import SsoProviderCreateDTO, SsoProviderUpdateDTO
from app.services.sso_provider import (
    create_sso_provider,
    delete_sso_provider,
    fetch_oidc_discovery,
    get_sso_provider_for_auth,
    list_active_login_providers,
    list_sso_providers,
    update_sso_provider,
)
from tests.conftest import seed_perm_basics


@pytest.fixture
def sso_env(tmp_path, monkeypatch):
    db_file = tmp_path / "sso_provider_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "test_secret_key_for_fernet_123456")

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_sso",
                FULL_NAME="Admin SSO",
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

        res_op = conn.execute(
            recon_user.insert().values(
                USERNAME="op_sso",
                FULL_NAME="Operator SSO",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        op_id = int(res_op.inserted_primary_key[0])  # type: ignore[index]
        seed_perm_basics(engine, {op_id: ["OPERATOR"]}, conn=conn)

    from app.services.perm import clear_perm_cache

    clear_perm_cache()

    return {
        "engine": engine,
        "admin": Ctx(user_id=adm_id, username="admin_sso", full_name="Admin SSO", roles=["ADMIN"]),
        "operator": Ctx(user_id=op_id, username="op_sso", full_name="Operator SSO", roles=["OPERATOR"]),
    }


def test_sso_provider_crud_requires_admin(sso_env) -> None:
    res_list = list_sso_providers(sso_env["operator"])
    assert res_list.ok is False
    assert res_list.code == ErrorCode.FORBIDDEN

    dto = SsoProviderCreateDTO(
        code="google",
        name="Google Workspace",
        provider_type="OIDC",
        discovery_url="https://accounts.google.com/.well-known/openid-configuration",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        client_id="google-client-id",
        client_secret="super-secret-google",
    )
    res_create = create_sso_provider(sso_env["operator"], dto)
    assert res_create.ok is False
    assert res_create.code == ErrorCode.FORBIDDEN


def test_create_update_delete_sso_provider_encrypts_secret_and_audits(sso_env) -> None:
    admin = sso_env["admin"]
    engine = sso_env["engine"]

    dto = SsoProviderCreateDTO(
        code="google",
        name="Đăng nhập với Google",
        provider_type="OIDC",
        icon="lucide:chrome",
        discovery_url="https://accounts.google.com/.well-known/openid-configuration",
        issuer="https://accounts.google.com",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        client_id="client-123",
        client_secret="plain-client-secret-xyz",
        allowed_domains="company.com",
    )
    res = create_sso_provider(admin, dto)
    assert res.ok is True
    assert res.data is not None
    assert res.data.code == "google"
    assert res.data.has_secret is True
    # Không bao giờ trả secret trong DTO phản hồi
    dumped_json = res.data.model_dump_json()
    assert "plain-client-secret-xyz" not in dumped_json

    # Trong DB phải lưu bản mã hóa khác plaintext
    with engine.connect() as conn:
        row = conn.execute(select(recon_sso_provider).where(recon_sso_provider.c.CODE == "google")).mappings().first()
        assert row is not None
        assert row["CLIENT_SECRET_ENC"]
        assert row["CLIENT_SECRET_ENC"] != "plain-client-secret-xyz"

        audit = conn.execute(
            select(recon_audit_log).where(
                recon_audit_log.c.ENTITY == "SSO_PROVIDER",
                recon_audit_log.c.ACTION == "CREATE",
            )
        ).mappings().first()
        assert audit is not None
        assert "plain-client-secret-xyz" not in (audit["NEW_JSON"] or "")

    # get_sso_provider_for_auth giải mã secret cho back-channel
    runtime = get_sso_provider_for_auth(engine, "google")
    assert runtime is not None
    assert runtime.client_secret == "plain-client-secret-xyz"

    # Update không truyền secret -> giữ nguyên secret cũ
    upd = update_sso_provider(
        admin,
        res.data.id,
        SsoProviderUpdateDTO(name="Google Corp", is_active=False),
    )
    assert upd.ok is True
    assert upd.data.name == "Google Corp"
    assert upd.data.is_active is False
    assert upd.data.has_secret is True
    assert get_sso_provider_for_auth(engine, "google") is None  # inactive

    # Active login providers chỉ trả các provider đang bật
    assert list_active_login_providers(engine) == []

    # Xóa provider
    del_res = delete_sso_provider(admin, res.data.id)
    assert del_res.ok is True


def test_fetch_oidc_discovery_success(sso_env) -> None:
    mock_doc = {
        "issuer": "https://login.microsoftonline.com/tenant-1/v2.0",
        "authorization_endpoint": "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token",
        "userinfo_endpoint": "https://graph.microsoft.com/oidc/userinfo",
        "jwks_uri": "https://login.microsoftonline.com/tenant-1/discovery/v2.0/keys",
    }

    class _FakeResp:
        def __enter__(self):
            return BytesIO(json.dumps(mock_doc).encode("utf-8"))

        def __exit__(self, *args):
            return False

    with patch("app.services.sso_provider.urllib.request.urlopen", return_value=_FakeResp()):
        res = fetch_oidc_discovery(
            sso_env["admin"],
            "https://login.microsoftonline.com/tenant-1/v2.0/.well-known/openid-configuration",
        )
    assert res.ok is True
    assert res.data is not None
    assert res.data["issuer"] == mock_doc["issuer"]
    assert res.data["auth_url"] == mock_doc["authorization_endpoint"]
    assert res.data["token_url"] == mock_doc["token_endpoint"]
    assert res.data["jwks_uri"] == mock_doc["jwks_uri"]
