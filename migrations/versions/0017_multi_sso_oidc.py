"""multi_sso_oidc

Revision ID: 0017_multi_sso_oidc
Revises: 0016_password_reset_token
Create Date: 2026-11-26

Task 105: Hỗ trợ đăng ký nhiều SSO Provider (Google, Microsoft Entra ID, OIDC bên thứ 3)
- Bảng RECON_SSO_PROVIDER: cấu hình nhà cung cấp SSO (INTERNAL | OIDC)
- Bảng RECON_USER_IDENTITY: liên kết tài khoản RECON_USER với (PROVIDER_CODE, SUBJECT)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_multi_sso_oidc"
down_revision: Union[str, None] = "0016_password_reset_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "RECON_SSO_PROVIDER",
        sa.Column(
            "ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("CODE", sa.String(40), nullable=False),
        sa.Column("NAME", sa.String(120), nullable=False),
        sa.Column("PROVIDER_TYPE", sa.String(20), nullable=False, server_default="OIDC"),
        sa.Column("ICON", sa.String(60), nullable=True),
        sa.Column("DISCOVERY_URL", sa.String(500), nullable=True),
        sa.Column("ISSUER", sa.String(500), nullable=True),
        sa.Column("AUTH_URL", sa.String(500), nullable=True),
        sa.Column("TOKEN_URL", sa.String(500), nullable=True),
        sa.Column("USERINFO_URL", sa.String(500), nullable=True),
        sa.Column("JWKS_URI", sa.String(500), nullable=True),
        sa.Column("CLIENT_ID", sa.String(255), nullable=True),
        sa.Column("CLIENT_SECRET_ENC", sa.String(1000), nullable=True),
        sa.Column("SCOPES", sa.String(300), nullable=False, server_default="openid profile email"),
        sa.Column("ALLOWED_DOMAINS", sa.String(500), nullable=True),
        sa.Column("JIT_ENABLED", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("AUTO_LINK_EMAIL", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("SORT_ORDER", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
        sa.Column("ROW_VERSION", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("CODE", name="uq_recon_sso_prov_code"),
        sa.CheckConstraint("PROVIDER_TYPE IN ('INTERNAL', 'OIDC')", name="ck_recon_sso_prov_type"),
        sa.CheckConstraint("JIT_ENABLED IN ('Y', 'N')", name="ck_recon_sso_prov_jit"),
        sa.CheckConstraint("AUTO_LINK_EMAIL IN ('Y', 'N')", name="ck_recon_sso_prov_autolink"),
        sa.CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_sso_prov_active"),
    )

    op.create_table(
        "RECON_USER_IDENTITY",
        sa.Column(
            "ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "USER_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_USER.ID"),
            nullable=False,
        ),
        sa.Column("PROVIDER_CODE", sa.String(40), nullable=False),
        sa.Column("SUBJECT", sa.String(255), nullable=False),
        sa.Column("EMAIL_AT_PROVIDER", sa.String(200), nullable=True),
        sa.Column("LAST_LOGIN_AT", sa.DateTime(), nullable=True),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("PROVIDER_CODE", "SUBJECT", name="uq_recon_sso_prov_sub"),
    )
    op.create_index("ix_recon_user_id_user", "RECON_USER_IDENTITY", ["USER_ID"])

    # Seed provider nội bộ mặc định để tương thích ngược với task 102
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sso_prov = sa.table(
        "RECON_SSO_PROVIDER",
        sa.column("CODE", sa.String),
        sa.column("NAME", sa.String),
        sa.column("PROVIDER_TYPE", sa.String),
        sa.column("ICON", sa.String),
        sa.column("SCOPES", sa.String),
        sa.column("JIT_ENABLED", sa.String),
        sa.column("AUTO_LINK_EMAIL", sa.String),
        sa.column("IS_ACTIVE", sa.String),
        sa.column("SORT_ORDER", sa.Integer),
        sa.column("CREATED_BY", sa.String),
        sa.column("CREATED_AT", sa.DateTime),
        sa.column("UPDATED_BY", sa.String),
        sa.column("UPDATED_AT", sa.DateTime),
        sa.column("ROW_VERSION", sa.Integer),
    )
    op.get_bind().execute(
        sso_prov.insert().values(
            CODE="internal",
            NAME="SSO Doanh nghiệp (Nội bộ)",
            PROVIDER_TYPE="INTERNAL",
            ICON="lucide:shield-check",
            SCOPES="openid profile email",
            JIT_ENABLED="Y",
            AUTO_LINK_EMAIL="Y",
            IS_ACTIVE="Y",
            SORT_ORDER=1,
            CREATED_BY="SYSTEM",
            CREATED_AT=now,
            UPDATED_BY="SYSTEM",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )


def downgrade() -> None:
    op.drop_index("ix_recon_user_id_user", table_name="RECON_USER_IDENTITY")
    op.drop_table("RECON_USER_IDENTITY")
    op.drop_table("RECON_SSO_PROVIDER")
