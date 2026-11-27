"""report_studio

Revision ID: 0019_report_studio
Revises: 0018_semantic_model
Create Date: 2026-11-27

Task 109 (REPORT-STUDIO-01D): Report Studio UI, Persistence & Viewer
- RECON_RPT_VISUAL, RECON_RPT_VISUAL_FIELD
- RECON_RPT_TPL_VER thêm MODEL_VERSION_ID + SOURCE_TYPE 'SEMANTIC_MODEL'
  (đổi CheckConstraint: SQLite cần batch_alter_table recreate="always")
- RECON_REPORT_RUN thêm VISUAL_ID + QUERY_SPEC_JSON
- Seed menu report_studio + cấp mặc định cho TEMPLATE_OWNER (idempotent)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.db.metadata import JsonText

revision: str = "0019_report_studio"
down_revision: Union[str, None] = "0018_semantic_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _id_column() -> sa.Column:
    return sa.Column(
        "ID",
        sa.BigInteger().with_variant(sa.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def _fk_id_col(name: str, target: str, fk_name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.BigInteger().with_variant(sa.Integer, "sqlite"),
        sa.ForeignKey(target, name=fk_name),
        nullable=nullable,
    )


def upgrade() -> None:
    now = _now()
    bind = op.get_bind()

    op.create_table(
        "RECON_RPT_VISUAL",
        _id_column(),
        _fk_id_col("VERSION_ID", "RECON_RPT_TPL_VER.ID", "fk_recon_rpt_visual_ver"),
        sa.Column("CODE", sa.String(60), nullable=False),
        sa.Column("TITLE", sa.String(200), nullable=False),
        sa.Column("VISUAL_TYPE", sa.String(20), nullable=False),
        sa.Column("DISPLAY_ORDER", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("GRID_SPAN", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("HEIGHT_SIZE", sa.String(10), nullable=False, server_default="M"),
        sa.Column("CONFIG_JSON", JsonText(), nullable=True),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
        sa.Column("ROW_VERSION", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("VERSION_ID", "CODE", name="uq_recon_rpt_visual_ver_code"),
        sa.CheckConstraint(
            "VISUAL_TYPE IN ('TABLE', 'MATRIX', 'KPI', 'BAR', 'LINE')",
            name="ck_recon_rpt_visual_type",
        ),
        sa.CheckConstraint("GRID_SPAN IN (3, 4, 6, 8, 12)", name="ck_recon_rpt_visual_grid_span"),
        sa.CheckConstraint("HEIGHT_SIZE IN ('S', 'M', 'L')", name="ck_recon_rpt_visual_height"),
    )
    op.create_index("ix_recon_rpt_visual_ver", "RECON_RPT_VISUAL", ["VERSION_ID"])

    op.create_table(
        "RECON_RPT_VISUAL_FIELD",
        _id_column(),
        sa.Column(
            "VISUAL_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_RPT_VISUAL.ID", name="fk_recon_rpt_visual_field_visual", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("WELL_ROLE", sa.String(20), nullable=False),
        _fk_id_col("FIELD_ID", "RECON_RPT_MODEL_FIELD.ID", "fk_recon_rpt_visual_field_field", nullable=True),
        _fk_id_col("MEASURE_ID", "RECON_RPT_MODEL_MEASURE.ID", "fk_recon_rpt_visual_field_measure", nullable=True),
        sa.Column("AGGREGATION", sa.String(20), nullable=True),
        sa.Column("DATE_PART", sa.String(20), nullable=True),
        sa.Column("ALIAS", sa.String(128), nullable=True),
        sa.Column("LABEL_OVERRIDE", sa.String(200), nullable=True),
        sa.Column("FORMAT_MASK", sa.String(100), nullable=True),
        sa.Column("SORT_DIRECTION", sa.String(10), nullable=True),
        sa.Column("DISPLAY_ORDER", sa.Integer(), nullable=False, server_default="10"),
        sa.CheckConstraint(
            "AGGREGATION IS NULL OR AGGREGATION IN ('NONE', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
            name="ck_recon_rpt_visual_field_agg",
        ),
        sa.CheckConstraint(
            "DATE_PART IS NULL OR DATE_PART IN ('DAY', 'MONTH', 'QUARTER', 'YEAR')",
            name="ck_recon_rpt_visual_field_date_part",
        ),
        sa.CheckConstraint(
            "SORT_DIRECTION IS NULL OR SORT_DIRECTION IN ('ASC', 'DESC')",
            name="ck_recon_rpt_visual_field_sort",
        ),
    )
    op.create_index("ix_recon_rpt_visual_field_vis", "RECON_RPT_VISUAL_FIELD", ["VISUAL_ID"])

    # RECON_RPT_TPL_VER: thêm MODEL_VERSION_ID + mở rộng SOURCE_TYPE.
    # SQLite không sửa được CheckConstraint tại chỗ -> batch recreate="always".
    recreate_mode = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("RECON_RPT_TPL_VER", recreate=recreate_mode) as batch_op:
        batch_op.add_column(
            sa.Column(
                "MODEL_VERSION_ID",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey("RECON_RPT_MODEL_VER.ID", name="fk_recon_rpt_tpl_ver_model_ver"),
                nullable=True,
            )
        )
        batch_op.drop_constraint("ck_recon_rpt_tpl_ver_source_type", type_="check")
        batch_op.create_check_constraint(
            "ck_recon_rpt_tpl_ver_source_type",
            "SOURCE_TYPE IS NULL OR SOURCE_TYPE IN ('CUSTOM_SQL', 'VIEW', 'TABLE', 'SEMANTIC_MODEL')",
        )

    # SQLite không ADD COLUMN kèm ForeignKey tại chỗ -> batch recreate="always".
    with op.batch_alter_table("RECON_REPORT_RUN", recreate=recreate_mode) as batch_op:
        batch_op.add_column(
            sa.Column(
                "VISUAL_ID",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey("RECON_RPT_VISUAL.ID", name="fk_recon_report_run_visual"),
                nullable=True,
            ),
        )
        batch_op.add_column(sa.Column("QUERY_SPEC_JSON", JsonText(), nullable=True))

    # Seed menu report_studio + cấp mặc định cho TEMPLATE_OWNER (mẫu 0018, idempotent).
    menu_exists = bind.execute(
        text("SELECT 1 FROM RECON_MENU WHERE CODE = :code"),
        {"code": "report_studio"},
    ).scalar_one_or_none()
    if menu_exists is None:
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
                "code": "report_studio",
                "path": "/report-studio",
                "icon": "lucide:bar-chart-2",
                "label": "Report Studio",
                "grp": "CAU_HINH",
                "ord": 47,
                "hideable": "Y",
                "now": now,
            },
        )

    owner_role_id = bind.execute(
        text("SELECT ID FROM RECON_ROLE WHERE CODE = :code"),
        {"code": "TEMPLATE_OWNER"},
    ).scalar_one_or_none()
    if owner_role_id is not None:
        granted = bind.execute(
            text("SELECT 1 FROM RECON_ROLE_MENU WHERE ROLE_ID = :rid AND MENU_CODE = :menu"),
            {"rid": int(owner_role_id), "menu": "report_studio"},
        ).scalar_one_or_none()
        if granted is None:
            bind.execute(
                text(
                    "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                    "VALUES (:rid, :menu, 'SEED', :now)"
                ),
                {"rid": int(owner_role_id), "menu": "report_studio", "now": now},
            )


def downgrade() -> None:
    bind = op.get_bind()
    visual_count = bind.execute(text("SELECT COUNT(*) FROM RECON_RPT_VISUAL")).scalar() or 0
    if visual_count:
        raise RuntimeError(
            f"Không downgrade được: đã có {visual_count} visual Report Studio. Xóa dữ liệu visual rồi chạy lại downgrade."
        )
    pinned_count = bind.execute(
        text("SELECT COUNT(*) FROM RECON_RPT_TPL_VER WHERE MODEL_VERSION_ID IS NOT NULL")
    ).scalar() or 0
    if pinned_count:
        raise RuntimeError(
            f"Không downgrade được: đã có {pinned_count} phiên bản template báo cáo pin MODEL_VERSION_ID. "
            "Gỡ pin rồi chạy lại downgrade."
        )

    bind.execute(text("DELETE FROM RECON_ROLE_MENU WHERE MENU_CODE = 'report_studio' AND GRANTED_BY = 'SEED'"))

    # Gỡ cột VISUAL_ID khỏi RECON_REPORT_RUN TRƯỚC khi xóa bảng VISUAL:
    # batch recreate reflect lại FK trỏ sang RECON_RPT_VISUAL nên bảng đó
    # phải còn tồn tại lúc này.
    recreate_mode = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("RECON_REPORT_RUN", recreate=recreate_mode) as batch_op:
        batch_op.drop_column("QUERY_SPEC_JSON")
        batch_op.drop_column("VISUAL_ID")

    op.drop_table("RECON_RPT_VISUAL_FIELD")
    op.drop_table("RECON_RPT_VISUAL")

    with op.batch_alter_table("RECON_RPT_TPL_VER", recreate=recreate_mode) as batch_op:
        batch_op.drop_column("MODEL_VERSION_ID")
        batch_op.drop_constraint("ck_recon_rpt_tpl_ver_source_type", type_="check")
        batch_op.create_check_constraint(
            "ck_recon_rpt_tpl_ver_source_type",
            "SOURCE_TYPE IS NULL OR SOURCE_TYPE IN ('CUSTOM_SQL', 'VIEW', 'TABLE')",
        )
