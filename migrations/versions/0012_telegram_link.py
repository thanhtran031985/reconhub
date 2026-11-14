"""telegram_link

Revision ID: 0012_telegram_link
Revises: 0011_notification_related
Create Date: 2026-11-14

Task 94: liên kết Telegram cho từng user — thêm 3 cột nullable vào
RECON_USER: TELEGRAM_CHAT_ID (chat id sau khi nhắn /start <mã>),
TELEGRAM_LINK_CODE (mã liên kết 8 ký tự) + TELEGRAM_LINK_EXPIRES_AT
(hạn 15 phút).

Chạy được cả SQLite và Oracle (op.add_column trực tiếp, mẫu 0011).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_telegram_link"
down_revision: Union[str, None] = "0011_notification_related"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "RECON_USER",
        sa.Column("TELEGRAM_CHAT_ID", sa.String(64), nullable=True),
    )
    op.add_column(
        "RECON_USER",
        sa.Column("TELEGRAM_LINK_CODE", sa.String(32), nullable=True),
    )
    op.add_column(
        "RECON_USER",
        sa.Column("TELEGRAM_LINK_EXPIRES_AT", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("RECON_USER", "TELEGRAM_LINK_EXPIRES_AT")
    op.drop_column("RECON_USER", "TELEGRAM_LINK_CODE")
    op.drop_column("RECON_USER", "TELEGRAM_CHAT_ID")
