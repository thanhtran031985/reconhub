"""notifications

Revision ID: 0010_notifications
Revises: 0009_queue_health_menu
Create Date: 2026-11-12

Task 78: trung tâm thông báo trong app — 2 bảng mới + menu /notifications.

- RECON_NOTIFICATION: thông báo lưu DB (người nhận, loại sự kiện,
  tiêu đề, nội dung, link, đã đọc, thời gian tạo); index
  (USER_ID, IS_READ, CREATED_AT) phục vụ đếm badge + liệt kê.
- RECON_NOTIFICATION_PREF: cài đặt nhận thông báo theo user
  (USER_ID, EVENT_TYPE, ENABLED); thiếu dòng = dùng mặc định
  (lỗi BẬT, DONE TẮT — quyết định task 52).
- Dữ liệu: menu "notifications" + cấp cho 3 vai trò còn lại
  (TEMPLATE_OWNER, OPERATOR, VIEWER; ADMIN thấy qua IS_SYSTEM),
  idempotent như mẫu 0009.

Chạy được cả SQLite và Oracle (create_table, không cần batch mode).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0010_notifications"
down_revision: Union[str, None] = "0009_queue_health_menu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENU_CODE = "notifications"
ROLE_CODES = ("TEMPLATE_OWNER", "OPERATOR", "VIEWER")


def _id_column() -> sa.Column:
    return sa.Column(
        "ID",
        sa.BigInteger().with_variant(sa.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    op.create_table(
        "RECON_NOTIFICATION",
        _id_column(),
        sa.Column(
            "USER_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_USER.ID"),
            nullable=False,
        ),
        sa.Column("TYPE", sa.String(40), nullable=False),
        sa.Column("TITLE", sa.String(200), nullable=False),
        sa.Column("MESSAGE", sa.String(1000), nullable=True),
        sa.Column("LINK", sa.String(500), nullable=True),
        sa.Column("IS_READ", sa.String(1), nullable=False, server_default="N"),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Index("ix_recon_notification_user_read_created", "USER_ID", "IS_READ", "CREATED_AT"),
    )
    op.create_table(
        "RECON_NOTIFICATION_PREF",
        sa.Column(
            "USER_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_USER.ID"),
            primary_key=True,
        ),
        sa.Column("EVENT_TYPE", sa.String(40), primary_key=True),
        sa.Column("ENABLED", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
    )

    # Menu + grant (idempotent, mẫu 0009).
    now = _now()
    bind = op.get_bind()
    exists = bind.execute(text("SELECT 1 FROM RECON_MENU WHERE CODE = :code"), {"code": MENU_CODE}).scalar_one_or_none()
    if exists is None:
        bind.execute(
            text(
                "INSERT INTO RECON_MENU (CODE, PATH, ICON, SOURCE_LABEL, "
                "SOURCE_GROUP, SOURCE_ORDER, DISPLAY_LABEL, DISPLAY_GROUP, "
                "DISPLAY_ORDER, IS_HIDEABLE, IS_HIDDEN, HIDDEN_REASON, "
                "HIDDEN_BY, HIDDEN_AT, IS_NEW, IS_REMOVED, SYNCED_AT, "
                "UPDATED_BY, UPDATED_AT, ROW_VERSION) VALUES (:code, :path, "
                ":icon, :label, :grp, :ord, NULL, NULL, NULL, :hideable, "
                "'N', NULL, NULL, NULL, 'Y', 'N', :now, 'SEED', :now, 1)"
            ),
            {
                "code": MENU_CODE,
                "path": "/notifications",
                "icon": "lucide:bell",
                "label": "Thông báo",
                "grp": "DOI_SOAT",
                "ord": 95,
                "hideable": "Y",
                "now": now,
            },
        )
    for role_code in ROLE_CODES:
        role_id = bind.execute(
            text("SELECT ID FROM RECON_ROLE WHERE CODE = :code"), {"code": role_code}
        ).scalar_one_or_none()
        if role_id is None:
            continue
        granted = bind.execute(
            text("SELECT 1 FROM RECON_ROLE_MENU WHERE ROLE_ID = :rid AND MENU_CODE = :menu"),
            {"rid": int(role_id), "menu": MENU_CODE},
        ).scalar_one_or_none()
        if granted is None:
            bind.execute(
                text(
                    "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, "
                    "GRANTED_BY, GRANTED_AT) VALUES (:rid, :menu, 'SEED', :now)"
                ),
                {"rid": int(role_id), "menu": MENU_CODE, "now": now},
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text("DELETE FROM RECON_ROLE_MENU WHERE MENU_CODE = :menu AND GRANTED_BY = 'SEED'"),
        {"menu": MENU_CODE},
    )
    op.drop_table("RECON_NOTIFICATION_PREF")
    op.drop_table("RECON_NOTIFICATION")
