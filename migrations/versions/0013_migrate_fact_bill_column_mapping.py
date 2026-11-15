"""migrate_fact_bill_column_mapping

Revision ID: 0013_fact_bill_col_map
Revises: 0012_telegram_link
Create Date: 2026-11-15

Task 95: Nạp 112 cột chưa tồn tại của FACT_BILL vào RECON_LOOKUP_CODE loại DB_COLUMN_MAPPING.
Chạy được cả SQLite và Oracle (thao tác dữ liệu qua connection).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.services.lookup import migrate_fact_bill_columns

revision: str = "0013_fact_bill_col_map"
down_revision: Union[str, None] = "0012_telegram_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    migrate_fact_bill_columns(conn)


def downgrade() -> None:
    pass
