"""batch_run

Revision ID: 0006_batch_run
Revises: 0005_export_claim
Create Date: 2026-11-06

Task 18 bước 1 (spec 10/10a): 5 bảng bộ đối soát (RECON_BATCH_DEF,
RECON_BATCH_DEF_ITEM, RECON_BATCH_RUN, RECON_BATCH_RUN_ITEM,
RECON_BATCH_RUN_FILE) + cột BATCH_RUN_ID/BATCH_RUN_ITEM_ID ở RECON_RUN
+ FILE_SET_HASH/SOURCE_FILES_JSON ở RECON_EXCEL_LOAD (UQ đổi sang
FILE_SET_HASH) + SOURCE_FILE_ID ở RECON_EXCEL_ROW (PK đổi sang
LOAD_ID, SOURCE_FILE_ID, EXCEL_ROW_NO).

Backfill dữ liệu cũ: FILE_SET_HASH = sha256(SHA256 của file);
SOURCE_FILE_ID = FILE_ID của lần nạp. 1 file: FILE_SET_HASH = hash
của 1 file (tương thích ngược).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0006_batch_run"
down_revision: Union[str, None] = "0005_export_claim"
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


def _single_file_set_hash(file_sha256: str) -> str:
    return hashlib.sha256(file_sha256.encode()).hexdigest()


def _control_total_ok(file_total: object, calc_total: object) -> str | None:
    if file_total is None or calc_total is None:
        return None
    try:
        return "Y" if Decimal(str(file_total)) == Decimal(str(calc_total)) else "N"
    except Exception:
        return None


def _backfill_excel_loads(bind) -> None:
    rows = bind.execute(
        text(
            "SELECT l.ID, l.FILE_ID, f.SHA256, f.ORIGINAL_NAME, l.ROWS_READ, "
            "l.CONTROL_TOTAL_FILE, l.CONTROL_TOTAL_CALC "
            "FROM RECON_EXCEL_LOAD l JOIN RECON_FILE f ON f.ID = l.FILE_ID"
        )
    ).fetchall()
    for load_id, file_id, sha256_hex, orig_name, rows_read, ct_file, ct_calc in rows:
        files_json = json.dumps(
            [
                {
                    "file_id": int(file_id),
                    "name": str(orig_name),
                    "rows": int(rows_read),
                    "control_total_ok": _control_total_ok(ct_file, ct_calc),
                }
            ],
            ensure_ascii=False,
        )
        bind.execute(
            text("UPDATE RECON_EXCEL_LOAD SET FILE_SET_HASH = :h, SOURCE_FILES_JSON = :j WHERE ID = :id"),
            {"h": _single_file_set_hash(str(sha256_hex)), "j": files_json, "id": int(load_id)},
        )


def _deduplicate_excel_loads(bind) -> None:
    """Gộp các bản nạp trùng nội dung trước khi đổi UQ sang FILE_SET_HASH.

    Lệch so với spec 10a §6 (ghi decisions.md): upload hiện tại không dedup
    theo SHA-256 nên cùng một file có thể có nhiều dòng RECON_FILE khác
    nhau; các bản nạp của chúng trùng nhau trên UQ mới (FILE_SET_HASH,
    SHEET, TEMPLATE, VERSION) và làm migration lỗi. Giữ bản nạp có ID nhỏ
    nhất, xóa dòng của các bản nạp trùng (nội dung giống hệt) và trỏ run
    sang bản nạp giữ lại.
    """
    groups = bind.execute(
        text(
            "SELECT FILE_SET_HASH, SHEET_NAME, TEMPLATE_ID, TEMPLATE_VERSION, "
            "MIN(ID) AS keep_id FROM RECON_EXCEL_LOAD "
            "GROUP BY FILE_SET_HASH, SHEET_NAME, TEMPLATE_ID, TEMPLATE_VERSION "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    for file_set_hash, sheet, template_id, version, keep_id in groups:
        dropped = (
            bind.execute(
                text(
                    "SELECT ID FROM RECON_EXCEL_LOAD WHERE FILE_SET_HASH = :h "
                    "AND SHEET_NAME = :s AND TEMPLATE_ID = :t AND TEMPLATE_VERSION = :v "
                    "AND ID <> :keep"
                ),
                {"h": file_set_hash, "s": sheet, "t": template_id, "v": version, "keep": keep_id},
            )
            .scalars()
            .all()
        )
        for drop_id in dropped:
            bind.execute(text("DELETE FROM RECON_EXCEL_ROW WHERE LOAD_ID = :d"), {"d": drop_id})
            bind.execute(
                text("UPDATE RECON_RUN SET EXCEL_LOAD_ID = :k WHERE EXCEL_LOAD_ID = :d"),
                {"k": keep_id, "d": drop_id},
            )
            bind.execute(text("DELETE FROM RECON_EXCEL_LOAD WHERE ID = :d"), {"d": drop_id})


def _unique_constraint_names(bind, table: str, columns: set[str]) -> list[str]:
    insp = sa.inspect(bind)
    return [
        str(c["name"]) for c in insp.get_unique_constraints(table) if set(c["column_names"]) == columns and c["name"]
    ]


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 5 bảng mới
    op.create_table(
        "RECON_BATCH_DEF",
        _id_column(),
        sa.Column("CODE", sa.String(60), nullable=False, unique=True),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("DESCRIPTION", sa.String(1000), nullable=True),
        sa.Column("STATUS", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("MAX_PARALLEL_PER_DS", sa.Integer, nullable=False, server_default="2"),
        sa.Column(
            "OWNER_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_USER.ID"),
            nullable=False,
        ),
        *_audit_columns(),
        sa.CheckConstraint("STATUS IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="ck_recon_batch_def_status"),
        sa.CheckConstraint("MAX_PARALLEL_PER_DS BETWEEN 1 AND 4", name="ck_recon_batch_def_max_parallel"),
        sa.Index("ix_recon_batch_def_status", "STATUS"),
    )
    op.create_table(
        "RECON_BATCH_DEF_ITEM",
        _id_column(),
        sa.Column(
            "BATCH_DEF_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_DEF.ID"),
            nullable=False,
        ),
        sa.Column(
            "TEMPLATE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_TEMPLATE.ID"),
            nullable=False,
        ),
        sa.Column("SEQ_NO", sa.Integer, nullable=False),
        sa.Column("PRIORITY", sa.Integer, nullable=False, server_default="100"),
        sa.Column("PROFILE_CODE", sa.String(60), nullable=True),
        sa.Column(
            "DATA_SOURCE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_DATA_SOURCE.ID"),
            nullable=True,
        ),
        sa.Column("FILE_PATTERN", sa.String(400), nullable=False),
        sa.Column("MULTI_FILE", sa.String(1), nullable=False, server_default="N"),
        sa.Column("IS_REQUIRED", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("PARAMS_OVERRIDE_JSON", sa.Text, nullable=True),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        *_audit_columns(),
        sa.UniqueConstraint("BATCH_DEF_ID", "TEMPLATE_ID", name="uq_recon_batch_def_item_def_tpl"),
        sa.CheckConstraint("SEQ_NO >= 1", name="ck_recon_batch_def_item_seq_no"),
        sa.Index("ix_recon_batch_def_item_def", "BATCH_DEF_ID", "IS_ACTIVE", "SEQ_NO"),
    )
    op.create_table(
        "RECON_BATCH_RUN",
        _id_column(),
        sa.Column(
            "BATCH_DEF_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_DEF.ID"),
            nullable=False,
        ),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("PERIOD", sa.String(7), nullable=False),
        sa.Column("PERIOD_FROM", sa.DateTime, nullable=False),
        sa.Column("PERIOD_TO", sa.DateTime, nullable=False),
        sa.Column("STATUS", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.Column("INCLUDE_WARN", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("PROD_CONFIRMED_BY", sa.String(60), nullable=True),
        sa.Column("CNT_ITEMS", sa.Integer, nullable=False, server_default="0"),
        sa.Column("CNT_DONE", sa.Integer, nullable=False, server_default="0"),
        sa.Column("CNT_FAILED", sa.Integer, nullable=False, server_default="0"),
        sa.Column("CNT_SKIPPED", sa.Integer, nullable=False, server_default="0"),
        sa.Column("CNT_NOT_RUN", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ZIP_PATH", sa.String(400), nullable=True),
        sa.Column("ZIP_RUN_SET_HASH", sa.String(64), nullable=True),
        sa.Column("STARTED_AT", sa.DateTime, nullable=True),
        sa.Column("FINISHED_AT", sa.DateTime, nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "STATUS IN ('DRAFT', 'RUNNING', 'DONE', 'PARTIAL', 'CANCELLED')",
            name="ck_recon_batch_run_status",
        ),
        sa.CheckConstraint("PERIOD_FROM <= PERIOD_TO", name="ck_recon_batch_run_period_range"),
        sa.Index("ix_recon_batch_run_def_period", "BATCH_DEF_ID", "PERIOD", "CREATED_AT"),
        sa.Index("ix_recon_batch_run_status", "STATUS", "CREATED_AT"),
    )
    op.create_table(
        "RECON_BATCH_RUN_ITEM",
        _id_column(),
        sa.Column(
            "BATCH_RUN_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_RUN.ID"),
            nullable=False,
        ),
        sa.Column(
            "BATCH_DEF_ITEM_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_DEF_ITEM.ID"),
            nullable=False,
        ),
        sa.Column("TEMPLATE_ID", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=False),
        sa.Column("TEMPLATE_VERSION", sa.Integer, nullable=True),
        sa.Column("PROFILE_CODE", sa.String(60), nullable=False),
        sa.Column(
            "DATA_SOURCE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_DATA_SOURCE.ID"),
            nullable=False,
        ),
        sa.Column("SEQ_NO", sa.Integer, nullable=False),
        sa.Column("PRIORITY", sa.Integer, nullable=False),
        sa.Column("MULTI_FILE", sa.String(1), nullable=False),
        sa.Column("IS_REQUIRED", sa.String(1), nullable=False),
        sa.Column("STATUS", sa.String(12), nullable=False, server_default="PENDING"),
        sa.Column("SKIP_REASON", sa.String(30), nullable=True),
        sa.Column("SKIPPED_BY", sa.String(60), nullable=True),
        sa.Column("PARAMS_RUN_OVERRIDE_JSON", sa.Text, nullable=True),
        sa.Column("PARAMS_RESOLVED_JSON", sa.Text, nullable=True),
        sa.Column("PRECHECK_JSON", sa.Text, nullable=True),
        sa.Column("PRECHECK_AT", sa.DateTime, nullable=True),
        # KHÔNG khai báo FK (decisions.md 04/11): tránh tham chiếu vòng.
        sa.Column("CURRENT_RUN_ID", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=True),
        sa.Column("ATTEMPT_NO", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ERROR_CODE", sa.String(60), nullable=True),
        sa.Column("ERROR_MSG", sa.String(2000), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("BATCH_RUN_ID", "BATCH_DEF_ITEM_ID", name="uq_recon_batch_run_item_run_defitem"),
        sa.CheckConstraint(
            "STATUS IN ('PENDING', 'READY', 'WARN', 'ERROR', 'SKIPPED', 'NOT_RUN', "
            "'QUEUED', 'RUNNING', 'DONE', 'FAILED')",
            name="ck_recon_batch_run_item_status",
        ),
        sa.Index("ix_recon_batch_run_item_run", "BATCH_RUN_ID", "STATUS", "SEQ_NO"),
    )
    op.create_table(
        "RECON_BATCH_RUN_FILE",
        _id_column(),
        sa.Column(
            "BATCH_RUN_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_RUN.ID"),
            nullable=False,
        ),
        sa.Column(
            "FILE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_FILE.ID"),
            nullable=False,
        ),
        sa.Column("ORIGINAL_NAME", sa.String(400), nullable=False),
        sa.Column("NORMALIZED_NAME", sa.String(400), nullable=False),
        sa.Column(
            "FROM_ZIP_FILE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_FILE.ID"),
            nullable=True,
        ),
        sa.Column(
            "BATCH_RUN_ITEM_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_BATCH_RUN_ITEM.ID"),
            nullable=True,
        ),
        sa.Column("MATCH_STATE", sa.String(12), nullable=False, server_default="UNMATCHED"),
        sa.Column("MATCH_BY", sa.String(10), nullable=True),
        sa.Column("CANDIDATE_ITEM_IDS", sa.Text, nullable=True),
        sa.Column("SHEET_NAME", sa.String(200), nullable=True),
        sa.Column("SEQ_IN_ITEM", sa.Integer, nullable=True),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime, nullable=False),
        sa.UniqueConstraint("BATCH_RUN_ID", "ORIGINAL_NAME", name="uq_recon_batch_run_file_run_name"),
        sa.CheckConstraint(
            "MATCH_STATE IN ('MATCHED', 'AMBIGUOUS', 'UNMATCHED', 'IGNORED', 'REPLACED')",
            name="ck_recon_batch_run_file_match_state",
        ),
        sa.CheckConstraint(
            "MATCH_BY IS NULL OR MATCH_BY IN ('PATTERN', 'HEADER', 'MANUAL')",
            name="ck_recon_batch_run_file_match_by",
        ),
        sa.Index("ix_recon_batch_run_file_item", "BATCH_RUN_ITEM_ID", "MATCH_STATE"),
        sa.Index("ix_recon_batch_run_file_hash", "BATCH_RUN_ID", "FILE_ID"),
    )

    # 2. RECON_RUN: run con của lần chạy bộ (cột FK phải thêm qua batch
    # mode — SQLite không cho ADD COLUMN kèm REFERENCES).
    with op.batch_alter_table("RECON_RUN", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "BATCH_RUN_ID",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey("RECON_BATCH_RUN.ID"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "BATCH_RUN_ITEM_ID",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey("RECON_BATCH_RUN_ITEM.ID"),
                nullable=True,
            )
        )
        batch_op.create_index("ix_recon_run_batch", ["BATCH_RUN_ID", "STATUS"])

    # 3. RECON_EXCEL_LOAD: FILE_SET_HASH + SOURCE_FILES_JSON, UQ mới
    op.add_column("RECON_EXCEL_LOAD", sa.Column("FILE_SET_HASH", sa.String(64), nullable=True))
    op.add_column("RECON_EXCEL_LOAD", sa.Column("SOURCE_FILES_JSON", sa.Text, nullable=True))
    _backfill_excel_loads(bind)
    _deduplicate_excel_loads(bind)
    old_uq = _unique_constraint_names(
        bind, "RECON_EXCEL_LOAD", {"FILE_ID", "SHEET_NAME", "TEMPLATE_ID", "TEMPLATE_VERSION"}
    )
    with op.batch_alter_table("RECON_EXCEL_LOAD", schema=None) as batch_op:
        batch_op.alter_column("FILE_SET_HASH", nullable=False)
        for name in old_uq:
            batch_op.drop_constraint(name, type_="unique")
        batch_op.create_unique_constraint(
            "uq_recon_excel_load_fileset_sheet_tmpl_ver",
            ["FILE_SET_HASH", "SHEET_NAME", "TEMPLATE_ID", "TEMPLATE_VERSION"],
        )

    # 4. RECON_EXCEL_ROW: SOURCE_FILE_ID + PK mới (cột FK thêm qua batch
    # mode; backfill giữa 2 lần dựng lại bảng).
    with op.batch_alter_table("RECON_EXCEL_ROW", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "SOURCE_FILE_ID",
                sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                sa.ForeignKey("RECON_FILE.ID"),
                nullable=True,
            )
        )
    bind.execute(
        text(
            "UPDATE RECON_EXCEL_ROW SET SOURCE_FILE_ID = ("
            "SELECT FILE_ID FROM RECON_EXCEL_LOAD "
            "WHERE RECON_EXCEL_LOAD.ID = RECON_EXCEL_ROW.LOAD_ID)"
        )
    )
    pk_name = sa.inspect(bind).get_pk_constraint("RECON_EXCEL_ROW").get("name") or "pk_RECON_EXCEL_ROW"
    with op.batch_alter_table("RECON_EXCEL_ROW", schema=None, recreate="always") as batch_op:
        batch_op.alter_column("SOURCE_FILE_ID", nullable=False)
        batch_op.drop_constraint(pk_name, type_="primary")
        batch_op.create_primary_key("pk_RECON_EXCEL_ROW", ["LOAD_ID", "SOURCE_FILE_ID", "EXCEL_ROW_NO"])


def downgrade() -> None:
    bind = op.get_bind()

    # 1. RECON_EXCEL_ROW: về PK cũ, bỏ SOURCE_FILE_ID
    pk_name = sa.inspect(bind).get_pk_constraint("RECON_EXCEL_ROW").get("name") or "pk_RECON_EXCEL_ROW"
    with op.batch_alter_table("RECON_EXCEL_ROW", schema=None, recreate="always") as batch_op:
        batch_op.drop_constraint(pk_name, type_="primary")
        batch_op.create_primary_key("pk_RECON_EXCEL_ROW", ["LOAD_ID", "EXCEL_ROW_NO"])
        batch_op.drop_column("SOURCE_FILE_ID")

    # 2. RECON_EXCEL_LOAD: về UQ cũ, bỏ 2 cột
    new_uq = _unique_constraint_names(
        bind,
        "RECON_EXCEL_LOAD",
        {"FILE_SET_HASH", "SHEET_NAME", "TEMPLATE_ID", "TEMPLATE_VERSION"},
    )
    with op.batch_alter_table("RECON_EXCEL_LOAD", schema=None) as batch_op:
        for name in new_uq:
            batch_op.drop_constraint(name, type_="unique")
        batch_op.create_unique_constraint(
            "uq_recon_excel_load_file_sheet_tmpl_ver",
            ["FILE_ID", "SHEET_NAME", "TEMPLATE_ID", "TEMPLATE_VERSION"],
        )
        batch_op.drop_column("FILE_SET_HASH")
        batch_op.drop_column("SOURCE_FILES_JSON")

    # 3. RECON_RUN: bỏ 2 cột + index (qua batch mode vì có FK)
    with op.batch_alter_table("RECON_RUN", schema=None) as batch_op:
        batch_op.drop_index("ix_recon_run_batch")
        batch_op.drop_column("BATCH_RUN_ITEM_ID")
        batch_op.drop_column("BATCH_RUN_ID")

    # 4. Xóa 5 bảng (ngược thứ tự tạo)
    op.drop_table("RECON_BATCH_RUN_FILE")
    op.drop_table("RECON_BATCH_RUN_ITEM")
    op.drop_table("RECON_BATCH_RUN")
    op.drop_table("RECON_BATCH_DEF_ITEM")
    op.drop_table("RECON_BATCH_DEF")
