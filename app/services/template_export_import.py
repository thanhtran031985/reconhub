from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_file, recon_template
from app.engine.mailer import AttachmentSpec, send_smtp_email
from app.engine.template_export import (
    build_templates_list_docx,
    build_templates_list_excel,
    build_templates_list_pdf,
)
from app.engine.template_sample import build_template_preview_excel
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services import service
from app.services.perm import requires_menu
from app.services.smtp_settings import get_smtp_config_internal
from app.services.template import get_template, list_templates, save_draft_template


@service
@requires_menu("template")
def export_template(
    ctx: Ctx,
    template_id: int,
    version: int | None = None,
) -> dict[str, Any]:
    """Xuất thông tin template và cấu hình CONFIG_JSON ra định dạng JSON."""

    tmpl_res = get_template(ctx, template_id=template_id, version=version)
    if not tmpl_res.ok or tmpl_res.data is None:
        raise ServiceError(tmpl_res.code or ErrorCode.NOT_FOUND, tmpl_res.message or "Không tìm thấy template")

    tmpl_data = dict(tmpl_res.data)
    return {
        "code": tmpl_data["code"],
        "name": tmpl_data["name"],
        "description": tmpl_data["description"],
        "version": tmpl_data["current_version"],
        "config": tmpl_data["config"],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": ctx.username,
    }


@service
@requires_menu("template")
def export_template_sample_excel(
    ctx: Ctx,
    template_id: int,
    version: int | None = None,
) -> dict[str, Any]:
    """Xuất file Excel mẫu của template từ đúng file mẫu đã tải lên.

    Nội dung là header và 5 dòng dữ liệu đầu tiên như bảng "Xem trước 5 dòng"
    ở trang sửa template, không tự sinh giá trị ví dụ. Template chưa có file
    mẫu hoặc file mẫu đã mất thì báo lỗi rõ, không trả file ví dụ thay thế.
    """

    tmpl_res = get_template(ctx, template_id=template_id, version=version)
    if not tmpl_res.ok or tmpl_res.data is None:
        raise ServiceError(tmpl_res.code or ErrorCode.NOT_FOUND, tmpl_res.message or "Không tìm thấy template")

    tmpl_data = dict(tmpl_res.data)
    try:
        config = TemplateConfig.model_validate(tmpl_data["config"])
    except Exception as exc:
        raise ServiceError(ErrorCode.TEMPLATE_INVALID, f"Cấu hình template không hợp lệ: {exc}") from exc

    sample_file_id = tmpl_data.get("sample_file_id")
    if not sample_file_id:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Template chưa có file mẫu tải lên. Hãy mở trang sửa template và tải file mẫu ở bước 1.",
        )

    engine = get_recon_engine()
    with engine.connect() as conn:
        file_row = conn.execute(select(recon_file).where(recon_file.c.ID == int(sample_file_id))).mappings().first()
    storage_path_str = str(file_row["STORAGE_PATH"]) if file_row else ""
    if (
        not file_row
        or file_row.get("PURGED_AT") is not None
        or not storage_path_str
        or not Path(storage_path_str).exists()
    ):
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Không tìm thấy file mẫu đã tải lên của template (file có thể đã bị xóa). "
            "Hãy tải lại file mẫu ở trang sửa template.",
        )

    try:
        content = build_template_preview_excel(Path(storage_path_str), config.file)
    except ValueError as exc:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, str(exc)) from exc

    code_val = str(tmpl_data["code"] or "template")
    return {
        "code": code_val,
        "filename": f"{code_val}_mau.xlsx",
        "content": content,
    }


