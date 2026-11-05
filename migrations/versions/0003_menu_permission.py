"""menu_permission

Revision ID: 0003_menu_permission
Revises: 0002_add_lookup_tables
Create Date: 2026-11-05

Task 19, spec 11/11a: 4 bảng menu/vai trò mới, RECON_USER_ROLE đổi
ROLE (STR) sang ROLE_ID (FK RECON_ROLE), seed vai trò + menu tương
đương v4, thêm PERM_REVISION và MENU_SYNC_LOCK vào RECON_APP_SETTING.

Seed menu/vai trò được khai báo inline ở đây (SEED_GROUPS, SEED_MENUS,
SEED_ROLES, SEED_ROLE_MENUS) để revision tự chứa dữ liệu, không phụ
thuộc code app về sau; test ở bước 2 đối chiếu seed này với
app/ui/menus.py để hai nơi không lệch nhau. Không gọi menu_sync trong
revision: menu_sync chạy khi khởi động web và sẽ đồng bộ lại từ code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0003_menu_permission"
down_revision: Union[str, None] = "0002_add_lookup_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Nhóm menu: (code, label, order)
SEED_GROUPS = [
    ("DOI_SOAT", "Đối soát", 10),
    ("CAU_HINH", "Cấu hình", 20),
    ("QUAN_TRI", "Quản trị", 30),
]

# Menu: (code, label, group, path, order, icon, hideable)
# Đường dẫn history giữ "/history" theo Q3 (code hiện tại), khác bảng
# seed 11a mục 7 ghi "/runs".
SEED_MENUS = [
    ("dashboard", "Dashboard", "DOI_SOAT", "/", 10, "lucide:layout-dashboard", "Y"),
    ("run", "Chạy đối soát", "DOI_SOAT", "/runs/new", 20, "lucide:play", "Y"),
    ("result", "Kết quả run", "DOI_SOAT", "/runs/<id>", 30, "lucide:file-text", "Y"),
    ("batch_run", "Chạy bộ đối soát", "DOI_SOAT", "/batch-runs", 40, "lucide:layers", "Y"),
    ("history", "Lịch sử", "DOI_SOAT", "/history", 50, "lucide:history", "Y"),
    ("issue", "Xử lý chênh lệch", "DOI_SOAT", "/issues", 60, "lucide:alert-circle", "Y"),
    ("template", "Templates", "CAU_HINH", "/templates", 10, "lucide:file-spreadsheet", "Y"),
    ("batch_def", "Bộ đối soát", "CAU_HINH", "/batches", 20, "lucide:layers", "Y"),
    ("data_source", "Data Sources", "CAU_HINH", "/data-sources", 30, "lucide:database", "Y"),
    ("lookup", "Danh mục hệ thống", "CAU_HINH", "/lookups", 40, "lucide:list", "Y"),
    ("user", "Người dùng", "QUAN_TRI", "/users", 10, "lucide:users", "N"),
    ("role", "Vai trò và phân quyền", "QUAN_TRI", "/roles", 20, "lucide:shield", "N"),
    ("menu_admin", "Danh sách menu", "QUAN_TRI", "/menus", 30, "lucide:list", "N"),
]

# Vai trò: (code, name, description, is_system)
SEED_ROLES = [
    ("ADMIN", "Quản trị viên", "Vai trò hệ thống: luôn có mọi menu, xem tất cả dữ liệu.", "Y"),
    ("TEMPLATE_OWNER", "Chủ sở hữu Template", "Đăng ký, sửa, kích hoạt template; chạy đối soát.", "N"),
    ("OPERATOR", "Chuyên viên đối soát", "Chạy đối soát và xử lý chênh lệch.", "N"),
    ("VIEWER", "Người xem báo cáo", "Xem dashboard, lịch sử và kết quả run của mình.", "N"),
]

# Vai trò -> menu (ADMIN không có dòng, quyền tính theo IS_SYSTEM)
SEED_ROLE_MENUS = {
    "TEMPLATE_OWNER": ["dashboard", "run", "result", "batch_run", "history", "issue", "template", "batch_def"],
    "OPERATOR": ["dashboard", "run", "result", "batch_run", "history", "issue"],
    "VIEWER": ["dashboard", "result", "history", "template", "batch_def"],
}

OLD_ROLE_CODES = {"ADMIN", "TEMPLATE_OWNER", "OPERATOR", "VIEWER"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    now = _now()
    bind = op.get_bind()

    op.create_table(
        "RECON_MENU_GROUP",
        sa.Column("CODE", sa.String(40), primary_key=True),
        sa.Column("SOURCE_LABEL", sa.String(100), nullable=False),
        sa.Column("SOURCE_ORDER", sa.Integer, nullable=False),
        sa.Column("DISPLAY_LABEL", sa.String(100), nullable=True),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=True),
        sa.Column("IS_REMOVED", sa.String(1), nullable=False, server_default="N"),
        sa.Column("SYNCED_AT", sa.DateTime, nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
        sa.Column("ROW_VERSION", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "RECON_MENU",
        sa.Column("CODE", sa.String(40), primary_key=True),
        sa.Column("PATH", sa.String(200), nullable=False),
        sa.Column("ICON", sa.String(60), nullable=True),
        sa.Column("SOURCE_LABEL", sa.String(100), nullable=False),
        sa.Column("SOURCE_GROUP", sa.String(40), nullable=False),
        sa.Column("SOURCE_ORDER", sa.Integer, nullable=False),
        sa.Column("DISPLAY_LABEL", sa.String(100), nullable=True),
        sa.Column("DISPLAY_GROUP", sa.String(40), nullable=True),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=True),
        sa.Column("IS_HIDEABLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_HIDDEN", sa.String(1), nullable=False, server_default="N"),
        sa.Column("HIDDEN_REASON", sa.String(300), nullable=True),
        sa.Column("HIDDEN_BY", sa.String(60), nullable=True),
        sa.Column("HIDDEN_AT", sa.DateTime, nullable=True),
        sa.Column("IS_NEW", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_REMOVED", sa.String(1), nullable=False, server_default="N"),
        sa.Column("SYNCED_AT", sa.DateTime, nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
        sa.Column("ROW_VERSION", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["SOURCE_GROUP"], ["RECON_MENU_GROUP.CODE"], name="fk_RECON_MENU_SOURCE_GROUP_RECON_MENU_GROUP"
        ),
        sa.ForeignKeyConstraint(
            ["DISPLAY_GROUP"], ["RECON_MENU_GROUP.CODE"], name="fk_RECON_MENU_DISPLAY_GROUP_RECON_MENU_GROUP"
        ),
        sa.CheckConstraint("IS_HIDDEN = 'N' OR IS_HIDEABLE = 'Y'", name="ck_recon_menu_hideable"),
        sa.CheckConstraint(
            "IS_HIDDEN = 'N' OR HIDDEN_REASON IS NOT NULL", name="ck_recon_menu_hidden_reason"
        ),
    )

    op.create_table(
        "RECON_ROLE",
        sa.Column(
            "ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("CODE", sa.String(30), nullable=False, unique=True),
        sa.Column("NAME", sa.String(100), nullable=False),
        sa.Column("DESCRIPTION", sa.String(300), nullable=True),
        sa.Column("IS_SYSTEM", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
        sa.Column("ROW_VERSION", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "RECON_ROLE_MENU",
        sa.Column("ROLE_ID", sa.BigInteger, nullable=False),
        sa.Column("MENU_CODE", sa.String(40), nullable=False),
        sa.Column("GRANTED_BY", sa.String(60), nullable=False),
        sa.Column("GRANTED_AT", sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint("ROLE_ID", "MENU_CODE", name="pk_RECON_ROLE_MENU"),
        sa.ForeignKeyConstraint(["ROLE_ID"], ["RECON_ROLE.ID"], name="fk_RECON_ROLE_MENU_ROLE_ID_RECON_ROLE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["MENU_CODE"], ["RECON_MENU.CODE"], name="fk_RECON_ROLE_MENU_MENU_CODE_RECON_MENU"),
    )

    # Seed nhóm, menu, vai trò, vai trò-menu
    for code, label, order in SEED_GROUPS:
        bind.execute(
            text(
                "INSERT INTO RECON_MENU_GROUP (CODE, SOURCE_LABEL, SOURCE_ORDER, "
                "DISPLAY_LABEL, DISPLAY_ORDER, IS_REMOVED, SYNCED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:code, :label, :ord, NULL, NULL, 'N', :now, 'SEED', :now, 1)"
            ),
            {"code": code, "label": label, "ord": order, "now": now},
        )
    for code, label, group, path, order, icon, hideable in SEED_MENUS:
        bind.execute(
            text(
                "INSERT INTO RECON_MENU (CODE, PATH, ICON, SOURCE_LABEL, SOURCE_GROUP, SOURCE_ORDER, "
                "DISPLAY_LABEL, DISPLAY_GROUP, DISPLAY_ORDER, IS_HIDEABLE, IS_HIDDEN, "
                "HIDDEN_REASON, HIDDEN_BY, HIDDEN_AT, IS_NEW, IS_REMOVED, SYNCED_AT, "
                "UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:code, :path, :icon, :label, :grp, :ord, NULL, NULL, NULL, "
                ":hideable, 'N', NULL, NULL, NULL, 'Y', 'N', :now, 'SEED', :now, 1)"
            ),
            {
                "code": code,
                "path": path,
                "icon": icon,
                "label": label,
                "grp": group,
                "ord": order,
                "hideable": hideable,
                "now": now,
            },
        )
    role_ids: dict[str, int] = {}
    for code, name, desc, is_system in SEED_ROLES:
        res = bind.execute(
            text(
                "INSERT INTO RECON_ROLE (CODE, NAME, DESCRIPTION, IS_SYSTEM, IS_ACTIVE, "
                "CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:code, :name, :desc, :sys, 'Y', 'SEED', :now, 'SEED', :now, 1)"
            ),
            {"code": code, "name": name, "desc": desc, "sys": is_system, "now": now},
        )
        role_ids[code] = int(res.lastrowid)
    for role_code, menus in SEED_ROLE_MENUS.items():
        for menu_code in menus:
            bind.execute(
                text(
                    "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                    "VALUES (:rid, :menu, 'SEED', :now)"
                ),
                {"rid": role_ids[role_code], "menu": menu_code, "now": now},
            )

    # Đổi RECON_USER_ROLE: thêm ROLE_ID/ASSIGNED_*, điền từ ROLE cũ, bỏ ROLE/ORG_SCOPE, đổi PK
    with op.batch_alter_table("RECON_USER_ROLE", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("ROLE_ID", sa.BigInteger, nullable=True))
        batch_op.add_column(sa.Column("ASSIGNED_BY", sa.String(60), nullable=True))
        batch_op.add_column(sa.Column("ASSIGNED_AT", sa.DateTime, nullable=True))

    bind.execute(
        text(
            "UPDATE RECON_USER_ROLE SET ROLE_ID = "
            "(SELECT ID FROM RECON_ROLE WHERE RECON_ROLE.CODE = RECON_USER_ROLE.ROLE), "
            "ASSIGNED_BY = 'SEED', ASSIGNED_AT = :now"
        ),
        {"now": now},
    )
    unmapped = bind.execute(text("SELECT COUNT(*) FROM RECON_USER_ROLE WHERE ROLE_ID IS NULL")).scalar()
    if unmapped:
        raise RuntimeError(
            f"Không chuyển được {unmapped} dòng RECON_USER_ROLE: ROLE cũ không có trong 4 vai trò seed."
        )

    with op.batch_alter_table("RECON_USER_ROLE", recreate="always") as batch_op:
        batch_op.drop_column("ROLE")
        batch_op.drop_column("ORG_SCOPE")
        batch_op.drop_constraint("pk_RECON_USER_ROLE", type_="primary")
        batch_op.create_primary_key("pk_RECON_USER_ROLE", ["USER_ID", "ROLE_ID"])
        batch_op.create_foreign_key(
            "fk_RECON_USER_ROLE_ROLE_ID_RECON_ROLE", "RECON_ROLE", ["ROLE_ID"], ["ID"]
        )

    # Khóa mới trong RECON_APP_SETTING
    bind.execute(
        text(
            "INSERT INTO RECON_APP_SETTING (KEY, VALUE, UPDATED_BY, UPDATED_AT) "
            "VALUES ('PERM_REVISION', '1', 'SEED', :now)"
        ),
        {"now": now},
    )
    bind.execute(
        text(
            "INSERT INTO RECON_APP_SETTING (KEY, VALUE, UPDATED_BY, UPDATED_AT) "
            "VALUES ('MENU_SYNC_LOCK', 'N', 'SEED', :now)"
        ),
        {"now": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    # Vai trò tự tạo (không có mã cũ) mà đang gán cho user thì không được
    # downgrade ngầm: báo lỗi rõ, giữ nguyên dữ liệu.
    custom = bind.execute(
        text(
            "SELECT r.CODE FROM RECON_ROLE r "
            "JOIN RECON_USER_ROLE ur ON ur.ROLE_ID = r.ID "
            "WHERE r.CODE NOT IN ('ADMIN', 'TEMPLATE_OWNER', 'OPERATOR', 'VIEWER')"
        )
    ).fetchall()
    if custom:
        codes = ", ".join(sorted({row[0] for row in custom}))
        raise RuntimeError(
            f"Không downgrade được: vai trò tự tạo {codes} đang gán cho người dùng. "
            "Gỡ vai trò khỏi người dùng (hoặc xóa vai trò) rồi chạy lại downgrade."
        )

    with op.batch_alter_table("RECON_USER_ROLE", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("ROLE", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("ORG_SCOPE", sa.String(200), nullable=True))

    bind.execute(
        text(
            "UPDATE RECON_USER_ROLE SET ROLE = "
            "(SELECT CODE FROM RECON_ROLE WHERE RECON_ROLE.ID = RECON_USER_ROLE.ROLE_ID)"
        )
    )
    with op.batch_alter_table("RECON_USER_ROLE", recreate="always") as batch_op:
        batch_op.drop_column("ROLE_ID")
        batch_op.drop_column("ASSIGNED_BY")
        batch_op.drop_column("ASSIGNED_AT")
        batch_op.drop_constraint("pk_RECON_USER_ROLE", type_="primary")
        batch_op.create_primary_key("pk_RECON_USER_ROLE", ["USER_ID", "ROLE"])

    bind.execute(text("DELETE FROM RECON_APP_SETTING WHERE KEY IN ('PERM_REVISION', 'MENU_SYNC_LOCK')"))
    op.drop_table("RECON_ROLE_MENU")
    op.drop_table("RECON_ROLE")
    op.drop_table("RECON_MENU")
    op.drop_table("RECON_MENU_GROUP")
