"""reporting_core

Revision ID: 0004_reporting_core
Revises: 0003_menu_permission
Create Date: 2026-11-06

Task 21, spec 12a: 11 bảng Dynamic Reporting (Report Master, Template,
Version, Param, LOV, Column, Run, Export, Favorite, Preset, LOV cache)
+ dòng khóa REPORT_ACTIVATE_LOCK trong RECON_APP_SETTING (mẫu
MENU_SYNC_LOCK ở 0003). Downgrade từ chối khi đã có dữ liệu report
(Q9), giống mẫu downgrade 0003 từ chối khi có vai trò tự tạo được gán.

RECON_REPORT_TEMPLATE.ACTIVE_VERSION_ID trỏ tới RECON_RPT_TPL_VER
(vòng FK hai chiều): tạo bảng template trước không kèm FK, thêm FK
sau khi tạo bảng version (batch_alter_table, chạy được SQLite và
Oracle).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.db.metadata import JsonText

revision: str = "0004_reporting_core"
down_revision: Union[str, None] = "0003_menu_permission"
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


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
        sa.Column("ROW_VERSION", sa.Integer, nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    now = _now()
    bind = op.get_bind()

    op.create_table(
        "RECON_REPORT",
        _id_column(),
        sa.Column("CODE", sa.String(60), nullable=False, unique=True),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("CATEGORY_CODE", sa.String(60), nullable=True),
        sa.Column("OWNER", sa.String(60), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.Column("DEFAULT_FAVORITE", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_VISIBLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        *_audit_columns(),
    )

    # Chưa kèm FK ACTIVE_VERSION_ID (bảng version chưa tồn tại); thêm sau.
    op.create_table(
        "RECON_REPORT_TEMPLATE",
        _id_column(),
        sa.Column("REPORT_ID", sa.BigInteger, nullable=False),
        sa.Column("CODE", sa.String(60), nullable=False),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=False, server_default="10"),
        sa.Column("ACTIVE_VERSION_ID", sa.BigInteger, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["REPORT_ID"], ["RECON_REPORT.ID"], name="fk_RECON_REPORT_TEMPLATE_REPORT_ID_RECON_REPORT"
        ),
        sa.UniqueConstraint("REPORT_ID", "CODE", name="uq_recon_report_template_report_code"),
    )

    op.create_table(
        "RECON_RPT_TPL_VER",
        _id_column(),
        sa.Column("TEMPLATE_ID", sa.BigInteger, nullable=False),
        sa.Column("VERSION_NO", sa.Integer, nullable=False),
        sa.Column("STATUS", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("DATA_SOURCE_ID", sa.BigInteger, nullable=True),
        sa.Column("SOURCE_TYPE", sa.String(20), nullable=True),
        sa.Column("SQL_TEXT", sa.Text, nullable=True),
        sa.Column("SOURCE_OWNER", sa.String(60), nullable=True),
        sa.Column("SOURCE_OBJECT", sa.String(128), nullable=True),
        sa.Column("TIMEOUT_SEC", sa.Integer, nullable=False, server_default="300"),
        sa.Column("PREVIEW_MAX_ROWS", sa.Integer, nullable=False, server_default="100"),
        sa.Column("EXPORT_MAX_ROWS", sa.Integer, nullable=False, server_default="1000000"),
        sa.Column("SQL_HASH", sa.String(64), nullable=True),
        sa.Column("ACTIVATED_BY", sa.String(60), nullable=True),
        sa.Column("ACTIVATED_AT", sa.DateTime, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["TEMPLATE_ID"],
            ["RECON_REPORT_TEMPLATE.ID"],
            name="fk_RECON_RPT_TPL_VER_TEMPLATE_ID_RECON_REPORT_TEMPLATE",
        ),
        sa.ForeignKeyConstraint(
            ["DATA_SOURCE_ID"],
            ["RECON_DATA_SOURCE.ID"],
            name="fk_RECON_RPT_TPL_VER_DATA_SOURCE_ID_RECON_DATA_SOURCE",
        ),
        sa.UniqueConstraint("TEMPLATE_ID", "VERSION_NO", name="uq_recon_rpt_tpl_ver_template_version"),
        sa.CheckConstraint(
            "STATUS IN ('DRAFT', 'DRY_RUN_OK', 'ACTIVE', 'ARCHIVED')",
            name="ck_recon_rpt_tpl_ver_status",
        ),
        sa.CheckConstraint(
            "SOURCE_TYPE IS NULL OR SOURCE_TYPE IN ('CUSTOM_SQL', 'VIEW', 'TABLE')",
            name="ck_recon_rpt_tpl_ver_source_type",
        ),
    )

    with op.batch_alter_table("RECON_REPORT_TEMPLATE", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_RECON_REPORT_TEMPLATE_ACTIVE_VERSION_ID_RECON_RPT_TPL_VER",
            "RECON_RPT_TPL_VER",
            ["ACTIVE_VERSION_ID"],
            ["ID"],
        )

    op.create_table(
        "RECON_RPT_PARAM",
        _id_column(),
        sa.Column("VERSION_ID", sa.BigInteger, nullable=False),
        sa.Column("CODE", sa.String(60), nullable=False),
        sa.Column("LABEL", sa.String(200), nullable=False),
        sa.Column("DATA_TYPE", sa.String(30), nullable=False),
        sa.Column("CONTROL_TYPE", sa.String(30), nullable=False),
        sa.Column("REQUIRED", sa.String(1), nullable=False, server_default="N"),
        sa.Column("DEFAULT_TYPE", sa.String(20), nullable=True),
        sa.Column("DEFAULT_VALUE", sa.String(500), nullable=True),
        sa.Column("DISPLAY_ROW", sa.Integer, nullable=False, server_default="1"),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=False, server_default="10"),
        sa.Column("GRID_SPAN", sa.Integer, nullable=False, server_default="6"),
        sa.Column("FILTER_COLUMN", sa.String(128), nullable=True),
        sa.Column("FILTER_OPERATOR", sa.String(20), nullable=True),
        sa.Column("IS_VISIBLE", sa.String(1), nullable=False, server_default="Y"),
        sa.ForeignKeyConstraint(
            ["VERSION_ID"], ["RECON_RPT_TPL_VER.ID"], name="fk_RECON_RPT_PARAM_VERSION_ID_RECON_RPT_TPL_VER"
        ),
        sa.UniqueConstraint("VERSION_ID", "CODE", name="uq_recon_rpt_param_version_code"),
        sa.CheckConstraint("GRID_SPAN BETWEEN 1 AND 12", name="ck_recon_rpt_param_grid_span"),
        sa.CheckConstraint("DISPLAY_ROW >= 1", name="ck_recon_rpt_param_display_row"),
        sa.CheckConstraint(
            "FILTER_OPERATOR IS NULL OR FILTER_OPERATOR IN "
            "('=', '>=', '<=', 'BETWEEN', 'IN', 'LIKE_PREFIX', 'IS_NULL')",
            name="ck_recon_rpt_param_filter_operator",
        ),
    )

    op.create_table(
        "RECON_RPT_PARAM_LOV",
        sa.Column("PARAM_ID", sa.BigInteger, primary_key=True),
        sa.Column("LOV_TYPE", sa.String(20), nullable=False, server_default="NONE"),
        sa.Column("DATA_SOURCE_ID", sa.BigInteger, nullable=True),
        sa.Column("SQL_TEXT", sa.Text, nullable=True),
        sa.Column("LOOKUP_TYPE", sa.String(60), nullable=True),
        sa.Column("STATIC_JSON", JsonText(), nullable=True),
        sa.Column("CACHE_SECONDS", sa.Integer, nullable=False, server_default="300"),
        sa.Column("MAX_ROWS", sa.Integer, nullable=False, server_default="5000"),
        sa.ForeignKeyConstraint(
            ["PARAM_ID"],
            ["RECON_RPT_PARAM.ID"],
            name="fk_RECON_RPT_PARAM_LOV_PARAM_ID_RECON_RPT_PARAM",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["DATA_SOURCE_ID"],
            ["RECON_DATA_SOURCE.ID"],
            name="fk_RECON_RPT_PARAM_LOV_DATA_SOURCE_ID_RECON_DATA_SOURCE",
        ),
        sa.CheckConstraint(
            "LOV_TYPE IN ('NONE', 'STATIC', 'SQL', 'LOOKUP')",
            name="ck_recon_rpt_param_lov_type",
        ),
        sa.CheckConstraint("CACHE_SECONDS BETWEEN 0 AND 3600", name="ck_recon_rpt_param_lov_cache"),
        sa.CheckConstraint("MAX_ROWS > 0", name="ck_recon_rpt_param_lov_max_rows"),
    )

    op.create_table(
        "RECON_RPT_COLUMN",
        _id_column(),
        sa.Column("VERSION_ID", sa.BigInteger, nullable=False),
        sa.Column("FIELD_NAME", sa.String(128), nullable=False),
        sa.Column("LABEL", sa.String(200), nullable=False),
        sa.Column("DATA_TYPE", sa.String(30), nullable=False),
        sa.Column("DISPLAY_ORDER", sa.Integer, nullable=False, server_default="10"),
        sa.Column("WEB_VISIBLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("EXCEL_VISIBLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("FORMAT_MASK", sa.String(100), nullable=True),
        sa.Column("ALIGNMENT", sa.String(10), nullable=False, server_default="LEFT"),
        sa.Column("WIDTH", sa.Integer, nullable=True),
        sa.Column("IS_TOTAL", sa.String(1), nullable=False, server_default="N"),
        sa.ForeignKeyConstraint(
            ["VERSION_ID"], ["RECON_RPT_TPL_VER.ID"], name="fk_RECON_RPT_COLUMN_VERSION_ID_RECON_RPT_TPL_VER"
        ),
        sa.UniqueConstraint("VERSION_ID", "FIELD_NAME", name="uq_recon_rpt_column_version_field"),
        sa.CheckConstraint(
            "ALIGNMENT IN ('LEFT', 'CENTER', 'RIGHT')",
            name="ck_recon_rpt_column_alignment",
        ),
    )

    op.create_table(
        "RECON_REPORT_RUN",
        _id_column(),
        sa.Column("REPORT_ID", sa.BigInteger, nullable=False),
        sa.Column("TEMPLATE_ID", sa.BigInteger, nullable=False),
        sa.Column("VERSION_ID", sa.BigInteger, nullable=False),
        sa.Column("PARAMS_JSON", JsonText(), nullable=False),
        sa.Column("STATUS", sa.String(30), nullable=False, server_default="QUEUED"),
        sa.Column("ROW_COUNT", sa.Integer, nullable=True),
        sa.Column("QUERY_MS", sa.Integer, nullable=True),
        sa.Column("ERROR_CODE", sa.String(60), nullable=True),
        sa.Column("ERROR_MESSAGE", sa.String(500), nullable=True),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("FINISHED_AT", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["REPORT_ID"], ["RECON_REPORT.ID"], name="fk_RECON_REPORT_RUN_REPORT_ID_RECON_REPORT"
        ),
        sa.ForeignKeyConstraint(
            ["TEMPLATE_ID"],
            ["RECON_REPORT_TEMPLATE.ID"],
            name="fk_RECON_REPORT_RUN_TEMPLATE_ID_RECON_REPORT_TEMPLATE",
        ),
        sa.ForeignKeyConstraint(
            ["VERSION_ID"], ["RECON_RPT_TPL_VER.ID"], name="fk_RECON_REPORT_RUN_VERSION_ID_RECON_RPT_TPL_VER"
        ),
        sa.CheckConstraint(
            "STATUS IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')",
            name="ck_recon_report_run_status",
        ),
    )

    op.create_table(
        "RECON_RPT_EXPORT",
        _id_column(),
        sa.Column("RUN_ID", sa.BigInteger, nullable=False),
        sa.Column("FORMAT", sa.String(10), nullable=False),
        sa.Column("STATUS", sa.String(30), nullable=False, server_default="QUEUED"),
        sa.Column("FILE_PATH", sa.String(500), nullable=True),
        sa.Column("FILE_SIZE", sa.BigInteger, nullable=True),
        sa.Column("FILE_HASH", sa.String(128), nullable=True),
        sa.Column("PART_COUNT", sa.Integer, nullable=False, server_default="1"),
        sa.Column("ROW_COUNT", sa.Integer, nullable=True),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("FINISHED_AT", sa.DateTime, nullable=True),
        sa.Column("ERROR_MESSAGE", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["RUN_ID"], ["RECON_REPORT_RUN.ID"], name="fk_RECON_RPT_EXPORT_RUN_ID_RECON_REPORT_RUN"
        ),
        sa.CheckConstraint("FORMAT IN ('XLSX', 'CSV', 'ZIP')", name="ck_recon_rpt_export_format"),
        sa.CheckConstraint(
            "STATUS IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'CANCELLED')",
            name="ck_recon_rpt_export_status",
        ),
    )

    op.create_table(
        "RECON_RPT_FAVORITE",
        sa.Column("USER_ID", sa.BigInteger, primary_key=True),
        sa.Column("REPORT_ID", sa.BigInteger, primary_key=True),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["USER_ID"], ["RECON_USER.ID"], name="fk_RECON_RPT_FAVORITE_USER_ID_RECON_USER"
        ),
        sa.ForeignKeyConstraint(
            ["REPORT_ID"], ["RECON_REPORT.ID"], name="fk_RECON_RPT_FAVORITE_REPORT_ID_RECON_REPORT"
        ),
    )

    op.create_table(
        "RECON_RPT_PRESET",
        _id_column(),
        sa.Column("USER_ID", sa.BigInteger, nullable=False),
        sa.Column("REPORT_ID", sa.BigInteger, nullable=False),
        sa.Column("TEMPLATE_ID", sa.BigInteger, nullable=False),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("PARAMS_JSON", JsonText(), nullable=False),
        sa.Column("IS_DEFAULT", sa.String(1), nullable=False, server_default="N"),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["USER_ID"], ["RECON_USER.ID"], name="fk_RECON_RPT_PRESET_USER_ID_RECON_USER"
        ),
        sa.ForeignKeyConstraint(
            ["REPORT_ID"], ["RECON_REPORT.ID"], name="fk_RECON_RPT_PRESET_REPORT_ID_RECON_REPORT"
        ),
        sa.ForeignKeyConstraint(
            ["TEMPLATE_ID"],
            ["RECON_REPORT_TEMPLATE.ID"],
            name="fk_RECON_RPT_PRESET_TEMPLATE_ID_RECON_REPORT_TEMPLATE",
        ),
    )

    op.create_table(
        "RECON_RPT_LOV_CACHE",
        sa.Column("CACHE_KEY", sa.String(200), primary_key=True),
        sa.Column("PAYLOAD_JSON", JsonText(), nullable=False),
        sa.Column("ROW_COUNT", sa.Integer, nullable=False, server_default="0"),
        sa.Column("EXPIRES_AT", sa.DateTime, nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
    )

    bind.execute(
        text(
            "INSERT INTO RECON_APP_SETTING (KEY, VALUE, UPDATED_BY, UPDATED_AT) "
            "VALUES ('REPORT_ACTIVATE_LOCK', 'N', 'SEED', :now)"
        ),
        {"now": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    # Đã có dữ liệu report thì không được downgrade ngầm: báo lỗi rõ,
    # giữ nguyên dữ liệu (Q9).
    report_count = bind.execute(text("SELECT COUNT(*) FROM RECON_REPORT")).scalar() or 0
    run_count = bind.execute(text("SELECT COUNT(*) FROM RECON_REPORT_RUN")).scalar() or 0
    if report_count or run_count:
        raise RuntimeError(
            f"Không downgrade được: đã có {report_count} report và {run_count} report run. "
            "Xóa dữ liệu báo cáo rồi chạy lại downgrade."
        )

    bind.execute(text("DELETE FROM RECON_APP_SETTING WHERE KEY = 'REPORT_ACTIVATE_LOCK'"))
    op.drop_table("RECON_RPT_LOV_CACHE")
    op.drop_table("RECON_RPT_PRESET")
    op.drop_table("RECON_RPT_FAVORITE")
    op.drop_table("RECON_RPT_EXPORT")
    op.drop_table("RECON_REPORT_RUN")
    op.drop_table("RECON_RPT_COLUMN")
    op.drop_table("RECON_RPT_PARAM_LOV")
    op.drop_table("RECON_RPT_PARAM")
    op.drop_table("RECON_RPT_TPL_VER")
    op.drop_table("RECON_REPORT_TEMPLATE")
    op.drop_table("RECON_REPORT")
