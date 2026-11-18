"""Service for managing customizable email templates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_email_template
from app.engine.email_template import (
    SUPPORTED_EMAIL_FUNCTIONS,
    get_builtin_default_template,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_dict(row: Any) -> dict[str, Any]:
    tokens = row.AVAILABLE_TOKENS
    if isinstance(tokens, str):
        try:
            tokens = json.loads(tokens)
        except Exception:
            tokens = []
    return {
        "template_code": row.TEMPLATE_CODE,
        "name": row.NAME,
        "function_code": row.FUNCTION_CODE,
        "subject_pattern": row.SUBJECT_PATTERN,
        "body_html": row.BODY_HTML,
        "available_tokens": tokens or [],
        "is_default": row.IS_DEFAULT,
        "created_by": row.CREATED_BY,
        "created_at": row.CREATED_AT.isoformat() if row.CREATED_AT else None,
        "updated_by": row.UPDATED_BY,
        "updated_at": row.UPDATED_AT.isoformat() if row.UPDATED_AT else None,
    }


def get_email_template_internal(function_code: str) -> dict[str, Any]:
    """Hàm nội bộ đọc cấu hình template cho mailer hoặc preview, không kiểm tra quyền.

    Nếu DB chưa có mẫu riêng cho function_code này:
    1. Tự động kiểm tra xem DB đã cấu hình Mẫu mặc định dùng chung (GENERAL_EXPORT) chưa để làm fallback.
    2. Nếu DB cũng chưa có tùy biến GENERAL_EXPORT, dùng built-in default của chính function_code.
    """
    engine = get_recon_engine()
    builtin = get_builtin_default_template(function_code)
    try:
        with engine.connect() as conn:
            # 1. Tìm mẫu riêng của function_code
            stmt = (
                select(recon_email_template)
                .where(recon_email_template.c.FUNCTION_CODE == function_code)
                .order_by(recon_email_template.c.UPDATED_AT.desc().nullslast())
                .limit(1)
            )
            row = conn.execute(stmt).fetchone()
            if row:
                result = _row_to_dict(row)
                if not result.get("available_tokens"):
                    result["available_tokens"] = builtin.get("available_tokens", [])
                result["mock_context"] = builtin.get("mock_context", {})
                result["is_fallback"] = False
                return result

            # 2. Nếu không có mẫu riêng và function_code != "GENERAL_EXPORT" -> fallback sang mẫu GENERAL_EXPORT từ DB
            if function_code != "GENERAL_EXPORT":
                gen_stmt = (
                    select(recon_email_template)
                    .where(recon_email_template.c.FUNCTION_CODE == "GENERAL_EXPORT")
                    .order_by(recon_email_template.c.UPDATED_AT.desc().nullslast())
                    .limit(1)
                )
                gen_row = conn.execute(gen_stmt).fetchone()
                if gen_row:
                    result = _row_to_dict(gen_row)
                    result["is_fallback"] = True
                    result["available_tokens"] = builtin.get("available_tokens", [])
                    result["mock_context"] = builtin.get("mock_context", {})
                    return result
    except Exception:
        pass
    builtin["is_fallback"] = function_code != "GENERAL_EXPORT"
    return builtin


@service
def list_supported_functions(ctx: Ctx) -> list[dict[str, Any]]:
    """Trả về danh sách các chức năng hỗ trợ tùy biến template email."""
    return SUPPORTED_EMAIL_FUNCTIONS


@service
def get_email_template_for_function(ctx: Ctx, function_code: str) -> dict[str, Any]:
    """Lấy mẫu email cho chức năng chỉ định.

    Mọi người dùng đã đăng nhập đều có thể đọc để xem mẫu.
    """
    return get_email_template_internal(function_code)


@service
def save_email_template(ctx: Ctx, data: dict[str, Any]) -> dict[str, Any]:
    """Lưu tùy biến mẫu email cho chức năng. Yêu cầu quyền admin."""
    if not is_admin(ctx):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ Quản trị viên mới có quyền cấu hình mẫu email")

    function_code = (data.get("function_code") or "").strip()
    if not function_code:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Chức năng (function_code) không được để trống")

    subject_pattern = (data.get("subject_pattern") or "").strip()
    if not subject_pattern:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Tiêu đề mẫu email không được để trống")

    body_html = (data.get("body_html") or "").strip()
    if not body_html:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Nội dung mẫu email không được để trống")

    builtin = get_builtin_default_template(function_code)
    name = (data.get("name") or "").strip() or f"Mẫu email {function_code}"
    template_code = (data.get("template_code") or "").strip() or f"TMPL_{function_code}"
    tokens = builtin.get("available_tokens", [])

    now = _now()
    engine = get_recon_engine()

    with engine.begin() as conn:
        existing = conn.execute(
            select(recon_email_template.c.TEMPLATE_CODE).where(
                recon_email_template.c.FUNCTION_CODE == function_code
            )
        ).scalar_one_or_none()

        if existing is None:
            conn.execute(
                recon_email_template.insert().values(
                    TEMPLATE_CODE=template_code,
                    NAME=name,
                    FUNCTION_CODE=function_code,
                    SUBJECT_PATTERN=subject_pattern,
                    BODY_HTML=body_html,
                    AVAILABLE_TOKENS=tokens,
                    IS_DEFAULT="N",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                )
            )
        else:
            conn.execute(
                recon_email_template.update()
                .where(recon_email_template.c.FUNCTION_CODE == function_code)
                .values(
                    NAME=name,
                    SUBJECT_PATTERN=subject_pattern,
                    BODY_HTML=body_html,
                    AVAILABLE_TOKENS=tokens,
                    IS_DEFAULT="N",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                )
            )

        write_audit_log(
            conn,
            ctx.username,
            "UPDATE_EMAIL_TEMPLATE",
            "RECON_EMAIL_TEMPLATE",
            template_code,
            {"function_code": function_code, "subject_pattern": subject_pattern},
        )

    return get_email_template_internal(function_code)


@service
def reset_email_template_to_default(ctx: Ctx, function_code: str) -> dict[str, Any]:
    """Khôi phục mẫu email của chức năng về mặc định của hệ thống. Yêu cầu quyền admin."""
    if not is_admin(ctx):
        raise ServiceError(ErrorCode.FORBIDDEN, "Chỉ Quản trị viên mới có quyền cấu hình mẫu email")

    builtin = get_builtin_default_template(function_code)
    now = _now()
    engine = get_recon_engine()

    with engine.begin() as conn:
        existing = conn.execute(
            select(recon_email_template.c.TEMPLATE_CODE).where(
                recon_email_template.c.FUNCTION_CODE == function_code
            )
        ).scalar_one_or_none()

        if existing is not None:
            conn.execute(
                recon_email_template.update()
                .where(recon_email_template.c.FUNCTION_CODE == function_code)
                .values(
                    NAME=builtin["name"],
                    SUBJECT_PATTERN=builtin["subject_pattern"],
                    BODY_HTML=builtin["body_html"],
                    AVAILABLE_TOKENS=builtin.get("available_tokens", []),
                    IS_DEFAULT="Y",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                )
            )

        write_audit_log(
            conn,
            ctx.username,
            "RESET_EMAIL_TEMPLATE",
            "RECON_EMAIL_TEMPLATE",
            function_code,
            {"function_code": function_code},
        )

    return get_email_template_internal(function_code)
