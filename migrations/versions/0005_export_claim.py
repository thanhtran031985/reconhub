"""export_claim

Revision ID: 0005_export_claim
Revises: 0004_reporting_core
Create Date: 2026-11-06

Task 26 (Q2): thêm LOCKED_BY/LOCKED_AT/HEARTBEAT_AT vào RECON_RPT_EXPORT để
worker export claim nguyên tử + reset stale, theo mẫu RECON_RUN_QUEUE.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_export_claim"
down_revision: Union[str, None] = "0004_reporting_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "RECON_RPT_EXPORT", sa.Column("LOCKED_BY", sa.String(60), nullable=True)
    )
    op.add_column(
        "RECON_RPT_EXPORT", sa.Column("LOCKED_AT", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "RECON_RPT_EXPORT", sa.Column("HEARTBEAT_AT", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("RECON_RPT_EXPORT", "HEARTBEAT_AT")
    op.drop_column("RECON_RPT_EXPORT", "LOCKED_AT")
    op.drop_column("RECON_RPT_EXPORT", "LOCKED_BY")
