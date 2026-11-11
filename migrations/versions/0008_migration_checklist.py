"""migration_checklist

Revision ID: 0008_migration_checklist
Revises: 0007_export_progress
Create Date: 2026-11-11

Task 63: thêm CHECKLIST_JSON vào RECON_METADATA_MIGRATION để service ghi
tiến độ checklist từng bước con trong lúc chạy, modal poll cập nhật trực tiếp.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_migration_checklist"
down_revision: Union[str, None] = "0007_export_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "RECON_METADATA_MIGRATION",
        sa.Column("CHECKLIST_JSON", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("RECON_METADATA_MIGRATION", "CHECKLIST_JSON")
