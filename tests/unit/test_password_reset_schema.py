from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from app.db.metadata import metadata, recon_password_reset_token, recon_user


@pytest.fixture
def test_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def test_password_reset_token_schema(test_engine):
    assert "RECON_PASSWORD_RESET_TOKEN" in metadata.tables

    table = metadata.tables["RECON_PASSWORD_RESET_TOKEN"]
    col_names = {c.name for c in table.columns}
    expected_cols = {"ID", "USER_ID", "TOKEN_HASH", "EXPIRES_AT", "IS_USED", "CREATED_AT", "CREATED_IP"}
    assert expected_cols.issubset(col_names)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_engine.begin() as conn:
        # Tạo user mẫu
        u_res = conn.execute(
            recon_user.insert().values(
                USERNAME="test_reset_user",
                FULL_NAME="User Test Reset",
                EMAIL="test_reset@company.local",
                PASSWORD_HASH="hash123",
                IS_ACTIVE="Y",
                SESSION_VERSION=1,
                CREATED_BY="TEST",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = u_res.inserted_primary_key[0]

        # Insert reset token
        t_res = conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH="a" * 64,
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="N",
                CREATED_AT=now,
                CREATED_IP="127.0.0.1",
            )
        )
        token_id = t_res.inserted_primary_key[0]

        # Query kiểm tra
        row = conn.execute(
            select(recon_password_reset_token).where(recon_password_reset_token.c.ID == token_id)
        ).mappings().first()
        assert row is not None
        assert row["USER_ID"] == user_id
        assert row["TOKEN_HASH"] == "a" * 64
        assert row["IS_USED"] == "N"
        assert row["CREATED_IP"] == "127.0.0.1"
