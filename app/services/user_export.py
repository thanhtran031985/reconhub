"""User Export Service — Dịch vụ xuất file và gửi email danh sách Người dùng.

Bao bọc các hàm engine thuần trong Transaction và Context chuẩn ReconHub.
Ghi nhận đầy đủ Audit Log khi xuất hoặc gửi danh sách tài khoản.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.engine.mail_renderer import render_html_email, resolve_tokens
from app.engine.mailer import AttachmentSpec, send_smtp_email
from app.engine.user_export import (
    build_users_list_docx,
    build_users_list_excel,
    build_users_list_pdf,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.mail_template_studio import get_active_template_for_event
from app.services.perm import requires_menu
from app.services.smtp_settings import build_app_url, get_smtp_config_internal
from app.services.user import list_users


def _get_filtered_users_and_info(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Lấy danh sách người dùng đã lọc và chuỗi mô tả bộ lọc."""
    active_val: bool | None = None
    if status_filter == "ACTIVE":
        active_val = True
    elif status_filter == "DISABLED":
        active_val = False

    role_val = None if not role or role == "ALL" else role
    res = list_users(ctx, q=q if q else None, role=role_val, active=active_val)
    if not res.ok:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, f"Không tải được danh sách người dùng: {res.message}")

    user_list = res.data or []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if status_filter == "LOCKED":
        user_list = [u for u in user_list if u.locked_until and u.locked_until > now]

    # Convert UserResponse to dict
    items: list[dict[str, Any]] = [u.model_dump() for u in user_list]

    filter_parts: list[str] = []
    if q and q.strip():
        filter_parts.append(f"Tìm kiếm: '{q.strip()}'")
    if role and role != "ALL":
        filter_parts.append(f"Vai trò: {role}")
    if status_filter and status_filter != "ALL":
        filter_parts.append(f"Trạng thái: {status_filter}")

    filters_info = " | ".join(filter_parts)
    return items, filters_info


@service
@requires_menu("user")
def export_users_list_excel(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Kết xuất file Excel (.xlsx) danh sách người dùng."""
    items, filters_info = _get_filtered_users_and_info(ctx, q, role, status)
    content = build_users_list_excel(items, exported_by=ctx.username, filters_info=filters_info)

    # Ghi audit log
    engine = get_recon_engine()
    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=0,
            action="EXPORT_USERS_EXCEL",
            actor=ctx.username,
            new_data={"count": len(items), "filters": filters_info},
        )

    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_nguoi_dung_{now_tag}.xlsx",
        "content": content,
        "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "count": len(items),
    }


@service
@requires_menu("user")
def export_users_list_docx(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Kết xuất file Word (.docx) danh sách người dùng."""
    items, filters_info = _get_filtered_users_and_info(ctx, q, role, status)
    content = build_users_list_docx(items, exported_by=ctx.username, filters_info=filters_info)

    engine = get_recon_engine()
    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=0,
            action="EXPORT_USERS_DOCX",
            actor=ctx.username,
            new_data={"count": len(items), "filters": filters_info},
        )

    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_nguoi_dung_{now_tag}.docx",
        "content": content,
        "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "count": len(items),
    }


