from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, select

from app.core.auth import hash_password
from app.db.metadata import (
    metadata,
    recon_role,
    recon_user,
    recon_user_identity,
    recon_user_role,
)
from app.schemas.errors import ErrorCode
from app.schemas.sso import SsoProviderRuntime
from app.services.sso_client import (
    build_oidc_authorize_url,
    exchange_oidc_code,
    generate_pkce_pair,
    sync_sso_user,
)
from tests.conftest import seed_perm_basics


def _b64uint(val: int) -> str:
    raw = val.to_bytes((val.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_rsa_jwk_and_private_key() -> tuple[dict[str, Any], Any]:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_nums = priv.public_key().public_numbers()
    jwk_dict = {
        "kty": "RSA",
        "kid": "test-kid-1",
        "use": "sig",
        "alg": "RS256",
        "n": _b64uint(pub_nums.n),
        "e": _b64uint(pub_nums.e),
    }
    return jwk_dict, priv


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    seed_perm_basics(engine)
    return engine


@pytest.fixture
def google_provider() -> SsoProviderRuntime:
    return SsoProviderRuntime(
        id=2,
        code="google",
        name="Google",
        provider_type="OIDC",
        issuer="https://accounts.google.com",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        client_id="reconhub-google-client",
        client_secret="secret-google",
        scopes="openid email profile",
        allowed_domains=["company.com"],
        jit_enabled=True,
        auto_link_email=True,
    )


def test_build_oidc_authorize_url_with_pkce(google_provider: SsoProviderRuntime) -> None:
    verifier, challenge = generate_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected

    url = build_oidc_authorize_url(
        provider=google_provider,
        redirect_uri="http://localhost:8050/auth/sso/google/callback",
        state="state_abc",
        nonce="nonce_xyz",
        code_challenge=challenge,
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    assert qs["client_id"] == ["reconhub-google-client"]
    assert qs["response_type"] == ["code"]
    assert qs["state"] == ["state_abc"]
    assert qs["nonce"] == ["nonce_xyz"]
    assert qs["code_challenge"] == [challenge]
    assert qs["code_challenge_method"] == ["S256"]


def test_exchange_oidc_code_verifies_id_token_and_nonce(
    monkeypatch, google_provider: SsoProviderRuntime
) -> None:
    jwk_dict, priv_key = _make_rsa_jwk_and_private_key()
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "reconhub-google-client",
        "sub": "google-sub-001",
        "email": "Alice.Tran@Company.com",
        "email_verified": True,
        "name": "Alice Tran",
        "nonce": "nonce_ok",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    id_token = jwt.encode(claims, priv_key, algorithm="RS256", headers={"kid": "test-kid-1"})

    def fake_urlopen(req, timeout=8):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url == google_provider.token_url:
            return BytesIO(json.dumps({"access_token": "acc-1", "id_token": id_token}).encode("utf-8"))
        if url == google_provider.jwks_uri:
            return BytesIO(json.dumps({"keys": [jwk_dict]}).encode("utf-8"))
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.services.sso_client.urllib.request.urlopen", fake_urlopen)

    res = exchange_oidc_code(
        provider=google_provider,
        code="auth-code-123",
        redirect_uri="http://localhost:8050/auth/sso/google/callback",
        code_verifier="verifier-123",
        expected_nonce="nonce_ok",
    )
    assert res.ok is True
    assert res.data is not None
    assert res.data["subject"] == "google-sub-001"
    assert res.data["email"] == "alice.tran@company.com"
    assert res.data["username"] == "alice.tran@company.com"
    assert res.data["email_verified"] is True

    # Nonce sai -> từ chối
    bad_res = exchange_oidc_code(
        provider=google_provider,
        code="auth-code-123",
        redirect_uri="http://localhost:8050/auth/sso/google/callback",
        code_verifier="verifier-123",
        expected_nonce="wrong_nonce",
    )
    assert bad_res.ok is False
    assert bad_res.code == ErrorCode.LOGIN_FAILED


def test_sync_sso_user_uses_email_as_username_and_auto_links(
    sqlite_engine, google_provider: SsoProviderRuntime
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # User có sẵn trong RECON_USER (tạo thủ công bởi Admin với username khác email)
    with sqlite_engine.begin() as conn:
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="tran.thanh",
                FULL_NAME="Trần Thanh",
                EMAIL="thanh.tran@company.com",
                PASSWORD_HASH=hash_password("pass123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        existing_uid = int(res_u.inserted_primary_key[0])  # type: ignore[index]
        op_role_id = conn.execute(select(recon_role.c.ID).where(recon_role.c.CODE == "OPERATOR")).scalar_one()
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=existing_uid,
                ROLE_ID=op_role_id,
                ASSIGNED_BY="admin",
                ASSIGNED_AT=now,
                CREATED_AT=now,
            )
        )

    # 1. Đăng nhập Google có email trùng với user sẵn có -> tự động liên kết
    res_link = sync_sso_user(
        sqlite_engine,
        {
            "provider_code": "google",
            "subject": "g-sub-777",
            "email": "thanh.tran@company.com",
            "email_verified": True,
            "full_name": "Thanh Tran (Google)",
        },
        provider=google_provider,
    )
    assert res_link.ok is True
    assert res_link.data is not None
    assert res_link.data.user_id == existing_uid
    assert res_link.data.roles == ["OPERATOR"]

    with sqlite_engine.connect() as conn:
        ident = conn.execute(
            select(recon_user_identity).where(
                recon_user_identity.c.PROVIDER_CODE == "google",
                recon_user_identity.c.SUBJECT == "g-sub-777",
            )
        ).mappings().first()
        assert ident is not None
        assert int(ident["USER_ID"]) == existing_uid

    # 2. User hoàn toàn mới từ Google -> lấy email làm USERNAME luôn + tạo identity
    res_new = sync_sso_user(
        sqlite_engine,
        {
            "provider_code": "google",
            "subject": "g-sub-888",
            "email": "new.user@company.com",
            "email_verified": True,
            "full_name": "New User",
        },
        provider=google_provider,
    )
    assert res_new.ok is True
    assert res_new.data is not None
    assert res_new.data.username == "new.user@company.com"
    assert res_new.data.roles == ["VIEWER"]


def test_sync_sso_user_blocks_disallowed_domain_and_unverified_email(
    sqlite_engine, google_provider: SsoProviderRuntime
) -> None:
    res_domain = sync_sso_user(
        sqlite_engine,
        {
            "provider_code": "google",
            "subject": "g-sub-outsider",
            "email": "outsider@gmail.com",
            "email_verified": True,
            "full_name": "Outsider",
        },
        provider=google_provider,
    )
    assert res_domain.ok is False
    assert res_domain.code == ErrorCode.SSO_DOMAIN_NOT_ALLOWED

    res_unverified = sync_sso_user(
        sqlite_engine,
        {
            "provider_code": "google",
            "subject": "g-sub-unv",
            "email": "unverified@company.com",
            "email_verified": False,
            "full_name": "Unverified",
        },
        provider=google_provider,
    )
    assert res_unverified.ok is False
    assert res_unverified.code == ErrorCode.LOGIN_FAILED


def test_sync_sso_user_handles_long_email_over_60_chars(
    sqlite_engine, google_provider: SsoProviderRuntime
) -> None:
    long_email = "very.long.corporate.employee.identifier.person.name@company.com"
    assert len(long_email) > 60
    res = sync_sso_user(
        sqlite_engine,
        {
            "provider_code": "google",
            "subject": "g-sub-long",
            "email": long_email,
            "email_verified": True,
            "full_name": "Long Email User",
        },
        provider=google_provider,
    )
    assert res.ok is True
    assert res.data is not None
    assert len(res.data.username) <= 60

    with sqlite_engine.connect() as conn:
        u = conn.execute(select(recon_user).where(recon_user.c.ID == res.data.user_id)).mappings().one()
        assert u["EMAIL"] == long_email
