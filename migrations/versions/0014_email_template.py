"""email_template

Revision ID: 0014_email_template
Revises: 0013_fact_bill_col_map
Create Date: 2026-11-18

Task 97: Bảng RECON_EMAIL_TEMPLATE lưu trữ mẫu email động theo từng chức năng,
hỗ trợ kéo thả token, Live Preview và tự động fallback về mẫu mặc định.
Chạy được cả SQLite và Oracle (create_table + seed mẫu mặc định qua Connection).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0014_email_template"
down_revision: Union[str, None] = "0013_fact_bill_col_map"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DEFAULT_AVAILABLE_TOKENS = [
    {"token": "user_name", "label": "Tên người gửi", "description": "Họ và tên đầy đủ của người gửi thư"},
    {"token": "username", "label": "Username", "description": "Tên tài khoản người gửi"},
    {"token": "created_at", "label": "Thời gian xuất", "description": "Thời điểm kết xuất dữ liệu (DD/MM/YYYY HH:MM)"},
    {"token": "items_count", "label": "Số lượng bản ghi", "description": "Tổng số template khớp bộ lọc"},
    {"token": "filters_info", "label": "Bộ lọc áp dụng", "description": "Chi tiết bộ lọc tìm kiếm và trạng thái"},
    {"token": "notes", "label": "Lời nhắn người gửi", "description": "Nội dung ghi chú kèm theo"},
    {"token": "files_list", "label": "Danh sách tệp đính kèm", "description": "Danh sách tên các tệp đính kèm thư"},
    {"token": "app_url", "label": "Đường dẫn hệ thống", "description": "Liên kết truy cập trang web ReconHub"},
]

DEFAULT_BODY_HTML = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #212529; max-width: 650px; line-height: 1.5;">
    <h2 style="color: #1971c2; margin-top: 0;">Danh sách Template đối soát ReconHub</h2>
    <p>Xin chào,</p>
    <p>Người dùng <strong>{{user_name}}</strong> ({{username}}) đã gửi cho bạn danh sách Template đối soát từ hệ thống <strong>ReconHub</strong>.</p>
    {{notes}}
    <div style="margin: 16px 0; padding: 12px; border: 1px solid #e9ecef; border-radius: 6px; background-color: #ffffff;">
        <p style="margin: 4px 0;"><strong>Thời gian kết xuất:</strong> {{created_at}}</p>
        <p style="margin: 4px 0;"><strong>Số lượng template:</strong> {{items_count}}</p>
        {{filters_info}}
        <p style="margin: 8px 0 4px 0;"><strong>Tệp đính kèm:</strong></p>
        <ul style="margin: 4px 0; padding-left: 20px;">
            {{files_list}}
        </ul>
    </div>
    <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
    <p style="font-size: 12px; color: #868e96; margin: 0;">
        Email này được gửi tự động từ hệ thống ReconHub. Vui lòng không trả lời trực tiếp email này.
    </p>
</div>"""


def upgrade() -> None:
    op.create_table(
        "RECON_EMAIL_TEMPLATE",
        sa.Column("TEMPLATE_CODE", sa.String(60), primary_key=True),
        sa.Column("NAME", sa.String(200), nullable=False),
        sa.Column("FUNCTION_CODE", sa.String(60), nullable=False),
        sa.Column("SUBJECT_PATTERN", sa.String(500), nullable=False),
        sa.Column("BODY_HTML", sa.Text(), nullable=False),
        sa.Column("AVAILABLE_TOKENS", sa.Text(), nullable=False),
        sa.Column("IS_DEFAULT", sa.String(1), nullable=False, server_default="N"),
        sa.Column("CREATED_BY", sa.String(60), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(), nullable=False),
        sa.Column("UPDATED_BY", sa.String(60), nullable=False),
        sa.Column("UPDATED_AT", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recon_email_template_func", "RECON_EMAIL_TEMPLATE", ["FUNCTION_CODE"])

    # Seed mẫu mặc định ban đầu cho TEMPLATE_LIST_EXPORT
    bind = op.get_bind()
    now = _now()
    tokens_json = json.dumps(DEFAULT_AVAILABLE_TOKENS, ensure_ascii=False)
    bind.execute(
        text(
            """
            INSERT INTO RECON_EMAIL_TEMPLATE (
                TEMPLATE_CODE, NAME, FUNCTION_CODE, SUBJECT_PATTERN, BODY_HTML,
                AVAILABLE_TOKENS, IS_DEFAULT, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT
            ) VALUES (
                :code, :name, :func, :subj, :body, :tokens, 'Y', 'system', :now, 'system', :now
            )
            """
        ),
        {
            "code": "TMPL_LIST_DEFAULT",
            "name": "Mẫu email danh sách Template chuẩn",
            "func": "TEMPLATE_LIST_EXPORT",
            "subj": "[ReconHub] Danh sách Template đối soát — {{created_at}}",
            "body": DEFAULT_BODY_HTML,
            "tokens": tokens_json,
            "now": now,
        },
    )


def downgrade() -> None:
    op.drop_index("ix_recon_email_template_func", table_name="RECON_EMAIL_TEMPLATE")
    op.drop_table("RECON_EMAIL_TEMPLATE")
