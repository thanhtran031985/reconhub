from __future__ import annotations

from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.metadata import (
    metadata,
    recon_sso_provider,
    recon_user,
    recon_user_identity,
)


def test_sso_tables_defined_in_metadata() -> None:
    assert "RECON_SSO_PROVIDER" in metadata.tables
    assert "RECON_USER_IDENTITY" in metadata.tables

    prov_cols = {c.name for c in recon_sso_provider.columns}
    assert {
        "ID",
        "CODE",
        "NAME",
        "PROVIDER_TYPE",
        "DISCOVERY_URL",
        "AUTH_URL",
        "TOKEN_URL",
        "JWKS_URI",
        "CLIENT_ID",
        "CLIENT_SECRET_ENC",
        "SCOPES",
        "ALLOWED_DOMAINS",
        "JIT_ENABLED",
        "AUTO_LINK_EMAIL",
        "IS_ACTIVE",
        "SORT_ORDER",
    }.issubset(prov_cols)

    id_cols = {c.name for c in recon_user_identity.columns}
    assert {
        "ID",
        "USER_ID",
        "PROVIDER_CODE",
        "SUBJECT",
        "EMAIL_AT_PROVIDER",
        "LAST_LOGIN_AT",
    }.issubset(id_cols)


def test_user_identity_unique_provider_subject() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="alice@company.com",
                FULL_NAME="Alice",
                EMAIL="alice@company.com",
                PASSWORD_HASH="!sso_managed_test",
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="SSO",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = int(res.inserted_primary_key[0])  # type: ignore[index]

        conn.execute(
            recon_user_identity.insert().values(
                USER_ID=user_id,
                PROVIDER_CODE="google",
                SUBJECT="sub-12345",
                EMAIL_AT_PROVIDER="alice@company.com",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                recon_user_identity.insert().values(
                    USER_ID=user_id,
                    PROVIDER_CODE="google",
                    SUBJECT="sub-12345",
                    EMAIL_AT_PROVIDER="alice@company.com",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )


def test_alembic_0017_upgrade_and_downgrade(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "alembic_0017.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert "RECON_SSO_PROVIDER" in tables
    assert "RECON_USER_IDENTITY" in tables

    with engine.connect() as conn:
        row = conn.execute(
            select(recon_sso_provider).where(recon_sso_provider.c.CODE == "internal")
        ).mappings().first()
        assert row is not None
        assert row["PROVIDER_TYPE"] == "INTERNAL"

    command.downgrade(cfg, "0016_password_reset_token")
    tables_after = set(inspect(engine).get_table_names())
    assert "RECON_SSO_PROVIDER" not in tables_after
    assert "RECON_USER_IDENTITY" not in tables_after
