"""mail_template_studio

Revision ID: 0015_mail_template_studio
Revises: 0014_email_template
Create Date: 2026-11-18

Task 98: Mail Template Studio (No-Code Email Builder & Multi-Version Engine)
Bao gồm:
- RECON_MAIL_TEMPLATE: Bảng cha quản lý danh mục mẫu email nghiệp vụ
- RECON_MAIL_TPL_VERSION: Quản lý đa phiên bản Draft / Active / Archived
- RECON_MAIL_RULE_BINDING: Liên kết quy tắc gửi email với mẫu tương ứng
- Đăng ký menu mail_template_studio vào RECON_MENU
- Khởi tạo seed mẫu email ban đầu cho các sự kiện cốt lõi (TEMPLATE_LIST_EXPORT, GENERAL_EXPORT, BATCH_RUN_COMPLETED, REPORT_EXPORT_COMPLETED)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0015_mail_template_studio"
down_revision: Union[str, None] = "0014_email_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MENU_CODE = "mail_template_studio"


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


def _make_default_design(event_code: str, title: str, intro: str) -> dict:
    return {
        "schemaVersion": 1,
        "canvasSettings": {
            "maxWidth": 600,
            "bgColor": "#f3f5f9",
            "fontFamily": "Segoe UI, Arial, sans-serif",
        },
        "blocks": [
            {
                "id": 1,
                "type": "header",
                "text": f"ReconHub | {title}",
                "color": "#1e3a5f",
                "bg": "#ffffff",
                "size": 20,
                "pad": 18,
                "align": "left",
                "condition": "always",
                "limit": 5,
                "url": "links.result",
                "columns": ["name", "status", "detail"],
            },
            {
                "id": 2,
                "type": "text",
                "text": f"Xin chào {{{{actor.name}}}},\n\n{intro}",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
                "limit": 5,
                "url": "links.result",
                "columns": ["name", "status", "detail"],
            },
            {
                "id": 3,
                "type": "kpi",
                "text": "Kết quả tổng hợp",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
                "limit": 5,
                "url": "links.result",
                "columns": ["name", "status", "detail"],
            },
            {
                "id": 4,
                "type": "button",
                "text": "Mở kết quả trên hệ thống",
                "color": "#ffffff",
                "bg": "#2563eb",
                "size": 13,
                "pad": 14,
                "align": "center",
                "condition": "always",
                "limit": 5,
                "url": "links.result",
                "columns": ["name", "status", "detail"],
            },
            {
                "id": 5,
                "type": "footer",
                "text": "Email được gửi tự động từ hệ thống ReconHub. Vui lòng không trả lời thư này.",
                "color": "#64748b",
                "bg": "#ffffff",
                "size": 11,
                "pad": 14,
                "align": "left",
                "condition": "always",
                "limit": 5,
                "url": "links.result",
                "columns": ["name", "status", "detail"],
            },
        ],
    }


def upgrade() -> None:
    now = _now()
    bind = op.get_bind()

    # 1. Tạo bảng RECON_MAIL_TEMPLATE
    op.create_table(
        "RECON_MAIL_TEMPLATE",
        _id_column(),
        sa.Column("CODE", sa.String(64), nullable=False, unique=True),
        sa.Column("NAME", sa.String(255), nullable=False),
        sa.Column("DESCRIPTION", sa.String(500), nullable=True),
        sa.Column("MENU_CODE", sa.String(64), nullable=False),
        sa.Column("EVENT_CODE", sa.String(64), nullable=False),
        sa.Column("CURRENT_ACTIVE_VERSION_ID", sa.BigInteger().with_variant(sa.Integer, "sqlite"), nullable=True),
        sa.Column("IS_ACTIVE", sa.String(1), nullable=False, server_default="Y"),
        *_audit_columns(),
    )
    op.create_index("ix_recon_mail_template_event", "RECON_MAIL_TEMPLATE", ["EVENT_CODE"])
    op.create_index("ix_recon_mail_template_menu", "RECON_MAIL_TEMPLATE", ["MENU_CODE"])

    # 2. Tạo bảng RECON_MAIL_TPL_VERSION
    op.create_table(
        "RECON_MAIL_TPL_VERSION",
        _id_column(),
        sa.Column(
            "TEMPLATE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_MAIL_TEMPLATE.ID"),
            nullable=False,
        ),
        sa.Column("VERSION_NO", sa.Integer, nullable=False),
        sa.Column("STATUS", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("EVENT_SCHEMA_VERSION", sa.Integer, nullable=False, server_default="1"),
        sa.Column("SUBJECT_TEMPLATE", sa.String(255), nullable=False),
        sa.Column("PREHEADER_TEMPLATE", sa.String(150), nullable=True),
        sa.Column("DESIGN_JSON", sa.Text, nullable=False),
        sa.Column("RENDERED_HTML", sa.Text, nullable=True),
        sa.Column("PLAIN_TEXT", sa.Text, nullable=True),
        sa.Column("DESIGN_HASH", sa.String(64), nullable=True),
        sa.Column("RENDERER_VERSION", sa.String(20), nullable=True),
        sa.Column("VALIDATION_JSON", sa.Text, nullable=True),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
        sa.Column("ACTIVATED_BY", sa.String(60), nullable=True),
        sa.Column("ACTIVATED_AT", sa.DateTime, nullable=True),
        sa.Column("ARCHIVED_AT", sa.DateTime, nullable=True),
        sa.UniqueConstraint("TEMPLATE_ID", "VERSION_NO", name="uq_recon_mail_tpl_version_no"),
        sa.CheckConstraint(
            "STATUS IN ('DRAFT', 'ACTIVE', 'ARCHIVED', 'INVALID')",
            name="ck_recon_mail_tpl_version_status",
        ),
    )
    op.create_index(
        "ix_recon_mail_tpl_ver_tmpl_status",
        "RECON_MAIL_TPL_VERSION",
        ["TEMPLATE_ID", "STATUS"],
    )

    # 3. Tạo bảng RECON_MAIL_RULE_BINDING
    op.create_table(
        "RECON_MAIL_RULE_BINDING",
        sa.Column("RULE_ID", sa.String(64), primary_key=True),
        sa.Column(
            "TEMPLATE_ID",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("RECON_MAIL_TEMPLATE.ID"),
            nullable=False,
        ),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime, nullable=False),
    )

    # 4. Thêm foreign key cho CURRENT_ACTIVE_VERSION_ID
    with op.batch_alter_table("RECON_MAIL_TEMPLATE", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_recon_mail_template_active_ver",
            "RECON_MAIL_TPL_VERSION",
            ["CURRENT_ACTIVE_VERSION_ID"],
            ["ID"],
        )

    # 5. Đăng ký menu vào RECON_MENU (idempotent)
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
                "path": "/mail-template-studio",
                "icon": "lucide:mail",
                "label": "Thiết kế mẫu mail",
                "grp": "CAU_HINH",
                "ord": 50,
                "hideable": "Y",
                "now": now,
            },
        )

    # 6. Seed các mẫu mặc định ban đầu
    seeds = [
        (
            "TMPL_TEMPLATE_LIST_DEFAULT",
            "Mẫu xuất danh sách Template",
            "Mẫu thông báo khi kết xuất danh sách cấu hình template",
            "template",
            "TEMPLATE_LIST_EXPORT",
            "[ReconHub] Danh sách Template đối soát [{{items_count}} template] — {{created_at}}",
            "Danh sách các mẫu đối soát đã được kết xuất thành công",
            _make_default_design(
                "TEMPLATE_LIST_EXPORT",
                "Danh sách Template đối soát",
                "Kính gửi anh/chị,\n\nHệ thống trân trọng gửi kèm tệp danh sách {{items_count}} template đối soát đã được kết xuất theo yêu cầu của {{actor.name}}.",
            ),
        ),
        (
            "TMPL_GENERAL_EXPORT_DEFAULT",
            "Mẫu xuất dữ liệu chung (Fallback)",
            "Mẫu email dự phòng dùng chung cho các chức năng kết xuất dữ liệu trong hệ thống",
            "common",
            "GENERAL_EXPORT",
            "[ReconHub] Kết xuất dữ liệu {{module_name}} — {{created_at}}",
            "Thông báo kết xuất dữ liệu thành công từ ReconHub",
            _make_default_design(
                "GENERAL_EXPORT",
                "Thông báo kết xuất dữ liệu",
                "Hệ thống đã hoàn tất kết xuất dữ liệu phân hệ {{module_name}} theo yêu cầu của bạn.",
            ),
        ),
        (
            "TMPL_BATCH_RUN_DEFAULT",
            "Mẫu thông báo chạy bộ đối soát",
            "Mẫu thông báo kết quả thực hiện bộ đối soát định kỳ",
            "batch_run",
            "BATCH_RUN_COMPLETED",
            "[ReconHub] Kết quả chạy bộ đối soát {{batch.name}}",
            "Thông báo hoàn tất phiên chạy bộ đối soát",
            _make_default_design(
                "BATCH_RUN_COMPLETED",
                "Kết quả phiên chạy bộ đối soát",
                "Phiên chạy bộ đối soát {{batch.name}} cho kỳ {{batch.period}} đã hoàn thành.",
            ),
        ),
        (
            "TMPL_REPORT_EXPORT_DEFAULT",
            "Mẫu kết xuất báo cáo",
            "Mẫu thông báo kết xuất tệp báo cáo hoàn tất",
            "report",
            "REPORT_EXPORT_COMPLETED",
            "[ReconHub] Báo cáo {{report.name}} đã sẵn sàng",
            "Tệp báo cáo đã được kết xuất và sẵn sàng tải về",
            _make_default_design(
                "REPORT_EXPORT_COMPLETED",
                "Báo cáo hoàn tất",
                "Báo cáo {{report.name}} đã được xử lý xong. Bạn có thể xem tệp đính kèm hoặc tải trực tiếp từ hệ thống.",
            ),
        ),
    ]

    for code, name, desc, menu, event, subj, preheader, design in seeds:
        res = bind.execute(
            text(
                """
                INSERT INTO RECON_MAIL_TEMPLATE (
                    CODE, NAME, DESCRIPTION, MENU_CODE, EVENT_CODE, IS_ACTIVE,
                    CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION
                ) VALUES (
                    :code, :name, :desc, :menu, :event, 'Y',
                    'system', :now, 'system', :now, 1
                )
                """
            ),
            {
                "code": code,
                "name": name,
                "desc": desc,
                "menu": menu,
                "event": event,
                "now": now,
            },
        )
        template_id = res.lastrowid
        # Nếu database không hỗ trợ lastrowid (vd một số dialect), query lại
        if not template_id:
            template_id = bind.execute(
                text("SELECT ID FROM RECON_MAIL_TEMPLATE WHERE CODE = :code"),
                {"code": code},
            ).scalar_one()

        v_res = bind.execute(
            text(
                """
                INSERT INTO RECON_MAIL_TPL_VERSION (
                    TEMPLATE_ID, VERSION_NO, STATUS, EVENT_SCHEMA_VERSION,
                    SUBJECT_TEMPLATE, PREHEADER_TEMPLATE, DESIGN_JSON,
                    CREATED_BY, CREATED_AT, ACTIVATED_BY, ACTIVATED_AT
                ) VALUES (
                    :t_id, 1, 'ACTIVE', 1,
                    :subj, :pre, :design,
                    'system', :now, 'system', :now
                )
                """
            ),
            {
                "t_id": template_id,
                "subj": subj,
                "pre": preheader,
                "design": json.dumps(design, ensure_ascii=False),
                "now": now,
            },
        )
        version_id = v_res.lastrowid
        if not version_id:
            version_id = bind.execute(
                text(
                    "SELECT ID FROM RECON_MAIL_TPL_VERSION WHERE TEMPLATE_ID = :t_id AND VERSION_NO = 1"
                ),
                {"t_id": template_id},
            ).scalar_one()

        bind.execute(
            text(
                "UPDATE RECON_MAIL_TEMPLATE SET CURRENT_ACTIVE_VERSION_ID = :v_id WHERE ID = :t_id"
            ),
            {"v_id": version_id, "t_id": template_id},
        )


def downgrade() -> None:
    op.drop_table("RECON_MAIL_RULE_BINDING")
    op.drop_table("RECON_MAIL_TPL_VERSION")
    op.drop_table("RECON_MAIL_TEMPLATE")
