"""export_progress

Revision ID: 0007_export_progress
Revises: 0006_batch_run
Create Date: 2026-11-10

Task 40: thêm PROGRESS_PCT/PROGRESS_STEP vào RECON_RPT_EXPORT để worker
export cập nhật % thật + bước hiện tại, UI poll hiển thị tới 100%.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_export_progress"
down_revision: Union[str, None] = "0006_batch_run"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "RECON_RPT_EXPORT",
        sa.Column("PROGRESS_PCT", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "RECON_RPT_EXPORT",
        sa.Column("PROGRESS_STEP", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("RECON_RPT_EXPORT", "PROGRESS_STEP")
    op.drop_column("RECON_RPT_EXPORT", "PROGRESS_PCT")
