"""Service for Mail Template Studio (No-Code Email Builder & Multi-Version Engine).

Cung cấp các API nghiệp vụ:
- Danh sách và chi tiết mẫu email
- Quản lý đa phiên bản (Draft, Active, Archived)
- Kiểm tra tính hợp lệ (Validation)
- Kích hoạt phiên bản (Atomic Transaction)
- Gửi thử nghiệm an toàn (Test Send với mock payload)
- Cung cấp mẫu Active cho các phân hệ nghiệp vụ (/templates, batch_run, report)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_mail_template,
    recon_mail_tpl_version,
    recon_user,
)
from app.engine.mail_event_registry import (
    get_event_definition,
    get_sample_payload,
)
from app.engine.mail_renderer import (
    RENDERER_VERSION,
    compute_design_hash,
    render_html_email,
    render_plain_text,
    resolve_tokens,
    validate_design,
)
from app.engine.mail_token_inspector import get_mock_payload_for_page
from app.engine.mailer import send_smtp_email
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.smtp_settings import get_smtp_config_internal


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _format_dt(dt: datetime | None) -> str | None:
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else None


def _make_default_design_for_event(event_code: str) -> dict[str, Any]:
    """Tạo cấu hình Design JSON ban đầu tương thích với từng sự kiện."""
    event = get_event_definition(event_code)
    label = event.label if event else "Thông báo"

    blocks: list[dict[str, Any]] = [
        {
            "id": 1,
            "type": "header",
            "text": f"ReconHub | {label}",
            "color": "#1e3a5f",
            "bg": "#ffffff",
            "size": 20,
            "pad": 18,
            "align": "left",
            "condition": "always",
        },
        {
            "id": 2,
            "type": "text",
            "text": "Xin chào {{actor.name}},\n\nHệ thống ReconHub trân trọng thông báo kết quả xử lý nghiệp vụ.",
            "color": "#26354a",
            "bg": "#ffffff",
            "size": 14,
            "pad": 16,
            "align": "left",
            "condition": "always",
        },
    ]

    if event_code == "BATCH_RUN_COMPLETED":
        blocks.extend(
            [
                {
                    "id": 3,
                    "type": "alert",
                    "text": "Cảnh báo: Có {{summary.failed}} template lỗi. Vui lòng kiểm tra trước khi chốt kỳ.",
                    "color": "#b54708",
                    "bg": "#fff4e5",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "errors",
                },
                {
                    "id": 4,
                    "type": "kpi",
                    "text": "Kết quả tổng hợp",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "always",
                },
                {
                    "id": 5,
                    "type": "table",
                    "text": "Các template cần kiểm tra",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "limit": 5,
                    "columns": ["name", "status", "detail"],
                    "condition": "errors",
                },
                {
                    "id": 6,
                    "type": "button",
                    "text": "Mở kết quả lần chạy bộ",
                    "color": "#ffffff",
                    "bg": "#2563eb",
                    "size": 13,
                    "pad": 14,
                    "align": "center",
                    "url": "links.result",
                    "condition": "always",
                },
            ]
        )
    elif event_code == "REPORT_EXPORT_COMPLETED":
        blocks.extend(
            [
                {
                    "id": 3,
                    "type": "text",
                    "text": "Tệp báo cáo <strong>{{report.name}}</strong> ({{export.filename}}) gồm <strong>{{export.rows}}</strong> dòng đã được kết xuất hoàn tất.",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "always",
                },
                {
                    "id": 4,
                    "type": "button",
                    "text": "Tải tệp báo cáo về máy",
                    "color": "#ffffff",
                    "bg": "#2563eb",
                    "size": 13,
                    "pad": 14,
                    "align": "center",
                    "url": "links.download",
                    "condition": "always",
                },
            ]
        )
    elif event_code == "USER_CREATED":
        blocks = [
            {
                "id": 1,
                "type": "header",
                "text": "ReconHub | Thông tin tài khoản người dùng",
                "color": "#1e3a5f",
                "bg": "#ffffff",
                "size": 20,
                "pad": 18,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 2,
                "type": "text",
                "text": "Xin chào <strong>{{user.full_name}}</strong>,\n\nTài khoản người dùng của bạn trên hệ thống ReconHub đã được tạo thành công bởi Quản trị viên <strong>{{actor.name}}</strong>.",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 3,
                "type": "text",
                "text": "<strong>Thông tin tài khoản đăng nhập:</strong><br><br>"
                        "• Tên đăng nhập: <code>{{user.username}}</code><br>"
                        "• Họ và tên: <strong>{{user.full_name}}</strong><br>"
                        "• Địa chỉ email: {{user.email}}<br>"
                        "• Vai trò: {{user.roles}}<br>"
                        "• Mật khẩu ban đầu: <code>{{user.temp_password}}</code><br>"
                        "• Yêu cầu đổi mật khẩu: {{user.must_change_pw}}",
                "color": "#26354a",
                "bg": "#f8fafc",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 4,
                "type": "button",
                "text": "Đăng nhập ReconHub",
                "color": "#ffffff",
                "bg": "#2563eb",
                "size": 13,
                "pad": 14,
                "align": "center",
                "url": "links.login",
                "condition": "always",
            },
            {
                "id": 5,
                "type": "footer",
                "text": "Email tự động từ hệ thống ReconHub. Vui lòng không trả lời thư này.",
                "color": "#64748b",
                "bg": "#f8fafc",
                "size": 12,
                "pad": 14,
                "align": "center",
                "condition": "always",
            },
        ]
        return {
            "canvasSettings": {"bgColor": "#f3f5f9"},
            "blocks": blocks,
        }
    elif event_code == "USER_LIST_EXPORT":
        blocks.extend(
            [
                {
                    "id": 3,
                    "type": "text",
                    "text": "Kính gửi anh/chị,\n\nDanh sách gồm <strong>{{items_count}}</strong> tài khoản người dùng đã được kết xuất kèm theo thư này.\n\n{{notes}}",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "always",
                },
                {
                    "id": 4,
                    "type": "button",
                    "text": "Mở trang Người dùng",
                    "color": "#ffffff",
                    "bg": "#2563eb",
                    "size": 13,
                    "pad": 14,
                    "align": "center",
                    "url": "links.page",
                    "condition": "always",
                },
            ]
        )
    elif event_code == "TEMPLATE_LIST_EXPORT":
        blocks.extend(
            [
                {
                    "id": 3,
                    "type": "text",
                    "text": "Kính gửi anh/chị,\n\nDanh sách gồm <strong>{{items_count}}</strong> mẫu đối soát đã được trích xuất kèm theo thư này.\n\n{{notes}}",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "always",
                },
                {
                    "id": 4,
                    "type": "button",
                    "text": "Truy cập Quản lý Template",
                    "color": "#ffffff",
                    "bg": "#2563eb",
                    "size": 13,
                    "pad": 14,
                    "align": "center",
                    "url": "links.template",
                    "condition": "always",
                },
            ]
        )
    else:
        blocks.extend(
            [
                {
                    "id": 3,
                    "type": "text",
                    "text": "Dữ liệu phân hệ <strong>{{module_name}}</strong> gồm <strong>{{items_count}}</strong> bản ghi đã được xử lý xong.\n\n{{notes}}",
                    "color": "#26354a",
                    "bg": "#ffffff",
                    "size": 14,
                    "pad": 16,
                    "align": "left",
                    "condition": "always",
                },
                {
                    "id": 4,
                    "type": "button",
                    "text": "Mở liên kết kết xuất",
                    "color": "#ffffff",
                    "bg": "#2563eb",
                    "size": 13,
                    "pad": 14,
                    "align": "center",
                    "url": "links.download",
                    "condition": "always",
                },
            ]
        )

    blocks.append(
        {
            "id": 7,
            "type": "footer",
            "text": "Email tự động từ ReconHub. Vui lòng không trả lời thư này.",
            "color": "#64748b",
            "bg": "#ffffff",
            "size": 11,
            "pad": 14,
            "align": "left",
            "condition": "always",
        }
    )

    return {
        "schemaVersion": 1,
        "canvasSettings": {
            "maxWidth": 600,
            "bgColor": "#f3f5f9",
            "fontFamily": "Segoe UI, Arial, sans-serif",
        },
        "blocks": blocks,
    }


@service
@requires_menu("mail_template_studio")
def list_mail_templates(
    ctx: Ctx,
    search: str = "",
    event_code: str = "",
) -> list[dict[str, Any]]:
    """Lấy danh sách tất cả các email template trong hệ thống."""
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version

    with engine.connect() as conn:
        stmt = (
            select(
                t.c.ID,
                t.c.CODE,
                t.c.NAME,
                t.c.DESCRIPTION,
                t.c.MENU_CODE,
                t.c.EVENT_CODE,
                t.c.CURRENT_ACTIVE_VERSION_ID,
                t.c.IS_ACTIVE,
                t.c.UPDATED_BY,
                t.c.UPDATED_AT,
                v.c.VERSION_NO.label("ACTIVE_VERSION_NO"),
                v.c.STATUS.label("ACTIVE_STATUS"),
            )
            .outerjoin(v, t.c.CURRENT_ACTIVE_VERSION_ID == v.c.ID)
            .order_by(t.c.UPDATED_AT.desc())
        )

        if search:
            kw = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                (func.lower(t.c.NAME).like(kw))
                | (func.lower(t.c.CODE).like(kw))
                | (func.lower(t.c.DESCRIPTION).like(kw))
            )

        if event_code:
            stmt = stmt.where(t.c.EVENT_CODE == event_code)

        rows = conn.execute(stmt).fetchall()

        # Đếm tổng số version của mỗi template
        v_count_stmt = select(v.c.TEMPLATE_ID, func.count(v.c.ID).label("cnt")).group_by(v.c.TEMPLATE_ID)
        counts = {r.TEMPLATE_ID: r.cnt for r in conn.execute(v_count_stmt)}

    result = []
    for r in rows:
        event = get_event_definition(r.EVENT_CODE)
        result.append(
            {
                "id": r.ID,
                "code": r.CODE,
                "name": r.NAME,
                "description": r.DESCRIPTION,
                "menu_code": r.MENU_CODE,
                "event_code": r.EVENT_CODE,
                "event_label": event.label if event else r.EVENT_CODE,
                "current_active_version_id": r.CURRENT_ACTIVE_VERSION_ID,
                "active_version_no": r.ACTIVE_VERSION_NO,
                "active_status": r.ACTIVE_STATUS or "NO_ACTIVE",
                "is_active": r.IS_ACTIVE,
                "versions_count": counts.get(r.ID, 0),
                "updated_by": r.UPDATED_BY,
                "updated_at": _format_dt(r.UPDATED_AT),
            }
        )
    return result


def _get_mail_template_detail(
    ctx: Ctx,
    template_id: int,
    version_id: int | None = None,
) -> dict[str, Any]:
    """Lấy chi tiết một template bao gồm danh sách version và dữ liệu của version đang chọn."""
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version

    with engine.connect() as conn:
        t_row = conn.execute(select(t).where(t.c.ID == template_id)).fetchone()
        if not t_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}.")

        # Danh sách tất cả version
        v_rows = conn.execute(
            select(
                v.c.ID,
                v.c.VERSION_NO,
                v.c.STATUS,
                v.c.CREATED_BY,
                v.c.CREATED_AT,
                v.c.ACTIVATED_BY,
                v.c.ACTIVATED_AT,
                v.c.ARCHIVED_AT,
            )
            .where(v.c.TEMPLATE_ID == template_id)
            .order_by(v.c.VERSION_NO.desc())
        ).fetchall()

        # Chọn version để hiển thị
        target_v_id = version_id
        if not target_v_id:
            # Ưu tiên active version, nếu không có lấy version mới nhất
            target_v_id = t_row.CURRENT_ACTIVE_VERSION_ID
            if not target_v_id and v_rows:
                target_v_id = v_rows[0].ID

        cur_v_row = None
        if target_v_id:
            cur_v_row = conn.execute(select(v).where(v.c.ID == target_v_id)).fetchone()

    event = get_event_definition(t_row.EVENT_CODE)

    versions_summary = []
    for vr in v_rows:
        versions_summary.append(
            {
                "id": vr.ID,
                "version_no": vr.VERSION_NO,
                "status": vr.STATUS,
                "created_by": vr.CREATED_BY,
                "created_at": _format_dt(vr.CREATED_AT),
                "activated_by": vr.ACTIVATED_BY,
                "activated_at": _format_dt(vr.ACTIVATED_AT),
                "is_current_active": (vr.ID == t_row.CURRENT_ACTIVE_VERSION_ID),
            }
        )

    current_version_dict = None
    if cur_v_row:
        design = cur_v_row.DESIGN_JSON
        if isinstance(design, str):
            try:
                design = json.loads(design)
            except Exception:
                design = _make_default_design_for_event(t_row.EVENT_CODE)

        val_json = cur_v_row.VALIDATION_JSON
        if isinstance(val_json, str):
            try:
                val_json = json.loads(val_json)
            except Exception:
                val_json = []

        current_version_dict = {
            "id": cur_v_row.ID,
            "template_id": cur_v_row.TEMPLATE_ID,
            "version_no": cur_v_row.VERSION_NO,
            "status": cur_v_row.STATUS,
            "subject_template": cur_v_row.SUBJECT_TEMPLATE,
            "preheader_template": cur_v_row.PREHEADER_TEMPLATE or "",
            "design_json": design,
            "rendered_html": cur_v_row.RENDERED_HTML or "",
            "plain_text": cur_v_row.PLAIN_TEXT or "",
            "design_hash": cur_v_row.DESIGN_HASH,
            "validation_errors": val_json or [],
            "created_by": cur_v_row.CREATED_BY,
            "created_at": _format_dt(cur_v_row.CREATED_AT),
            "activated_by": cur_v_row.ACTIVATED_BY,
            "activated_at": _format_dt(cur_v_row.ACTIVATED_AT),
        }

    return {
        "template": {
            "id": t_row.ID,
            "code": t_row.CODE,
            "name": t_row.NAME,
            "description": t_row.DESCRIPTION or "",
            "menu_code": t_row.MENU_CODE,
            "event_code": t_row.EVENT_CODE,
            "event_label": event.label if event else t_row.EVENT_CODE,
            "current_active_version_id": t_row.CURRENT_ACTIVE_VERSION_ID,
            "is_active": t_row.IS_ACTIVE,
            "updated_by": t_row.UPDATED_BY,
            "updated_at": _format_dt(t_row.UPDATED_AT),
        },
        "versions": versions_summary,
        "current_version": current_version_dict,
        "event_meta": {
            "code": event.code if event else t_row.EVENT_CODE,
            "label": event.label if event else t_row.EVENT_CODE,
            "description": event.description if event else "",
            "variables": [
                {
                    "key": var.key,
                    "label": var.label,
                    "data_type": var.data_type,
                    "category": var.category,
                    "description": var.description,
                }
                for var in (event.variables if event else [])
            ],
            "scenarios": list(event.scenarios.keys()) if event else ["success"],
        },
    }


@service
@requires_menu("mail_template_studio")
def get_mail_template_detail(
    ctx: Ctx,
    template_id: int,
    version_id: int | None = None,
) -> dict[str, Any]:
    """Lấy chi tiết một template bao gồm danh sách version và dữ liệu của version đang chọn."""
    return _get_mail_template_detail(ctx, template_id, version_id)


@service
@requires_menu("mail_template_studio")
def create_mail_template(
    ctx: Ctx,
    code: str,
    name: str,
    event_code: str,
    description: str = "",
    menu_code: str | None = None,
) -> dict[str, Any]:
    """Tạo mới một template và khởi tạo phiên bản v1 (DRAFT)."""
    c = (code or "").strip().upper()
    if not c or not re.match(r"^[A-Z0-9_]{3,64}$", c):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Mã template phải từ 3 đến 64 ký tự chữ hoa, chữ số hoặc gạch dưới (vd: TMPL_DAILY_ALERT).",
        )

    n = (name or "").strip()
    if not n:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tên mẫu email không được để trống.")

    event = get_event_definition(event_code)
    if not event:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Mã sự kiện '{event_code}' không tồn tại trong hệ thống.")

    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version
    now = _now()

    with engine.begin() as conn:
        # Kiểm tra trùng mã CODE
        dup = conn.execute(select(t.c.ID).where(t.c.CODE == c)).scalar_one_or_none()
        if dup:
            raise ServiceError(ErrorCode.TEMPLATE_CODE_EXISTS, f"Mã template '{c}' đã tồn tại trong hệ thống.")

        # Tạo template master
        target_menu = menu_code.strip() if menu_code and menu_code.strip() else event.menu_code
        res = conn.execute(
            t.insert().values(
                CODE=c,
                NAME=n,
                DESCRIPTION=description.strip() or None,
                MENU_CODE=target_menu,
                EVENT_CODE=event_code,
                CURRENT_ACTIVE_VERSION_ID=None,
                IS_ACTIVE="Y",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        template_id = res.lastrowid
        if not template_id:
            template_id = conn.execute(select(t.c.ID).where(t.c.CODE == c)).scalar_one()

        # Tạo default design ban đầu
        default_design = _make_default_design_for_event(event_code)
        subject = f"[ReconHub] {event.label}"
        sample_ctx = get_sample_payload(event_code, "success")
        rendered_html = render_html_email(default_design, sample_ctx)
        plain_text = render_plain_text(default_design, sample_ctx)
        d_hash = compute_design_hash(default_design)

        v_res = conn.execute(
            v.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                EVENT_SCHEMA_VERSION=1,
                SUBJECT_TEMPLATE=subject,
                PREHEADER_TEMPLATE="",
                DESIGN_JSON=json.dumps(default_design, ensure_ascii=False),
                RENDERED_HTML=rendered_html,
                PLAIN_TEXT=plain_text,
                DESIGN_HASH=d_hash,
                RENDERER_VERSION=RENDERER_VERSION,
                VALIDATION_JSON="[]",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        version_id = v_res.lastrowid
        if not version_id:
            version_id = conn.execute(
                select(v.c.ID).where(v.c.TEMPLATE_ID == template_id, v.c.VERSION_NO == 1)
            ).scalar_one()

        write_audit_log(
            conn=conn,
            entity="RECON_MAIL_TEMPLATE",
            entity_id=c,
            action="CREATE_MAIL_TEMPLATE",
            actor=ctx.username,
            new_data={"template_id": template_id, "name": n, "event_code": event_code},
        )

    return _get_mail_template_detail(ctx, template_id, version_id)


@service
@requires_menu("mail_template_studio")
def save_draft_version(
    ctx: Ctx,
    template_id: int,
    version_id: int | None,
    subject: str,
    preheader: str,
    design_json: dict[str, Any],
    page_code: str | None = None,
) -> dict[str, Any]:
    """Lưu bản nháp thiết kế.

    Nếu version đang chọn là ACTIVE: tự động nhân bản thành DRAFT v(N+1).
    Nếu version đang chọn là DRAFT: ghi đè cập nhật trực tiếp.
    Cập nhật page_code và event_code tương ứng nếu được truyền vào.
    """
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version
    now = _now()

    subj = (subject or "").strip()
    pre = (preheader or "").strip()

    with engine.begin() as conn:
        t_row = conn.execute(select(t).where(t.c.ID == template_id)).fetchone()
        if not t_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}.")

        event_code = t_row.EVENT_CODE
        menu_code = page_code or t_row.MENU_CODE

        # Tự động ánh xạ event_code khi chọn page tương ứng
        if page_code:
            if page_code == "user" and event_code in ("GENERAL_EXPORT", "common"):
                event_code = "USER_CREATED"
            elif page_code == "template" and event_code in ("GENERAL_EXPORT", "common"):
                event_code = "TEMPLATE_LIST_EXPORT"

            conn.execute(
                update(t)
                .where(t.c.ID == template_id)
                .values(MENU_CODE=page_code, EVENT_CODE=event_code, UPDATED_BY=ctx.username, UPDATED_AT=now)
            )

        # Chạy validation
        val_errors = validate_design(design_json, event_code, subject=subj, name=t_row.NAME, menu_code=menu_code)
        val_json = json.dumps(val_errors, ensure_ascii=False)

        sample_ctx = get_sample_payload(event_code, "success")
        rendered_html = render_html_email(design_json, sample_ctx, preheader=pre)
        plain_text = render_plain_text(design_json, sample_ctx)
        d_hash = compute_design_hash(design_json)

        # Lấy thông tin version mục tiêu nếu có
        target_v = None
        if version_id:
            target_v = conn.execute(select(v).where(v.c.ID == version_id, v.c.TEMPLATE_ID == template_id)).fetchone()

        # Nếu target_v là DRAFT: update trực tiếp
        if target_v and target_v.STATUS == "DRAFT":
            conn.execute(
                update(v)
                .where(v.c.ID == version_id)
                .values(
                    SUBJECT_TEMPLATE=subj,
                    PREHEADER_TEMPLATE=pre or None,
                    DESIGN_JSON=json.dumps(design_json, ensure_ascii=False),
                    RENDERED_HTML=rendered_html,
                    PLAIN_TEXT=plain_text,
                    DESIGN_HASH=d_hash,
                    RENDERER_VERSION=RENDERER_VERSION,
                    VALIDATION_JSON=val_json,
                )
            )
            saved_version_id = version_id
            action_name = "SAVE_MAIL_TEMPLATE_DRAFT"
        else:
            # Ngược lại: target_v là ACTIVE/ARCHIVED hoặc chưa có -> Tạo DRAFT v(max + 1)
            max_v = conn.execute(
                select(func.coalesce(func.max(v.c.VERSION_NO), 0)).where(v.c.TEMPLATE_ID == template_id)
            ).scalar_one()
            new_v_no = int(max_v) + 1

            ins_res = conn.execute(
                v.insert().values(
                    TEMPLATE_ID=template_id,
                    VERSION_NO=new_v_no,
                    STATUS="DRAFT",
                    EVENT_SCHEMA_VERSION=1,
                    SUBJECT_TEMPLATE=subj,
                    PREHEADER_TEMPLATE=pre or None,
                    DESIGN_JSON=json.dumps(design_json, ensure_ascii=False),
                    RENDERED_HTML=rendered_html,
                    PLAIN_TEXT=plain_text,
                    DESIGN_HASH=d_hash,
                    RENDERER_VERSION=RENDERER_VERSION,
                    VALIDATION_JSON=val_json,
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                )
            )
            saved_version_id = ins_res.lastrowid
            if not saved_version_id:
                saved_version_id = conn.execute(
                    select(v.c.ID).where(v.c.TEMPLATE_ID == template_id, v.c.VERSION_NO == new_v_no)
                ).scalar_one()
            action_name = "CLONE_MAIL_TEMPLATE_VERSION"

        # Cập nhật thời gian sửa đổi trên master template
        conn.execute(update(t).where(t.c.ID == template_id).values(UPDATED_BY=ctx.username, UPDATED_AT=now))

        write_audit_log(
            conn=conn,
            entity="RECON_MAIL_TEMPLATE",
            entity_id=t_row.CODE,
            action=action_name,
            actor=ctx.username,
            new_data={
                "template_id": template_id,
                "version_id": saved_version_id,
                "validation_errors_count": len(val_errors),
            },
        )

    return _get_mail_template_detail(ctx, template_id, saved_version_id)


@service
@requires_menu("mail_template_studio")
def activate_version(
    ctx: Ctx,
    template_id: int,
    version_id: int,
) -> dict[str, Any]:
    """Kích hoạt một phiên bản làm ACTIVE trong 1 Transaction SQLAlchemy duy nhất.

    - Kiểm tra validation: chỉ cho phép kích hoạt khi không có lỗi.
    - Chuyển version ACTIVE hiện tại sang ARCHIVED.
    - Đặt version này thành ACTIVE.
    - Cập nhật CURRENT_ACTIVE_VERSION_ID trên template master.
    - Ghi audit log.
    """
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version
    now = _now()

    with engine.begin() as conn:
        t_row = conn.execute(select(t).where(t.c.ID == template_id)).fetchone()
        if not t_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}.")

        v_row = conn.execute(select(v).where(v.c.ID == version_id, v.c.TEMPLATE_ID == template_id)).fetchone()
        if not v_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiên bản có ID {version_id}.")

        design = v_row.DESIGN_JSON
        if isinstance(design, str):
            design = json.loads(design)

        # Kiểm tra validation toàn diện
        errors = validate_design(
            design,
            t_row.EVENT_CODE,
            subject=v_row.SUBJECT_TEMPLATE,
            name=t_row.NAME,
            menu_code=t_row.MENU_CODE,
        )
        if errors:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Chưa thể kích hoạt mẫu do còn {len(errors)} lỗi: " + "; ".join(errors),
            )

        # 1. Archive version ACTIVE hiện tại của template (nếu có)
        conn.execute(
            update(v)
            .where(
                v.c.TEMPLATE_ID == template_id,
                v.c.STATUS == "ACTIVE",
                v.c.ID != version_id,
            )
            .values(STATUS="ARCHIVED", ARCHIVED_AT=now)
        )

        # 2. Đặt version mục tiêu thành ACTIVE
        conn.execute(
            update(v)
            .where(v.c.ID == version_id)
            .values(
                STATUS="ACTIVE",
                ACTIVATED_BY=ctx.username,
                ACTIVATED_AT=now,
                VALIDATION_JSON="[]",
            )
        )

        # 3. Cập nhật master template trỏ tới version mới
        conn.execute(
            update(t)
            .where(t.c.ID == template_id)
            .values(
                CURRENT_ACTIVE_VERSION_ID=version_id,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
            )
        )

        write_audit_log(
            conn=conn,
            entity="RECON_MAIL_TEMPLATE",
            entity_id=t_row.CODE,
            action="ACTIVATE_MAIL_TEMPLATE_VERSION",
            actor=ctx.username,
            new_data={
                "template_id": template_id,
                "version_id": version_id,
                "version_no": v_row.VERSION_NO,
            },
        )

    return _get_mail_template_detail(ctx, template_id, version_id)


@service
@requires_menu("mail_template_studio")
def clone_version(
    ctx: Ctx,
    template_id: int,
    source_version_id: int,
) -> dict[str, Any]:
    """Nhân bản một version sẵn có thành version DRAFT mới."""
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version
    now = _now()

    with engine.begin() as conn:
        t_row = conn.execute(select(t).where(t.c.ID == template_id)).fetchone()
        if not t_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}.")

        src = conn.execute(select(v).where(v.c.ID == source_version_id, v.c.TEMPLATE_ID == template_id)).fetchone()
        if not src:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy version nguồn có ID {source_version_id}.")

        max_v = conn.execute(
            select(func.coalesce(func.max(v.c.VERSION_NO), 0)).where(v.c.TEMPLATE_ID == template_id)
        ).scalar_one()
        new_v_no = int(max_v) + 1

        ins_res = conn.execute(
            v.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=new_v_no,
                STATUS="DRAFT",
                EVENT_SCHEMA_VERSION=src.EVENT_SCHEMA_VERSION,
                SUBJECT_TEMPLATE=src.SUBJECT_TEMPLATE,
                PREHEADER_TEMPLATE=src.PREHEADER_TEMPLATE,
                DESIGN_JSON=src.DESIGN_JSON,
                RENDERED_HTML=src.RENDERED_HTML,
                PLAIN_TEXT=src.PLAIN_TEXT,
                DESIGN_HASH=src.DESIGN_HASH,
                RENDERER_VERSION=src.RENDERER_VERSION,
                VALIDATION_JSON=src.VALIDATION_JSON,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        new_id = ins_res.lastrowid
        if not new_id:
            new_id = conn.execute(
                select(v.c.ID).where(v.c.TEMPLATE_ID == template_id, v.c.VERSION_NO == new_v_no)
            ).scalar_one()

        write_audit_log(
            conn=conn,
            entity="RECON_MAIL_TEMPLATE",
            entity_id=t_row.CODE,
            action="CLONE_MAIL_TEMPLATE_VERSION",
            actor=ctx.username,
            new_data={
                "template_id": template_id,
                "source_version_id": source_version_id,
                "new_version_id": new_id,
                "new_version_no": new_v_no,
            },
        )

    return _get_mail_template_detail(ctx, template_id, new_id)


@service
@requires_menu("mail_template_studio")
def test_send_template(
    ctx: Ctx,
    template_id: int,
    version_id: int,
    recipient_email: str | None = None,
    scenario: str = "success",
) -> dict[str, Any]:
    """Gửi email thử nghiệm sử dụng dữ liệu mẫu (mock scenario payload).

    - Địa chỉ nhận: Người thiết kế hoặc người nhận do Admin chỉ định.
    - Tiêu đề gắn tiền tố: [TEST]
    - Cấm sử dụng dữ liệu sản xuất thật.
    """
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version

    with engine.connect() as conn:
        t_row = conn.execute(select(t).where(t.c.ID == template_id)).fetchone()
        if not t_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}.")

        v_row = conn.execute(select(v).where(v.c.ID == version_id, v.c.TEMPLATE_ID == template_id)).fetchone()
        if not v_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiên bản có ID {version_id}.")

        # Tìm email của người dùng hiện tại nếu chưa chỉ định recipient
        user_email = None
        u_row = conn.execute(select(recon_user.c.EMAIL).where(recon_user.c.USERNAME == ctx.username)).fetchone()
        if u_row and u_row.EMAIL:
            user_email = u_row.EMAIL

    # Xác định người nhận an toàn
    target_email = (recipient_email or "").strip()
    if not target_email or not is_admin(ctx, engine):
        target_email = user_email or "designer@reconhub.local"

    if "@" not in target_email or "." not in target_email:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Địa chỉ email nhận thử nghiệm '{target_email}' không hợp lệ.",
        )

    design = v_row.DESIGN_JSON
    if isinstance(design, str):
        design = json.loads(design)

    # Kiểm tra validation trước khi gửi
    errors = validate_design(design, t_row.EVENT_CODE, subject=v_row.SUBJECT_TEMPLATE, name=t_row.NAME)
    if errors:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Cần khắc phục các lỗi sau trước khi gửi thử: " + "; ".join(errors),
        )

    # Chuẩn bị payload và render
    mock_payload = get_sample_payload(t_row.EVENT_CODE, scenario)
    page_mock = get_mock_payload_for_page(t_row.MENU_CODE or "user", scenario)
    merged_payload = {**mock_payload, **page_mock}

    # Đảm bảo các links an toàn có host tuyệt đối
    from app.services.smtp_settings import build_app_url

    for l_key in list(merged_payload.keys()):
        if l_key.startswith("links.") and isinstance(merged_payload[l_key], str) and merged_payload[l_key].startswith("/"):
            merged_payload[l_key] = build_app_url(merged_payload[l_key])

    resolved_subject = resolve_tokens(v_row.SUBJECT_TEMPLATE, merged_payload, escape_html=False)
    test_subject = f"[TEST] {resolved_subject}"

    body_html = render_html_email(design, merged_payload, preheader=v_row.PREHEADER_TEMPLATE or "")

    # Đọc cấu hình máy chủ SMTP
    smtp_cfg = get_smtp_config_internal()
    if not smtp_cfg.get("host"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chưa cấu hình máy chủ SMTP trong hệ thống. Vui lòng vào Cài đặt hệ thống > Máy chủ Email (SMTP) để cấu hình.",
        )

    sender_name = smtp_cfg.get("from_name") or "ReconHub Studio"
    sender_email = smtp_cfg.get("from_email") or smtp_cfg.get("username") or "no-reply@reconhub.local"
    from_full = f"{sender_name} <{sender_email}>"

    # Gửi qua SMTP Mailer
    res = send_smtp_email(
        host=smtp_cfg["host"],
        port=smtp_cfg["port"],
        security=smtp_cfg["security"],
        username=smtp_cfg["username"],
        password=smtp_cfg["password"],
        from_addr=from_full,
        to_addrs=[target_email],
        subject=test_subject,
        body_html=body_html,
        timeout=10,
    )

    if not res.get("ok"):
        raise ServiceError(
            ErrorCode.INTERNAL_ERROR,
            f"Không thể gửi email thử nghiệm: {res.get('error', 'Lỗi kết nối SMTP')}",
        )

    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="RECON_MAIL_TEMPLATE",
            entity_id=t_row.CODE,
            action="TEST_SEND_MAIL_TEMPLATE",
            actor=ctx.username,
            new_data={
                "template_id": template_id,
                "version_id": version_id,
                "recipient": target_email,
                "scenario": scenario,
            },
        )

    return {
        "ok": True,
        "recipient": target_email,
        "subject": test_subject,
        "message": f"Đã gửi email thử nghiệm thành công tới {target_email}.",
    }


def get_active_template_for_event(event_code: str) -> dict[str, Any] | None:
    """Hàm nội bộ đọc template ACTIVE cho các phân hệ nghiệp vụ (/templates, batch_run, report...).

    Không kiểm tra quyền, tự động fallback nếu không tìm thấy bản Active trong DB.
    """
    engine = get_recon_engine()
    t = recon_mail_template
    v = recon_mail_tpl_version

    try:
        with engine.connect() as conn:
            stmt = (
                select(
                    t.c.ID.label("TEMPLATE_ID"),
                    t.c.CODE,
                    t.c.NAME,
                    t.c.EVENT_CODE,
                    v.c.ID.label("VERSION_ID"),
                    v.c.VERSION_NO,
                    v.c.SUBJECT_TEMPLATE,
                    v.c.PREHEADER_TEMPLATE,
                    v.c.DESIGN_JSON,
                    v.c.RENDERED_HTML,
                )
                .join(v, t.c.CURRENT_ACTIVE_VERSION_ID == v.c.ID)
                .where(t.c.EVENT_CODE == event_code, t.c.IS_ACTIVE == "Y", v.c.STATUS == "ACTIVE")
                .limit(1)
            )
            row = conn.execute(stmt).fetchone()
            if row:
                design = row.DESIGN_JSON
                if isinstance(design, str):
                    design = json.loads(design)
                return {
                    "template_id": row.TEMPLATE_ID,
                    "code": row.CODE,
                    "name": row.NAME,
                    "event_code": row.EVENT_CODE,
                    "version_id": row.VERSION_ID,
                    "version_no": row.VERSION_NO,
                    "subject_template": row.SUBJECT_TEMPLATE,
                    "preheader_template": row.PREHEADER_TEMPLATE or "",
                    "design_json": design,
                    "rendered_html": row.RENDERED_HTML or "",
                }
    except Exception:
        pass

    # Fallback to default
    default_design = _make_default_design_for_event(event_code)
    event = get_event_definition(event_code)
    label = event.label if event else event_code
    return {
        "template_id": None,
        "code": f"TMPL_{event_code}_FALLBACK",
        "name": f"Mẫu dự phòng {label}",
        "event_code": event_code,
        "version_id": None,
        "version_no": 1,
        "subject_template": (
            "[ReconHub] Danh sách Template đối soát [{{items_count}} template] — {{created_at}}"
            if event_code == "TEMPLATE_LIST_EXPORT"
            else f"[ReconHub] {label}"
        ),
        "preheader_template": "",
        "design_json": default_design,
        "rendered_html": "",
    }
