"""add_lookup_tables

Revision ID: 0002_add_lookup_tables
Revises: 0001_init
Create Date: 2026-11-02 22:40:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_lookup_tables"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "RECON_LOOKUP_TYPE",
        sa.Column("LOOKUP_TYPE", sa.String(50), primary_key=True),
        sa.Column("TYPE_NAME", sa.String(200), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.Column("IS_SYSTEM", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
    )

    op.create_table(
        "RECON_LOOKUP_CODE",
        sa.Column("LOOKUP_TYPE", sa.String(50), nullable=False),
        sa.Column("LOOKUP_CODE", sa.String(50), nullable=False),
        sa.Column("MEANING", sa.String(200), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=False, server_default="0"),
        sa.Column("COLOR_BADGE", sa.String(30), nullable=True),
        sa.Column("ICON_NAME", sa.String(60), nullable=True),
        sa.Column("IS_DEFAULT", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_SYSTEM", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        sa.PrimaryKeyConstraint("LOOKUP_TYPE", "LOOKUP_CODE", name="pk_RECON_LOOKUP_CODE"),
        sa.ForeignKeyConstraint(
            ["LOOKUP_TYPE"],
            ["RECON_LOOKUP_TYPE.LOOKUP_TYPE"],
            name="fk_RECON_LOOKUP_CODE_LOOKUP_TYPE_RECON_LOOKUP_TYPE",
        ),
    )


def downgrade() -> None:
    op.drop_table("RECON_LOOKUP_CODE")
    op.drop_table("RECON_LOOKUP_TYPE")

