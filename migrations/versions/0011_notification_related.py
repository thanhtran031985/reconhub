"""notification_related

Revision ID: 0011_notification_related
Revises: 0010_notifications
Create Date: 2026-11-12

Task 79: panel chi tiết cần tham chiếu entity gốc — thêm 2 cột
nullable vào RECON_NOTIFICATION: RELATED_TYPE (RUN / REPORT_RUN /
EXPORT / BATCH / SYSTEM) + RELATED_ID. Emit ghi luôn lúc tạo.

Chạy được cả SQLite và Oracle (op.add_column trực tiếp, mẫu 0008).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_notification_related"
down_revision: Union[str, None] = "0010_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "RECON_NOTIFICATION",
        sa.Column("RELATED_TYPE", sa.String(40), nullable=True),
    )
    op.add_column(
        "RECON_NOTIFICATION",
        sa.Column(
            "RELATED_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("RECON_NOTIFICATION", "RELATED_ID")
    op.drop_column("RECON_NOTIFICATION", "RELATED_TYPE")
