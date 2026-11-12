"""queue_health_menu

Revision ID: 0009_queue_health_menu
Revises: 0008_migration_checklist
Create Date: 2026-11-12

Task 66: tách card sức khỏe khỏi dashboard thành tab riêng — cấp menu
queue_health cho 3 vai trò còn lại (TEMPLATE_OWNER, OPERATOR, VIEWER;
ADMIN thấy qua IS_SYSTEM). Chỉ dữ liệu, không đổi schema.

Revision tự chứa dữ liệu (theo mẫu 0003): chèn cả dòng RECON_MENU cho
queue_health vì RECON_ROLE_MENU.MENU_CODE có FK tới RECON_MENU.CODE —
db-migrate chạy trước khi app khởi động lại nên menu_sync chưa kịp đồng
bộ dòng menu mới. Viết idempotent (chỉ chèn khi chưa có) để chạy lại
được; downgrade chỉ gỡ các dòng grant do chính migration này thêm
(GRANTED_BY='SEED'), giữ nguyên dòng RECON_MENU (thuộc về menu_sync,
ADMIN có thể đã sửa DISPLAY_*).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0009_queue_health_menu"
down_revision: Union[str, None] = "0008_migration_checklist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENU_CODE = "queue_health"
ROLE_CODES = ("TEMPLATE_OWNER", "OPERATOR", "VIEWER")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    now = _now()
    bind = op.get_bind()

    # 1. Dòng menu (theo đúng cột/giá trị menu_sync ghi — xem 0003).
    exists = bind.execute(
        text("SELECT 1 FROM RECON_MENU WHERE CODE = :code"), {"code": MENU_CODE}
    ).scalar_one_or_none()
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
                "path": "/queue-health",
                "icon": "lucide:activity",
                "label": "Hàng đợi & worker",
                "grp": "DOI_SOAT",
                "ord": 90,
                "hideable": "Y",
                "now": now,
            },
        )

    # 2. Cấp quyền cho 3 vai trò (chỉ thêm khi chưa có).
    for role_code in ROLE_CODES:
        role_id = bind.execute(
            text("SELECT ID FROM RECON_ROLE WHERE CODE = :code"), {"code": role_code}
        ).scalar_one_or_none()
        if role_id is None:
            continue
        granted = bind.execute(
            text(
                "SELECT 1 FROM RECON_ROLE_MENU "
                "WHERE ROLE_ID = :rid AND MENU_CODE = :menu"
            ),
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
    # Chỉ gỡ grant do migration này thêm; giữ dòng RECON_MENU (xem
    # docstring đầu file).
    bind.execute(
        text(
            "DELETE FROM RECON_ROLE_MENU "
            "WHERE MENU_CODE = :menu AND GRANTED_BY = 'SEED'"
        ),
        {"menu": MENU_CODE},
    )
