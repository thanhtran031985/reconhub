"""semantic_model

Revision ID: 0018_semantic_model
Revises: 0017_multi_sso_oidc
Create Date: 2026-11-26

Task 106 (REPORT-STUDIO-01A): Semantic Model Core
- RECON_RPT_MODEL, RECON_RPT_MODEL_VER (vòng FK ACTIVE_VERSION_ID xử lý bằng batch_alter_table)
- RECON_RPT_MODEL_TABLE, RECON_RPT_MODEL_REL, RECON_RPT_MODEL_FIELD
- RECON_RPT_MODEL_MEASURE, RECON_RPT_MODEL_RLS
- Khóa đồng bộ MODEL_PUBLISH_LOCK trong RECON_APP_SETTING
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.db.metadata import JsonText

revision: str = "0018_semantic_model"
down_revision: Union[str, None] = "0017_multi_sso_oidc"
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
        "RECON_RPT_MODEL",
        _id_column(),
        sa.Column("CODE", sa.String(60), nullable=False),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        _fk_id_col("DATA_SOURCE_ID", "RECON_DATA_SOURCE.ID", "fk_recon_rpt_model_ds"),
        sa.Column("ACTIVE_VERSION_ID", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=True),
        sa.Column("IS_ARCHIVED", sa.String(1), nullable=False, server_default="N"),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
        sa.Column("ROW_VERSION", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("CODE", name="uq_recon_rpt_model_code"),
        sa.CheckConstraint("IS_ARCHIVED IN ('Y', 'N')", name="ck_recon_rpt_model_archived"),
    )

    op.create_table(
        "RECON_RPT_MODEL_VER",
        _id_column(),
        _fk_id_col("MODEL_ID", "RECON_RPT_MODEL.ID", "fk_recon_rpt_model_ver_model"),
        sa.Column("VERSION_NO", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("CHANGE_NOTE", sa.String(500), nullable=True),
        sa.Column("VALIDATION_JSON", JsonText(), nullable=True),
        sa.Column("PUBLISHED_BY", sa.String(60), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(), nullable=True),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
        sa.Column("ROW_VERSION", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("MODEL_ID", "VERSION_NO", name="uq_recon_rpt_model_ver_no"),
        sa.CheckConstraint(
            "STATUS IN ('DRAFT', 'VALIDATED', 'ACTIVE', 'ARCHIVED')",
            name="ck_recon_rpt_model_ver_status",
        ),
    )
    op.create_index("ix_recon_rpt_model_ver_status", "RECON_RPT_MODEL_VER", ["MODEL_ID", "STATUS"])

    recreate_mode = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("RECON_RPT_MODEL", recreate=recreate_mode) as batch_op:
        batch_op.create_foreign_key(
            "fk_recon_rpt_model_active_ver",
            "RECON_RPT_MODEL_VER",
            ["ACTIVE_VERSION_ID"],
            ["ID"],
        )

    op.create_table(
        "RECON_RPT_MODEL_TABLE",
        _id_column(),
        _fk_id_col("MODEL_VERSION_ID", "RECON_RPT_MODEL_VER.ID", "fk_recon_rpt_model_tbl_ver"),
        sa.Column("SOURCE_OWNER", sa.String(60), nullable=True),
        sa.Column("SOURCE_OBJECT", sa.String(128), nullable=False),
        sa.Column("OBJECT_TYPE", sa.String(20), nullable=False, server_default="TABLE"),
        sa.Column("ALIAS", sa.String(60), nullable=False),
        sa.Column("DISPLAY_NAME", sa.String(200), nullable=False),
        sa.Column("TABLE_ROLE", sa.String(20), nullable=False, server_default="UNCLASSIFIED"),
        sa.Column("GRAIN_DESC", sa.String(500), nullable=True),
        sa.Column("GRAIN_KEYS_JSON", JsonText(), nullable=True),
        sa.Column("DEFAULT_DATE_FIELD", sa.String(128), nullable=True),
        sa.Column("IS_HIDDEN", sa.String(1), nullable=False, server_default="N"),
        sa.Column("POS_X", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("POS_Y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ROW_ESTIMATE", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=True),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.UniqueConstraint("MODEL_VERSION_ID", "ALIAS", name="uq_recon_rpt_model_tbl_alias"),
        sa.UniqueConstraint("MODEL_VERSION_ID", "SOURCE_OWNER", "SOURCE_OBJECT", name="uq_recon_rpt_model_tbl_src"),
        sa.CheckConstraint("OBJECT_TYPE IN ('TABLE', 'VIEW')", name="ck_recon_rpt_model_tbl_obj_type"),
        sa.CheckConstraint(
            "TABLE_ROLE IN ('FACT', 'DIMENSION', 'BRIDGE', 'UNCLASSIFIED')",
            name="ck_recon_rpt_model_tbl_role",
        ),
        sa.CheckConstraint("IS_HIDDEN IN ('Y', 'N')", name="ck_recon_rpt_model_tbl_hidden"),
    )
    op.create_index("ix_recon_rpt_model_tbl_ver", "RECON_RPT_MODEL_TABLE", ["MODEL_VERSION_ID"])

    op.create_table(
        "RECON_RPT_MODEL_REL",
        _id_column(),
        _fk_id_col("MODEL_VERSION_ID", "RECON_RPT_MODEL_VER.ID", "fk_recon_rpt_model_rel_ver"),
        sa.Column("NAME", sa.String(120), nullable=False),
        _fk_id_col("FROM_TABLE_ID", "RECON_RPT_MODEL_TABLE.ID", "fk_recon_rpt_model_rel_from"),
        sa.Column("FROM_COLUMN", sa.String(128), nullable=False),
        _fk_id_col("TO_TABLE_ID", "RECON_RPT_MODEL_TABLE.ID", "fk_recon_rpt_model_rel_to"),
        sa.Column("TO_COLUMN", sa.String(128), nullable=False),
        sa.Column("CARDINALITY", sa.String(20), nullable=False, server_default="MANY_TO_ONE"),
        sa.Column("JOIN_TYPE", sa.String(20), nullable=False, server_default="LEFT_OUTER"),
        sa.Column("CROSS_FILTER", sa.String(20), nullable=False, server_default="SINGLE"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("VALIDATION_STATUS", sa.String(20), nullable=True),
        sa.Column("VALIDATION_JSON", JsonText(), nullable=True),
        sa.CheckConstraint("CARDINALITY IN ('MANY_TO_ONE', 'ONE_TO_ONE')", name="ck_recon_rpt_model_rel_card"),
        sa.CheckConstraint("JOIN_TYPE IN ('LEFT_OUTER', 'INNER')", name="ck_recon_rpt_model_rel_join"),
        sa.CheckConstraint("CROSS_FILTER IN ('SINGLE')", name="ck_recon_rpt_model_rel_cf"),
        sa.CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_rpt_model_rel_active"),
    )
    op.create_index("ix_recon_rpt_model_rel_ver", "RECON_RPT_MODEL_REL", ["MODEL_VERSION_ID"])

    op.create_table(
        "RECON_RPT_MODEL_FIELD",
        _id_column(),
        _fk_id_col("TABLE_ID", "RECON_RPT_MODEL_TABLE.ID", "fk_recon_rpt_model_fld_tbl"),
        sa.Column("SOURCE_COLUMN", sa.String(128), nullable=False),
        sa.Column("FIELD_CODE", sa.String(128), nullable=False),
        sa.Column("DISPLAY_NAME", sa.String(200), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.Column("DATA_TYPE", sa.String(30), nullable=False),
        sa.Column("FIELD_ROLE", sa.String(30), nullable=False, server_default="DIMENSION"),
        sa.Column("DEFAULT_AGG", sa.String(20), nullable=False, server_default="NONE"),
        sa.Column("FORMAT_MASK", sa.String(100), nullable=True),
        sa.Column("IS_VISIBLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_FILTERABLE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_PK", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_FK", sa.String(1), nullable=False, server_default="N"),
        _fk_id_col("SORT_BY_FIELD_ID", "RECON_RPT_MODEL_FIELD.ID", "fk_recon_rpt_model_fld_sort", nullable=True),
        sa.Column("FOLDER", sa.String(100), nullable=True),
        sa.Column("ENABLE_DATE_HIERARCHY", sa.String(1), nullable=False, server_default="N"),
        sa.Column("SENSITIVITY", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("DISPLAY_ORDER", sa.Integer(), nullable=False, server_default="10"),
        sa.UniqueConstraint("TABLE_ID", "FIELD_CODE", name="uq_recon_rpt_model_fld_code"),
        sa.UniqueConstraint("TABLE_ID", "SOURCE_COLUMN", name="uq_recon_rpt_model_fld_col"),
        sa.CheckConstraint(
            "FIELD_ROLE IN ('DIMENSION', 'MEASURE_CANDIDATE', 'KEY', 'HIDDEN')",
            name="ck_recon_rpt_model_fld_role",
        ),
        sa.CheckConstraint(
            "DEFAULT_AGG IN ('NONE', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
            name="ck_recon_rpt_model_fld_agg",
        ),
        sa.CheckConstraint("IS_VISIBLE IN ('Y', 'N')", name="ck_recon_rpt_model_fld_vis"),
        sa.CheckConstraint("IS_FILTERABLE IN ('Y', 'N')", name="ck_recon_rpt_model_fld_flt"),
        sa.CheckConstraint("IS_PK IN ('Y', 'N')", name="ck_recon_rpt_model_fld_pk"),
        sa.CheckConstraint("IS_FK IN ('Y', 'N')", name="ck_recon_rpt_model_fld_fk"),
        sa.CheckConstraint("ENABLE_DATE_HIERARCHY IN ('Y', 'N')", name="ck_recon_rpt_model_fld_dh"),
        sa.CheckConstraint(
            "SENSITIVITY IN ('NORMAL', 'INTERNAL', 'RESTRICTED')",
            name="ck_recon_rpt_model_fld_sens",
        ),
    )
    op.create_index("ix_recon_rpt_model_fld_tbl", "RECON_RPT_MODEL_FIELD", ["TABLE_ID"])

    op.create_table(
        "RECON_RPT_MODEL_MEASURE",
        _id_column(),
        _fk_id_col("MODEL_VERSION_ID", "RECON_RPT_MODEL_VER.ID", "fk_recon_rpt_model_meas_ver"),
        _fk_id_col("TABLE_ID", "RECON_RPT_MODEL_TABLE.ID", "fk_recon_rpt_model_meas_tbl", nullable=True),
        sa.Column("CODE", sa.String(60), nullable=False),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("MEASURE_TYPE", sa.String(20), nullable=False, server_default="SIMPLE"),
        _fk_id_col("BASE_FIELD_ID", "RECON_RPT_MODEL_FIELD.ID", "fk_recon_rpt_model_meas_fld", nullable=True),
        sa.Column("AGGREGATION", sa.String(20), nullable=True),
        sa.Column("EXPR_JSON", JsonText(), nullable=True),
        sa.Column("FORMAT_MASK", sa.String(100), nullable=True),
        sa.Column("FOLDER", sa.String(100), nullable=True),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.UniqueConstraint("MODEL_VERSION_ID", "CODE", name="uq_recon_rpt_model_meas_code"),
        sa.UniqueConstraint("MODEL_VERSION_ID", "NAME", name="uq_recon_rpt_model_meas_name"),
        sa.CheckConstraint("MEASURE_TYPE IN ('SIMPLE', 'CALCULATED')", name="ck_recon_rpt_model_meas_type"),
        sa.CheckConstraint(
            "AGGREGATION IS NULL OR AGGREGATION IN ('SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'COUNT_DISTINCT')",
            name="ck_recon_rpt_model_meas_agg",
        ),
    )
    op.create_index("ix_recon_rpt_model_meas_ver", "RECON_RPT_MODEL_MEASURE", ["MODEL_VERSION_ID"])

    op.create_table(
        "RECON_RPT_MODEL_RLS",
        _id_column(),
        _fk_id_col("MODEL_VERSION_ID", "RECON_RPT_MODEL_VER.ID", "fk_recon_rpt_model_rls_ver"),
        _fk_id_col("TABLE_ID", "RECON_RPT_MODEL_TABLE.ID", "fk_recon_rpt_model_rls_tbl"),
        sa.Column("COLUMN_NAME", sa.String(128), nullable=False),
        sa.Column("POLICY_TYPE", sa.String(30), nullable=False, server_default="OWNER_USERNAME"),
        sa.Column("SCOPE_ATTR", sa.String(60), nullable=True),
        sa.Column("ADMIN_BYPASS", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.UniqueConstraint("MODEL_VERSION_ID", "TABLE_ID", "COLUMN_NAME", name="uq_recon_rpt_model_rls_col"),
        sa.CheckConstraint(
            "POLICY_TYPE IN ('OWNER_USERNAME', 'ROLE_LIST', 'ORG_SCOPE_HOOK')",
            name="ck_recon_rpt_model_rls_type",
        ),
        sa.CheckConstraint("ADMIN_BYPASS IN ('Y', 'N')", name="ck_recon_rpt_model_rls_bypass"),
        sa.CheckConstraint("IS_ACTIVE IN ('Y', 'N')", name="ck_recon_rpt_model_rls_active"),
    )
    op.create_index("ix_recon_rpt_model_rls_ver", "RECON_RPT_MODEL_RLS", ["MODEL_VERSION_ID"])

    exists = bind.execute(
        text("SELECT 1 FROM RECON_APP_SETTING WHERE KEY = 'MODEL_PUBLISH_LOCK'")
    ).scalar_one_or_none()
    if exists is None:
        bind.execute(
            text(
                "INSERT INTO RECON_APP_SETTING (KEY, VALUE, UPDATED_BY, UPDATED_AT) "
                "VALUES ('MODEL_PUBLISH_LOCK', 'N', 'SEED', :now)"
            ),
            {"now": now},
        )

    # Seed menu report_model + cấp mặc định cho TEMPLATE_OWNER (mẫu 0009, idempotent).
    menu_exists = bind.execute(
        text("SELECT 1 FROM RECON_MENU WHERE CODE = :code"),
        {"code": "report_model"},
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
                "code": "report_model",
                "path": "/report-models",
                "icon": "lucide:boxes",
                "label": "Mô hình báo cáo",
                "grp": "CAU_HINH",
                "ord": 45,
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
            {"rid": int(owner_role_id), "menu": "report_model"},
        ).scalar_one_or_none()
        if granted is None:
            bind.execute(
                text(
                    "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                    "VALUES (:rid, :menu, 'SEED', :now)"
                ),
                {"rid": int(owner_role_id), "menu": "report_model", "now": now},
            )


def downgrade() -> None:
    bind = op.get_bind()
    model_count = bind.execute(text("SELECT COUNT(*) FROM RECON_RPT_MODEL")).scalar() or 0
    if model_count:
        raise RuntimeError(
            f"Không downgrade được: đã có {model_count} semantic model. Xóa dữ liệu model rồi chạy lại downgrade."
        )

    bind.execute(text("DELETE FROM RECON_ROLE_MENU WHERE MENU_CODE = 'report_model' AND GRANTED_BY = 'SEED'"))
    bind.execute(text("DELETE FROM RECON_APP_SETTING WHERE KEY = 'MODEL_PUBLISH_LOCK'"))
    op.drop_table("RECON_RPT_MODEL_RLS")
    op.drop_table("RECON_RPT_MODEL_MEASURE")
    op.drop_table("RECON_RPT_MODEL_FIELD")
    op.drop_table("RECON_RPT_MODEL_REL")
    op.drop_table("RECON_RPT_MODEL_TABLE")
    recreate_mode = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("RECON_RPT_MODEL", recreate=recreate_mode) as batch_op:
        batch_op.drop_constraint("fk_recon_rpt_model_active_ver", type_="foreignkey")
    op.drop_table("RECON_RPT_MODEL_VER")
    op.drop_table("RECON_RPT_MODEL")