@service
@requires_menu("user")
def export_users_list_pdf(
    ctx: Ctx,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Kết xuất file PDF (.pdf) danh sách người dùng."""
    items, filters_info = _get_filtered_users_and_info(ctx, q, role, status)
    content = build_users_list_pdf(items, exported_by=ctx.username, filters_info=filters_info)

    engine = get_recon_engine()
    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=0,
            action="EXPORT_USERS_PDF",
            actor=ctx.username,
            new_data={"count": len(items), "filters": filters_info},
        )

    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_nguoi_dung_{now_tag}.pdf",
        "content": content,
        "mimetype": "application/pdf",
        "count": len(items),
    }


@service
@requires_menu("user")
def send_users_list_email(
    ctx: Ctx,
    to_emails: list[str],
    format_types: list[str],
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    custom_subject: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Gửi email đính kèm danh sách tài khoản người dùng theo các định dạng được chọn."""
    # 1. Validate người nhận
    clean_to_emails = [e.strip() for e in to_emails if e and e.strip() and "@" in e]
    if not clean_to_emails:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Danh sách người nhận không được để trống hoặc không hợp lệ.")

    # 2. Validate định dạng tệp đính kèm
    valid_formats = [f.upper() for f in format_types if f and f.upper() in ("XLSX", "DOCX", "PDF")]
    if not valid_formats:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Vui lòng chọn ít nhất một định dạng tệp đính kèm (XLSX, DOCX, PDF)."
        )

    # 3. Lấy cấu hình SMTP
    smtp_cfg = get_smtp_config_internal()
    if not smtp_cfg.get("host"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Hệ thống chưa được cấu hình máy chủ SMTP. Vui lòng liên hệ Quản trị viên để cấu hình trong trang Cài đặt.",
        )

    # 4. Lấy dữ liệu và tạo attachments
    items, filters_info = _get_filtered_users_and_info(ctx, q, role, status)
    now = datetime.now()
    now_tag = now.strftime("%Y%m%d_%H%M%S")
    now_str = now.strftime("%d/%m/%Y %H:%M")

    attachments: list[AttachmentSpec] = []
    if "XLSX" in valid_formats:
        xlsx_bytes = build_users_list_excel(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_nguoi_dung_{now_tag}.xlsx",
                content=xlsx_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )
    if "DOCX" in valid_formats:
        docx_bytes = build_users_list_docx(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_nguoi_dung_{now_tag}.docx",
                content=docx_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        )
    if "PDF" in valid_formats:
        pdf_bytes = build_users_list_pdf(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_nguoi_dung_{now_tag}.pdf",
                content=pdf_bytes,
                mimetype="application/pdf",
            )
        )

    # 5. Dựng email body và subject qua Mail Template Studio
    sender_name = ctx.full_name or ctx.username
    filenames = [att.filename for att in attachments]

    notes_text = notes.strip() if notes and notes.strip() else ""
    safe_notes_html = (
        f"""
    <div style="background-color: #f8f9fa; border-left: 4px solid #1971c2; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
        <strong style="font-size: 13px;">Lời nhắn từ người gửi:</strong>
        <p style="margin: 4px 0 0 0; color: #495057; font-size: 13px;">{notes_text.replace(chr(10), "<br>")}</p>
    </div>
    """
        if notes_text
        else ""
    )

    context = {
        "actor.name": sender_name,
        "actor.username": ctx.username,
        "module_name": "Danh sách người dùng",
        "created_at": now_str,
        "items_count": len(items),
        "notes": safe_notes_html,
        "files_list": filenames,
        "filters_info": filters_info or "Tất cả",
        "links.page": build_app_url("/users"),
        "links.login": build_app_url("/login"),
    }

    # Ưu tiên mẫu ACTIVE từ Mail Template Studio cho USER_LIST_EXPORT hoặc GENERAL_EXPORT
    studio_tpl = get_active_template_for_event("USER_LIST_EXPORT")
    if not studio_tpl:
        studio_tpl = get_active_template_for_event("GENERAL_EXPORT")

    if studio_tpl and studio_tpl.get("design_json"):
        if custom_subject and custom_subject.strip():
            subject = custom_subject.strip()
        else:
            subject = resolve_tokens(studio_tpl.get("subject_template", ""), context, escape_html=False)
            if not subject:
                subject = f"[ReconHub] Danh sách tài khoản người dùng — {now_str}"

        html_body = render_html_email(
            studio_tpl["design_json"],
            context,
            preheader=studio_tpl.get("preheader_template", ""),
        )
    else:
        # Fallback HTML cơ bản nếu chưa có template
        subject = custom_subject.strip() if custom_subject and custom_subject.strip() else f"[ReconHub] Danh sách tài khoản người dùng — {now_str}"
        files_html = "".join(f"<li>{html.escape(f)}</li>" for f in filenames)
        html_body = f"""
        <div style="font-family: Arial, sans-serif; color: #2D3748; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1A365D; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px;">ReconHub — Danh sách người dùng</h2>
            <p>Xin chào,</p>
            <p>Hệ thống gửi kèm danh sách gồm <strong>{len(items)}</strong> tài khoản người dùng theo yêu cầu của <strong>{html.escape(sender_name)}</strong>.</p>
            {safe_notes_html}
            <p><strong>Tệp đính kèm:</strong></p>
            <ul>{files_html}</ul>
            <p style="font-size: 12px; color: #718096; margin-top: 30px; border-top: 1px solid #E2E8F0; padding-top: 10px;">
                Email tự động từ hệ thống ReconHub. Vui lòng không trả lời thư này.
            </p>
        </div>
        """

    # 6. Gửi thư qua SMTP
    from_name = smtp_cfg.get("from_name", "").strip()
    from_email = smtp_cfg.get("from_email", "").strip() or "reconhub@noreply.com"
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    send_res = send_smtp_email(
        host=smtp_cfg["host"],
        port=smtp_cfg.get("port", 587),
        security=smtp_cfg.get("security", "STARTTLS"),
        username=smtp_cfg.get("username", ""),
        password=smtp_cfg.get("password", ""),
        from_addr=from_header,
        to_addrs=clean_to_emails,
        subject=subject,
        body_html=html_body,
        attachments=attachments,
    )
    if not send_res.get("ok"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Không thể gửi email: {send_res.get('message')}",
        )

    # Ghi audit log
    engine = get_recon_engine()
    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="USER",
            entity_id=0,
            action="SEND_USERS_LIST_EMAIL",
            actor=ctx.username,
            new_data={
                "recipients": clean_to_emails,
                "formats": valid_formats,
                "count": len(items),
                "subject": subject,
            },
        )

    return {
        "success": True,
        "recipients_count": len(clean_to_emails),
        "attachments_count": len(attachments),
    }
