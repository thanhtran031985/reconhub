"""password_reset_token

Revision ID: 0016_password_reset_token
Revises: 0015_mail_template_studio
Create Date: 2026-11-24

Task 103: Chức năng quên mật khẩu và đặt lại mật khẩu tự phục vụ qua email
Bảng RECON_PASSWORD_RESET_TOKEN:
- ID: BigInteger PK
- USER_ID: BigInteger FK -> RECON_USER.ID
- TOKEN_HASH: String(64) SHA-256 hash của token
- EXPIRES_AT: DateTime (hạn 20 phút)
- IS_USED: String(1) default 'N'
- CREATED_AT: DateTime
- CREATED_IP: String(60)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_password_reset_token"
down_revision: Union[str, None] = "0015_mail_template_studio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "RECON_PASSWORD_RESET_TOKEN",
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
        sa.Column("TOKEN_HASH", sa.String(64), nullable=False),
        sa.Column("EXPIRES_AT", sa.DateTime(), nullable=False),
        sa.Column("IS_USED", sa.String(1), nullable=False, server_default="N"),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("CREATED_IP", sa.String(60), nullable=True),
    )
    op.create_index(
        "ix_recon_pwd_reset_token_hash",
        "RECON_PASSWORD_RESET_TOKEN",
        ["TOKEN_HASH"],
    )
    op.create_index(
        "ix_recon_pwd_reset_user_expires",
        "RECON_PASSWORD_RESET_TOKEN",
        ["USER_ID", "EXPIRES_AT"],
    )


def downgrade() -> None:
    op.drop_index("ix_recon_pwd_reset_user_expires", table_name="RECON_PASSWORD_RESET_TOKEN")
    op.drop_index("ix_recon_pwd_reset_token_hash", table_name="RECON_PASSWORD_RESET_TOKEN")
    op.drop_table("RECON_PASSWORD_RESET_TOKEN")