@service
@requires_menu("template")
def import_template(
    ctx: Ctx,
    data: dict[str, Any],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Nhập template từ dictionary/file JSON và xác thực cấu hình chặt chẽ."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)

    code = str(data.get("code") or "").strip().upper()
    if not code:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Dữ liệu nhập thiếu 'code' template")

    name = str(data.get("name") or code).strip()
    description = data.get("description")

    raw_config = data.get("config")
    if not raw_config:
        # Trường hợp file JSON chỉ chứa trực tiếp TemplateConfig
        raw_config = data

    try:
        validated_config = TemplateConfig.model_validate(raw_config)
    except Exception as exc:
        raise ServiceError(ErrorCode.TEMPLATE_INVALID, f"Cấu hình template không hợp lệ: {exc}") from exc

    engine = get_recon_engine()
    with engine.connect() as conn:
        existing = conn.execute(select(recon_template).where(recon_template.c.CODE == code)).mappings().first()

    if existing is not None:
        if not overwrite:
            raise ServiceError(
                ErrorCode.TEMPLATE_CODE_EXISTS,
                f"Template với mã '{code}' đã tồn tại. Đặt overwrite=True để ghi đè.",
            )
        row_version = int(existing["ROW_VERSION"])
    else:
        row_version = None

    save_res = save_draft_template(
        ctx=ctx,
        code=code,
        name=name,
        config=validated_config,
        description=description,
        row_version=row_version,
    )
    if not save_res.ok or save_res.data is None:
        raise ServiceError(save_res.code or ErrorCode.VALIDATION_ERROR, save_res.message or "Lưu template thất bại")

    return dict(save_res.data)


def _get_filtered_templates(
    ctx: Ctx,
    search_term: str = "",
    status_filter: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Lấy và lọc danh sách template theo từ khóa và trạng thái."""
    res = list_templates(ctx)
    items: list[dict[str, Any]] = res.data or [] if res.ok else []

    if search_term:
        term = search_term.strip().lower()
        items = [
            it
            for it in items
            if term in str(it.get("code") or it.get("template_id", "")).lower()
            or term in str(it.get("name", "")).lower()
            or term in str(it.get("file_pattern", "")).lower()
            or term in str(it.get("sheet", "")).lower()
        ]

    if status_filter:
        items = [it for it in items if it.get("status") == status_filter]

    filters_parts: list[str] = []
    if status_filter:
        filters_parts.append(f"Trạng thái: {status_filter}")
    if search_term:
        filters_parts.append(f"Từ khóa: '{search_term}'")
    filters_info = "Bộ lọc: " + ", ".join(filters_parts) if filters_parts else ""

    return items, filters_info


@service
@requires_menu("template")
def export_templates_list_excel(
    ctx: Ctx,
    search_term: str = "",
    status_filter: str = "",
) -> dict[str, Any]:
    """Xuất danh sách template ra file Excel (.xlsx)."""
    items, filters_info = _get_filtered_templates(ctx, search_term, status_filter)
    content = build_templates_list_excel(items, exported_by=ctx.username, filters_info=filters_info)
    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_template_{now_tag}.xlsx",
        "content": content,
    }


@service
@requires_menu("template")
def export_templates_list_docx(
    ctx: Ctx,
    search_term: str = "",
    status_filter: str = "",
) -> dict[str, Any]:
    """Xuất danh sách template ra file Microsoft Word (.docx)."""
    items, filters_info = _get_filtered_templates(ctx, search_term, status_filter)
    content = build_templates_list_docx(items, exported_by=ctx.username, filters_info=filters_info)
    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_template_{now_tag}.docx",
        "content": content,
    }


@service
@requires_menu("template")
def export_templates_list_pdf(
    ctx: Ctx,
    search_term: str = "",
    status_filter: str = "",
) -> dict[str, Any]:
    """Xuất danh sách template ra file PDF (.pdf)."""
    items, filters_info = _get_filtered_templates(ctx, search_term, status_filter)
    content = build_templates_list_pdf(items, exported_by=ctx.username, filters_info=filters_info)
    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "filename": f"danh_sach_template_{now_tag}.pdf",
        "content": content,
    }


@service
@requires_menu("template")
def send_templates_list_email(
    ctx: Ctx,
    to_emails: list[str],
    format_types: list[str],
    search_term: str = "",
    status_filter: str = "",
    custom_subject: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Gửi email đính kèm danh sách template đối soát theo các định dạng được chọn."""
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
    items, filters_info = _get_filtered_templates(ctx, search_term, status_filter)
    now = datetime.now()
    now_tag = now.strftime("%Y%m%d_%H%M%S")
    now_str = now.strftime("%d/%m/%Y %H:%M")

    attachments: list[AttachmentSpec] = []
    if "XLSX" in valid_formats:
        xlsx_bytes = build_templates_list_excel(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_template_{now_tag}.xlsx",
                content=xlsx_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )
    if "DOCX" in valid_formats:
        docx_bytes = build_templates_list_docx(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_template_{now_tag}.docx",
                content=docx_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        )
    if "PDF" in valid_formats:
        pdf_bytes = build_templates_list_pdf(items, exported_by=ctx.username, filters_info=filters_info)
        attachments.append(
            AttachmentSpec(
                filename=f"danh_sach_template_{now_tag}.pdf",
                content=pdf_bytes,
                mimetype="application/pdf",
            )
        )

    # 5. Dựng email body và subject
    subject = (
        custom_subject.strip()
        if custom_subject and custom_subject.strip()
        else f"[ReconHub] Danh sách Template đối soát — {now_str}"
    )
    sender_name = ctx.full_name or ctx.username

    notes_html = ""
    if notes and notes.strip():
        safe_notes = notes.strip().replace("\n", "<br>")
        notes_html = f"""
        <div style="background-color: #f8f9fa; border-left: 4px solid #228be6; padding: 12px; margin: 16px 0; border-radius: 4px;">
            <strong>Lời nhắn từ người gửi:</strong><br>
            <p style="margin: 4px 0 0 0; color: #495057;">{safe_notes}</p>
        </div>
        """

    filter_html = f"<p style='margin: 4px 0; color: #666;'><strong>{filters_info}</strong></p>" if filters_info else ""
    files_list_html = "".join([f"<li><code>{att.filename}</code></li>" for att in attachments])

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #212529; max-width: 650px; line-height: 1.5;">
        <h2 style="color: #1971c2; margin-top: 0;">Danh sách Template đối soát ReconHub</h2>
        <p>Xin chào,</p>
        <p>Người dùng <strong>{sender_name}</strong> ({ctx.username}) đã gửi cho bạn danh sách Template đối soát từ hệ thống <strong>ReconHub</strong>.</p>
        {notes_html}
        <div style="margin: 16px 0; padding: 12px; border: 1px solid #e9ecef; border-radius: 6px; background-color: #ffffff;">
            <p style="margin: 4px 0;"><strong>Thời gian kết xuất:</strong> {now_str}</p>
            <p style="margin: 4px 0;"><strong>Số lượng template:</strong> {len(items)}</p>
            {filter_html}
            <p style="margin: 8px 0 4px 0;"><strong>Tệp đính kèm ({len(attachments)} tệp):</strong></p>
            <ul style="margin: 4px 0; padding-left: 20px;">
                {files_list_html}
            </ul>
        </div>
        <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
        <p style="font-size: 12px; color: #868e96; margin: 0;">
            Email này được gửi tự động từ hệ thống ReconHub. Vui lòng không trả lời trực tiếp email này.
        </p>
    </div>
    """

    # 6. Gửi mail
    from_name = smtp_cfg.get("from_name", "").strip()
    from_email = smtp_cfg.get("from_email", "").strip() or "reconhub@noreply.com"
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    send_smtp_email(
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

    # 7. Ghi audit log
    engine = get_recon_engine()
    with engine.begin() as conn:
        write_audit_log(
            conn=conn,
            entity="TEMPLATE_LIST",
            entity_id=0,
            action="SEND_TEMPLATE_EMAIL",
            actor=ctx.username,
            new_data={
                "to_emails": clean_to_emails,
                "formats": valid_formats,
                "count": len(items),
                "subject": subject,
            },
        )

    return {
        "to_emails": clean_to_emails,
        "attachments_count": len(attachments),
        "subject": subject,
    }
